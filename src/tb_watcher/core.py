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
    fetch_threads: int,
    force: bool = False,
    number_posts_to_cap: int = DEF_NUM_TWEETS,
    bio_only: bool = False):
    """Primary driver of the program."""

    # We add one to the fetch_threads as we need to include the thread id themselves.
    twitter_bio = TwitterBio(fpath, url, fetch_threads=fetch_threads + 1, existing_driver=driver)
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
