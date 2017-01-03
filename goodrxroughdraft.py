import os
import re
import sys
import csv
import time
import logging
import unicodedata
from collections import namedtuple

import requests
from bs4 import BeautifulSoup as bs
from fake_useragent import UserAgent as UA

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Set up logging
logFormatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")
log = logging.getLogger()
consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(logFormatter)
log.addHandler(consoleHandler)
log.setLevel(logging.INFO)

## UTILITIES
def csvAcquire():
    rows = []
    Drug = namedtuple("Drug", ["drug_name", "form", "dosage", "quantity",
                              "label_override", "location"])
    try:
        csv_input = sys.argv[1]
        with open(csv_input, "rb") as csvfile:
            reader = csv.reader(csvfile)
            for n, row in enumerate(reader):
                rows.append(Drug(row[0],row[1],row[2],row[3],row[4],row[5]))
    except:
        logging.error("Unable to open csv input file")
        sys.exit()
    log.info("Loaded csv data from %s" % (csv_input,))
    return rows[1:]


def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        pass

    try:
        unicodedata.numeric(s)
        return True
    except (TypeError, ValueError):
        pass
    return False


def buildURL(drug, mobile=""):
    if mobile == True:
        mobile = 'm.'
    return "https://{}goodrx.com/{}?drug-name={}&form={}&dosage={}&quantity="\
        "{}&days_supply=&label_override={}".format(mobile, drug.drug_name, drug.drug_name,
            drug.form, drug.dosage, drug.quantity, drug.label_override)


def processButton(button_text):
    if "Discount" in button_text:
        return "Discount"
    if "Coupon" in button_text:
        return "Coupon"
    else:
        return "Online"

## UTILITIES OVER
class Request():

    def __init__(self):
        self.setUpUserAgents()
        self.findChromedriver()


    def setUpUserAgents(cls):
        user_agents = []
        UserAgent = namedtuple("UserAgent", ["browser_name", "user_agent"])

        try:
            args = sys.argv[2]
        except:
            logging.error("No User-Agent Command Line Arg provided")
            sys.exit()

        if "Safari" in args:
            url = "http://useragentstring.com/pages/useragentstring.php?name=Safari"
            response = requests.get(url)
            response_text = response.text
            bsobject = bs(response_text, "html.parser")
            links = bsobject.find_all("a")
            for link in links:
                if "iPhone OS 4_1" in link.text:
                    user_agents.append(UserAgent("Safari", link.text))
                    log.info("Obtained Safari User-Agent")
                    break

        if ("Internet Explorer" in args) or ("Chrome" in args):
            ua = UA()
            ua.update()
            if "Internet Explorer" in args:
                user_agents.append(UserAgent("Internet Explorer", ua.ie))
                log.info("Obtained Internet Explorer User-Agent")
            if "Chrome" in args:
                user_agents.append(UserAgent("Chrome", ua.chrome))
                log.info("Obtained Chrome User-Agent")

        if not user_agents:
            logging.error("Incorrect User-Agent Command Line Arg provided")
            sys.exit()

        cls.user_agents = user_agents


    def findChromedriver(cls):
        """Assume chromedriver is at the same level as this script"""
        BASE_DIR = os.path.abspath(os.path.dirname(__file__))
        DIR = os.path.join(BASE_DIR, 'chromedriver')
        cls.chromedriver_path = DIR
        log.info("Chromedriver found")


    def yieldBrowsers(cls):
        """This creates a chromedriver iterator"""
        for user_agent in cls.user_agents:
            if (user_agent.browser_name == "Chrome") or \
               (user_agent.browser_name == "Internet Explorer"):

                opts = Options()
                opts.add_argument("user-agent=%s" % (user_agent.user_agent,))
                log.info(user_agent.user_agent)

                try:
                    browser = webdriver.Chrome(executable_path=cls.chromedriver_path,
                                               chrome_options=opts)
                except:
                    log.error("Invalid chromedriver path. Is it in the same directory as the exe?")
                    sys.exit()
                yield browser, user_agent.browser_name

            if user_agent.browser_name == "Safari":
                mobile_emulation = {
                    "deviceMetrics": { "width": 360, "height": 640, "pixelRatio": 3.0 },
                    "userAgent": user_agent.user_agent}
                chrome_options = Options()
                chrome_options.add_experimental_option("mobileEmulation", mobile_emulation)

                try:
                    browser = webdriver.Chrome(executable_path=cls.chromedriver_path,
                        chrome_options=chrome_options)
                except:
                    log.error("Invalid chromedriver path. Is it in the same directory as the exe?")
                    sys.exit()
                yield browser, user_agent.browser_name


def Chrome(browser, browser_name, drug, url):
    try:
        location_button = WebDriverWait(browser, 5).until(\
            EC.presence_of_element_located((By.ID, "setLocationButton")))
        location_button.click()
    except:
        log.error("Couldn't find location button for " + str(drug))
        return False
    try:
        location_modal = WebDriverWait(browser, 5).until(\
            EC.presence_of_element_located((By.ID, "locationDetection")))
        modal = browser.switch_to_active_element()
        location_input = modal.find_element_by_id("manualLocationQuery")
        location_input.send_keys(str(drug.location))
        location_input.send_keys(Keys.ENTER)
    except:
        log.error("Couldn't enter location for " + str(drug))
        return False
    try:
        location_loaded = WebDriverWait(browser, 5).until(\
            EC.presence_of_element_located((\
            By.XPATH, "//*[contains(text(), 'Lowest prices near')]")))
    except:
        log.error("Couldn't load location for " + str(drug))
        return False

    view_more_pharmacies = True
    content = []
    while view_more_pharmacies:
        if content:
            browser.find_element_by_class_name("view-button").click()
            time.sleep(5)
        view_more_pharmacies = False
        page = bs(browser.page_source, 'html.parser')
        container = page.find("div", id="locationDetection").parent
        rows = container.find_all("div", class_="price-row")
        for row in rows:
            store_name = row.find("div", class_="store-name").text
            method = processButton(row.find("button").text)

            price = ""
            prices = row.find_all("span", class_="font-weight-medium")
            for price_possible in prices:
                if is_number(price_possible.text):
                    price = price_possible.text

            possible_content = [
                price,
                store_name,
                drug.drug_name,
                drug.form,
                drug.dosage,
                drug.quantity,
                drug.label_override,
                drug.location,
                method,
                browser_name]
            if possible_content not in content:
                content.append(possible_content)
                view_more_pharmacies = True
    log.info(content)
    return content

if __name__ == "__main__":
    log.info("Start script")
    csv_input = csvAcquire()

    request = Request()

    for drug in csv_input:
        for browser, browser_name in request.yieldBrowsers():
            # url = buildURL(drug)
            # log.info(url)
            # browser.get(url)
            if browser_name == "Chrome":
                log.info("HERE")
                content = Chrome(browser, browser_name, drug, url)
            if browser_name == "Internet Explorer":
                log.info("NOW IN IE")
            if browser_name == "Safari":
                url = buildURL(drug=drug, mobile=True)
                browser.get(url)
                log.info("NOW IN SAFARI")
                # location = browser.find_elements_by_class_name("-clickable")
                # l_click = location[1].find_elements_by_css_selector("span")[1]
                # log.info(l_click.text)
                # l_click.click()
                import pdb;pdb.set_trace()
                # except:
                #     log.error("Error processing page data for " + str(drug))
                #     pass
            # try:
            #     clickables = WebDriverWait(browser, 6).until(\
            #         EC.presence_of_all_elements_located((By.CLASS_NAME, "-clickable")))
            # except:
            #     log.error("Couldn't access page for drug " + str(drug))
            #     sys.exit()
            # for clickable in clickables:
            #     if clickable.find_elements_by_class_name("location-bar"):
            #         print clickable.text
            #         clickable.click()
            # import pdb;pdb.set_trace()
            # text_box = browser.find_element_by_class_name("third-text-input")
            # text_box.send_keys(drug.location)
            # text_box.send_keys(Keys.ENTER)
            # try:
            #     elements = WebDriverWait(browser, 10).until(\
            #         EC.presence_of_elements_located((By.CLASS_NAME, "list-item-element")))
            # except:
            #     log.error("Couldn't load in location for drug " + str(drug))
            browser.quit()
