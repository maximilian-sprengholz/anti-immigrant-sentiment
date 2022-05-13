# -*- coding: utf-8 -*-

'''

This file checks the scraped data for consistency.

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

# check city datasets
df = pd.read_feather(wd + 'data/temp/tripadvisor_results_restaurant_oelsnitzvogtland_14523300_g1931731d5511518.feather')
