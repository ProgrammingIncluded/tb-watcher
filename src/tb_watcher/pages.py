"""
Logic dealing with snapshotting different pages.
Great level of abstraction for multithreading as each
page is independent of another page.

By: ProgrammingIncluded
"""
# std
import os
import random
import time
import json
import shutil

from abc import abstractmethod
from typing import Callable, List
from dataclasses import asdict
from urllib.parse import urlparse

# tb_watcher
from tb_watcher.logger import logger
from tb_watcher.driver_utils import (BioMetadata, MaxCapturesReached, Scroller, TweetExtractor, Tweet,
                                     ensures_or, remove_elements, create_chrome_driver, tweet_dom_get_basic_metadata)

# selenium
import selenium
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

class TwitterPage:
    """Interface for a page on Twitter.
    Each page can allow for a driveer to optimize multi-threading.
    """
    def __init__(self, root_dir: str, url: str, *args, auto_fetch_threads=False, existing_driver: webdriver = None, **kwargs):
        self.metadata = None
        self.root_dir = root_dir
        self.auto_fetch_threads = auto_fetch_threads

        if existing_driver:
            self.driver = existing_driver
        else:
            self.driver = create_chrome_driver()
        self.url = url

    def get_driver(self) -> webdriver:
        """
        Returns the driver for a given page.
        """
        return self.driver

    @abstractmethod
    def fetch_metadata(self):
        """
        Fetches the metadata associated with the page.
        """

    def fetch_tweets(
        self,
        number_posts_to_cap: int,
        load_time: int,
        offset_func: Callable
    ) -> List[Tweet]:
        if self.url not in self.driver.current_url:
            self.driver.get(self.url)

        if self.metadata is None:
            self.fetch_metadata()

        save_path = os.path.join(self.root_dir, self.metadata.unique_id())
        extractor = TweetExtractor(save_path, number_posts_to_cap)
        # Skip the first tweet of a thread current metadata applies.
        # Which only occurs in threads.
        extractor.tweets_tracker.add(self.metadata)

        last_id_count = 0
        last_id = 0
        # Wrap the offset function with extract height context.
        try:
            time.sleep(random.uniform(load_time, load_time + 2))
            for _ in Scroller(self.driver, extractor.create_offset_function(offset_func), load_time):
                if last_id_count > 5:
                    logger.debug("No more data to load?")
                    break

                # Just in case we keep hitting the same id.
                if last_id == extractor.counter:
                    last_id_count += 1
                else:
                    last_id = extractor.counter
                    last_id_count = 0

                # Capture the tweets and generates files for them
                extractor.capture_all_available_tweets(self.driver, self.auto_fetch_threads, load_time, offset_func)
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
            extractor.write_json()

class TwitterThread(TwitterPage):
    """
    Class encapsulating a twitter thread page.
    Also used to resolve Tweet ID as a thread will contain
    the Tweet's ID.
    """
    def __init__(self, *args, **kwargs):
        # Force auto fetching threads to false to prevent recursion.
        auto_fetch_threads = kwargs.get("auto_fetch_threads", False)
        kwargs["auto_fetch_threads"] = auto_fetch_threads
        super().__init__(*args, **kwargs)

    def fetch_metadata(self) -> Tweet:
        raw_url = self.driver.current_url
        if self.url not in raw_url:
            self.driver.get(self.url)
            raw_url = self.url

        state = ""
        while state != "complete":
            time.sleep(random.uniform(3, 5))
            state = self.driver.execute_script("return document.readyState")

        WebDriverWait(self.driver, 30).until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, '[data-testid="tweet"]')))

        # We only want the first tweet of the page which is the main tweet
        # don't use TweetExtractor as internally it calls this function for metadata of the tweet.
        tweets = self.driver.find_elements(By.CSS_SELECTOR, '[data-testid="tweet"]')
        main_tweet = tweets[0]
        dtm = tweet_dom_get_basic_metadata(main_tweet)

        # Grab unique tweet id
        assert "status/" in raw_url, "Is this a valid status URL?: {}".format(raw_url)
        path = urlparse(raw_url).path
        post_url =path.split("status/")[-1]
        dtm.id = post_url.split("/")[0]

        self.metadata = dtm

        # Create a folder to house pictures, etc.
        tweet_folder_fpath = os.path.join(self.root_dir, dtm.id)
        os.makedirs(tweet_folder_fpath, exist_ok=True)

        # Remove initial popups.
        remove_elements(self.driver, ["sheetDialog", "confirmationSheetDialog", "mask"])

        # delete bottom element
        remove_elements(self.driver, ["BottomBar"])

        # Take a screenshot of the tweet.
        main_tweet.screenshot(os.path.join(tweet_folder_fpath, "{}.png".format(dtm.id)))
        return dtm


class TwitterBio(TwitterPage):
    """
    Class encapsulating a twitter bio page.
    """
    def fetch_metadata(self) -> BioMetadata:
        if self.url not in self.driver.current_url:
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

    def get_bio_as_dict(self) -> dict:
        return asdict(self.metadata)

    def write_json(self, force=False) -> bool:
        """
        Returns true if wrote to file, otherwise returns false.
        """
        username = self.metadata.username
        assert self.metadata.username[0] == "@"
        username = username[1:]

        fpath = os.path.join(self.root_dir, username)
        if not force and os.path.exists(fpath):
            logger.info("Folder already exists, skipping: {}".format(fpath))
            return False
        elif force and os.path.exists(fpath):
            shutil.rmtree(fpath)

        os.makedirs(fpath)

        # Force utf-8
        # Save a copy of the metadata
        with open(os.path.join(fpath, "metadata.json"), "w", encoding="utf-8") as f:
            json.dump(self.get_bio_as_dict(), f, ensure_ascii=False)

        # Save a screen shot of the bio
        self.driver.save_screenshot(os.path.join(fpath, "profile.png"))
        return True
