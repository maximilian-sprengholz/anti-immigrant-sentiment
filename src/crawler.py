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
from selenium.webdriver.support.expected_conditions import presence_of_element_located

# working dir (Jupyter proof), add src to import search locations
try:
    wd = str(Path(__file__).parents[1].absolute()) + '/'
except NameError:
    wd = str(Path().absolute()) + '/'
    print('You seem to be using a Jupyter environment. Make sure this points to the repository root: ' + wd)
sys.path.append(wd + 'src')

'''

Steps:
------

Use Tripadvisor's restaurant site as database
 └─ Loop over all defined cities
     └─ Loop over all restaurants within city (via pagination)
         └─ Select all tagged as non-German cuisine
             └─ Select subset with reviews in 2013
                 └─ Extract information on restaurant and reviews

'''

# city list (can be supplies via spreadsheet later)
cities = ['Berlin']

# loop over cities
for city in cities:

    ### search for city
    driver = webdriver.Firefox()
    wait = WebDriverWait(driver, 10)
    driver.get('https://www.tripadvisor.com/Restaurants')
    original_window = driver.current_window_handle
    # accept cookies
    cookie_prompt = wait.until(presence_of_element_located((By.CSS_SELECTOR, '#_evidon-accept-button')))
    cookie_prompt.click()
    # search city by city and open first result of suggestions
    form = driver.find_element(By.CSS_SELECTOR, 'div.restaurants_home form')
    form.find_element(By.NAME, 'q').send_keys(city + ' Germany')
    url = wait.until(lambda d: d.find_element(By.CSS_SELECTOR, 'div#typeahead_results > a').get_attribute('href'))
    driver.get(url)

    ### check restaurant fit
    '''
    Not possible to avoid hard-coding gibberish class names from CSS modules in
    all cases. Can be a problem when recompiled.
    '''
    res_list_item_class = driver.find_element(By.CSS_SELECTOR, '[data-test="1_list_item"]').get_attribute('class')
    res_list = driver.find_elements(By.CSS_SELECTOR, '#EATERY_SEARCH_RESULTS div.' + res_list_item_class)
    for res in res_list:
        if ('German' not in res.find_element(By.CSS_SELECTOR, 'div._3d9EnJpt span.EHA742uW span._1p0FLy4t').text):
            ### go to restaurant page (let driver stay on results page in tab)
            res_link = res.find_element(By.CSS_SELECTOR, 'a._15_ydu6b').get_attribute('href')
            driver.switch_to.new_window('tab')
            driver.get(res_link + '#REVIEWS')
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
                print("German not one of the main review languages")
            finally:
                driver.close()
                driver.switch_to.window(original_window)


# driver = webdriver.Firefox()
# wait = WebDriverWait(driver, 10)
# driver.get('https://www.tripadvisor.com/Restaurant_Review-g187323-d2456695-Reviews-Die_Eselin_von_A-Berlin.html')
# # accept cookies
# cookie_prompt = wait.until(presence_of_element_located((By.CSS_SELECTOR, '#_evidon-accept-button')))
# cookie_prompt.click()
# #
# driver.find_element(By.CSS_SELECTOR, '#filters_detail_language_filterLang_de').click()
# rev_list = driver.find_elements(By.CSS_SELECTOR, 'div.listContainer > div')
# name = driver.find_element(By.CSS_SELECTOR, '[data-test-target="top-info-header"]').text
# for r, rev in enumerate(rev_list):
#     try:
#         rating = rev.find_element(By.CSS_SELECTOR, 'span.ui_bubble_rating').get_attribute('class').replace('ui_bubble_rating bubble_','')
#         print(name + ' ' + str(int(int(rating)/10)) + '/5')
#     except:
#         continue
