# -*- coding: utf-8 -*-

'''

This file prepares a CSV file that contains municipality information 
which will be fed as input to the scraper.

'''

# imports
import os
import sys
import subprocess
import re
from pathlib import Path
from ast import literal_eval
import math
import numpy as np
import pandas as pd
from time import sleep
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import StaleElementReferenceException
from selenium.common.exceptions import ElementNotInteractableException
from selenium.webdriver.firefox.service import Service
from webdriver_manager.firefox import GeckoDriverManager

# working dir (Jupyter proof), add src to import search locations
try:
    wd = str(Path(__file__).parents[1].absolute()) + '/'
except NameError:
    wd = str(Path().absolute()) + '/'
    print('You seem to be using a Jupyter environment.' 
          'Make sure this points to the repository root: ' 
          + wd)
sys.path.append(wd + 'src')

### gen municipality dataset from OSM contributor correspondence table
'''
We use the OSM correspondence table to map municipalities (identified via the Amtlicher 
Gemeindeschlüssel) to names, postcodes, and federal states. We also generate a default query 
string for Tripadvisor that is just name + state.
'''
df = pd.read_csv(wd + 'data/raw/zuordnung_plz_ort.csv', dtype={'ags': object, 'plz': object})
df = df.groupby(['ags', 'ort', 'bundesland'])['plz'].unique().reset_index(name='plz')
df['plz'] = df['plz'].apply(list) # convert nd.array to list
df.columns = ['ags', 'municipality', 'state', 'postcodes']
df['querystring'] = df['municipality'] + ' ' + df['state']
df = df[df['ags'].isin(['14523300', '16073077', '14523320', '13003000'])] # subset for now
df.to_csv(wd + 'data/raw/tripadvisor_input_municipalities.csv', sep=';', index=False)

