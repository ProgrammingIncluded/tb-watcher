"""
Houses the main logic for fetching data and interfacing with Selenium.
By: ProgrammingIncluded
"""
# std
import os
import random
import json
import shutil
import time

from typing import Callable

# bluebird watcher
from tb_watcher.driver_utils import TweetExtractor, ensures_or, remove_elements
from tb_watcher.logger import logger

# selenium
import selenium
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

DEF_NUM_TWEETS = 20

def fetch_html(
    driver: webdriver,
    url: str,
    fpath: str,
    load_times: float,
    offset_func: Callable,
    force: bool = False,
    number_posts_to_cap: int = DEF_NUM_TWEETS,
    bio_only: bool = False):
    """Primary driver of the program."""

    # Many thanks to: https://www.scrapingbee.com/blog/web-scraping-twitter/
    # for the inspiration.
    # Major adjustments to make UX a lot smoother.

    driver.get(url)
    state = ""
    while state != "complete":
        time.sleep(random.uniform(3, 5))
        state = driver.execute_script("return document.readyState")

    WebDriverWait(driver, 30).until(EC.presence_of_element_located(
        (By.CSS_SELECTOR, '[data-testid="tweet"]')))

    # Remove initial popups.
    remove_elements(driver, ["sheetDialog", "confirmationSheetDialog", "mask"])

    # delete bottom element
    remove_elements(driver, ["BottomBar"])

    metadata = {}
    metadata["bio"] = ensures_or(lambda: driver.find_element(By.CSS_SELECTOR,'div[data-testid="UserDescription"]').text)
    metadata["name"], metadata["username"] = ensures_or(lambda: driver.find_element(By.CSS_SELECTOR,'div[data-testid="UserName"]').text.split('\n'), ("NULL", "NULL"))
    metadata["location"] = ensures_or(lambda: driver.find_element(By.CSS_SELECTOR,'span[data-testid="UserLocation"]').text)
    metadata["website"] = ensures_or(lambda: driver.find_element(By.CSS_SELECTOR,'a[data-testid="UserUrl"]').text)
    metadata["join_date"] = ensures_or(lambda: driver.find_element(By.CSS_SELECTOR,'span[data-testid="UserJoinDate"]').text)
    metadata["following"] = ensures_or(lambda: driver.find_element(By.XPATH, "//span[contains(text(), 'Following')]/ancestor::a/span").text) 
    metadata["followers"] = ensures_or(lambda: driver.find_element(By.XPATH, "//span[contains(text(), 'Followers')]/ancestor::a/span").text)

    if metadata.get("username", "NULL") == "NULL":
        raise RuntimeError("Fatal error, unable to resolve username {}".format(metadata))

    # Change the fpath and resolve username
    username = metadata["username"]
    username = username[1:] if username.startswith("@") else username

    fpath = os.path.join(fpath, username) 
    if not force and os.path.exists(fpath):
        logger.info("Folder already exists, skipping: {}".format(fpath))
        return
    elif force and os.path.exists(fpath):
        shutil.rmtree(fpath)

    os.makedirs(fpath)

    # Force utf-8
    # Save a copy of the metadata
    with open(os.path.join(fpath, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False)

    # Save a screen shot of the bio
    driver.save_screenshot(os.path.join(fpath, "profile.png"))

    if bio_only:
        return

    # Create tweets folder
    tweets_path = os.path.join(fpath, "tweets")
    os.makedirs(tweets_path)

    id_tracker = 0
    last_id = id_tracker
    last_id_count = 0
    extractor = TweetExtractor(tweets_path, max_captures=number_posts_to_cap)
    try:
        last_height = 0
        new_height = 0
        time.sleep(random.uniform(load_times, load_times + 2))
        while True:
            if id_tracker >= number_posts_to_cap - 1:
                break
            elif last_id_count > 5:
                logger.debug("No more data to load?")
                break

            if last_id == id_tracker:
                last_id_count += 1
            else:
                last_id = id_tracker
                last_id_count = 0

            # Capture the tweets and generates files for them
            extractor.capture_all_available_tweets(driver)

            # Scroll!
            predict_next_scroll = offset_func(extractor.get_scroll_offset_history())
            driver.execute_script("window.scrollTo(0, {});".format(extractor.prev_height + predict_next_scroll))
            # Sleep to let the next "pages" of tweet to load
            time.sleep(random.uniform(load_times, load_times + 2))

            # If scrolling no longer offsets the page, then we have hit the bottom!
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

    except selenium.common.exceptions.StaleElementReferenceException as e:
        logger.warning("Tweet limit reached, for {} unable to fetch more data. Authentication is required.".format(username))
        logger.warning("Or you can try to bump loading times.")
        raise e
    except Exception as e:
        raise e
    finally:
        # Dump all metadata
        with open(os.path.join(tweets_path, "tweets.json"), "w", encoding="utf-8") as f:
            json.dump(extractor.get_tweets_as_dict(), f, ensure_ascii=False)
