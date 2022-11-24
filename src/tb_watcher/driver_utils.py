"""
Helpers for Selenium driver.
By: ProgrammingIncluded
"""

# std
import os
import time
import json
import random
from abc import abstractmethod
from urllib.parse import urlparse

from typing import Callable, List
from dataclasses import dataclass, asdict

# tb_watcher
from tb_watcher.logger import logger

# selenium
import selenium
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

def ensures_or(f: str, otherwise: str = "NULL"):
    try:
        return f()
    except Exception as e:
        logger.debug("Could not obtain using {} instead. Error: {}".format(otherwise, str(e)))

    return otherwise

class Unique:
    @abstractmethod
    def unique_id(self):
        """Used for folder writing."""

@dataclass(init=True, repr=True, unsafe_hash=True)
class Tweet(Unique):
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

    def get_url(self):
        return "https://www.twitter.com/{clean_handle}/status/{id}".format(self.handle[1:], self.id)

    def unique_id(self):
        """Used for folder writing."""
        return self.id

@dataclass(init=True, repr=True, unsafe_hash=True)
class BioMetadata(Unique):
    username: str
    bio: str
    name: str
    location: str
    website: str
    join_date: str
    following: str
    followers: str

    def unique_id(self):
        """Used for folder writing."""
        return self.username[1:]

class MaxCapturesReached(RuntimeError):
    """The specified number of captures have been reached."""

def tweet_dom_get_basic_metadata(tweet_dom):
    """Retrieves all metadata from tweet dom except unique id."""
    tm = {"id": "null"}
    tm["tag_text"] = ensures_or(lambda: tweet_dom.find_element(By.CSS_SELECTOR,'div[data-testid="User-Names"]').text)
    try:
        tm["name"], tm["handle"], _, tm["timestamp"] = ensures_or(lambda: tm["tag_text"].split('\n'), tuple(["UKNOWN" for _ in range(4)]))
    except Exception as e:
        tm["name"], tm["handle"], tm["timestamp"] = tm["tag_text"], "ERR", "ERR"

    tm["tweet_text"] = ensures_or(lambda: tweet_dom.find_element(By.CSS_SELECTOR,'div[data-testid="tweetText"]').text)
    tm["retweet_count"] = ensures_or(lambda: tweet_dom.find_element(By.CSS_SELECTOR,'div[data-testid="retweet"]').text)
    tm["like_count"] = ensures_or(lambda: tweet_dom.find_element(By.CSS_SELECTOR,'div[data-testid="like"]').text)
    tm["reply_count"] = ensures_or(lambda: tweet_dom.find_element(By.CSS_SELECTOR,'div[data-testid="reply"]').text)
    tm["potential_boost"] = False
    return Tweet(**tm)

class TweetExtractor:
    """
    Generates Tweets from a page of tweets.
    Since tweets can occur in several types of pages, this is considered a helper.
    """

    def __init__(self, root_dir: str, max_captures: int = None):
        self.counter = 0
        self.last_id = 0
        self.last_id_count = 0
        self.prev_height = 0.0
        self.height_diffs = []
        self.div_track = set() # Used for tracking unique ids between tweet scraping.
        self.boosted_tracker = set() # Used for tracking boosted tweets by saving tweet texts.

        self.tweets_tracker = set()
        self.root_dir = root_dir
        self.max_captures = max_captures

    def get_scroll_offset_history(self) -> List[float]:
        """
        Returns a list of offset scrolls done by capture_all_available_tweets()
        which is proportional to the height of each tweet.
        """
        return self.height_diffs

    def write_json(self):
        with open(os.path.join(self.root_dir, "tweets.json"), "w", encoding="utf-8") as f:
            json.dump(self.get_tweets_as_dict(), f, ensure_ascii=False)

    def get_tweet(self, tweet_dom, driver: webdriver, fetch_threads: bool, load_time: int, offset_func: Callable) -> Tweet:
        # Lazy load because of circular dependencies.
        # this can be avoided if we pull out the logic at some point.
        from tb_watcher.pages import TwitterThread

        # Determine the id of the tweet by look at it in a separate window
        windows_before  = driver.current_window_handle
        try:
            action = webdriver.common.action_chains.ActionChains(driver)
            action.move_to_element_with_offset(tweet_dom, tweet_dom.size["width"] // 2, 5) \
                  .key_down(Keys.CONTROL) \
                  .click() \
                  .key_up(Keys.CONTROL) \
                  .perform()
        except selenium.common.exceptions.ElementClickInterceptedException:
            # It is okay for clicks to be intercepted.
            pass

        WebDriverWait(driver, 10).until(EC.number_of_windows_to_be(2))
        windows_after = driver.window_handles
        all_new_windows = [x for x in windows_after if x != windows_before]
        driver.switch_to.window(all_new_windows[0])

        # Clicking on a tweet guarantees it to be a TwitterThread page.
        tm = TwitterThread(self.root_dir, driver.current_url, existing_driver=driver).fetch_metadata()
        if tm.tweet_text != "NULL":
            if tm.tweet_text in self.boosted_tracker:
                # We need to go back in time to find the boosted post!
                # We match boosts by tweet text.
                for t in self.tweets_tracker:
                    if t.tweet_text == tm.tweet_text:
                        t.potential_boost = True
                        break

            tm.potential_boost = False
            self.boosted_tracker.add(tm.tweet_text)
        else:
            tm.potential_boost = False


        if fetch_threads:
            # TODO, save to file
            threads = tm.fetch_tweets(
                self.max_captures,
                self.load_time,
                self.offset_func
            )

        # Close all non-windows
        for n in all_new_windows:
            driver.switch_to.window(n)
            driver.close()

        driver.switch_to.window(windows_before)
        return tm

    def capture_all_available_tweets(self, driver: webdriver, fetch_threads: bool, load_time: int, offset_func: Callable) -> List[Tweet]:
        """
        Obtains post data at current scroll location of the driver and returns an instance of all available tweets.

        Args:
            driver (webdriver): Webdriver from which the scraping occurs.
            num_posts_to_cap (int): Number of posts to capture.

        Returns:
            [Tweet]: The tweet metadata.

        Raises:
            MaxCapturesReached: Total number of saved tweets have been met.
        """
        if self.max_captures and self.counter >= self.max_captures:
            raise MaxCapturesReached()

        tweets = driver.find_elements(By.CSS_SELECTOR, '[data-testid="tweet"]')
        for tweet in tweets:
            try:
                ad = remove_ads(driver)
                remove_elements(driver, ["sheetDialog", "confirmationSheetDialog", "mask"])
                if ad:
                    continue

                # To save potential duplicates, we check
                # first a unique id via tags to see if
                # we can skip prior to heavy post-processing.
                div_id = tweet.get_attribute("aria-labelledby")
                if div_id in self.div_track:
                    continue

                self.div_track.add(div_id)
                driver.execute_script("return arguments[0].scrollIntoView();", tweet)
                driver.execute_script("window.scrollTo(0, window.pageYOffset - 50);")
            except:
                continue

            # If there was no scroll while targeting the next element or the scroll is
            # smaller than the prior, then we hit a duplicate and we skip.
            height = float(driver.execute_script("return window.scrollTop || window.pageYOffset;"))
            if height < self.prev_height:
                continue
            self.height_diffs.append(height - self.prev_height)
            self.prev_height = height

            # Tweet info
            dtm = self.get_tweet(tweet, driver, fetch_threads, load_time, offset_func)
            # We've seen this post before
            if dtm in self.tweets_tracker:
                continue

            # Create a tweet's folder
            self.counter += 1
            self.tweets_tracker.add(dtm)

            if self.max_captures and self.counter > self.max_captures:
                break

    def get_tweets_as_dict(self) -> List[dict]:
        results = []
        for t in self.tweets_tracker:
            results.append(asdict(t))
        return results

    def create_offset_function(self, offset_func: Callable):
        return lambda: offset_func(self.height_diffs)

class Scroller:
    """
    Encapsulates a scrolling mechanism to generate more Tweets on a given page.
    Requires a data previous scrolls to do predictions.
    """
    def __init__(self, driver: webdriver, offset_func: Callable, load_time: int):
        self.prev_height = 0
        self.offset_func = offset_func
        self.driver = driver
        self.load_time = load_time
        self.height = 0

    def __iter__(self):
        self.prev_height = 0
        self.height = 0
        return self

    def __next__(self):
        predict_next_scroll = self.offset_func() + self.prev_height
        self.driver.execute_script("window.scrollTo(0, {});".format(predict_next_scroll))

        # Wait for data to load.
        time.sleep(random.uniform(self.load_time, self.load_time + 2))

        new_height = self.driver.execute_script("return document.body.scrollHeight")
        if new_height == self.prev_height:
            # We've  hit the end of the page
            raise StopIteration

        self.prev_height = new_height


def remove_elements(driver: webdriver , elements: List[str], remove_parent: bool = True):
    elements = ["'{}'".format(v) for v in elements]
    if remove_parent:
        # Some weird elements are better removing parent to
        # remove render artifacts.
        driver.execute_script("""
        const values = [{}];
        for (let i = 0; i < values.length; ++i) {{
            var element = document.querySelector(`[data-testid='${{values[i]}}']`);
            if (element)
                element.parentNode.parentNode.removeChild(element.parentNode);
        }}
        """.format(",".join(elements)))

    driver.execute_script("""
    const values = [{}];
    for (let i = 0; i < values.length; ++i) {{
        var element = document.querySelector(`[data-testid='${{values[i]}}']`);
        if (element)
            element.parentNode.removeChild(element);
    }}
    """.format(",".join(elements)))

def remove_ads(driver: webdriver) -> bool:
    return driver.execute_script("""
        var elems = document.querySelectorAll("*"),
            res = Array.from(elems).find(v => v.textContent == 'Promoted Tweet');

        if (res) {
            let p = res.parentNode.parentNode.parentNode;
            p.innerHTML="";
            return true;
        }
        return false;
    """)

def create_chrome_driver() -> webdriver:
    """Creates a chrome driver with silenced warnings and custom options."""
    options = webdriver.ChromeOptions()
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    return webdriver.Chrome(options=options, service=Service(ChromeDriverManager().install()))
