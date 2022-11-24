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

from dataclasses import dataclass
from typing import Callable

# bluebird watcher
from tb_watcher.driver_utils import remove_elements, remove_ads
from tb_watcher.logger import logger

# selenium
import selenium
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

DEF_NUM_TWEETS = 20

@dataclass(init=True, repr=True, unsafe_hash=True)
class Tweet:
    """
    Helper class for representing metadata of a tweet.
    Useful for hashing functions and lookup tables.
    """
    id: str
    tag_text: str
    name: str
    tweet_text: str
    retweet_count: str
    handle: str
    timestamp: str
    like_count: str
    reply_count: str
    potential_boost: bool

def ensures_or(f: str, otherwise: str = "NULL"):
    try:
        return f()
    except Exception as e:
        logger.debug("Could not obtain using {} instead. Error: {}".format(otherwise, str(e)))

    return otherwise

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

    tweets_metadata = []
    id_tracker = 0
    last_id = id_tracker
    last_id_count = 0
    tweets_tracker = set()
    boosted_tracker = set()
    estimated_height = 0
    height_diffs = []
    div_track = set()
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

            tweets = driver.find_elements(By.CSS_SELECTOR, '[data-testid="tweet"]')
            for tweet in tweets:
                # Try to scroll there first and retry 2x load times before giving up.
                # Then bump up global load times by one.
                try:
                    ad = remove_ads(driver)
                    if ad:
                        continue

                    div_id = tweet.get_attribute("aria-labelledby")
                    if div_id in div_track:
                        continue

                    div_track.add(div_id)
                    driver.execute_script("return arguments[0].scrollIntoView();", tweet)
                    driver.execute_script("window.scrollTo(0, window.pageYOffset - 50);")

                except:
                    continue

                height = float(driver.execute_script("return window.scrollTop || window.pageYOffset;"))
                if height < estimated_height:
                    continue
                height_diffs.append(height - estimated_height)
                estimated_height = height

                tm = {"id": id_tracker}
                tm["tag_text"] = ensures_or(lambda: tweet.find_element(By.CSS_SELECTOR,'div[data-testid="User-Names"]').text)
                try:
                    tm["name"], tm["handle"], _, tm["timestamp"] = ensures_or(lambda: tm["tag_text"].split('\n'), tuple(["UKNOWN" for _ in range(4)]))
                except Exception as e:
                    tm["name"], tm["handle"], tm["timestamp"] = tm["tag_text"], "ERR", "ERR"
    
                tm["tweet_text"] = ensures_or(lambda: tweet.find_element(By.CSS_SELECTOR,'div[data-testid="tweetText"]').text)
                tm["retweet_count"] = ensures_or(lambda: tweet.find_element(By.CSS_SELECTOR,'div[data-testid="retweet"]').text)
                tm["like_count"] = ensures_or(lambda: tweet.find_element(By.CSS_SELECTOR,'div[data-testid="like"]').text)
                tm["reply_count"] = ensures_or(lambda: tweet.find_element(By.CSS_SELECTOR,'div[data-testid="reply"]').text)

                if tm["tweet_text"] != "NULL":
                    if tm["tweet_text"] in boosted_tracker:
                        # We need to go back in time to find the boosted post!
                        for t in tweets_metadata:
                            if t["tweet_text"] == tm["tweet_text"]:
                                t["potential_boost"] = True
                                break

                    tm["potential_boost"] = False
                    boosted_tracker.add(tm["tweet_text"])
                else:
                    tm["potential_boost"] = False

                dtm = Tweet(**tm)
                if dtm in tweets_tracker:
                    continue

                try:
                    # Try to remove elements before screenshot
                    remove_elements(driver, ["sheetDialog", "confirmationSheetDialog", "mask"])
                    tweet.screenshot(os.path.join(tweets_path, "{}.png".format(id_tracker)))
                except Exception as e:
                    # Failure to screenshot maybe because the tweet is too stale. Skip for now.
                    continue

                id_tracker += 1
                tweets_metadata.append(tm)
                tweets_tracker.add(dtm)

                if id_tracker > number_posts_to_cap:
                    break
    
            # Scroll!
            driver.execute_script("window.scrollTo(0, {});".format(estimated_height + offset_func(height_diffs)))
            time.sleep(random.uniform(load_times, load_times + 2))
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
            json.dump(tweets_metadata, f, ensure_ascii=False)
