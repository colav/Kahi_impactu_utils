from re import sub, split, UNICODE, search, match, findall
import unidecode
from datetime import datetime as dt

from langid import classify
import pycld2 as cld2
from fastspell import FastSpell
from urllib.parse import unquote
import requests

from racebert import RaceBERT

fast_spell = FastSpell("en", mode="cons")

model = RaceBERT()


def get_origin(s, api_key):
    """
    Analyzes an unsplit full name (first name and last name) to identify its country of origin.

    Parameters:
    ----------
    s:str
      Full name
    api_key:str
      API key from https://namsor.app/api-documentation

    Returns:
    -------
    str
      Code fo country of origin ('ES' as default)
    """
    url = f"https://v2.namsor.com/NamSorAPIv2/api2/json/originFull/{s}"
    # split names → funciona mal
    # url = f"https://v2.namsor.com/NamSorAPIv2/api2/json/parseName/{s}"

    headers = {
        "X-API-KEY": api_key,
        "Accept": "application/json"
    }

    response = requests.request("GET", url, headers=headers)
    if response.status_code == 200:
        return response.json().get('countryOrigin')
    else:
        return 'ES'  # default value


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


def flatten(xss):
    return [x for xs in xss for x in xs]


def get_name_connector():
    """
    Collections of name connectors in multiple languages.
    """
    return ['DE', 'DEL', 'LA', 'EL', 'JR', 'JR.', 'VAN', 'DER', 'DA', 'DO', 'DI', 'VON', 'LOS', 'DAS', 'DAL', 'LAS', 'I', 'E']


def split_name_part(name, connectors=get_name_connector()):
    """
    Allows to split a name into its parts, taking into account the connectors that are usually used in names.
    This can be used to split  surenames or last names in a name. Some surenames and lastnames have connectors like 'DE', 'DEL', 'LA' etc..

    Example:
    given the name "BUSTAMANTE CARDONA, BERNARDO MARÍA DE LA CRUZ"
    you need to split the surename "BERNARDO MARÍA DE LA CRUZ"

    using   split_name_part("BERNARDO MARÍA DE LA CRUZ")

    the function will return ['BERNARDO', 'MARÍA', 'DE LA CRUZ']


    Parameters:
    ----------
    name:str
        The name to be processed.

    connectors:list
        The connectors to be used to split the name.

    Returns:
    -------
    list
        The parts of the name.
    """
    if connectors is None:
        connectors = [
            "DE",
            "DEL",
            "LA",
            "EL",
            "VAN",
            "DER",
            "DA",
            "DO",
            "DI",
            "VON",
            "LOS",
            "DAS",
            "DAL",
            "LAS",
            "I",
            "E"
        ]

    connectors = [c.upper() for c in connectors]

    name = " ".join(name.strip().split()).title()

    words = name.split()
    part_names = []
    buffer = []

    for word in words:
        if word.upper() in connectors:
            buffer.append(word)
        else:
            if buffer:
                part_names.append(" ".join(buffer + [word]))
                buffer = []
            else:
                part_names.append(word)
    return part_names


def split_names(s, connectors=get_name_connector(), sep=':',
                reverse=False, namsor_api_key=None, countryOrigin=None,
                LA=['ES', 'PT', 'AR', 'BO', 'BR', 'CL', 'CO', 'CR', 'CU', 'DO',
                    'EC', 'SV', 'GT', 'HN', 'MX', 'NI', 'PA', 'PY', 'PE', 'PR',
                    'UY', 'VE']):
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
          'SOL ANA DE ZEA GIL',
          'ANTONIO ENEA ROMANO'
    Fails:
    ----
        s='RANGEL MARTINEZ VILLAL ANDRES MAURICIO' # more than 2 last names
        s='Ramón Fernandez de la Vara-Prieto'

    Parameters:
    ----------
    s:str
        The full name to be processed.
    connectors:list
        A list of connectors between names which are assumed to be at least of
        length 2.
    sep:str
        The separator to be used to split the names.
    revers:boolean
        True if the name is reversed
    namsor_api_key:str
        If not `None`, check the country of origin with the namsor API key to
        split names of 3 components. One first name and two last names if
        country in `LA` (Hispanic). If `None` the module `racebert` will be used
        to predict if the name is not Hispanic
        with accuracy: 0.996 (https://bit.ly/4lFjMyT)
    countryOrigin:str
        ISO 3166-1 alpha-2 code for the country of origin of the name of 3
        components to split; If `None` and `namsor_api_key` is also`None`,
        the module `racebert` will be used to predict if the name is not Hispanic
        with accuracy: 0.996 (https://bit.ly/4lFjMyT)
    LA:list
        List of country codes with origin in Ibero America

    Returns:
    -------
    dict
        A dictionary with the extracted parts of the full name.
    """
    if s.strip().startswith('-'):
        s = s[1:].strip()
    s = s.title()
    s = sub(r'\s*\-\s*', '-', s)  # hyphenation without space
    # Remove until 3 middle initials
    # s = sub(r'\s\w\.*\s', ' ', sub(r'\s\w\.*\s', ' ', s))
    connectors = [e.title() for e in connectors]
    sl = sub(r"([\s\-]\w{1,3})\s", rf"\1{sep}", s, UNICODE)  # noqa: W605
    sl = sub(
        r"([\s\-]\w{1,3}%s\w{1,3})\s" % sep, rf"\1{sep}", sl, UNICODE
    )  # noqa: W605
    sl = sub(r"^(\w{1,3})\s", rf"\1{sep}", sl, UNICODE)  # noqa: W605

    # Clean connectors
    # Extract short names list
    lst = [s for s in split(
        r'(\w{1,3})%s' % sep, sl) if len(s) >= 1 and len(s) <= 3]  # noqa: W605
    # intersection with connectors list
    exc = [value for value in lst if value not in connectors]
    if exc:
        for e in exc:
            sl = sl.replace('{}{}'.format(e, sep), '{} '.format(e))

    # Go to standard 4-names components if possible
    if sl.find('-') and len(sl.split()) == 3:
        sl = sl.replace('-', ' ')

    sll = sl.split()

    # Fill two first names (last names) as empty strings if reverse = False (True)
    if len(sll) == 1:
        if not reverse:
            sll = ['', ''] + sl.split()[0:1]
        else:
            sll = sl.split()[0:1] + ['', '']

    # Add sll[1] → ''
    elif len(sll) == 2:
        sll = sl.split()[0:1] + [''] + sl.split()[1:2]

    # Fill the fourth item with an empty string
    elif len(sll) == 3:
        foreign = False
        if namsor_api_key:
            origin = get_origin(s, namsor_api_key)
        elif countryOrigin:
            origin = countryOrigin
        else:
            mdl = model.predict_ethnicity(s)
            ethnicity = mdl[0].get('label').split(',')[-1]
            score = mdl[0].get('score')
            race = model.predict_race(s)[0].get('label')

            if ethnicity != 'Hispanic' and score > 0.5 and race != 'hispanic':            
                origin = ethnicity
            else:
                origin = 'ES'

        if origin not in LA:
            foreign = True

        max_first_names = 1
        if foreign:
            max_first_names = 2

        max_last_names = 3 - max_first_names
        if not reverse:
            sll = sl.split()[0:max_first_names] + [''] + sl.split()[max_first_names:]
        else:
            sll = sl.split()[0:max_last_names] + [''] + sl.split()[max_last_names:]

    #  Ignore empty strings
    if not reverse:
        d = {
            'first_names': [x.replace(sep, ' ') for x in sll[:2] if x],
            'last_names': [x.replace(sep, ' ') for x in sll[2:] if x],
        }
    else:
        d = {
            'first_names': [x.replace(sep, ' ') for x in sll[2:] if x],
            'last_names': [x.replace(sep, ' ') for x in sll[:2] if x],
        }

    if any([x.find('-') > -1 for x in d['first_names']]):
        d['first_names'] = flatten([x.split('-') for x in d['first_names']])
    if any([x.find('-') > -1 for x in d['last_names']]):
        d['last_names'] = flatten([x.split('-') for x in d['last_names']])

    d['full_name'] = ' '.join(d['first_names'] + d['last_names'])
    d['initials'] = "".join([x[0] for x in d['first_names']])

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
        return f"https://doi.org/{match.group().strip().strip('.').lower()}"
    doi_candidate = doi.replace(" ", "").strip().strip(
        '.').lower().replace("%2f", "/").replace("doi", "")
    match = search(doi_regex, doi_candidate)
    if match:
        return f"https://doi.org/{match.group().strip().strip('.').lower()}"
    if ('http' in doi_candidate or 'www' in doi_candidate or 'dx' in doi_candidate) and "10." in doi_candidate:
        doi_candidate = doi_candidate.split("/10")[-1].replace("%2f", "/")
        doi_candidate = "10" + doi_candidate
        match = search(doi_regex, doi_candidate)
        if match:
            return f"https://doi.org/{match.group().strip('.').lower()}"
    if doi_candidate.startswith("0."):
        doi_candidate = "1" + doi_candidate
    match = search(doi_regex, doi_candidate)
    if match:
        return f"https://doi.org/{match.group().strip().strip('.').lower()}"
    doi_candidate = doi.split("/")
    if doi_candidate[0].endswith('.'):
        doi_candidate[0] = doi_candidate[0].strip('.')
    if "." not in doi_candidate[0]:
        doi_candidate[0] = doi_candidate[0].replace("10", "10.")
    doi_candidate = '/'.join(doi_candidate)
    match = search(doi_regex, doi_candidate)
    if match:
        return f"https://doi.org/{match.group().strip().strip('.').lower()}"

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
        date_list = date_str.split("-")
        if date_list[0] == "00":  # required for bad format in scienti data
            year = date_list[1]
            return int(dt.strptime(year, "%Y").timestamp())
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
        return "publons"
    if "webofscience" in url:
        return "wos"
    if "ssrn" in url:
        return "ssrn"
    if "openalex" in url:
        return "openalex"
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
    if "webofscience" in value:
        _value = search(r'/(\d+)', value)
        if _value:
            return "https://www.webofscience.com/wos/author/record/" + _value.group(1)
    return None


def parse_publons_id_from_url(value):
    """
    Function to parse the wos id from the url,
    it is the value of the profile path in the url
    NOTE: publons redirects to the wos profile, but it is a different id

    Parameters:
    ----------
    value: str
        The url of the publons profile

    Returns:
    --------
    str
        The publons id
    """
    if "publons" in value:
        _value = search(r'/(\d+)', value)
        if _value:
            return "https://publons.com/researcher/" + _value.group(1)
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
    value = unquote(str(value))
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
    # this is different that wos id, to do unicity redirect to wos have to be solved
    if get_id_type_from_url(value) == "publons":
        return parse_publons_id_from_url(value)
    if get_id_type_from_url(value) == "ssrn":
        return parse_ssrn_id_from_url(value)
    if get_id_type_from_url(value) == "openalex":
        return value
    return None


def split_names_fix(author1, author2):
    """
    Method to fix the split names function, it is used to fix the split names function when it fails to split the names correctly
    based on the good name that has an id such as cedula.

    Parameters:
    ----------
    author1:dict
        The name to be fixed ex: openalex name
    author2:dict
        The name to be used as reference ex: kahi name from scienti or puntaje

    Returns:
    --------
    dict
        The fixed name
    """
    intersection = set(author1['last_names']).intersection(
        author2['first_names'])   # intersection = ['SN_name2']
    if intersection:
        author1['last_names'] = [x for x in author1['last_names']
                                 if x not in intersection]  # .union could change the order
        author1['first_names'] = author1['first_names'] + list(intersection)
        return author1
    return []


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
    return unidecode.unidecode(name).encode("ascii", "ignore").decode('ascii').lower().strip()


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


def compare_authors_initials(initials1: str, last_name1: str, initials2: str, last_name2: str):
    """
    Function to compare two authors by their initials and last name

    Parameters:
    ----------
    initials1:str
        The initials of the first author
    last_name1:str
        The last name of the first author
    initials2:str
        The initials of the second author
    last_name2:str
        The last name of the second author

    Returns:
    --------
    bool
        True if the authors are the same, False otherwise
    """
    initials1 = [*normalize_name(initials1).replace(".", "")]
    initials2 = [*normalize_name(initials2).replace(".", "")]

    if initials1 == initials2 and normalize_name(last_name1) == normalize_name(last_name2):
        return True
    return False


def compare_authors_ids_scienti(author1: dict, author2: dict, verbose=4):
    """
    Function to compare two authors by their ids of scienti.

    Parameters
    ----------
    author1 : dict
        Author 1 (kahi record)
    author2 : dict
        Author 2 (kahi record)

    Returns
    -------
    bool
        True if the authors are the same, False otherwise, None if the ids are not found.
    """
    if "external_ids" not in author1.keys() or "external_ids" not in author2.keys():
        if verbose > 4:
            print("WARNING: External ids not found in the authors")
            print(author1)
            print(author2)
        return None
    id1 = [i["id"]
           for i in author1["external_ids"] if i["source"] == "scienti"]
    id2 = [i["id"]
           for i in author2["external_ids"] if i["source"] == "scienti"]
    if id1 and id2:
        return id1 == id2
    else:
        return None


def compare_authors_ids(author1: dict, author2: dict, verbose=4):
    """
    Function to compare two authors by their ids, the comparison is done by comparing the ids of the authors.

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
    if "external_ids" not in author1.keys() or "external_ids" not in author2.keys():
        if verbose > 4:
            print("WARNING: External ids not found in the authors")
            print(author1)
            print(author2)
        return False
    values = []
    for source in ["scienti", "scopus", "orcid", "scholar"]:
        for id1 in author1["external_ids"]:
            for id2 in author2["external_ids"]:
                if id1["source"] == id2["source"] and id2["source"] == source and id1["id"] == id2["id"]:
                    values.append(True)
                if id1["source"] == id2["source"] and id2["source"] == source and id1["id"] != id2["id"]:
                    values.append(False)

                # if we are in scienti and they are different we can return false/ with orcid and scopus we can't(we are not sure)
                if id1["source"] == id2["source"] and source == "scienti" and id1["id"] == id2["id"]:
                    return True
                if id1["source"] == id2["source"] and source == "scienti" and id1["id"] != id2["id"]:
                    return False
    if values:
        return all(values)
    else:
        return False


def compare_author(author1: dict, author2: dict, n_authors: int):
    """
    Function to compare two authors, the comparison is done by comparing the first and last name of the authors.

    Parameters
    ----------
    author1 : dict
        Author 1 (kahi record)
    author2 : dict
        Author 2 (kahi record)
    n_authors : int
        The number of authors in the work, used to limit the comparison of authors by initials.

    Returns
    -------
    bool
        True if the authors are the same, False otherwise.
    """
    # compare authors by ids of scienti
    found = compare_authors_ids_scienti(author1, author2)
    if found is not None:
        return found
    # compare authors by ids
    if compare_authors_ids(author1, author2):
        return True
    # compare authors by full names
    if normalize_name(author1["full_name"]) == normalize_name(author2["full_name"]):
        return True
    # compare authors by first and last names of initials
    if len(author1["first_names"]) > 0 and len(author1["last_names"]) > 0:
        if len(author2["first_names"]) > 0 and len(author2["last_names"]) > 0:
            name_found = set(normalize_names(author1["first_names"])).intersection(
                normalize_names(author2["first_names"]))
            if name_found and normalize_name(
                    author1["last_names"][0]) == normalize_name(
                    author2["last_names"][0]):
                return True
            else:
                if compare_authors_initials(author1["initials"], author1["last_names"][0], author2["initials"], author2["last_names"][0]):
                    return True
                return False
        else:
            author2_names = split_names(author2["full_name"])
            author2_names_fix = split_names_fix(author1, author2_names)
            if author2_names_fix:
                author2_names = author2_names_fix
            if len(author2_names["first_names"]) > 0 and len(author2_names["last_names"]) > 0:
                name_found = set(normalize_names(author1["first_names"])).intersection(
                    normalize_names(author2_names["first_names"]))
                if name_found and normalize_name(
                        author1["last_names"][0]) == normalize_name(
                        author2_names["last_names"][0]):
                    return True
                else:
                    if n_authors <= 10:
                        if compare_authors_initials(author1["initials"], author1["last_names"][0], author2_names["initials"], author2_names["last_names"][0]):
                            return True
                    return False
            return False
    else:
        author1_names = split_names(author1["full_name"])
        author1_names_fix = split_names_fix(author1_names, author2)
        if author1_names_fix:
            author1_names = author1_names_fix
        if len(author2["first_names"]) > 0 and len(author2["last_names"]) > 0:
            if len(author1_names["first_names"]) > 0 and len(author1_names["last_names"]) > 0:
                name_found = set(normalize_names(author1_names["first_names"])).intersection(
                    normalize_names(author2["first_names"]))
                if name_found and normalize_name(
                        author1_names["last_names"][0]) == normalize_name(
                        author2["last_names"][0]):
                    return True
                else:
                    if n_authors <= 10:
                        if compare_authors_initials(author1_names["initials"], author1_names["last_names"][0], author2["initials"], author2["last_names"][0]):
                            return True
                    return False
            else:
                return False
        else:
            author2_names = split_names(author2["full_name"])
            author2_names_fix = split_names_fix(author1_names, author2_names)
            if author2_names_fix:
                author2_names = author2_names_fix
            if len(author2_names["first_names"]) > 0 and len(author2_names["last_names"]) > 0:
                if len(author1_names["first_names"]) > 0 and len(author1_names["last_names"]):
                    name_found = set(normalize_names(author1_names["first_names"])).intersection(
                        normalize_names(author2_names["first_names"]))

                    if name_found and normalize_name(
                            author1_names["last_names"][0]) == normalize_name(
                            author2_names["last_names"][0]):
                        return True
                    else:
                        if n_authors <= 10:
                            if compare_authors_initials(author1_names["initials"], author1_names["last_names"][0], author2_names["initials"], author2_names["last_names"][0]):
                                return True
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
