# -*- coding: utf-8 -*-

'''

This file scrapes Google review information for 
 
 - restaurants
 - places of worship
 - supermarkets/grocery stores

for German postcode areas.

'''

# imports
import os
import sys
import re
from pathlib import Path
import math
import numpy as np
import pandas as pd
from time import sleep
from datetime import datetime

from selenium import webdriver
# from selenium import JavascriptExecutor
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.firefox.service import Service
from webdriver_manager.firefox import GeckoDriverManager

# working dir (Jupyter proof), add src to import search locations
try:
    wd = str(Path(__file__).parents[1].absolute()) + '/'
except NameError:
    wd = str(Path().absolute()) + '/'
    print('You seem to be using a Jupyter environment. Make sure this points to the repository root: ' + wd)
sys.path.append(wd + 'src')

# selenium options
options = webdriver.FirefoxOptions()
options.set_preference('intl.accept_languages', 'de-DE, de')
#options.headless = True
#options.binary_location = wd + 'env/Library/bin/firefox.exe' # activate when sharing code, does not work with group policy

'''

Steps:
------

x
 └─ x
     └─ x
        └─ x

'''

# start driver
driver = webdriver.Firefox(service=Service(GeckoDriverManager().install()), options=options)

# options / functions
driver.implicitly_wait(1)
wait = WebDriverWait(driver, 10) # wait 15 seconds