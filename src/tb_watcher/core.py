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

from abc import ABC, abstractmethod
from typing import Callable, List
from dataclasses import asdict

# bluebird watcher
from tb_watcher.driver_utils import (BioMetadata, MaxCapturesReached, Scroller, TweetExtractor, Tweet,
                                     ensures_or, remove_elements, create_chrome_driver)
from tb_watcher.logger import logger

# selenium
import selenium
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

DEF_NUM_TWEETS = 20

class TwitterPageInterface(ABC):
    """Interface for a page on Twitter.
    Each page can allow for a driveer to optimize multi-threading.
    """
    @abstractmethod
    def get_driver(self) -> webdriver:
        """
        Returns the driver for a given page.
        """

class TwitterBio(TwitterPageInterface):
    """
    Class encapsulating a twitter bio page.
    Owns an instance of driver for capturing your driving needs.
    """
    def __init__(self, url: str, existing_driver: webdriver = None):
        # Must be fetched or deserialized.
        self.metadata = None

        if existing_driver:
            self.driver = existing_driver
        else:
            self.driver = create_chrome_driver()
        self.url = url

    def get_driver(self) -> webdriver:
        return self.driver

    def fetch_bio_data(self) -> BioMetadata:
        self.driver.get(self.url)

        state = ""
        while state != "complete":
            time.sleep(random.uniform(3, 5))
            state = self.driver.execute_script("return document.readyState")
    
        WebDriverWait(self.driver, 30).until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, '[data-testid="tweet"]')))
    
        # Remove initial popups.
        remove_elements(self.driver, ["sheetDialog", "confirmationSheetDialog", "mask"])
    
        # delete bottom element
        remove_elements(self.driver, ["BottomBar"])
    
        metadata = {}
        metadata["bio"] = ensures_or(lambda: self.driver.find_element(By.CSS_SELECTOR,'div[data-testid="UserDescription"]').text)
        metadata["name"], metadata["username"] = ensures_or(lambda: self.driver.find_element(By.CSS_SELECTOR,'div[data-testid="UserName"]').text.split('\n'), ("NULL", "NULL"))
        metadata["location"] = ensures_or(lambda: self.driver.find_element(By.CSS_SELECTOR,'span[data-testid="UserLocation"]').text)
        metadata["website"] = ensures_or(lambda: self.driver.find_element(By.CSS_SELECTOR,'a[data-testid="UserUrl"]').text)
        metadata["join_date"] = ensures_or(lambda: self.driver.find_element(By.CSS_SELECTOR,'span[data-testid="UserJoinDate"]').text)
        metadata["following"] = ensures_or(lambda: self.driver.find_element(By.XPATH, "//span[contains(text(), 'Following')]/ancestor::a/span").text) 
        metadata["followers"] = ensures_or(lambda: self.driver.find_element(By.XPATH, "//span[contains(text(), 'Followers')]/ancestor::a/span").text)
    
        if metadata.get("username", "NULL") == "NULL":
            raise RuntimeError("Fatal error, unable to resolve username {}".format(metadata))

        # Save metadata as local value.
        self.metadata = BioMetadata(**metadata)
    
        return self.metadata

    def fetch_tweets(
        self,
        number_posts_to_cap: int,
        tweets_path: str,
        load_time: int,
        offset_func: Callable
    ) -> List[Tweet]:
        id_tracker = 0
        last_id = id_tracker
        last_id_count = 0

        extractor = TweetExtractor(tweets_path, max_captures=number_posts_to_cap)

        # Wrap the offset function with extract height context.
        offset_func = extractor.create_offset_function(offset_func)
        try:
            time.sleep(random.uniform(load_time, load_time + 2))
            for _ in Scroller(self.driver, offset_func, load_time):
                if id_tracker >= number_posts_to_cap - 1:
                    break
                elif last_id_count > 5:
                    logger.debug("No more data to load?")
                    break

                # Just in case we keep hitting the same id.
                if last_id == id_tracker:
                    last_id_count += 1
                else:
                    last_id = id_tracker
                    last_id_count = 0

                # Capture the tweets and generates files for them
                extractor.capture_all_available_tweets(self.driver)
        except selenium.common.exceptions.StaleElementReferenceException as e:
            logger.warning("Tweet limit reached, for {} unable to fetch more data. Authentication is required.".format(self.metadata.username))
            logger.warning("Or you can try to bump loading times.")
            raise e
        except MaxCapturesReached as e:
            pass
        except Exception as e:
            raise e
        finally:
            # Dump all metadata
            with open(os.path.join(tweets_path, "tweets.json"), "w", encoding="utf-8") as f:
                json.dump(extractor.get_tweets_as_dict(), f, ensure_ascii=False)

    def get_bio_as_dict(self) -> dict:
        return asdict(self.metadata)

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
    twitter_bio = TwitterBio(url, existing_driver=driver)
    b_meta = twitter_bio.fetch_bio_data()

    username = b_meta.username
    assert b_meta.username[0] == "@"
    username = username[1:]

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
        json.dump(twitter_bio.get_bio_as_dict(), f, ensure_ascii=False)

    # Save a screen shot of the bio
    driver.save_screenshot(os.path.join(fpath, "profile.png"))

    if bio_only:
        return

    # Create tweets folder
    tweets_path = os.path.join(fpath, "tweets")
    os.makedirs(tweets_path)

    twitter_bio.fetch_tweets(
        number_posts_to_cap,
        tweets_path,
        load_times,
        offset_func
    )
