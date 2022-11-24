"""
Helpers for Selenium driver.
By: ProgrammingIncluded
"""

# std
import os

from typing import List
from dataclasses import dataclass, asdict

# tb_watcher
from tb_watcher.logger import logger

# selenium
from selenium import webdriver
from selenium.webdriver.common.by import By

def ensures_or(f: str, otherwise: str = "NULL"):
    try:
        return f()
    except Exception as e:
        logger.debug("Could not obtain using {} instead. Error: {}".format(otherwise, str(e)))

    return otherwise

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

class MaxCapturesReached(RuntimeError):
    """The specified number of captures have been reached."""

class TweetExtractor:
    """
    Generates Tweets from a given post.
    """

    def __init__(self, tweets_path: str, max_captures: int = None):
        self.id_tracker = 0
        self.last_id = 0
        self.last_id_count = 0
        self.prev_height = 0.0
        self.height_diffs = []
        self.div_track = set() # Used for tracking unique ids between tweet scraping.
        self.boosted_tracker = set() # Used for tracking boosted tweets by saving tweet texts.

        self.tweets_tracker = set()
        self.tweets_path = tweets_path
        self.max_captures = max_captures

    def get_scroll_offset_history(self) -> List[float]:
        """
        Returns a list of offset scrolls done by capture_all_available_tweets()
        which is proportional to the height of each tweet.
        """
        return self.height_diffs

    def get_tweet(self, tweet_dom) -> Tweet:
        tm = {"id": self.id_tracker}
        tm["tag_text"] = ensures_or(lambda: tweet_dom.find_element(By.CSS_SELECTOR,'div[data-testid="User-Names"]').text)
        try:
            tm["name"], tm["handle"], _, tm["timestamp"] = ensures_or(lambda: tm["tag_text"].split('\n'), tuple(["UKNOWN" for _ in range(4)]))
        except Exception as e:
            tm["name"], tm["handle"], tm["timestamp"] = tm["tag_text"], "ERR", "ERR"
    
        tm["tweet_text"] = ensures_or(lambda: tweet_dom.find_element(By.CSS_SELECTOR,'div[data-testid="tweetText"]').text)
        tm["retweet_count"] = ensures_or(lambda: tweet_dom.find_element(By.CSS_SELECTOR,'div[data-testid="retweet"]').text)
        tm["like_count"] = ensures_or(lambda: tweet_dom.find_element(By.CSS_SELECTOR,'div[data-testid="like"]').text)
        tm["reply_count"] = ensures_or(lambda: tweet_dom.find_element(By.CSS_SELECTOR,'div[data-testid="reply"]').text)

        if tm["tweet_text"] != "NULL":
            if tm["tweet_text"] in self.boosted_tracker:
                # We need to go back in time to find the boosted post!
                # We match boosts by tweet text.
                for t in self.tweets_tracker:
                    if t.tweet_text == tm["tweet_text"]:
                        t.potential_boost = True
                        break

            tm["potential_boost"] = False
            self.boosted_tracker.add(tm["tweet_text"])
        else:
            tm["potential_boost"] = False

        return Tweet(**tm)

    def capture_all_available_tweets(self, driver: webdriver) -> List[Tweet]:
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
        if self.max_captures and self.id_tracker >= self.max_captures:
            raise MaxCapturesReached()

        tweets = driver.find_elements(By.CSS_SELECTOR, '[data-testid="tweet"]')
        for tweet in tweets:
            try:
                ad = remove_ads(driver)
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
            dtm = self.get_tweet(tweet)
            # We've seen this post before
            if dtm in self.tweets_tracker:
                continue

            try:
                # Try to remove elements before screenshot
                remove_elements(driver, ["sheetDialog", "confirmationSheetDialog", "mask"])
                tweet.screenshot(os.path.join(self.tweets_path, "{}.png".format(self.id_tracker)))
            except Exception as e:
                # Failure to screenshot maybe because the tweet is too stale. Skip for now.
                continue

            self.id_tracker += 1
            self.tweets_tracker.add(dtm)

            if self.max_captures and self.id_tracker > self.max_captures:
                break

    def get_tweets_as_dict(self) -> List[dict]:
        results = []
        for t in self.tweets_tracker:
            results.append(asdict(t))
        return results

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
