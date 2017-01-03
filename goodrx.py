import os
import re
import sys
import csv
import time
import logging
import datetime
import traceback
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

def setupLogger():
    # Set up logging
    logFormatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")
    global log
    log = logging.getLogger()
    consoleHandler = logging.StreamHandler()
    consoleHandler.setFormatter(logFormatter)
    log.addHandler(consoleHandler)
    log.setLevel(logging.INFO)
    log.info("Start script")

def setupWaitTime():
    global wait
    try:
        possible_wait = sys.argv[3]
    except:
        logging.info("No wait time supplied, using default of 5 seconds")
    if possible_wait:
        wait = int(possible_wait)
        logging.info("Using wait time of %s" % (str(wait)))
    else:
        wait = 5


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

def processButton(button_text):
    button_text = button_text.upper()
    if "CASH" in button_text:
        return "Cash"
    if "DISCOUNT" in button_text:
        return "Discount"
    if "NO COUPON" in button_text:
        return "No Coupon"
    if "COUPON" in button_text:
        return "Coupon"
    if "ONLINE" in button_text:
        return "Online"
    if "MEMBERSHIP" in button_text:
        return "Membership"
    return "No method found"

def processStore(store):
    if "Other" in store:
        return "Other pharmacies"
    if "Name Hidden" in store:
        return "Name Hidden"
    return store

class CSV():
    def __init__(self):
        self.to_csv = []
        self.csvToDrug()


    def csvToDrug(self):
        self.drugs = []
        Drug = namedtuple("Drug",
            ["drug_name",
            "form",
            "dosage",
            "quantity",
            "label_override",
            "location"])
        try:
            csv_input = sys.argv[1]
            with open(csv_input, "rb") as csvfile:
                raw_csv = csv.reader(csvfile)
                for n, row in enumerate(raw_csv):
                    if n == 0:
                        continue
                    self.drugs.append(Drug(row[0],row[1],row[2],row[3],row[4],row[5]))
        except Exception as e:
            log.error(traceback.format_exc())
            log.error("Unable to open csv input file")
            sys.exit()


    def putcsv(self, drug, coupon, browser, user_agent):
        self.to_csv.append([
            drug.drug_name,
            drug.form,
            drug.dosage,
            drug.quantity,
            drug.label_override,
            drug.location,
            coupon.price,
            coupon.store_name,
            coupon.method,
            browser,
            user_agent])


    def savecsv(self):
        self.to_csv.insert(0,[
            "Drug Name",
            "Form",
            "Dosage",
            "Quantity",
            "Label Override",
            "Zip/Location",
            "Price",
            "Store",
            "Method",
            "Browser",
            "User-Agent"])
        file_destination = "GoodRx-%s" % \
            (datetime.datetime.now().strftime("%m-%d-%y-%H:%M"),)
        try:
            with open(file_destination, "wb") as outfile:
                writer = csv.writer(outfile)
                writer.writerows(self.to_csv)
                log.info("Wrote output to file %s" % (file_destination),)
        except Exception as e:
            log.error(traceback.format_exc())
            log.error("Error writing to file.  Check file writing permissions?")

class Driver():
    def __init__(self):
        self.findChromedriver()
        self.setupUserAgents()


    def findChromedriver(self):
        """Assume chromedriver is at the same level as this script"""
        BASE_DIR = os.path.abspath(os.path.dirname(__file__))
        self.chromedriver_path = os.path.join(BASE_DIR, 'chromedriver')
        log.info("Chromedriver found")


    def safariUserAgentHelper(self):
        UserAgent = namedtuple("UserAgent", ["browser", "user_agent"])
        user_agent = None
        url = "http://useragentstring.com/pages/useragentstring.php?name=Safari"
        try:
            response = requests.get(url, timeout=wait)
            response_text = response.text
            bsobject = bs(response_text, "html.parser")
            links = bsobject.find_all("a")
            specific_safari_version = "iPhone OS 4_1"
            for link in links:
                if specific_safari_version in link.text:
                    user_agent = UserAgent("Safari", link.text)
                    log.info("Safari User-Agent loaded")
                    break
        except Exception as e:
            log.error(traceback.format_exc())
            log.info("Can't pull Safari User-Agent from useragentstring.com.  Using default Safari User-Agent")
            user_agent_string = "Mozilla/5.0 (iPhone; CPU iPhone OS 5_1_1 like "\
                "Mac OS X) AppleWebKit/534.46 (KHTML, like Gecko) Version/5.1 "\
                "Mobile/9B206 Safari/7534.48.3"
            user_agent = UserAgent("Safari", user_agent_string)
        return user_agent

    def setupUserAgents(self):
        user_agents = []
        UserAgent = namedtuple("UserAgent", ["browser", "user_agent"])

        try:
            args = sys.argv[2]
        except:
            logging.error("Browsers like Chrome, Internet Explorer, and/or "\
                "Safari need to be in the 2nd position command line arguments")
            sys.exit()

        if "Safari" in args:
            safari_user_agent = self.safariUserAgentHelper()
            if safari_user_agent:
                user_agents.append(safari_user_agent)

        if ("Internet Explorer" in args) or ("Chrome" in args):
            ua = None
            try:
                ua = UA()
            except:
                log.error("Unable to load fakeuseragent package for Chrome and Internet Explorer User-Agents")
            try:
                if ua:
                    ua.update()
            except:
                log.error("Unable to update fakeuseragent package for Chrome and Internet Explorer User-Agents")
            if not ua:
                UA = namedtuple("UA", ["ie", "chrome"])
                ua = UA("Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 6.1; "\
                    "WOW64; Trident/4.0; SLCC2; .NET CLR 2.0.50727; Media "\
                    "Center PC 6.0; .NET CLR 3.5.30729; .NET CLR 3.0.30729; .NET4.0C)",
                    "Mozilla/5.0 (X11; CrOS i686 4319.74.0) AppleWebKit/537.36 "\
                    "(KHTML, like Gecko) Chrome/29.0.1547.57 Safari/537.36")
                log.info("Using default User-Agents for Internet Explorer and/or Chrome")
            if "Internet Explorer" in args:
                user_agents.append(UserAgent("Internet Explorer", ua.ie))
                log.info("Internet Explorer User-Agent loaded")
            if "Chrome" in args:
                user_agents.append(UserAgent("Chrome", ua.chrome))
                log.info("Chrome User-Agent loaded")

        if not user_agents:
            logging.error("Browsers like Chrome, Internet Explorer, and/or "\
                "Safari need to be in the 2nd position command line arguments")
            sys.exit()
        self.user_agents = user_agents


    def initWebsiteDriver(self, user_agent):
        opts = Options()
        opts.add_argument("user-agent=%s" % (user_agent,))

        try:
            driver = webdriver.Chrome(executable_path=self.chromedriver_path,
                                       chrome_options=opts)
        except Exception as e:
            log.error(traceback.format_exc())
            log.error("Can't initialize browser. Is the chromedriver in the same directory as the exe?")
            sys.exit()
        return driver


    def initMobileDriver(self, user_agent):
        mobile_emulation = {
            "deviceMetrics": { "width": 360, "height": 640, "pixelRatio": 3.0 },
            "userAgent": user_agent}
        opts = Options()
        opts.add_experimental_option("mobileEmulation", mobile_emulation)
        try:
            driver = webdriver.Chrome(executable_path=self.chromedriver_path,
                                      chrome_options=opts)
        except Exception as e:
            log.error(traceback.format_exc())
            log.error("Can't initialize browser. Is the chromedriver in the same directory as the exe?")
            sys.exit()
        return driver


    def buildURL(self, drug, mobile=""):
        if mobile == True:
            mobile = 'm.'
        return "https://{}goodrx.com/{}?drug-name={}&form={}&dosage={}&quantity="\
            "{}&days_supply=&label_override={}".format(mobile, drug.drug_name, drug.drug_name,
                drug.form, drug.dosage, drug.quantity, drug.label_override)


    def setupDrivers(self, drug):
        for user_agent in self.user_agents:
            browser = user_agent.browser
            user_agent = user_agent.user_agent
            if browser == "Safari":
                driver = self.initMobileDriver(user_agent)
                url = self.buildURL(drug=drug, mobile=True)
                yield driver, user_agent, browser, url
            else:
                driver = self.initWebsiteDriver(user_agent)
                url = self.buildURL(drug)
                yield driver, user_agent, browser, url


def Chrome(driver, drug):
    try:
        location_button = WebDriverWait(driver, wait).until(\
            EC.presence_of_element_located((By.ID, "setLocationButton")))
        location_button.click()

        location_modal = WebDriverWait(driver, wait).until(\
            EC.presence_of_element_located((By.ID, "locationDetection")))
        modal = driver.switch_to_active_element()
        location_input = modal.find_element_by_id("manualLocationQuery")
        location_input.send_keys(str(drug.location)+"\n")

        location_loaded = WebDriverWait(driver, wait).until(\
            EC.presence_of_element_located((\
            By.XPATH, "//*[contains(text(), 'Lowest prices near')]")))
    except Exception as e:
        log.error(traceback.format_exc())
        log.error("Couldn't load location for %s in browser %s" % (drug, "Chrome"))
        return []

    view_more_pharmacies = True
    coupons = []
    Coupon = namedtuple("Coupon", ["price", "store_name", "method"])
    try:
        while view_more_pharmacies:
            view_more_pharmacies = False
            if coupons:
                driver.find_element_by_class_name("view-button").click()
                time.sleep(wait)
            page = bs(driver.page_source, 'html.parser')
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
                    if price_possible.text == "Free":
                        price = 0

                possible_coupon = Coupon(price, store_name, method)
                if possible_coupon not in coupons:
                    coupons.append(possible_coupon)
                    view_more_pharmacies = True
    except Exception as e:
        log.error(traceback.format_exc())
        log.error("Main parsing logic broken for Chrome:\n%s\n%s" % (drug, coupons,))
    return coupons


def InternetExplorer(driver, drug):
    location_input = WebDriverWait(driver, wait).until(\
        EC.presence_of_element_located((By.XPATH,
        "//input[contains(@class, 'span9') and "\
        "contains(@placeholder, 'Enter your ZIP code')]")))
    location_input.send_keys(str(drug.location) + "\n")
    time.sleep(wait)

    view_more_pharmacies = True
    coupons = []
    Coupon = namedtuple("Coupon", ["price", "store_name", "method"])
    while view_more_pharmacies:
        view_more_pharmacies = False
        if coupons:
            driver.find_element_by_id("load-more-pharmacies").click()
            time.sleep(wait)
            modal = driver.find_elements_by_xpath("//div[contains(@class, 'modal-backdrop') "\
            "and contains(@class, 'in')]")
            if modal:
                dont_show_again = WebDriverWait(driver, wait).until(\
                    EC.presence_of_element_located((By.CLASS_NAME, "dont-show-again")))
                time.sleep(wait)
                dont_show_again.click()

        row_region = driver.find_element_by_class_name("price-group-expanded")
        rows = row_region.find_elements_by_class_name("drug-prices-result")
        for row in rows:
            store_name = row.find_element_by_class_name("result-title").text
            method = processButton(row.find_element_by_class_name("span3").text)
            possible_price = row.find_element_by_class_name("price").text
            if not is_number(possible_price):
                if possible_price == "FREE":
                    price = 0
                else:
                    price = "Could not find price"
            else:
                price = possible_price

            possible_coupon = Coupon(price, store_name, method)
            if possible_coupon not in coupons:
                coupons.append(possible_coupon)
                view_more_pharmacies = True
    return coupons


def Safari(driver, drug):
    try:
        location_button = WebDriverWait(driver, wait).\
            until(EC.presence_of_element_located(\
            (By.XPATH,"//div[contains(@class, '-clickable') and "\
                      "contains(.//text(),'Add your location')]")))
        location_button.click()

        location_modal = WebDriverWait(driver, wait).\
            until(EC.presence_of_element_located(\
            (By.XPATH, "//div[contains(@class, 'floatfix') and "\
                       "contains(@class ,'scroll-overflow')]")))
        location_input = location_modal.find_element_by_tag_name("input")
        location_input.send_keys(str(drug.location) + "\n")
        time.sleep(wait)
        location_loaded = WebDriverWait(driver, wait).\
            until_not(EC.presence_of_element_located(\
            (By.XPATH, "//body[contains(@class, 'no-overflow')]")))
    except Exception as e:
        log.error(traceback.format_exc())
        log.error("Couldn't load location for %s in browser %s" % (drug, "Safari",))
        return []

    view_more_pharmacies = True
    coupons = []
    Coupon = namedtuple("Coupon", ["price", "store_name", "method"])

    try:
        while view_more_pharmacies:
            view_more_pharmacies = False
            if coupons:
                drug_list = driver.find_element_by_class_name("drug-price-list")
                other_pharmacies = drug_list.find_element_by_class_name("more-pharmacies-bar")
                other_pharmacies.click()
                time.sleep(wait)
            drug_list = driver.find_element_by_class_name("drug-price-list")
            rows = drug_list.find_elements_by_class_name("list-item")
            for row in rows:
                store_name = row.find_element_by_class_name("pharmacy-name").text
                raw_method = row.find_element_by_class_name("drug-price-qualifier").text
                method = processButton(raw_method)

                price = None
                price_check = row.find_elements_by_class_name("price-without-dollar")
                if price_check:
                    price = price_check[0].text
                    if not is_number(price):
                        price = 0
                else:
                    price_free = row.find_elements_by_class_name("price-free")
                    if price_free:
                        if price_free[0].text == "Free":
                            price = 0
                if price == None:
                    price = "Could not find price"

                possible_coupon = Coupon(price, store_name, method)
                if possible_coupon not in coupons:
                    coupons.append(possible_coupon)
                    view_more_pharmacies = True
    except Exception as e:
        log.error(traceback.format_exc())
        log.error("Main parsing logic broken for Safari:\n%s\n%s" % (drug, coupons,))
    return coupons


if __name__ == "__main__":
    setupLogger()
    setupWaitTime()
    csv_tool = CSV()
    driver_tool = Driver()
    for drug in csv_tool.drugs:
        for driver, user_agent, browser, url in driver_tool.setupDrivers(drug):
            driver.get(url)
            if browser == "Safari":
                coupons = Safari(driver, drug)
            if browser == "Chrome":
                coupons = Chrome(driver, drug)
            if browser == "Internet Explorer":
                coupons = InternetExplorer(driver, drug)
            log.info("\nLoaded coupons from browser %s @ %s\n%s" % (browser, url, drug))
            for coupon in coupons:
                csv_tool.putcsv(drug, coupon, browser, user_agent)
            driver.quit()
    csv_tool.savecsv()
