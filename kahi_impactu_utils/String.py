from titlecase import titlecase
from bs4 import BeautifulSoup
from re import sub, findall, search, IGNORECASE, compile as re_compile
import html

# Hyphen and dash code points found in author names: ASCII hyphen-minus, Unicode
# hyphen, non-breaking hyphen, figure dash, en dash, em dash, horizontal bar and
# minus sign.
DASH_CHARS = "\u002d\u2010\u2011\u2012\u2013\u2014\u2015\u2212"
_DASH_RE = re_compile("[" + DASH_CHARS + "]")


def has_dash(value):
    """Return True when `value` contains any hyphen or dash variant."""
    return bool(value) and _DASH_RE.search(str(value)) is not None


def normalize_dashes(value, replacement=" "):
    """
    Replace every hyphen or dash variant in a personal name.

    All characters in DASH_CHARS are replaced by `replacement` (a space by
    default), whitespace is collapsed and dash-only tokens disappear, so
    "A Alonso\u2010Herrero" becomes "A Alonso Herrero" and "Cooman -" becomes
    "Cooman". With replacement="-" the dashes are canonicalised to the ASCII
    hyphen instead, which lets hyphen-aware parsers keep the parts together.

    Parameters:
    -----------
    value : str or None
        The name to normalise. None and empty values are returned unchanged.
    replacement : str
        The text that takes the place of each dash.

    Returns:
    --------
    str
        The normalised name.
    """
    if not value:
        return value
    text = _DASH_RE.sub(replacement, str(value))
    if replacement.strip() == "":
        return " ".join(text.split())
    # Canonical hyphen: drop dash-only tokens and dashes glued to whitespace.
    tokens = [t.strip(replacement) for t in text.split()]
    return " ".join(t for t in tokens if t)


def abbreviations(word, **kwargs):
    """
    Function to handle abbreviations in the titlecase function

    Parameters:
    -----------
    word : str
        The word to be checked.
    kwargs : dict
        The dictionary with the configuration parameters.

    Returns:
    --------
    str
        The word in lowercase if it is an abbreviation, otherwise the original word.
    """
    if word.lower() in ('de', 'del', 'e', 'en', 'la', 'las', 'los', 'y'):
        return word.lower()
    if word.upper() in ('EAFIT', 'EIA'):
        return word.upper()
    if word in ('UdeA', 'GitHub'):
        return word
    return word.capitalize()


def title_case(word):
    """
    Function to convert a word to title case.

    Parameters:
    -----------
    word : str
        The word to be converted.

    Returns:
    --------
    str
        The word in title case.
    """
    return titlecase(word, callback=abbreviations)


def parse_mathml(string):
    """
    Function to parse the string of a mathml element,
    only if mathml code is found in the string.

    Parameters:
    -----------
    string : str
        The string to be parsed.

    Returns:
    --------
    str
        The parsed title.
    """
    math_tag = r'<\s*/?\s*(?:[\w.-]+:)?[\w.-]*math[\w.-]*(?:\s|/?>)'
    if search(math_tag, string, IGNORECASE):
        string = sub('\n', ' ', BeautifulSoup(
            sub(r"([a-zA-Z])<", r"\1 <", string), 'lxml').text.strip())
    return string


def parse_html(string):
    """
    Function to parse the string of a html element,
    only if html code is found in the string.

    Parameters:
    -----------
    string : str
        The string to be parsed.

    Returns:
    --------
    str
        The parsed title.
    """
    if "&lt;" in string:
        string = html.unescape(string)
    found = findall(r'<[^>]+>', string)
    if found:
        soup = BeautifulSoup(string, 'html.parser')
        return soup.get_text()
    return string


def text_to_inverted_index(string):
    """
    Function to create an inverted index from a list of strings.

    Parameters:
    -----------
    string : str
        The string to be indexed.

    Returns:
    --------
    dict
        The inverted index.
    """
    data = string.split()
    index = {}
    for idx, string in enumerate(data):
        for word in string.split():
            if word in index:
                index[word].append(idx)
            else:
                index[word] = [idx]
    return index


def inverted_index_to_text(inv_index):
    """
    Function to convert an inverted index to the original text.

    Parameters:
    -----------
    inv_index : dict
        The inverted index.

    Returns:
    --------
    str
        The original text.
    """
    max_position = max(pos for positions in inv_index.values()
                       for pos in positions)

    text = [''] * (max_position + 1)

    for term, positions in inv_index.items():
        for pos in positions:
            text[pos] = term

    return ' '.join(text)
