
<center><img src="https://raw.githubusercontent.com/colav/colav.github.io/master/img/Logo.png"/></center>

# Kahi impactu utils 
KAHI is a powerful ETL (Extract, Transform, Load) application designed to construct an academic database by merging databases and files from various sources. It simplifies the database construction process by offering a framework to define a workflow of sequential tasks using a plugin system that KAHI understands.

Kahi impactu utils is a package that contains a set of utils required for multiple plugins to work.
This package provide utils such as: name processing, laguage detection, data schemas for works, affiliations, persons, etc.

## Installation

To install Kahi impactu utils, follow these simple steps:

1. Make sure you have Python installed on your system.
2. Open a terminal or command prompt.
3. Run the following command:

```shell
pip install kahi_impactu_utils
```


# Usage
## Split names example
```python
from kahi_impactu_utils.Utils import split_names

name = "John Doe"
names = split_names(name)
print(names) ## {'names': ['John'], 'surenames': ['Doe'], 'initials': ['J.']}
```

## Detect language example
```python
from kahi_impactu_utils.Utils import lang_poll
print(lang_poll("Alguna frase en español")) ## returns "es"
```

## Process DOIs example
```python
from kahi_impactu_utils.Utils import doi_processor
doi = doi_processor("https://doi.org/10.1007/S11192-020-03647-4")
print(doi) ## returns "10.1007/s11192-020-03647-4"
```

## Check date format example
```python
from kahi_impactu_utils.Utils import check_date_format
date = "2020-01-01"
print(check_date_format(date)) ## returns 1577854800  (UTC-5) for this date
```

## Mapping example
```python
from kahi_impactu_utils.Mapping import ciarp_mapping
ciarp_mapping("https://ror.org/03bp5hc83", "works") ## returns a list of categories for the entity works
```

# License
BSD-3-Clause License 

# Links
http://colav.udea.edu.co/



