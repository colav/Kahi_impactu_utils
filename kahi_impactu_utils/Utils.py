from re import sub, split, UNICODE, search, match
import unidecode
from datetime import datetime as dt

from langid import classify
import pycld2 as cld2
from langdetect import DetectorFactory, PROFILES_DIRECTORY
from fastspell import FastSpell
from lingua import LanguageDetectorBuilder
import iso639

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

    if detected_language:
        lang_list.append(detected_language[0][-1].lower())

    try:
        _factory = DetectorFactory()
        _factory.load_profile(PROFILES_DIRECTORY)
        detector = _factory.create()
        detector.append(text)
        lang_list.append(detector.detect().lower())
    except Exception as e:
        if verbose > 4:
            print("Language detection error using langdetect")
            print(e)

    try:
        result = fast_spell.getlang(text)  # low_memory breaks the function
        lang_list.append(result.lower())
    except Exception as e:
        if verbose > 4:
            print("Language detection error using fastSpell")
            print(e)

    detector = LanguageDetectorBuilder.from_all_languages().build()
    res = detector.detect_language_of(text)
    if res:
        if res.name.capitalize() == "Malay":
            la = "ms"
        elif res.name.capitalize() == "Sotho":
            la = "st"
        elif res.name.capitalize() == "Bokmal":
            la = "no"
        elif res.name.capitalize() == "Swahili":
            la = "sw"
        elif res.name.capitalize() == "Nynorsk":
            la = "is"
        elif res.name.capitalize() == "Slovene":
            la = "sl"
        else:
            la = iso639.find(
                res.name.capitalize())["iso639_1"].lower()
        lang_list.append(la)

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

    d = {'NOMBRES': [x.replace(sep, ' ') for x in sll[:2] if x],
         'APELLIDOS': [x.replace(sep, ' ') for x in sll[2:] if x],
         }
    d['INICIALES'] = [x[0] + '.' for x in d['NOMBRES']]

    return d


def dois_processor(doi):
    """
    Process a DOI (Digital Object Identifier) and return a cleaned version.
    Args:
        doi (str): The DOI to be processed.
    Returns:
        str or bool: If a valid DOI is found, return the cleaned DOI; otherwise, return False.
    """
    doi_regex = r"\b10\.\d{3,}/[^\s]+"
    match = search(doi_regex, doi)
    if match:
        return match.group().strip().strip('.')
    doi_candidate = doi.replace(" ", "").strip().strip('.').lower().replace("%2f", "/").replace("doi", "")
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

    Args:
        date_str (str): A string representing a date.

    Returns:
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
    """
    if date_str is None:
        return ""
    wdmyhmsz_format = r"^\w{3}, \d{2} \w{3} \d{4} \d{2}:\d{2}:\d{2} \w{3}$"
    ymdhms_format = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"
    dmyhms_format = r"\d{2}-\d{2}-\d{4} \d{2}:\d{2}:\d{2}"
    ymd_format = r"\d{4}-\d{2}-\d{2}"
    dmy_format = r"\d{2}-\d{2}-\d{4}"
    ym_format = r"\d{4}-\d{2}"
    my_format = r"\d{2}-\d{4}"
    if match(wdmyhmsz_format, date_str):
        return int(dt.strptime(date_str, "%a, %d %b %Y %H:%M:%S %Z").timestamp())
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
