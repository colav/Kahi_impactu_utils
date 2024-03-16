from titlecase import titlecase


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
