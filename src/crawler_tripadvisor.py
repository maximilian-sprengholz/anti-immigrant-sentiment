# -*- coding: utf-8 -*-

'''

This file scrapes tripadvisor review information for restaurants in German
cities for which there are reviews from 2013 to 2017 (around the refugee influx
in 2015).

'''

# imports
import os
import sys
import re
from pathlib import Path
import math
import numpy as np
import pandas as pd

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
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
#options.headless = True
#options.binary_location = wd + 'env/Library/bin/firefox.exe' # activate when sharing code, does not work with group policy

'''

Steps:
------

Use Tripadvisor's restaurant site as database
 └─ Loop over all defined cities
     └─ Loop over all restaurants within city (via pagination)
                 └─ Extract information on restaurant and reviews

Extract everything and subset later (non-German cuisine, reviews 2014-2016,...)

'''

# start driver
driver = webdriver.Firefox(service=Service(GeckoDriverManager().install()), options=options)

# options / functions
driver.implicitly_wait(5)
wait = WebDriverWait(driver, 15) # wait 15 seconds

def accept_cookies():
    # accept cookies when prompted
    try: 
        cookie_prompt = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#onetrust-accept-btn-handler')))
        cookie_prompt.click()
    except:
        pass

# city list (can be supplied via spreadsheet later)
cities = ['Berlin']

# loop over cities
for city in cities:

    # get restaurant page
    driver.get('https://www.tripadvisor.com/Restaurants')
    original_window = driver.current_window_handle
    accept_cookies()
    
    # search for city, open first result of suggestions
    query = city + ' Germany'
    form = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'div.restaurants_home form')))
    form.find_element(By.NAME, 'q').send_keys(query)
    wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[value="' + query + '"]'))) # wait until full input processed
    url = wait.until(lambda d: d.find_element(By.CSS_SELECTOR, 'div#typeahead_results > a').get_attribute('href')) # wait until suggestions show
    driver.get(url)
    accept_cookies()

    # loop over list of restaurants displayed (=30)
    res_list = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, '#EATERY_SEARCH_RESULTS')))
    res_list = res_list.find_elements(by=By.XPATH, value='.//div[contains(@data-test,"list_item")]')
    for res in res_list:
            ### go to restaurant page (let driver stay on results page in tab)
            res_link = res.find_element(by=By.XPATH, value='.//a[contains(@href,"Restaurant_Review")]').get_attribute('href')
            driver.switch_to.new_window('tab')
            driver.get(res_link + '#REVIEWS')
            accept_cookies()
            # get restaurant general info

            # get reviews and review related info
            try:
                name = driver.find_element(By.CSS_SELECTOR, '[data-test-target="top-info-header"]').text
                # select reviews in German
                langbtn = wait.until(lambda d: d.find_element(By.CSS_SELECTOR, '#filters_detail_language_filterLang_de'))
                langbtn.click()
                # fetch all reviews on page
                rev_list = driver.find_elements(By.CSS_SELECTOR, 'div.listContainer > div')
                for r, rev in enumerate(rev_list):
                    try:
                        rating = rev.find_element(By.CSS_SELECTOR, 'span.ui_bubble_rating').get_attribute('class').replace('ui_bubble_rating bubble_','')
                        print(name + ' ' + str(int(int(rating)/10)) + '/5')
                    except:
                        continue
            except:
                print("German is not one of the main review languages")
            finally:
                driver.close()
                driver.switch_to.window(original_window)

# think about whether exclusion rules makes sense beforehand
# if ('German' not in res.find_element(By.CSS_SELECTOR, 'div._3d9EnJpt span.EHA742uW span._1p0FLy4t').text):
