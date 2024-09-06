from titlecase import titlecase
from bs4 import BeautifulSoup
from re import sub, findall
import html


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
    if [tag.name for tag in BeautifulSoup(string, 'lxml').find_all() if tag.name.find('math') > -1]:
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
