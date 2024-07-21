from titlecase import titlecase
from bs4 import BeautifulSoup
from re import sub, findall
import html
import tempfile


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
    with tempfile.NamedTemporaryFile(delete=True, mode='w+', suffix='.xml', prefix='temp_', dir='./') as temp_file:
        temp_file.write(string)
        temp_file.flush()
        temp_file.seek(0)
        if [tag.name for tag in BeautifulSoup(temp_file, 'lxml').find_all() if tag.name.find('math') > -1]:
            temp_file.seek(0)
            temp_file.truncate()
            temp_file.write(sub(r"([a-zA-Z])<", r"\1 <", string))
            temp_file.flush()
            temp_file.seek(0)
            string = sub('\n', ' ', BeautifulSoup(
                temp_file, 'lxml').text.strip())
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
