# -*- coding: utf-8 -*-

'''

This file scrapes Tripadvisor review information 
for restaurants in German cities.

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
from selenium.common.exceptions import StaleElementReferenceException
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


### DRIVER / FUNCTIONS ###

# start driver
driver = webdriver.Firefox(service=Service(GeckoDriverManager().install()), options=options)

# options / functions
driver.implicitly_wait(1)
wait = WebDriverWait(driver, 10) # wait 15 seconds

def accept_cookies():
    # accept cookies when prompted
    try: 
        cookie_prompt = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#onetrust-accept-btn-handler')))
        cookie_prompt.click()
    except TimeoutException:
        pass

def close_overlays(element=driver):
    # in some cases triggered overlays do not close
    # this function checks if one is open (=closing x exists) and attempts another close
    try:
        xs = element.find_elements(By.CSS_SELECTOR, 'div.ui_close_x')
        for x in xs:
            driver.execute_script('arguments[0].click();', x)
    except (NoSuchElementException, StaleElementReferenceException):
        pass

def expand_teaser_text():
    # expand automatically trimmed text (find and click first occurence of 'mehr anzeigen', applies to all elements on page)
    try:
        driver.execute_script('arguments[0].click();', driver.find_element(by=By.XPATH, value='.//p[contains(@class, "partial_entry")]/span[contains(@onclick,"clickExpand")]'))
    except NoSuchElementException:
        pass

def switch_to_next_page(page):  
    # try to switch to next page, break if no possible
    try:
        pagelink = driver.find_element(by=By.XPATH, value='.//div[contains(@class, "pageNumbers")]/a[contains(@data-page-number,"' + str(page+1) + '")]')
        driver.execute_script('arguments[0].click();', pagelink)
        sleep(2)
        return True
    except NoSuchElementException:
        return False

def search_for_city(query):
    # search for city, open first result of suggestions
    query = query + ' Deutschland'
    form = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'div.restaurants_home form')))
    form.find_element(By.NAME, 'q').send_keys(query)
    wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[value="' + query + '"]'))) # wait until full input processed
    driver.get(wait.until(lambda d: d.find_element(By.CSS_SELECTOR, 'div#typeahead_results > a').get_attribute('href'))) # wait until suggestions show

def get_restaurant_info_from_results_page(data_dict):
    res_list = wait.until(EC.visibility_of_element_located((By.XPATH, './/div[contains(@data-test-target,"restaurants-list")]')))
    res_list = res_list.find_elements(by=By.XPATH, value='.//div[contains(@data-test,"list_item")]')
    for res in res_list:
        # check if reviews exist here (otherwise do not bother to save)
        try:
            res.find_element(by=By.XPATH, value='.//a[contains(@href, "#REVIEWS")]')
            link = res.find_element(by=By.XPATH, value='(.//a[contains(@href,"Restaurant_Review")])[2]')
            data_dict['name'].append(re.sub(r'[0-9]+\.\s', '', link.text))
            data_dict['url'].append(link.get_attribute('href'))
            data_dict['timestamp'].append(datetime.now().strftime('%Y-%m-%d, %H:%M:%S'))
        except NoSuchElementException:
            print('Skipped')
            continue

def get_review_languages():
    try:
        languagepicker = driver.find_element(by=By.XPATH, value='.//div[span[contains(text(),"Weitere Sprachen")]]')
        driver.execute_script('arguments[0].click();', languagepicker)
        languages = driver.find_elements(By.CSS_SELECTOR, 'div.ui_overlay.prw_filters_detail_language div.item')
        inputtype = 'overlay'
        close_overlays()
        sleep(0.5)
    except NoSuchElementException:
        # if no language dropdown, use list of radio buttons
        languages = driver.find_elements(By.CSS_SELECTOR, 'div.filters div.choices div.prw_filters_detail_language div.item')
        inputtype = 'radio'
    finally:
        lang_count = len(languages)
        return(inputtype, lang_count) # passing the language picker leads to stale reference upon page change --> fetch in set_language

def set_review_language(inputtype, langno):
    close_overlays()      
    if (inputtype == 'overlay'):
        languagepicker = driver.find_element(by=By.XPATH, value='.//div[span[contains(text(),"Weitere Sprachen")]]')
        driver.execute_script('arguments[0].click();', languagepicker) # make overlay show again
        languages = driver.find_elements(By.CSS_SELECTOR, 'div.ui_overlay.prw_filters_detail_language div.item') # re-fetch from new overlay
    elif (inputtype == 'radio'):
        languages = driver.find_elements(By.CSS_SELECTOR, 'div.filters div.choices div.prw_filters_detail_language div.item')
    language = languages[langno].get_attribute('data-value') # language name
    # set if not already active
    if (languages[langno].find_element(By.CSS_SELECTOR, 'input').get_attribute('checked') == 'true'):
        close_overlays()
    else:
        driver.execute_script('arguments[0].click();', languages[langno].find_element(By.CSS_SELECTOR, 'input'))
    sleep(0.5)
    return(language)

def fetch_data_attribute(element, attr, fallback):
    # fetch attributes in try/except setting
    # pass element (container which is searched) and attribute fetching/processing rules
    try:
        # fetch passed attribute
        if (attr == 'name'):
            value = element.find_element(By.CSS_SELECTOR, '[data-test-target="top-info-header"]').text
        elif (attr == 'street_w_no'):
            value = element.find_element(by=By.XPATH, value='.//a[contains(@href,"#MAPVIEW")]').text.split(', ', 1)
            value = value[0]
        elif (attr == 'postcode'):
            value = element.find_element(by=By.XPATH, value='.//a[contains(@href,"#MAPVIEW")]').text.split(', ', 1)
            value = int(re.sub(r'[^\d]+', '', value[1])) # keep only postcode, delete city/country info
        elif (attr == 'city'):
            value = c # provided via list over which we loop
        elif (attr == 'cuisine1'):
            value = element.find_element(by=By.XPATH, value='.//div[contains(text(), "KÜCHEN")]/following-sibling::div').text.split(', ', 3)
            value = value[0]
        elif (attr == 'cuisine2'):
            value = element.find_element(by=By.XPATH, value='.//div[contains(text(), "KÜCHEN")]/following-sibling::div').text.split(', ', 3)
            value = value[1]
        elif (attr == 'cuisine3'):
            value = element.find_element(by=By.XPATH, value='.//div[contains(text(), "KÜCHEN")]/following-sibling::div').text.split(', ', 3)
            value = value[2]
        elif (attr == 'pricerange_lo'):
            value = element.find_element(by=By.XPATH, value='.//div[contains(text(), "PREISSPANNE")]/following-sibling::div').text.split(' - ', 1)
            value = int(re.sub(r'[^\d]+', '', value[0]))
        elif (attr == 'pricerange_hi'):
            value = element.find_element(by=By.XPATH, value='.//div[contains(text(), "PREISSPANNE")]/following-sibling::div').text.split(' - ', 1)
            value = int(re.sub(r'[^\d]+', '', value[1]))
        elif (attr == 'review_user_name'):
            if (fallback==0):
                value = element.find_element(By.CSS_SELECTOR, 'h3.username').text
            else:
                value = element.find_element(by=By.XPATH, value='.//div[contains(@class, "member_info")]/div[@class, "info_text")]/div').text
        elif (attr == 'review_user_city'):
            if (fallback==0):
                value = element.find_element(by=By.XPATH, value='(.//ul[contains(@class, "memberdescriptionReviewEnhancements")]/li)[2]').text.split(', ', 1)
                value = value[0].replace('Aus ','')
            else:
                value = np.nan
        elif (attr == 'review_user_country'):
            if (fallback==0):
                value = element.find_element(by=By.XPATH, value='(.//ul[contains(@class, "memberdescriptionReviewEnhancements")]/li)[2]').text.split(', ', 1)
                value = value[1]
            else:
                value = np.nan
        elif (attr == 'review_user_signup'):
            if (fallback==0):
                value = element.find_element(by=By.XPATH, value='.//li[contains(text(), "Tripadvisor-Mitglied seit")]').text
                value = int(re.sub(r'[^\d]+', '', value))
            else:
                value = np.nan
        elif (attr == 'review_user_reviews'):
            if (fallback==0):
                value = element.find_element(by=By.XPATH, value='.//li[contains(@class, "countsReviewEnhancementsItem")]/span[contains(text(), "Beitr")]').text
                value = int(re.sub(r'[^\d]+', '', value))
            else:
                value = element.find_element(by=By.XPATH, value='.//div[contains(@class, "member_info")]/span[contains(text(), "Bewertung")]').text
                value = int(re.sub(r'[^\d]+', '', value))
        elif (attr == 'review_user_thumbsup'):
            if (fallback==0):
                value = element.find_element(by=By.XPATH, value='.//li[contains(@class, "countsReviewEnhancementsItem")]/span[contains(text(), "Hilfreich")]').text
                value = int(re.sub(r'[^\d]+', '', value))
            else:
                value=np.nan
        elif (attr == 'review_user_cities_visited'):
            if (fallback==0):
                value = element.find_element(by=By.XPATH, value='.//li[contains(@class, "countsReviewEnhancementsItem")]/span[contains(text(), "besuchte")]').text
                value = int(re.sub(r'[^\d]+', '', value))
            else:
                value=np.nan
        elif (attr == 'review_user_id'):
            value = element.find_element(By.CSS_SELECTOR, 'div.memberOverlayLink.clickable').get_attribute('id').split('-', 1)
            value = value[0].split("_", 1)
            value = value[1]
        elif (attr == 'review_date'):
            value = element.find_element(By.CSS_SELECTOR, 'span.ratingDate').get_attribute('title') # use German format, clean afterwards
        elif (attr == 'review_score'):
            value = element.find_element(By.CSS_SELECTOR, 'span.ui_bubble_rating').get_attribute('class').replace('ui_bubble_rating bubble_','')
            value = int(int(value)/10)
        elif (attr == 'review_title'):
            value = element.find_element(By.CSS_SELECTOR, 'div.quote a span.noQuotes').text
        elif (attr == 'review_text'):
            value = element.find_element(By.CSS_SELECTOR, 'div.entry p.partial_entry').text
        elif (attr == 'review_id'):
            value = element.get_attribute('data-reviewid')
    except Exception:
        value = np.nan
    finally:
        return(value)  


### (1) RESTAURANT LIST ###
'''
 Fetch all restaurants per city, save:
 - names
 - urls (direct links)
 - timestamp
'''
cities = ['Itzehoe'] # provide via csv

for c, city in enumerate(cities):

    print('')
    print('Scraping Tripadvisor restaurant database')
    #print(city + ':' + x + 'Restaurants')

    # get restaurant page
    driver.get('https://www.tripadvisor.de/Restaurants')
    accept_cookies()

    # search for city
    search_for_city(city)
    
    # loop over pages of restaurants displayed (assume a maximum of 1000 pages, each with 30 results)
    data = {
        'name': [],
        'url': [],
        'timestamp': []
    }
    for page in range(1,1000):
        # fetch and save result info from page
        get_restaurant_info_from_results_page(data)
        # switch to next page until depleted
        if (switch_to_next_page(page) is False):
            break
    
    # create dataframe, drop duplicates, save CSV
    df = pd.DataFrame.from_dict(data)
    df = df.drop_duplicates()
    df.to_csv('file1.csv', index=False) # NAMING SCHEME?
    print('(' + c + ') ' + city + ': ' + len(df) + 'restaurants saved in scraping list.')


# def check_inclusion_criteria ():
# # REWRITE SO THAT THIS IS ALREADY CHECKED WHEN RESTAURANT LIST IS SCRAPED!
# # check if reviews exist (skip restaurant if not)
# try:
#     driver.find_element(By.CSS_SELECTOR, 'div#REVIEWS span.reviews_header_count')
#     res_count = res_count + 1 # counter for results from which we scrape info
#     rev_count = 0 # counter for reviews for each result
#     sys.stdout.write('\n')
#     print('(' + str(res_count) + ') ' + driver.find_element(By.CSS_SELECTOR, '[data-test-target="top-info-header"]').text)
# except NoSuchElementException:
#     # think of a way to exclude from saved restaurant list?
#     continue



# for res in res_list:
        
#     sleep(3)
    
#     ### go to restaurant page
#     res_link = 'https://www.tripadvisor.de/Restaurant_Review-g187323-d19821000-Reviews-Ama_Cafe-Berlin.html'
#     driver.get(res_link + '#REVIEWS')
#     accept_cookies()

#     # dict to be filled for each restaurant
#     data = {
#         'name': [],
#         'url': [],
#         'street_w_no': [],
#         'postcode': [],
#         'city': [],
#         'cuisine1': [],
#         'cuisine2': [],
#         'cuisine3': [],
#         'pricerange_lo': [],
#         'pricerange_hi': [],
#         'review_user_name': [],
#         'review_user_city': [],
#         'review_user_country': [],
#         'review_user_signup': [],
#         'review_user_reviews': [],
#         'review_user_thumbsup': [],
#         'review_user_cities_visited': [],
#         'review_user_overlay_failed': [],
#         'review_user_id': [],
#         'review_date': [],
#         'review_score': [],
#         'review_title': [],
#         'review_text': [],
#         'review_language': [],
#         'review_id': [],
#         'timestamp': [],
#     }

#     # get restaurant general info
#     attributes_restaurant = [
#         'name',
#         'url',
#         'street_w_no',
#         'postcode',
#         'city',
#         'cuisine1',
#         'cuisine2',
#         'cuisine3',
#         'pricerange_lo',
#         'pricerange_hi'
#     ]
#     for attr in attributes_restaurant:
#         if (attr != 'url'):
#             data[attr].append(fetch_data_attribute(element=driver, attr=attr, fallback=0))
#         else:
#             data[attr].append(res_link)

#     ### get reviews and review related info

#     # (1) review language selection
#     inputtype, lang_count = get_review_languages()
#     for l in range(1, lang_count):
        
#         language = set_review_language(inputtype=inputtype, langno=l) 
#         sleep(2)
        
#         # (2) extract review info (loop over pages)
#         unscrapedpages = True # as long as there are further pages, continue                
#         while unscrapedpages is True: 
#         expand_teaser_text()
#         # fetch all reviews on page
#         rev_list = driver.find_elements(By.CSS_SELECTOR, 'div.listContainer div.review-container')
#         for rev in rev_list:
#             # scroll into view
#             driver.execute_script('arguments[0].scrollIntoView();', rev)
#             # continue loop if review translated (then only fetch original)
#             translated = rev.find_element(By.CSS_SELECTOR, 'div.quote span.noQuotes')
#             if (str(translated.get_attribute('lang')) != ''):
#                 continue
#             else:
#                 # count
#                 rev_count = rev_count + 1
#                 # user / review info
#                 attributes_user_overlay = [
#                     'review_user_name',
#                     'review_user_city',
#                     'review_user_country', 
#                     'review_user_signup', 
#                     'review_user_reviews', 
#                     'review_user_thumbsup', 
#                     'review_user_cities_visited' 
#                 ]
#                 attributes_review = [
#                     'review_user_id',
#                     'review_date',
#                     'review_score', 
#                     'review_title', 
#                     'review_text',
#                     'review_id'
#                 ]
#                 # fetch
#                 try:
#                     # try to get user info overlay
#                     close_overlays()
#                     sleep(0.5) # allow DOM to adjust
#                     driver.execute_script('arguments[0].click();', rev.find_element(By.CSS_SELECTOR, 'div.memberOverlayLink.clickable'))
#                     wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'span.ui_popover div.memberOverlay h3.username'))) # wait until overlay content visible
#                     overlay = driver.find_element(By.CSS_SELECTOR, 'span.ui_popover div.memberOverlay')
#                     fallback = 0
#                     for attr in attributes_user_overlay:
#                         data[attr].append(fetch_data_attribute(element=overlay, attr=attr, fallback=fallback))
#                     close_overlays() 
#                 except TimeoutException:
#                     # if user overlay fails, get user info set already visible
#                     fallback = 1
#                     for attr in attributes_user_overlay:
#                         data[attr].append(fetch_data_attribute(element=rev, attr=attr, fallback=fallback))
#                 finally:
#                     data['review_user_overlay_failed'].append(fallback)
#                     # get review info
#                     for attr in attributes_review:
#                         data[attr].append(fetch_data_attribute(element=rev, attr=attr, fallback=0))
#                     data['review_language'].append(language)
#                     # append current timestamp
#                     data['timestamp'].append(datetime.now().strftime('%Y-%m-%d, %H:%M:%S'))
#                     # print status
#                     sys.stdout.write('\r └─ Review languages %i, total reviews %i' % (l, rev_count))
#                     sys.stdout.flush()
#         if (i>1):
#                 try:
#                     pagelink = driver.find_element(by=By.XPATH, value='.//div[contains(@class, "pageNumbers")]/a[contains(@data-page-number,"' + str(i) + '")]')
#                     driver.execute_script('arguments[0].click();', pagelink)
#                 except NoSuchElementException:
#                     break # no more pages
    
#     # save dataframe per restaurant
#     for attr in attributes_restaurant: 
#         data[attr] = data[attr]*rev_count # expand fixed restaurant info
#     df = pd.DataFrame.from_dict(data)
#     print(df[['review_user_name','review_user_signup','review_id', 'review_user_overlay_failed']])

#     # close driver and switch to city restaurant results window
#     driver.close()
#     driver.switch_to.window(original_window)

# # combine all restaurant datasets per city


# # city loop close
# print('Fetched info for ' + str(res_count) + ' Restaurants in ' + c + '.')
# driver.close()
