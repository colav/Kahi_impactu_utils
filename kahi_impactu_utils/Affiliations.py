"""Author units (faculty, department) for a work, validated by year.

Shared by the works importers so every source applies the same rule: units
are attached only when the work itself carries the parent institution for
the author, and only those whose affiliation years cover the publication
year (or the previous one, to absorb publication lag).
"""
from datetime import datetime, timezone

from kahi_impactu_utils.Utils import normalize_publication_year

UNIT_TYPES = ("faculty", "department")
NON_INSTITUTION_TYPES = ("group", "department", "faculty")
YEAR_TOLERANCE = 1


def _date_year(value):
    """Return the UTC year for a stored affiliation timestamp."""
    if value in (None, "", -1):
        return None
    if isinstance(value, datetime):
        return value.year
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc).year
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def affiliation_covers_year(affiliation, year, current_year=None):
    """Use explicit covered years when present, otherwise a dated interval.

    An affiliation without years and without a start date never covers a year.
    """
    if year is None:
        return False
    if "years" in affiliation:
        return year in (affiliation.get("years") or [])
    start = _date_year(affiliation.get("start_date"))
    if start is None:
        return False
    end_value = affiliation.get("end_date")
    end = ((current_year or datetime.now(timezone.utc).year)
           if end_value in (None, "", -1) else _date_year(end_value))
    return end is not None and start <= year <= end


def affiliation_covers_publication(affiliation, publication_year,
                                   tolerance=YEAR_TOLERANCE, current_year=None):
    """True when the affiliation covers the publication year or up to
    ``tolerance`` years before it."""
    year = normalize_publication_year(publication_year, current_year=current_year)
    if year is None:
        return False
    return any(affiliation_covers_year(affiliation, candidate, current_year)
               for candidate in range(year - tolerance, year + 1))


def _resolve_affiliation(db, affiliation):
    """Find the affiliations document for a work affiliation by id or external id."""
    projection = {"_id": 1, "types": 1}
    affiliation_id = affiliation.get("id")
    if affiliation_id:
        aff_db = db["affiliations"].find_one({"_id": affiliation_id}, projection)
        if aff_db:
            return aff_db
    for external_id in affiliation.get("external_ids") or []:
        identifier = external_id.get("id") if isinstance(external_id, dict) else None
        if identifier in (None, ""):
            continue
        aff_db = db["affiliations"].find_one({"external_ids.id": identifier}, projection)
        if aff_db:
            return aff_db
    return None


def find_work_institution(db, author_db, affiliations):
    """Return the _id of the first parent institution the work lists for the
    author that also appears in the author's person affiliations, else None."""
    for affiliation in affiliations or []:
        aff_db = _resolve_affiliation(db, affiliation)
        if not aff_db:
            continue
        types = [item.get("type") for item in aff_db.get("types") or []]
        if any(unit_type in types for unit_type in NON_INSTITUTION_TYPES):
            continue
        if db["person"].count_documents({
                "_id": author_db["_id"],
                "affiliations.id": aff_db["_id"]}) > 0:
            return aff_db["_id"]
    return None


def get_units_affiliations(db, author_db, affiliations, publication_year=None,
                           tolerance=YEAR_TOLERANCE, current_year=None):
    """Return the author's faculty and department entries for the parent
    institution the work lists for that author.

    Parameters
    ----------
    db : pymongo.database.Database
        Kahi database (affiliations and person collections).
    author_db : dict
        The person document matched for the work author.
    affiliations : list
        Affiliations the work itself carries for the author (signature,
        group institution, repository institution). Without a parent
        institution here no unit is returned.
    publication_year : int or None
        Year of the work. Without it no unit is returned.
    tolerance : int
        Years before the publication year still accepted (publication lag).
    """
    units = []
    if not author_db or not affiliations:
        return units
    year = normalize_publication_year(publication_year, current_year=current_year)
    if year is None:
        return units
    institution_id = find_work_institution(db, author_db, affiliations)
    if institution_id is None:
        return units
    for affiliation in author_db.get("affiliations") or []:
        unit_id = affiliation.get("id")
        if not unit_id or unit_id == institution_id:
            continue
        types = [item.get("type") for item in affiliation.get("types") or []]
        if not any(unit_type in types for unit_type in UNIT_TYPES):
            continue
        if not affiliation_covers_publication(affiliation, year, tolerance, current_year):
            continue
        if db["affiliations"].count_documents({
                "_id": unit_id, "relations.id": institution_id}) == 0:
            continue
        units.append(affiliation)
    return units
