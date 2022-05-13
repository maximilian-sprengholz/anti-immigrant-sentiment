# -*- coding: utf-8 -*-

'''

This file scrapes Tripadvisor review information 
for restaurants in German municipalities.

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
from pandas.api.types import union_categoricals
import time
from datetime import datetime
import colorama
from colorama import Fore
from colorama import Style

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import StaleElementReferenceException
from selenium.common.exceptions import ElementNotInteractableException
from selenium.common.exceptions import WebDriverException
from selenium.common.exceptions import InvalidSessionIdException
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

# selenium options
options = webdriver.FirefoxOptions()
options.set_preference('intl.accept_languages', 'de-DE, de')
options.headless = True
#options.binary_location = wd + 'env/Library/bin/firefox.exe' # activate

# init colorama (enable colored terminal printing)
colorama.init()

##### FUNCTIONS #####

def run_shell_command(command=str, wd=wd):
    # allow for quoted strings
    substrings = command.split(' ',)
    command = []
    inquote = False
    for word in substrings:
        # determine begin of quoted string
        if (re.search('^"', word) != None) & (inquote==False):
            quoted_string = word
            inquote=True
        # in quoted string?
        elif (inquote==True):
            quoted_string = quoted_string + ' ' + word
        else:
            command.append(word)
        # determine end of quoted string
        if (re.search('"$', word) != None) & (inquote==True):
            command.append(quoted_string.replace('"',''))
            inquote=False
    # run and return error codes
    result = subprocess.run(command, shell=True, check=False, capture_output=True, cwd=wd)
    return result.returncode, result.stderr.decode("utf-8")

def track_status_in_readme(count=int, total=int):
    # pushes the current scraping status to the repo README
    # replaces '0/0 municipalities' scraped (municipalities unique to Tripadvisor)
    returncode = 0
    while (returncode==0):
        returncode, error = run_shell_command('git fetch -all')
        returncode, error = run_shell_command('git checkout origin/main --README.md')
        try:
            with open(wd + 'README.md', 'r') as file:
                filedata = file.read()
                status_string = str(count) + '/' + str(total) + ' municipalities'
                filedata = re.sub(r'[0-9]+/[0-9]+\smunicipalities', status_string, filedata)
        except IOError:
            return 'README could not be opened.'
        try:
            with open(wd + 'README.md', 'w') as file:
                file.write(filedata)
        except IOError:
            return 'README could not be written.'
        returncode, error = run_shell_command('git add README.md')
        returncode, error = run_shell_command('git commit -m "Automatic status update"')
        returncode, error = run_shell_command('git push origin main')
        break
    if (returncode != 0): 
        return 'Scraping status could not be tracked. ' + error
    else:
        return 'Scraping status successfully tracked.'

def concat_dfs_with_cat_data(dfs):
    '''
    Concatenate dataframe but keep categorical dtypes.
    Credit: https://stackoverflow.com/a/57809778
    '''
    # Iterate on categorical columns common to all dfs
    for col in set.intersection(
            *[
                set(df.select_dtypes(include='category').columns)
                for df in dfs
            ]
            ):
        # Generate the union category across dfs for this column
        # exclude columns with only NaN, the float64 dtype differs from object
        cols = [df[col] for df in dfs if df[col].isnull().all()==False]
        if len(cols)>0:
            uc = union_categoricals(cols)
            # Change to union category for all dataframes
            for df in dfs:
                df[col] = pd.Categorical(df[col].values, categories=uc.categories)
    return pd.concat(dfs, ignore_index=True)

def accept_cookies():
    # accept cookies when prompted
    try:
        cookie_prompt = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '#onetrust-accept-btn-handler'))
            )
        driver.execute_script('arguments[0].click();', cookie_prompt)
    except TimeoutException:
        pass

def close_overlays(element):
    # in some cases triggered overlays do not close
    # this function checks if a closing x exists and attempts another close
    try:
        xs = element.find_elements(By.CSS_SELECTOR, 'div.ui_close_x')
        for x in xs:
            driver.execute_script('arguments[0].click();', x)
    except (NoSuchElementException, StaleElementReferenceException):
        pass

def expand_teaser_text():
    # expand automatically trimmed text: 
    # find and click first occurence of 'mehr anzeigen',
    # applies to all elements on page
    try:
        driver.execute_script(
            'arguments[0].click();', 
            driver.find_element(
                By.XPATH, 
                './/p[contains(@class, "partial_entry")]/span[contains(@onclick,"clickExpand")]'
                )
            )
    except NoSuchElementException:
        pass

def switch_to_next_page(page=int):  
    # try to switch to next page, break if no possible
    try:
        pagelink = driver.find_element(
            By.XPATH, 
            './/div[contains(@class, "pageNumbers")]/a[contains(@data-page-number,"' 
            + str(page+1) + '")]'
            )
        driver.execute_script('arguments[0].click();', pagelink)
        time.sleep(1)
        return True
    except NoSuchElementException:
        return False

def search_for_municipality(query=str):
    # search for municipality, open first result of suggestions
    query = query + ' Deutschland'
    form = wait.until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, 'div.restaurants_home form'))
        )
    form.find_element(By.NAME, 'q').send_keys(query)
    wait.until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[value="' + query + '"]'))
        ) 
    driver.get(
        wait.until(
            lambda d: d.find_element(
                By.CSS_SELECTOR, 'div#typeahead_results > a'
                ).get_attribute('href')
            )
        )

def check_postcode_match(postcodes):
    # check if postcode belongs to municipality
    first_result = wait.until(
        EC.visibility_of_element_located((By.XPATH, './/div[contains(@data-test,"1_list_item")]'))
        )
    link = first_result.find_element(
        By.XPATH, '(.//a[contains(@href,"Restaurant_Review")])[2]'
        ).get_attribute('href')
    # open in new tab, check, switch back
    original_window = driver.current_window_handle
    driver.switch_to.new_window('tab')
    driver.get(link)
    postcode = driver.find_element(
                By.XPATH, './/a[contains(@href,"#MAPVIEW")]'
                ).text.split(', ', 1)
    postcode = re.sub(r'[^\d]+', '', postcode[1])
    if (postcode in postcodes):
        postcode_match = True
    else:
        postcode_match = False
    driver.close()
    driver.switch_to.window(original_window)
    return(postcode_match)

def get_restaurant_info_from_results_page(data_dict, municipality, ags, postcodes, scraped):
    wait.until(
        EC.visibility_of_element_located((By.XPATH, './/div[contains(@data-test,"1_list_item")]'))
        )
    res_list = driver.find_elements(
        By.XPATH, 
        '//div[contains(@data-test-target, "restaurants-list")]'
        + '/div[contains(@data-test, "list_item")]')
    res_skipped = 0 # counter for restaurants with no reviews, breaks loop if 3 in a row
    for res in res_list:
        # check if reviews exist (otherwise do not bother to save)
        continue_scrape = True
        try:
            res.find_element(By.XPATH, './/a[contains(@href, "#REVIEWS")]')
            link = res.find_element(
                By.XPATH, '(.//a[contains(@href,"Restaurant_Review")])[2]'
                )
            data_dict['name'].append(re.sub(r'[0-9]+\.\s', '', link.text))
            data_dict['url'].append(link.get_attribute('href'))
            data_dict['timestamp'].append(datetime.now().strftime('%Y-%m-%d, %H:%M:%S'))
            data_dict['municipality'].append(municipality)
            data_dict['ags'].append(ags)
            id_string = link.get_attribute('href').split('-', 3)
            data_dict['id'].append(id_string[1] + id_string[2])
            data_dict['scraped'].append(scraped)
        except NoSuchElementException:
            res_skipped = res_skipped + 1
            if (res_skipped > 2):
                continue_scrape = False 
                break
    return continue_scrape

def file_suffix_from_municipality_name(municipality_string):
    # replaces German umlaute, strips spaces and /, returns lowercase string
    umlaute_dict = {
        'ä': 'ae', 
        'ö': 'oe',
        'ü': 'ue', 
        'Ä': 'Ae',
        'Ö': 'Oe', 
        'Ü': 'Ue',
        'ß': 'ss',
        }
    for k in umlaute_dict.keys():
        municipality_string = municipality_string.replace(k, umlaute_dict[k]).lower()
    municipality_suffix = municipality_string.replace(' ', '').replace('.', '').replace('/', '')
    return municipality_suffix

def get_review_languages():
    try:
        # fetch review languages from language picker overlay
        languagepicker = driver.find_element(
            By.XPATH, './/div[span[contains(text(),"Weitere Sprachen")]]'
            )
        driver.execute_script('arguments[0].click();', languagepicker)
        languages = driver.find_elements(
            By.CSS_SELECTOR, 'div.ui_overlay.prw_filters_detail_language div.item'
            )
        inputtype = 'overlay'
        close_overlays(driver)
        time.sleep(0.5)
    except NoSuchElementException:
        # if no language dropdown, use list of radio buttons
        languages = driver.find_elements(
            By.CSS_SELECTOR, 'div#REVIEWS div.prw_filters_detail_language div.choices div.item'
            )
        inputtype = 'radio'
    finally:
        lang_count = len(languages)
        return(inputtype, lang_count)

def set_review_language(inputtype, langno):
    close_overlays(driver)      
    if (inputtype == 'overlay'):
        # trigger overlay and re-fetch language options
        languagepicker = driver.find_element(
            By.XPATH, './/div[span[contains(text(),"Weitere Sprachen")]]'
            )
        driver.execute_script('arguments[0].click();', languagepicker)
        languages = driver.find_elements(
            By.CSS_SELECTOR, 'div.ui_overlay.prw_filters_detail_language div.item'
            )
    elif (inputtype == 'radio'):
        languages = driver.find_elements(
            By.CSS_SELECTOR, 'div#REVIEWS div.prw_filters_detail_language div.choices div.item'
            )
    language = languages[langno].get_attribute('data-value') # language name
    # set if not already active
    if (languages[langno].find_element(
            By.CSS_SELECTOR, 'input'
            ).get_attribute('checked') == 'true'):
        close_overlays(driver)
    else:
        driver.execute_script(
            'arguments[0].click();', languages[langno].find_element(By.CSS_SELECTOR, 'input')
            )
    time.sleep(1)
    return(language)

def fetch_data_attribute(element, attr, fallback):
    # fetch attributes in try/except setting
    # pass element (container which is searched) and attribute fetching/processing rules
    try:
        # fetch passed attribute
        if (attr == 'name'):
            value = element.find_element(
                By.CSS_SELECTOR, '[data-test-target="top-info-header"]'
                ).text
        elif (attr == 'street_w_no'):
            value = element.find_element(
                By.XPATH, './/a[contains(@href,"#MAPVIEW")]'
                ).text.split(', ', 1)
            value = value[0]
        elif (attr == 'postcode'):
            value = element.find_element(
                By.XPATH, './/a[contains(@href,"#MAPVIEW")]'
                ).text.split(', ', 1)
            value = re.sub(r'[^\d]+', '', value[1])
        elif (attr == 'cuisine1'):
            value = element.find_element(
                By.XPATH, './/div[contains(text(), "KÜCHEN")]/following-sibling::div'
                ).text.split(', ', 3)
            value = value[0]
        elif (attr == 'cuisine2'):
            value = element.find_element(
                By.XPATH, './/div[contains(text(), "KÜCHEN")]/following-sibling::div'
                ).text.split(', ', 3)
            value = value[1]
        elif (attr == 'cuisine3'):
            value = element.find_element(
                By.XPATH, './/div[contains(text(), "KÜCHEN")]/following-sibling::div'
                ).text.split(', ', 3)
            value = value[2]
        elif (attr == 'pricerange_lo'):
            value = element.find_element(
                By.XPATH, 
                './/div[contains(text(), "PREISSPANNE")]/following-sibling::div'
                ).text.split(' - ', 1)
            value = int(re.sub(r'[^\d]+', '', value[0]))
        elif (attr == 'pricerange_hi'):
            value = element.find_element(
                By.XPATH, 
                './/div[contains(text(), "PREISSPANNE")]/following-sibling::div'
                ).text.split(' - ', 1)
            value = int(re.sub(r'[^\d]+', '', value[1]))
        elif (attr == 'review_user_name'):
            if (fallback==0):
                value = element.find_element(By.CSS_SELECTOR, 'h3.username').text
            else:
                value = element.find_element(
                    By.XPATH, 
                    './/div[contains(@class, "member_info")]/div[@class, "info_text")]/div'
                    ).text
        elif (attr == 'review_user_gender'):
            if (fallback==0):
                value = element.find_element(
                    By.XPATH, 
                    '(.//ul[contains(@class, "memberdescriptionReviewEnhancements")]/li)[2]'
                    ).text
                if ('Mann' in value):
                    value = 'Mann'
                elif ('Frau' in value):
                    value = 'Frau'
                else:
                    value = np.nan
                value = value[0]
            else:
                value = np.nan
        elif (attr == 'review_user_age'):
            if (fallback==0):
                value = element.find_element(
                    By.XPATH, 
                    '(.//ul[contains(@class, "memberdescriptionReviewEnhancements")]/li)[2]'
                    ).text.re.findall(r'[0-9]+-[0-9]+')
                value = value[0]
                if (len(value)==0):
                    value = np.nan
            else:
                value = np.nan
        elif (attr == 'review_user_municipality'):
            if (fallback==0):
                value = element.find_element(
                    By.XPATH, 
                    '(.//ul[contains(@class, "memberdescriptionReviewEnhancements")]/li)[2]'
                    ).text.split(', ', 1)
                if ('aus' in value[0]):
                    value = value[0].split(' aus ', 1)
                    value = value[1]
                elif ('Aus' in value[0]):
                    value = value[0].text.split('').replace('Aus ','')
                else:
                    value = np.nan
            else:
                value = np.nan
        elif (attr == 'review_user_country'):
            if (fallback==0):
                value = element.find_element(
                    By.XPATH, 
                    '(.//ul[contains(@class, "memberdescriptionReviewEnhancements")]/li)[2]'
                    ).text.split(', ', 1)
                value = value[1]
            else:
                value = np.nan
        elif (attr == 'review_user_signup'):
            if (fallback==0):
                value = element.find_element(
                    By.XPATH, './/li[contains(text(), "Tripadvisor-Mitglied seit")]'
                    ).text
                value = int(re.sub(r'[^\d]+', '', value))
            else:
                value = np.nan
        elif (attr == 'review_user_reviews'):
            if (fallback==0):
                value = element.find_element(
                    By.XPATH, 
                    './/li[contains(@class, "countsReviewEnhancementsItem")]/span[contains(text(), "Beitr")]'
                    ).text
                value = int(re.sub(r'[^\d]+', '', value))
            else:
                value = element.find_element(
                    By.XPATH, 
                    './/div[contains(@class, "member_info")]/span[contains(text(), "Bewertung")]'
                    ).text
                value = int(re.sub(r'[^\d]+', '', value))
        elif (attr == 'review_user_thumbsup'):
            if (fallback==0):
                value = element.find_element(
                    By.XPATH, 
                    './/li[contains(@class, "countsReviewEnhancementsItem")]/span[contains(text(), "Hilfreich")]'
                    ).text
                value = int(re.sub(r'[^\d]+', '', value))
            else:
                value=np.nan
        elif (attr == 'review_user_municipalities_visited'):
            if (fallback==0):
                value = element.find_element(
                    By.XPATH, 
                    './/li[contains(@class, "countsReviewEnhancementsItem")]/span[contains(text(), "besuchte")]'
                    ).text
                value = int(re.sub(r'[^\d]+', '', value))
            else:
                value = np.nan
        elif (attr == 'review_user_overlay_failed'):
                value = fallback
        elif (attr == 'review_user_id'):
            value = element.find_element(
                By.CSS_SELECTOR, 'div.memberOverlayLink.clickable'
                ).get_attribute('id').split('-', 1)
            value = value[0].split("_", 1)
            value = value[1]
        elif (attr == 'review_date'):
            value = element.find_element(By.CSS_SELECTOR, 'span.ratingDate').get_attribute('title')
        elif (attr == 'review_score'):
            value = element.find_element(
                By.CSS_SELECTOR, 'span.ui_bubble_rating'
                ).get_attribute('class').replace('ui_bubble_rating bubble_','')
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

def init_scraper(driver, wait):
    '''
    Checks for the current scraping status and initializes the scraper for the information we miss.
    Keep tabs in the municipality query log (tripadvisor_query_municipalities.csv) and the 
    restaurant query log for each municipality (tripadvisor_query_restaurants_MUNICIPALITY.csv).

    (1) Check if municipality list has changed in user input.
    (2) Check if restaurant scraping targets have been collected for each municipality.
    (3) Check if restaurant info and reviews have been scraped for each municipality/restaurant.
    '''
    print('')
    print('Checking Tripadvisor scraping status:')
    print('-------------------------------------')

    # initiate municipality query log
    try:
        df_query_municipalities = pd.read_csv(
            wd + 'data/raw/tripadvisor_query_municipalities.csv',
            sep=";",
            dtype={'ags': object}
            )
    except FileNotFoundError:
        df_query_municipalities = pd.DataFrame(
            columns=['ags', 'municipality', 'state', 'postcodes', 'querystring', 
                     'scraping_targets', 'scraped']
            )
    
    # (1) update municipality list from user input
    # We ensure uniqueness via the ags code (Amtlicher Gemeindeschlüssel)
    df_input_municipalities = pd.read_csv(
        wd + 'data/raw/tripadvisor_input_municipalities.csv',
        sep=";",
        converters={'postcodes': literal_eval},
        dtype={'ags': object}
        )
    municipalities_added = 0
    querystrings_changed_user = 0
    querystrings_changed_postcode_flag = 0
    for municipality, ags, postcodes, state, querystring in zip(
            df_input_municipalities['municipality'],
            df_input_municipalities['ags'],
            df_input_municipalities['postcodes'],
            df_input_municipalities['state'],
            df_input_municipalities['querystring']
            ):
        # add new municipalities
        if (ags not in df_query_municipalities['ags'].values):
            municipalities_added = municipalities_added + 1
            if (pd.isnull(querystring)):
                querystring = municipality + ' ' + state # default query string
            df_query_municipalities_row = pd.DataFrame(
                [[ags, municipality, state, postcodes, querystring, np.nan, np.nan]], 
                columns=['ags', 'municipality', 'state', 'postcodes', 'querystring', 
                           'scraping_targets', 'scraped']
                )
            df_query_municipalities = pd.concat(
                [df_query_municipalities, df_query_municipalities_row], 
                ignore_index=True
                )
        # change default querystring value to user provided string (querystring is unique)
        # querystring is np.nan if postcode check returned false in get_scraping_targets()
        if ((querystring not in df_query_municipalities['querystring'].values)
                & (~pd.isnull(querystring))):
            querystrings_changed_user = querystrings_changed_user + 1
            df_query_municipalities['querystring'].mask(
                    df_query_municipalities['ags'] == ags, 
                    querystring, 
                    inplace=True
                    )
        elif (pd.isnull(querystring)):
            querystrings_changed_postcode_flag = querystrings_changed_postcode_flag + 1
            df_query_municipalities['querystring'].mask(
                df_query_municipalities['ags'] == ags, 
                querystring, 
                inplace=True
                )
    # replace query log file and print status
    df_query_municipalities.to_csv(
        wd + 'data/raw/tripadvisor_query_municipalities.csv', sep=";", index=False
        )
    if ((municipalities_added > 0) 
            | (querystrings_changed_user > 0) 
            | (querystrings_changed_postcode_flag > 0)):
        print(str(municipalities_added) + ' municipalities added to municipality query list.')
        print(str(querystrings_changed_user) + ' query strings changed to user provided values.')
        print(str(querystrings_changed_postcode_flag) 
              + ' query strings set to missing after postcode consistency check.')
    else:
        print('Municipality query list up to date.')

    # (2) Get list of municipalities for which we have a querystring but no scraping targets yet
    municipalities_to_be_scraped = df_query_municipalities[
        (df_query_municipalities['scraping_targets'].isin([np.nan]))
        & (~df_query_municipalities['querystring'].isin([np.nan]))
        ][['municipality', 'ags', 'postcodes', 'querystring']]
    if (len(municipalities_to_be_scraped) > 0):
        print('Scraping target list missing for ' + str(len(municipalities_to_be_scraped)) 
              + ' municipalities.')
        get_scraping_targets(
            df_input_municipalities, 
            df_query_municipalities, 
            municipalities_to_be_scraped
            )
    else:
        print('Scraping target list available for each municipality.')
 
    # (3) Get list of municipalities with no/incomplete scraping of restaurant info/reviews
    municipalities_to_be_scraped = df_query_municipalities[
        (~df_query_municipalities['scraping_targets'].isin([np.nan]))
        & df_query_municipalities['scraped'].isin([np.nan])
        ][['municipality', 'ags', 'scraping_targets']]
    if (len(municipalities_to_be_scraped) > 0):
        print('Restaurant info/reviews missing for ' + str(len(municipalities_to_be_scraped)) 
              + ' municipalities.')
        scrape_target_info(
            df_query_municipalities, 
            municipalities_to_be_scraped
            )
    else:
        print('Total running time: ' + str(time_start - time.perf_counter()))
        sys.exit(
            Fore.GREEN 
            + 'Information has been scraped for all municipalities and restaurants. Exiting...'
        )

def get_scraping_targets(
        df_input_municipalities, df_query_municipalities, municipalities_to_be_scraped
        ):
    '''
    Fetch all restaurants per municipality, save:
    - municipality
    - ags
    - restaurant names
    - restaurant urls (direct links)
    - restaurant id
    - timestamp
    - scraped: intitally empty, holds the link of the final dataset per municipality
    '''
    print('')
    print('Scraping target lists:')
    print('----------------------')
    
    # data structure
    data = {
        'municipality': [],
        'ags': [],
        'name': [],
        'url': [],
        'id': [],
        'timestamp': [],
        'scraped': []
    }

    ### loop over municipalities
    for municipality, ags, postcodes, querystring in zip(
            municipalities_to_be_scraped['municipality'],
            municipalities_to_be_scraped['ags'],
            municipalities_to_be_scraped['postcodes'],
            municipalities_to_be_scraped['querystring']
            ):

        # get restaurant page and search for municipality
        driver.get('https://www.tripadvisor.de/Restaurants')
        accept_cookies()
        search_for_municipality(querystring)

        # opt-out geo search radius broadening
        try:
            driver.find_element(By.CSS_SELECTOR, 'div#geobroaden_opt_out').click()
            time.sleep(3)
        except (NoSuchElementException, ElementNotInteractableException):
            pass

        # check if postcode of first search result corresponds to the searched-for municipality
        # if not: set to missing in log (requires manual determination of search strings)
        if (check_postcode_match(postcodes) == False):
            df_input_municipalities['querystring'].mask(
                df_query_municipalities['ags'] == ags, 
                np.nan, 
                inplace=True
                )
            print(Fore.YELLOW + ags + ' ' + municipality 
                  + ': Skipped. Query did not return results with matching postcodes. '
                  + 'Please provide correct querystrings manually.' + Style.RESET_ALL)
            continue
        
        # start clean
        for value in data.values():
            del value[:]

        # loop over pages of restaurant search results (assume max. 1000 pages with 30 results)
        for page in range(1,1000):
            # fetch and save result info from page
            results = get_restaurant_info_from_results_page(
                data_dict=data, municipality=municipality, ags=ags, postcodes=postcodes, 
                scraped=np.nan
                )
            if (results == True):
                # switch to next page until depleted
                if (switch_to_next_page(page) is False): break
            else:
                break
        
        # create dataframe
        # drop potential duplicates due to sponsored results
        # check for missings (no missings permissible except for 'scraped' column)
        # save CSV
        df = pd.DataFrame.from_dict(data)
        df.drop_duplicates(subset=['url'], inplace=True)
        missings = df.isnull().sum().sum() # should 
        if ((len(df)!=0) & (missings <= len(df))):
            relpath = (
                'data/raw/tripadvisor_query_restaurants_' 
                + file_suffix_from_municipality_name(municipality) + '_' + ags + '.csv'
                )
            df.to_csv(wd + relpath, sep = ";", index=False)
            print(Fore.GREEN + ags + ' ' + municipality + ': ' + str(len(df)) 
                + ' restaurants saved in scraping target list.' + Style.RESET_ALL)
            # add path to status file
            df_query_municipalities['scraping_targets'].mask(
                df_query_municipalities['ags'] == ags, 
                relpath, 
                inplace=True,
                )
            df_query_municipalities.to_csv(
                wd + 'data/raw/tripadvisor_query_municipalities.csv', sep=";", index=False
                )
        else:
            print(Fore.YELLOW + ' ' + municipality + ': No scraping list saved due to ' 
                + str(missings) + ' missings / ' + str(len(df)) + ' rows in dataframe.'
                + Style.RESET_ALL)
            break

    # re-init scraper after completion (will continue with target info when all targets scraped)
    init_scraper(driver, wait)

def scrape_target_info(df_query_municipalities, municipalities_to_be_scraped):
    '''
    municipality-by-municipality:
    - Scrape restaurant info and reviews for each target (keep track)
    - Save dataset for each target
    - Merge datasets for all targets and save municipality dataset (keep track)
    '''
    print('')
    print('Scraping restaurant info/reviews:')
    print('---------------------------------')

    # data structure
    data = {
        'id': [],
        'name': [],
        'url': [],
        'street_w_no': [],
        'postcode': [],
        'municipality': [],
        'ags': [],
        'cuisine1': [],
        'cuisine2': [],
        'cuisine3': [],
        'pricerange_lo': [],
        'pricerange_hi': [],
        'review_user_name': [],
        'review_user_gender': [],
        'review_user_age': [],
        'review_user_municipality': [],
        'review_user_country': [],
        'review_user_signup': [],
        'review_user_reviews': [],
        'review_user_thumbsup': [],
        'review_user_municipalities_visited': [],
        'review_user_overlay_failed': [],
        'review_user_id': [],
        'review_date': [],
        'review_score': [],
        'review_title': [],
        'review_text': [],
        'review_language': [],
        'review_id': [],
        'timestamp': [],
        }
    attributes_restaurant = [
        'id', 'name', 'url', 'street_w_no', 'postcode', 'municipality', 'ags', 'cuisine1', 
        'cuisine2', 'cuisine3', 'pricerange_lo', 'pricerange_hi'
        ]
    attributes_user_overlay = [
        'review_user_name', 'review_user_gender', 'review_user_age', 'review_user_municipality', 
        'review_user_country', 'review_user_signup', 'review_user_reviews', 'review_user_thumbsup', 
        'review_user_municipalities_visited', 'review_user_overlay_failed' 
        ]
    attributes_review = [
        'review_user_id', 'review_date', 'review_score', 'review_title', 'review_text', 
        'review_language', 'review_id', 'timestamp'
        ]

    ### loop over municipalities
    for c, (municipality, ags, relpath_query_restaurants) in enumerate(zip(
                municipalities_to_be_scraped['municipality'], 
                municipalities_to_be_scraped['ags'],
                municipalities_to_be_scraped['scraping_targets']
                ),
            start=1):

        print(ags + ' ' + municipality)

        # get restaurant links from target list file per municipality (check if already scraped)
        df_query_restaurants = pd.read_csv(wd + relpath_query_restaurants, sep=";")
        targets = df_query_restaurants[
            df_query_restaurants['scraped'].isin([np.nan])
            ]

        ### loop over restaurants
        for target_id, target_name, target_link in zip(
                targets['id'], targets['name'], targets['url']
                ):
        
            time.sleep(3) # pause should avoid being blocked
            driver.get(target_link + '#REVIEWS')
            accept_cookies()
            
            # start clean
            for value in data.values():
                del value[:]

            # get restaurant data
            for attr in attributes_restaurant:
                if (attr == 'municipality'):
                    data[attr].append(municipality)
                elif (attr == 'ags'):
                    data[attr].append(ags)
                elif (attr == 'id'):
                    data[attr].append(target_id)
                elif (attr == 'name'):
                    data[attr].append(target_name)
                elif (attr == 'url'):
                    data[attr].append(target_link)
                else:
                    data[attr].append(fetch_data_attribute(element=driver, attr=attr, fallback=0))

            ### get reviews and review related info
            rev_count = 0
            # review language selection
            inputtype, lang_count = get_review_languages()
            for l in range(1, lang_count):
                language = set_review_language(inputtype=inputtype, langno=l)
                selected_review_language_end = False # make sure only untranslated reviews count 
                # extract review info per language (loop over pages)
                for page in range(1,1000):
                    expand_teaser_text()
                    # fetch all reviews on page
                    rev_list = driver.find_elements(
                        By.CSS_SELECTOR, 'div.listContainer div.review-container'
                        )
                    for rev in rev_list:
                        # scroll into view
                        driver.execute_script('arguments[0].scrollIntoView();', rev)
                        # break loop when translated reviews start (only fetch original language)
                        # only applies for german (quirk on Tripadvisor page)
                        if (language == 'de'):
                            try:
                                rev.find_element(By.CSS_SELECTOR, 'div.prw_reviews_mt_header_hsx')
                                selected_review_language_end = True
                                break
                            except NoSuchElementException:
                                pass
                        # count
                        rev_count = rev_count + 1
                        # fetch
                        try:
                            # try to get user info overlay
                            close_overlays(driver)
                            # time.sleep(0.5) # allow DOM to adjust
                            driver.execute_script(
                                'arguments[0].click();', 
                                rev.find_element(By.CSS_SELECTOR, 'div.memberOverlayLink.clickable')
                                )
                            wait.until(EC.visibility_of_element_located(
                                (By.CSS_SELECTOR, 'span.ui_popover div.memberOverlay h3.username')
                                )) # wait until overlay content visible
                            overlay = driver.find_element(
                                By.CSS_SELECTOR, 'span.ui_popover div.memberOverlay'
                                )
                            for attr in attributes_user_overlay:
                                data[attr].append(fetch_data_attribute(
                                    element=overlay, attr=attr, fallback=0
                                    ))
                            close_overlays(driver) 
                        except (NoSuchElementException, TimeoutException):
                            # if user overlay fails, get user info set already visible
                            # can fail due to missing user info (e.g. deleted acc) or timeout
                            for attr in attributes_user_overlay:
                                data[attr].append(fetch_data_attribute(
                                    element=rev, attr=attr, fallback=1
                                    ))
                        finally:
                            # get review info
                            for attr in attributes_review:
                                if (attr == 'review_language'):
                                    data[attr].append(language)
                                elif (attr == 'timestamp'):
                                    data[attr].append(datetime.now().strftime('%Y-%m-%d, %H:%M:%S'))
                                else:
                                    data[attr].append(fetch_data_attribute(
                                        element=rev, attr=attr, fallback=0
                                        ))
                            # print status
                            sys.stdout.write(
                                '\r ├─ %s: Review languages %i, total reviews scraped %i' 
                                % (target_name, l, rev_count)
                                )
                            sys.stdout.flush()
                    # switch to next language when scraper arrives at translated review block
                    if (selected_review_language_end is True): break
                    # switch to next page until depleted
                    if (switch_to_next_page(page) is False): break
                # language loop close
            # create dataframe per restaurant
            for attr in attributes_restaurant: 
                data[attr] = data[attr]*rev_count # expand fixed restaurant info
            df = pd.DataFrame.from_dict(data)
            
            ### save dataframe per restaurant after some basic checks, keep log
            # Drop duplicates: last resort technique to prevent that translated reviews
            # appear twice (usually the check in the review loop works, but not always). 
            df.drop_duplicates(subset=['review_id'], keep='last', inplace=True)
            missings = df.isnull().sum().sum()
            rev_count_site = int(re.sub(r'[^\d]+', '', 
                driver.find_element(By.CSS_SELECTOR, 'span.reviews_header_count').text
                ))
            if (len(df)==0):
                print('\n │  └─ ' + Fore.YELLOW + 'Dataframe not saved: Length is 0' 
                      + Style.RESET_ALL)
                continue                
            elif (len(df) < rev_count_site):
                # A scraped review count lower than the review count on page usually happens
                # when reviews do not load properly. There might also be a slight chance that 
                # new reviews get added while we scrape, but this is uncheckable in the process. 
                # A new scraping iteration should fix both.
                # A higher review count does not matter as long as there are no duplicates (which
                # is fixed above). Also: The Tripadvisor count is sometimes 1 too large. 
                print('\n │  └─ ' + Fore.YELLOW 
                        + 'Dataframe not saved: Length (after dropping potential duplicates) is' 
                        + 'smaller than page review count ('+ str(len(df)) + ' vs. ' 
                        + str(rev_count_site) + ')' + Style.RESET_ALL
                    )
                continue
            elif (missings > (0.5*len(df)*len(df.columns))):
                print('\n │  └─ ' + Fore.YELLOW + 'Dataframe not saved: >50 % ('
                      + str(missings) + '/' + str(len(df)*len(df.columns)) + ') missing.'
                      + Style.RESET_ALL
                    )
                continue
            else:
                # Use categorical dtypes wherever possible
                columns_categorical = [
                    'id', 'name', 'url', 'street_w_no', 'postcode', 'municipality', 'ags', 
                    'cuisine1', 'cuisine2', 'cuisine3', 'review_user_name', 'review_user_gender', 
                    'review_user_age', 'review_user_municipality', 'review_user_country', 
                    'review_user_id', 'review_language'
                ]
                for col in columns_categorical:
                    df[col] = df[col].astype('category')
                # save under temp (will be deleted after dataset is complete for municipality)
                # data can be feather instead of CSV
                relpath_results_restaurants = (
                    'data/temp/tripadvisor_results_restaurant_' 
                    + file_suffix_from_municipality_name(municipality)
                    + '_' + ags + '_'+ target_id + '.feather'
                    )
                df.reset_index().to_feather(wd + relpath_results_restaurants)
                print('\n │  └─ ' + Fore.GREEN + 'Dataframe saved: ' 
                        + relpath_results_restaurants + Style.RESET_ALL)
                # add path to restaurant query file
                df_query_restaurants['scraped'].mask(
                    df_query_restaurants['id'] == target_id, 
                    relpath_results_restaurants, 
                    inplace=True
                    )
                df_query_restaurants.to_csv(wd + relpath_query_restaurants, sep=";", index=False)

        ### combine restaurant datasets per municipality and save ONLY when everything is complete
        if (df_query_restaurants['scraped'].isnull().sum()==0):

            # append
            for r, relpath_results_restaurants in enumerate(df_query_restaurants['scraped']):
                df_restaurant = pd.read_feather(wd + relpath_results_restaurants)
                if (r==0):
                    df_results_municipality = df_restaurant
                else:
                    df_results_municipality = concat_dfs_with_cat_data(
                        [df_results_municipality, df_restaurant]
                        )
            
            # save feather and delete delete restaurant result spreadsheets when successful
            try:
                relpath_results_municipality = (
                    'data/raw/tripdavisor_results_' 
                    + file_suffix_from_municipality_name(municipality)
                    + '_' + ags + '.feather'
                    )
                df_results_municipality.reset_index().to_feather(
                    wd + relpath_results_municipality
                    )
                save_success = True
                print(' ├─ ' + Fore.GREEN + 'Merged dataset saved: ' 
                      + relpath_results_municipality + Style.RESET_ALL)
                print(' └─ ' + Fore.GREEN + track_status_in_readme(c, len(df_query_municipalities))
                      + Style.RESET_ALL)
            except Exception:
                save_success = False
                print(' └─ ' + Fore.RED + 'Merged dataset for ' + municipality 
                      + ' could not be saved.' + Style.RESET_ALL)
            if (save_success == True):
                # delete temp files (if any)
                for relpath_results_restaurants in df_query_restaurants['scraped']:
                    try:
                        os.remove(wd + relpath_results_restaurants)
                    except FileNotFoundError:
                        pass
                # replace status in log files with link to feather file
                df_query_municipalities['scraped'].mask(
                    df_query_municipalities['ags'] == ags, 
                    relpath_results_municipality, 
                    inplace=True
                    )
                df_query_municipalities.to_csv(
                    wd + 'data/raw/tripadvisor_query_municipalities.csv', sep=";", index=False
                    )
        else:
            print(' └─ ' + Fore.YELLOW 
                  + 'Scraping results incomplete. Re-try next iteration, continuing...'
                  + Style.RESET_ALL)
            continue
    
    # re-init scraper after completion (will exit when everything is scraped)
    init_scraper(driver, wait)


##### RUN #####
driver = webdriver.Firefox(
    service=Service(GeckoDriverManager().install()), 
    options=options
)
driver.implicitly_wait(1)
wait = WebDriverWait(driver, 10) 
time_start = time.perf_counter()
# start scraper with some top-level exception handling
restarts_after_error = 0
try:
    init_scraper(driver, wait)
except (InvalidSessionIdException) as e:
    # restart driver if connection to driver is lost (e.g. due to crash)
    print('')
    print(Fore.YELLOW + 'InvalidSessionIdException: ' + str(e))
    if (restarts_after_error<3):
        restarts_after_error+=1
        print(Fore.YELLOW + 'Restarting scraper...' + Style.RESET_ALL)
        print('')
        driver = webdriver.Firefox(
            service=Service(GeckoDriverManager().install()), 
            options=options
        )
    else:
        sys.exit(Fore.RED + 'Scraper stopped after 3 errors.' + Style.RESET_ALL)
        print('Total running time: ' + str(time_start - time.perf_counter()))
except (TimeoutException, StaleElementReferenceException) as e:
    # when timeout occurs, wait for 1 minute and restart
    print(Fore.YELLOW + 'TimeoutException/StaleElementReferenceException: ' + str(e))
    if (restarts_after_error<3):
        restarts_after_error+=1
        print(Fore.YELLOW + 'Restarting scraper...' + Style.RESET_ALL)
        print('')
        time.sleep(60)
        init_scraper(driver, wait)
    else:
        sys.exit(Fore.RED + 'Scraper stopped after 3 errors.' + Style.RESET_ALL)
        print('Total running time: ' + str(time_start - time.perf_counter()))
except (WebDriverException) as e:
    # something like a net-error should induce a waiting time (10 minutes)
    print(Fore.YELLOW + 'WebDriverException: ' + str(e))
    if (restarts_after_error<3):
        restarts_after_error+=1
        print(Fore.YELLOW + 'Restarting scraper...' + Style.RESET_ALL)
        print('')
        time.sleep(600)
        init_scraper(driver, wait)
    else:
        sys.exit(Fore.RED + 'Scraper stopped after 3 errors.' + Style.RESET_ALL)
        print('Total running time: ' + str(time_start - time.perf_counter()))
