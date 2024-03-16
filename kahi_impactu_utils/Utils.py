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


def split_names(s, exceptions=['GIL', 'LEW', 'LIZ', 'PAZ', 'REY', 'RIO', 'ROA', 'RUA', 'SUS', 'ZEA',
                               'ANA', 'LUZ', 'SOL', 'EVA', 'EMA'], sep=':'):
    """
    Extract the parts of the full name `s` in the format ([] → optional):

    [SMALL_CONECTORS] FIRST_LAST_NAME [SMALL_CONECTORS] [SECOND_LAST_NAME] NAMES

    * If len(s) == 2 → Foreign name assumed with single last name on it
    * If len(s) == 3 → Colombian name assumed two last mames and one first name

    Add short last names to `exceptions` list if necessary

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
    exceptions:list
        A list of short last names to be considered as exceptions.
    sep:str
        The separator to be used to split the names.

    Returns:
    -------
    dict
        A dictionary with the extracted parts of the full name.
    """
    s = s.title()
    exceptions = [e.title() for e in exceptions]
    sl = sub('(\s\w{1,3})\s', fr'\1{sep}', s, UNICODE)  # noqa: W605
    sl = sub('(\s\w{1,3}%s\w{1,3})\s' % sep, fr'\1{sep}', sl, UNICODE)  # noqa: W605
    sl = sub('^(\w{1,3})\s', fr'\1{sep}', sl, UNICODE)  # noqa: W605
    # Clean exceptions
    # Extract short names list
    lst = [s for s in split(
        '(\w{1,3})%s' % sep, sl) if len(s) >= 1 and len(s) <= 3]  # noqa: W605
    # intersection with exceptions list
    exc = [value for value in exceptions if value in lst]
    if exc:
        for e in exc:
            sl = sl.replace('{}{}'.format(e, sep), '{} '.format(e))

    sll = sl.split()

    if len(sll) == 2:
        sll = [sl.split()[0]] + [''] + [sl.split()[1]]

    if len(sll) == 3:
        sll = [sl.split()[0]] + [''] + sl.split()[1:]

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
            return value
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
        return value.group(1)
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
        return value.group(1)
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
    value = value.replace("-", "")
    value = value.replace("_", "")
    value = search(
        r"(?:ORCID\s?)?([a-zA-Z0-9]{4})-?([a-zA-Z0-9]{4})-?([a-zA-Z0-9]{4})-?([a-zA-Z0-9]{4})", value)
    if value:
        return "-".join(value.groups())
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

    ##
    value = search(r"(?:authorId=|authorID=)(\d+)", value)
    if value:
        return f"https://www.scopus.com/authid/detail.uri?authorId={value.group(1)}"
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

    return None


def compare_author(author_id, comparison_name, author_full_name):
    """
    Compares the given author's full name with a comparison name and returns the comparison method used.

    Parameters:
    ----------
    author_id : int
        The ID of the author.
    comparison_name : str
        The name to compare with the author's full name.
    author_full_name : str
        The full name of the author.

    Returns:
    ----------
    dict or bool:
        A dictionary containing author information and the comparison method used if a match is found,
        or False if no match is found.
    """

    def some(iterable, condition, num_required):
        """
        Returns True if at least num_required items in the iterable satisfy the condition; otherwise, False.

        Parameters:
        ----------
        iterable : iterable
            The iterable to be checked.
        condition : function
            The condition to be satisfied.
        num_required : int
            The minimum number of items that need to satisfy the condition.

        Returns:
        ----------
        bool:
            True if num_required items satisfy the condition; otherwise, False.
        """
        count = 0
        for item in iterable:
            if condition(item):
                count += 1
                if count >= num_required:
                    return True
        return False

    full_name_clean = unidecode.unidecode(
        author_full_name.lower()).strip().strip(".").replace("-", " ")
    comparison_name_clean = unidecode.unidecode(
        comparison_name.lower()).strip().strip(".").replace("-", " ")

    # full_name_parts = full_name_clean.split()
    comparison_parts = comparison_name_clean.split()

    if all(part in full_name_clean for part in comparison_parts):
        return {'author_full_name': author_full_name, 'author_id': author_id, 'method': 'all'}
    elif some(comparison_parts, lambda part: part in full_name_clean, 2):
        return {'author_full_name': author_full_name, 'author_id': author_id, 'method': 'some'}
    # elif any(part in full_name_clean for part in comparison_parts):
        # return {'author_full_name': author_full_name, 'author_id': author_id, 'method': 'any'}

    return False
