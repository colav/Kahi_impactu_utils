from re import sub, split, UNICODE, search, match, findall
import unidecode
from datetime import datetime as dt

from langid import classify
import pycld2 as cld2
from fastspell import FastSpell
from urllib.parse import unquote

fast_spell = FastSpell("en", mode="cons")


def lang_poll(text, verbose=0):
    """
    function to detect the language of a given text, it uses several libraries to detect the language
    doing a poll to get the most voted language.

    Parameters:
    -----------
    text : str
        The text to detect the language from.
    verbose : int
        The level of verbosity of the function, the higher the number the more verbose the function will be.
    Returns:
    --------
    str
        The language detected.
    """
    text = text.lower()
    text = text.replace("\n", "")
    lang_list = []

    lang_list.append(classify(text)[0].lower())

    detected_language = None
    try:
        _, _, _, detected_language = cld2.detect(text, returnVectors=True)
    except Exception as e:
        if verbose > 4:
            print("Language detection error using cld2, trying without ascii")
            print(e)
        try:
            text = str(unidecode.unidecode(text).encode("ascii", "ignore"))
            _, _, _, detected_language = cld2.detect(text, returnVectors=True)
        except Exception as e:
            if verbose > 4:
                print("Language detection error using cld2")
                print(e)

    try:
        result = fast_spell.getlang(text)  # low_memory breaks the function
        lang_list.append(result.lower())
    except Exception as e:
        if verbose > 4:
            print("Language detection error using fastSpell")
            print(e)

    lang = None
    for prospect in set(lang_list):
        votes = lang_list.count(prospect)
        if votes > len(lang_list) / 2:
            lang = prospect
            break
    return lang


def split_names(s, connectors=['DE', 'DEL', 'LA', 'EL', 'JR', 'JR.'], sep=':', foreign=False):
    """
    Extract the parts of the full name `s` in the format ([] → optional):

    NAMES [SMALL_CONECTORS] FIRST_LAST_NAME [SMALL_CONECTORS] [SECOND_LAST_NAME]

    * If len(s) == 2 → Foreign name assumed with single last name on it
    * If len(s) == 3 → Colombian name assumed two last mames and one first name

    Add connectors, like 'DE', to `connectors` list if necessary

    Works with:
    ----
          'DANIEL ANDRES LA ROTTA FORERO',
          'MARIA DEL CONSUELO MONTES RAMIREZ',
          'RICARDO DE LA MERCED CALLEJAS POSADA',
          'MARIA DEL CARMEN DE LA CUESTA BENJUMEA',
          'CARLOS MARTI JARAMILLO OCAMPO NICOLAS',
          'DIEGO ALEJANDRO RESTREPO QUINTERO',
          'JAIRO HUMBERTO RESTREPO ZEA',
          'MARLEN JIMENEZ DEL RIO ',
          'SARA RESTREPO FERNÁNDEZ', # Colombian: NAME two LAST_NAMES
          'ENRICO NARDI', # Foreing
          'ANA ZEA',
          'SOL ANA DE ZEA GIL'
    Fails:
    ----
        s='RANGEL MARTINEZ VILLAL ANDRES MAURICIO' # more than 2 last names
        s='ROMANO ANTONIO ENEA' # Foreing → LAST_NAME NAMES

    Parameters:
    ----------
    s:str
        The full name to be processed.
    connectors:list
        A list of connectors between names which are assumed to be at least of length 2.
    sep:str
        The separator to be used to split the names.
    foreign:boolean
        True if only there are one last name in the name

    Returns:
    -------
    dict
        A dictionary with the extracted parts of the full name.
    """
    s = s.title()
    s = sub(r'\s\w\.*\s', ' ', s)  # Remove middle initials
    connectors = [e.title() for e in connectors]
    sl = sub('(\s\w{2,3})\s', fr'\1{sep}', s, UNICODE)  # noqa: W605
    sl = sub('(\s\w{2,3}%s\w{2,3})\s' % sep, fr'\1{sep}', sl, UNICODE)  # noqa: W605
    sl = sub('^(\w{2,3})\s', fr'\1{sep}', sl, UNICODE)  # noqa: W605
    # Clean connectors
    # Extract short names list
    lst = [s for s in split(
        '(\w{1,3})%s' % sep, sl) if len(s) >= 1 and len(s) <= 3]  # noqa: W605
    # intersection with connectors list
    exc = [value for value in lst if value not in connectors]
    if exc:
        for e in exc:
            sl = sl.replace('{}{}'.format(e, sep), '{} '.format(e))

    sll = sl.split()

    if len(sll) == 2:
        sll = [sl.split()[0]] + [''] + [sl.split()[1]]

    if len(sll) == 3:
        if not foreign:
            sll = [sl.split()[0]] + [''] + sl.split()[1:]
        else:
            sll = sl.split()[:2] + [sl.split()[2]] + ['']

    d = {'names': [x.replace(sep, ' ') for x in sll[:2] if x],
         'surenames': [x.replace(sep, ' ') for x in sll[2:] if x],
         }
    d['full_name'] = ' '.join(d['names'] + d['surenames'])
    d['initials'] = [x[0] + '.' for x in d['names']]

    return d


def doi_processor(doi):
    """
    Process a DOI (Digital Object Identifier) and return a cleaned version.
    Parameters:
    ----------
        doi:str
            The DOI to be processed.
    Returns:
    -------
        str or bool: If a valid DOI is found, return the cleaned DOI; otherwise, return False.
    """
    doi_regex = r"\b10\.\d{3,}/[^\s]+"
    match = search(doi_regex, doi)
    if match:
        return match.group().strip().strip('.').lower()
    doi_candidate = doi.replace(" ", "").strip().strip(
        '.').lower().replace("%2f", "/").replace("doi", "")
    match = search(doi_regex, doi_candidate)
    if match:
        return match.group().strip().strip('.').lower()
    if ('http' in doi_candidate or 'www' in doi_candidate or 'dx' in doi_candidate) and "10." in doi_candidate:
        doi_candidate = doi_candidate.split("/10")[-1].replace("%2f", "/")
        doi_candidate = "10" + doi_candidate
        match = search(doi_regex, doi_candidate)
        if match:
            return match.group().strip('.').lower()
    if doi_candidate.startswith("0."):
        doi_candidate = "1" + doi_candidate
    match = search(doi_regex, doi_candidate)
    if match:
        return match.group().strip().strip('.').lower()
    doi_candidate = doi.split("/")
    if doi_candidate[0].endswith('.'):
        doi_candidate[0] = doi_candidate[0].strip('.')
    if "." not in doi_candidate[0]:
        doi_candidate[0] = doi_candidate[0].replace("10", "10.")
    doi_candidate = '/'.join(doi_candidate)
    match = search(doi_regex, doi_candidate)
    if match:
        return match.group().strip().strip('.').lower()

    return False


def check_date_format(date_str):
    """
    Check the format of a date string and return its timestamp if valid.

    Parameters:
    ----------
        date_str:str
            A string representing a date.

    Returns:
    -------
        int or str: If the date string matches any of the supported formats,
            return its timestamp; otherwise, return an empty string.

    Supported date formats:
        - Weekday, Day Month Year Hour:Minute:Second Timezone (e.g., "Sun, 20 Nov 1994 12:45:30 UTC")
        - Year-Month-Day Hour:Minute:Second (e.g., "1994-11-20 12:45:30")
        - Day-Month-Year Hour:Minute:Second (e.g., "20-11-1994 12:45:30")
        - Year-Month-Day (e.g., "1994-11-20")
        - Day-Month-Year (e.g., "20-11-1994")
        - Year-Month (e.g., "1994-11")
        - Month-Year (e.g., "11-1994")
        - Year-Month-DayTHour:Minute:Second.Millisecond (e.g., "2011-02-01T00:00:00.000")
    """
    if date_str is None:
        return ""
    wdmyhmsz_format = r"^\w{3}, \d{2} \w{3} \d{4} \d{2}:\d{2}:\d{2} \w{3}$"
    ymdhmsf_format = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}"
    ymdhms_format = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"
    dmyhms_format = r"\d{2}-\d{2}-\d{4} \d{2}:\d{2}:\d{2}"
    ymd_format = r"\d{4}-\d{2}-\d{2}"
    dmy_format = r"\d{2}-\d{2}-\d{4}"
    ym_format = r"\d{4}-\d{2}"
    my_format = r"\d{2}-\d{4}"
    if match(wdmyhmsz_format, date_str):
        return int(dt.strptime(date_str, "%a, %d %b %Y %H:%M:%S %Z").timestamp())
    elif match(ymdhmsf_format, date_str):
        return int(dt.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%f").timestamp())
    elif match(ymdhms_format, date_str):
        return int(dt.strptime(date_str, "%Y-%m-%d %H:%M:%S").timestamp())
    elif match(dmyhms_format, date_str):
        return int(dt.strptime(date_str, "%d-%m-%Y %H:%M:%S").timestamp())
    elif match(ymd_format, date_str):
        return int(dt.strptime(date_str, "%Y-%m-%d").timestamp())
    elif match(dmy_format, date_str):
        return int(dt.strptime(date_str, "%d-%m-%Y").timestamp())
    elif match(ym_format, date_str):
        return int(dt.strptime(date_str, "%Y-%m").timestamp())
    elif match(my_format, date_str):
        return int(dt.strptime(date_str, "%m-%Y").timestamp())
    return ""


def get_id_type_from_url(url):
    """
    This function returns the type of the id based on the url

    Parameters:
    ----------
    url: str
        The url of the id
    Returns:
    --------
    str
        The type of the id
    """
    if "orcid" in url:
        return "orcid"
    if "researchgate" in url:
        return "researchgate"
    if "linkedin" in url:
        return "linkedin"
    if "scholar.google" in url:
        return "scholar"
    if "scopus" in url:
        return "scopus"
    if "publons" in url:
        return "wos"
    if "webofscience" in url:
        return "wos"
    if "ssrn" in url:
        return "ssrn"
    return None


def parse_scholar_id_from_url(value):
    """
    Parse the google scholar id from the url,
    the id is the value of the user parameter.

    Parameters:
    ----------
    value: str
        The url of the google scholar profile

    Returns:
    --------
    str
        The google scholar id
    """
    value = value.replace("authuser", "")
    value = findall(r"user=([^&]{1,12})", value)
    if value:
        value = value[-1]
        if len(value) == 12:
            return "https://scholar.google.com/citations?user=" + value
    return None


def parse_researchgate_id_from_url(value):
    """
    Function to parse the researchgate id from the url,
    it is the value of the profile path in the url

    Parameters:
    ----------
    value: str
        The url of the researchgate profile

    Returns:
    --------
    str
        The researchgate id
    """
    value = search(
        r"https://www\.researchgate\.net/profile/([^\s/?&]+)", value)
    if value:
        return "https://www.researchgate.net/profile/" + value.group(1)
    return None


def parse_linkedin_id_from_url(value):
    """
    Function to parse the linkedin id from the url,
    it is the value of the "in" parameter in the url.

    Parameters:
    ----------
    value: str
        The url of the linkedin profile

    Returns:
    --------
    str
        The linkedin id
    """
    value = search(r"linkedin\.com/in/([^/?&]+)", value)
    if value:
        return "https://www.linkedin.com/in/" + value.group(1)
    return None


def parse_orcid_id_from_url(value):
    """
    Function to parse the orcid id from the url,
    it is the value of the orcid parameter in the url.
    It is four groups of four characters separated by dashes.

    Parameters:
    ----------
    value: str
        The url of the orcid profile

    Returns:
    --------
    str
        The orcid id
    """
    value = value.replace("-", "").replace("_", "").replace(" ", "")
    value = search(
        r"(?:ORCID\s?)?([a-zA-Z0-9]{4})-?([a-zA-Z0-9]{4})-?([a-zA-Z0-9]{4})-?([a-zA-Z0-9]{4})", value)
    if value:
        return "https://orcid.org/" + "-".join(value.groups())
    return None


def parse_scopus_id_from_url(value):
    """
    Function to parse the scopus id from the url,
    it is the value of the authorID or authorId parameter in the url.
    some of the ids where removed from the scopus web site, but it is still useful to have them.
    scopus message:
    "This author profile does not exist or has merged with another author profile. Try to search on another author name."

    Parameters:
    ----------
    value: str
        The url of the scopus profile

    Returns:
    --------
    str
        The scopus id
    """
    value = search(r"(?:authorId=|authorID=)(\d+)", value)
    if value:
        return f"https://www.scopus.com/authid/detail.uri?authorId={value.group(1)}"
    return None


def parse_ssrn_id_from_url(value):
    """
    Function to parse the ssrn id from the url,
    it is the value of the profile path in the url

    Parameters:
    ----------
    value: str
        The url of the web of ssrn profile

    Returns:
    --------
    str
        The ssrn id
    """
    value = search(r'(?:per_id|partid|partID|author)=([\d]+)', value)
    if value:
        return "https://papers.ssrn.com/sol3/cf_dev/AbsByAuth.cfm?per_id=" + value.group(1)
    return None


def parse_wos_id_from_url(value):
    """
    Function to parse the wos id from the url,
    it is the value of the profile path in the url

    Parameters:
    ----------
    value: str
        The url of the web of science profile

    Returns:
    --------
    str
        The wos id
    """
    if "publons" in value:
        _value = search(r'/(\d+)/', value)
        if _value:
            return _value.group(1)
    if "webofscience" in value:
        _value = search(r'/(\d+)', value)
        if _value:
            return "https://www.webofscience.com/wos/author/record/" + _value.group(1)
    return None


def get_id_from_url(value):
    """
    Function to get the id from the url, it uses the get_id_type function to get the type of the id
    and then uses the corresponding function to parse the id from the url.
    Returns the ids without url encoding, without spaces and without url path.

    Parameters:
    ----------
    value: str
        The url of the profile

    Returns:
    --------
    str
        The id of the profile
    """
    value = unquote(value)
    value = value.replace(" ", "")
    if get_id_type_from_url(value) == "scholar":
        return parse_scholar_id_from_url(value)
    if get_id_type_from_url(value) == "researchgate":
        return parse_researchgate_id_from_url(value)
    if get_id_type_from_url(value) == "linkedin":
        return parse_linkedin_id_from_url(value)
    if get_id_type_from_url(value) == "orcid":
        return parse_orcid_id_from_url(value)
    if get_id_type_from_url(value) == "scopus":
        return parse_scopus_id_from_url(value)
    if get_id_type_from_url(value) == "wos":
        return parse_wos_id_from_url(value)
    if get_id_type_from_url(value) == "ssrn":
        return parse_ssrn_id_from_url(value)

    return None


def normalize_name(name):
    """
    Simple function for unidecode names only to do comparison between them, NOT TO BE SAVED IN RECORDS.

    Parameters:
    ----------
    name:str
        The name to be normalized

    Returns:
    --------
    str
        The normalized name
    """
    return str(unidecode.unidecode(name).encode("ascii", "ignore")).lower()


def normalize_names(names):
    """
    Function to normalize names in a loop using normalize_name function

    Parameters:
    ----------
    names:list
        The names to be normalized

    Returns:
    --------
    list
        The normalized names

    """
    return [normalize_name(name) for name in names]


def compare_author(author1: dict, author2: dict):
    """
    Function to compare two authors, the comparison is done by comparing the first and last name of the authors.

    Parameters
    ----------
    author1 : dict
        Author 1 (kahi record)
    author2 : dict
        Author 2 (kahi record)

    Returns
    -------
    bool
        True if the authors are the same, False otherwise.
    """
    if len(author1["first_names"]) > 0 and len(author1["last_names"]) > 0:
        if len(author2["first_names"]) > 0 and len(author2["last_names"]) > 0:
            name_found = set(normalize_names(author1["first_names"])).intersection(
                normalize_names(author2["first_names"]))
            if name_found and normalize_name(
                    author1["last_names"][0]) == normalize_name(
                    author2["last_names"][0]):
                return True
            else:
                return False
        else:
            author2_names = split_names(author2["full_name"])
            if len(author2_names["names"]) > 0 and len(author2_names["surenames"]) > 0:
                name_found = set(normalize_names(author1["first_names"])).intersection(
                    normalize_names(author2_names["names"]))
                if name_found and normalize_name(
                        author1["last_names"][0]) == normalize_name(
                        author2_names["surenames"][0]):
                    return True
                else:
                    return False
            return False
    else:
        author1_names = split_names(author1["full_name"])
        if len(author2["first_names"]) > 0 and len(author2["last_names"]) > 0:
            if len(author1_names["names"]) > 0 and len(author1_names["surenames"]) > 0:
                name_found = set(normalize_names(author1_names["names"])).intersection(
                    normalize_names(author2["first_names"]))
                if name_found and normalize_name(
                        author1_names["surenames"][0]) == normalize_name(
                        author2["last_names"][0]):
                    return True
                else:
                    return False
            else:
                return False
        else:
            author2_names = split_names(author2["full_name"])
            if len(author2_names["names"]) > 0 and len(author2_names["surenames"]) > 0:
                if len(author1_names["names"]) > 0 and len(author1_names["surenames"]):
                    name_found = set(normalize_names(author1_names["names"])).intersection(
                        normalize_names(author2_names["names"]))

                    if name_found and normalize_name(
                            author1_names["surenames"][0]) == normalize_name(
                            author2_names["surenames"][0]):
                        return True
                    else:
                        return False
                else:
                    return False
            else:
                return False


def parse_sex(sex: str, lang: str = "es") -> str:
    """
    Function to normalize sex name

    Parameters:
    ----------
    sex:str
        The sex to be normalized

    Returns:
    --------
    str
        The sex normalized
    """
    sex = sex.strip().lower()
    if sex == "m" or sex == 'masculino':
        return "Hombre" if lang == "es" else "Men"
    if sex == "f" or sex == 'femenino':
        return "Mujer" if lang == "es" else "Woman"
    if sex == "i" or "intersexual":
        return "Intersexual"
    return sex
