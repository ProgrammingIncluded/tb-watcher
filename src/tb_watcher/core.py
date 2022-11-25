"""
Houses the main logic for fetching data and interfacing with Selenium.
By: ProgrammingIncluded
"""
# std
from typing import Callable

# bluebird watcher
from tb_watcher.logger import logger
from tb_watcher.pages import TwitterBio

# selenium
from selenium import webdriver

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
    twitter_bio = TwitterBio(fpath, url, auto_fetch_threads=True, existing_driver=driver)
    twitter_bio.fetch_metadata()
    if not twitter_bio.write_json(force=force):
        return
    elif bio_only:
        return

    # Create tweets folder
    twitter_bio.fetch_tweets(
        number_posts_to_cap,
        load_times,
        offset_func,
    )
