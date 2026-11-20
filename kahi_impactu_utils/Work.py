"""DOI identity using existing work fields and external coordination."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from functools import lru_cache, wraps
from html import unescape
import logging
import re
import time
from uuid import uuid4
from unicodedata import combining, normalize

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from langid.langid import LanguageIdentifier, model as _LANGID_MODEL
from rapidfuzz.fuzz import ratio
from unidecode import unidecode

from kahi_impactu_utils.Utils import doi_processor


DOI_COLLATION = {"locale": "en", "strength": 2}
COORDINATION_COLLECTION = "_kahi_work_identity"
# Works sharing a DOI are the same publication unless their titles show no
# resemblance at all: the title only guards against DOIs typed by hand on
# the wrong record. Scores: 100 exact, 95 one title contained in the other,
# 70-99 similar wording, 70 translation with compatible years.
# Non-DOI routes (ISBN, source ids, fingerprints, Elasticsearch) pass
# strict=True: similar wording only, no containment and no translation.
TITLE_THRESHOLD = 70
STRICT_THRESHOLD = 90
CONTAINMENT_SCORE = 95
TRANSLATION_SCORE = 70
CONTAINMENT_MIN_LENGTH = 25
LANGUAGE_MIN_LENGTH = 30
LANGUAGE_MIN_PROBABILITY = 0.95
TITLE_LANGUAGES = ("es", "en", "pt", "fr", "it", "de")
YEAR_TOLERANCE = 1
_TITLE_PUNCTUATION = re.compile(r"[\W_]+")
_TITLE_MARKUP = re.compile(r"</?[a-z][^>]*>", re.IGNORECASE)
_TITLE_SIGN = re.compile(r"(?<!\w)([-+])(?=\d)")
LOGGER = logging.getLogger(__name__)


class AmbiguousWorkDOI(ValueError):
    """Contradictory source identities; skip that record without stopping ETL."""


def skip_work_doi_conflicts(operation):
    @wraps(operation)
    def process(*args, **kwargs):
        try:
            return operation(*args, **kwargs)
        except AmbiguousWorkDOI as error:
            LOGGER.warning("DOI conflict; record skipped: %s", error)
            return None
    return process


def canonical_work_doi(value):
    if not isinstance(value, str) or not value.strip():
        return None
    doi = doi_processor(value)
    if isinstance(doi, str) and re.fullmatch(r"https://doi.org/10\.\d{4,9}/\S+", doi):
        return doi
    return None


def ensure_work_doi_indexes(collection):
    for name, specification in collection.index_information().items():
        if any(field == "_doi_key" for field, _ in specification.get("key", [])):
            collection.drop_index(name)
    collection.create_index("doi", name="work_doi_lookup", collation=DOI_COLLATION)
    collection.create_index("external_ids.id", name="work_doi_external_lookup",
                            collation=DOI_COLLATION)


def prepare_work_doi(entry, provenance):
    entry.pop("_doi_key", None)
    doi = canonical_work_doi(entry.get("doi"))
    if doi is None:
        return None
    entry["doi"] = doi
    identifiers = entry.setdefault("external_ids", [])
    if not any(ext.get("source") == "doi" and ext.get("id") == doi for ext in identifiers):
        identifiers.append({"provenance": provenance, "source": "doi", "id": doi})
    return doi


@lru_cache(maxsize=32768)
def normalize_work_title(value):
    """Bounded, process-local cache; no fields or HTTP requests are needed."""
    if not isinstance(value, str):
        return ""
    value = _TITLE_MARKUP.sub("", unescape(value))
    value = value.replace("−", "-").replace("+/-", "±")
    for symbol, text in (("<=", "less equal"), (">=", "greater equal"),
                         ("≤", "less equal"), ("≥", "greater equal"),
                         ("<", "less"), (">", "greater"), ("±", "plus minus")):
        value = value.replace(symbol, f" {text} ")
    value = "".join(char for char in normalize("NFKD", value.casefold()) if not combining(char))
    value = unidecode(value)  # dotless i, l with stroke, ligatures and other letters without decomposition
    value = _TITLE_SIGN.sub(lambda match: "minus " if match[1] == "-" else "plus ", value)
    return _TITLE_PUNCTUATION.sub(" ", value).strip()


@lru_cache(maxsize=1)
def _language_identifier():
    identifier = LanguageIdentifier.from_modelstring(_LANGID_MODEL, norm_probs=True)
    identifier.set_languages(TITLE_LANGUAGES)
    return identifier


@lru_cache(maxsize=4096)
def _detect_language(normalized_title):
    """Language of a title when langid is confident; None otherwise."""
    if len(normalized_title) < LANGUAGE_MIN_LENGTH:
        return None
    language, probability = _language_identifier().classify(normalized_title)
    return language if probability >= LANGUAGE_MIN_PROBABILITY else None


def _normalized_titles(titles):
    """Normalized title -> declared language (None when unknown)."""
    result = {}
    for item in titles or []:
        if not isinstance(item, dict) or not isinstance(item.get("title"), str):
            continue
        normalized = normalize_work_title(item["title"])
        if normalized and normalized not in result:
            lang = item.get("lang")
            result[normalized] = lang.lower() if isinstance(lang, str) and lang.strip() else None
    return result


def _title_language(normalized, declared):
    return declared or _detect_language(normalized)


def _years_compatible(left, right):
    """Both publication years known and within tolerance (translations need this)."""
    try:
        left, right = int(left or 0), int(right or 0)
    except (TypeError, ValueError):
        return False
    return bool(left and right) and abs(left - right) <= YEAR_TOLERANCE


def _near_title_score(left, right, left_lang=None, right_lang=None, years_compatible=False,
                      strict=False):
    if not left or not right:
        return 0
    if strict:
        return ratio(left, right, score_cutoff=STRICT_THRESHOLD)
    shorter, longer = sorted((left, right), key=len)
    if len(shorter) >= CONTAINMENT_MIN_LENGTH and shorter in longer:
        return CONTAINMENT_SCORE
    score = ratio(left, right, score_cutoff=TITLE_THRESHOLD)
    if score:
        return min(score, CONTAINMENT_SCORE - 1)
    if not years_compatible:
        return 0
    left_lang = _title_language(left, left_lang)
    right_lang = _title_language(right, right_lang)
    if left_lang and right_lang and left_lang != right_lang:
        return TRANSLATION_SCORE
    return 0


def _normalized_title_score(incoming, stored, years_compatible=False, strict=False):
    if set(incoming).intersection(stored):
        return 100
    return max((_near_title_score(a, b, incoming[a], stored[b], years_compatible, strict)
                for a in incoming for b in stored), default=0)


def _title_score(incoming, stored, incoming_year=None, stored_year=None, strict=False):
    return _normalized_title_score(_normalized_titles(incoming), _normalized_titles(stored),
                                   _years_compatible(incoming_year, stored_year), strict)


def work_titles_match(incoming, stored, incoming_year=None, stored_year=None, *, strict=False):
    """Same publication: equal, similar, nested or translated titles (years within tolerance).

    strict=True (non-DOI evidence) accepts equal or closely similar titles only.
    """
    threshold = STRICT_THRESHOLD if strict else TITLE_THRESHOLD
    return _title_score(incoming, stored, incoming_year, stored_year, strict) >= threshold


def _select_work(matches, titles, allow_distinct_titles, year=None):
    if not matches:
        return None
    normalized = _normalized_titles(titles)
    if not normalized:
        raise AmbiguousWorkDOI("A source title is required to choose an existing DOI work")
    # The retained compatibility argument must never bypass title validation.
    ranked = sorted(((_normalized_title_score(normalized, _normalized_titles(work.get("titles")),
                                              _years_compatible(year, work.get("year_published"))),
                      str(work["_id"]), work)
                     for work in matches), key=lambda item: (-item[0], item[1]))
    compatible = [item for item in ranked if item[0] >= TITLE_THRESHOLD]
    if not compatible:
        LOGGER.warning("DOI/title conflict for works %s; keeping a separate work",
                       [str(work["_id"]) for work in matches])
        return None
    if len(compatible) > 1:
        LOGGER.warning("Multiple compatible DOI works; selecting closest title: %s", compatible[0][1])
    return compatible[0][2]


def find_work_by_doi(collection, value, projection=None, *, titles=None, year=None,
                     allow_distinct_titles=True):
    doi = canonical_work_doi(value)
    if doi is None:
        return None
    bare = doi.removeprefix("https://doi.org/")
    aliases = list(dict.fromkeys([doi, value.strip(), bare, f"http://doi.org/{bare}",
                                  f"http://dx.doi.org/{bare}", f"https://dx.doi.org/{bare}",
                                  f"doi:{bare}", f"doi: {bare}"]))
    query = {"$or": [{"doi": {"$in": aliases}}, {"external_ids.id": {"$in": aliases}}]}
    selected_projection = projection
    if projection is not None and titles is not None:
        selected_projection = dict(projection)
        selected_projection["titles"] = 1
        selected_projection["year_published"] = 1
    matches = list(collection.find(query, projection=selected_projection, collation=DOI_COLLATION))
    return _select_work(matches, titles, allow_distinct_titles, year)


def claim_work_doi(collection, work, value):
    """Fill the existing DOI field with an atomic comparison, never a new key."""
    doi = canonical_work_doi(value)
    if doi is None:
        return work
    current = canonical_work_doi(work.get("doi"))
    if current is not None:
        if current != doi:
            raise AmbiguousWorkDOI(f"Work {work['_id']} has DOI {current}, conflicting with {doi}")
        return work
    previous = work.get("doi")
    response = collection.update_one({"_id": work["_id"], "doi": previous}, {"$set": {"doi": doi}})
    if response.matched_count == 0:
        stored = collection.find_one({"_id": work["_id"]}, {"doi": 1})
        if not stored or canonical_work_doi(stored.get("doi")) != doi:
            raise AmbiguousWorkDOI(f"Work {work['_id']} changed DOI concurrently")
    work["doi"] = doi
    return work


def merge_work_identifiers(collection, work, incoming):
    additions = {}
    for field in ("external_ids", "titles"):
        values = incoming.get(field) or []
        if values:
            additions[field] = {"$each": values}
            current = work.setdefault(field, [])
            for value in values:
                if value not in current:
                    current.append(value)
    if additions:
        collection.update_one({"_id": work["_id"]}, {"$addToSet": additions})


@contextmanager
def _coordinate_doi(collection, doi, timeout=150, lease_seconds=120):
    """Coordinate decisions outside works; reservations survive process failure."""
    control = collection.database[COORDINATION_COLLECTION]
    key = f"{collection.name}:{doi}"
    owner = uuid4().hex
    deadline = time.monotonic() + timeout
    while True:
        now = datetime.now(timezone.utc)
        try:
            state = control.find_one_and_update({
                "_id": key, "$or": [{"expires_at": {"$lte": now}}, {"owner": owner}],
            }, {"$set": {"owner": owner, "expires_at": now + timedelta(seconds=lease_seconds)},
                "$setOnInsert": {"reservations": []}}, upsert=True, return_document=ReturnDocument.AFTER)
            break
        except DuplicateKeyError as error:
            if (error.details or {}).get("keyPattern") not in (None, {"_id": 1}):
                raise
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Timed out coordinating DOI {doi}") from error
            time.sleep(0.02)
    try:
        yield control, key, owner, state
    finally:
        # Preserve reservations: the existing ObjectId arbitrates pending
        # inserts even after a process recovers another owner's expired lease.
        control.update_one({"_id": key, "owner": owner}, {
            "$set": {"expires_at": datetime.now(timezone.utc)}, "$unset": {"owner": ""}})


def insert_work_by_doi(collection, entry, *, allow_distinct_titles=True):
    doi = canonical_work_doi(entry.get("doi"))
    if not doi:
        raise ValueError("A valid DOI is required")
    entry.pop("_doi_key", None)
    while True:
        with _coordinate_doi(collection, doi) as (control, key, owner, state):
            existing = find_work_by_doi(collection, doi, titles=entry.get("titles"),
                                        year=entry.get("year_published"),
                                        allow_distinct_titles=allow_distinct_titles)
            if existing is not None:
                return None, claim_work_doi(collection, existing, doi)
            pending = [item for item in state.get("reservations", [])
                       if collection.find_one({"_id": item["_id"]}, {"_id": 1}) is None]
            reservation = _select_work(pending, entry.get("titles"), allow_distinct_titles,
                                       entry.get("year_published"))
            if reservation is None:
                reservation = {"_id": entry.get("_id") or ObjectId(), "titles": entry.get("titles") or [],
                               "year_published": entry.get("year_published")}
                response = control.update_one({"_id": key, "owner": owner,
                                               "expires_at": {"$gt": datetime.now(timezone.utc)}},
                                              {"$push": {"reservations": reservation}})
                if response.matched_count == 0:
                    continue
            document = {"_id": reservation["_id"], **{field: value for field, value in entry.items() if field != "_id"}}
            try:
                collection.insert_one(document)
                return reservation["_id"], None
            except DuplicateKeyError as error:
                if (error.details or {}).get("keyPattern") not in (None, {"_id": 1}):
                    raise
                winner = collection.find_one({"_id": reservation["_id"]})
                if winner is None:
                    raise
                if not work_titles_match(entry.get("titles"), winner.get("titles"),
                                         entry.get("year_published"), winner.get("year_published")):
                    raise AmbiguousWorkDOI(f"Reserved work {winner['_id']} has an incompatible title")
                return None, claim_work_doi(collection, winner, doi)
