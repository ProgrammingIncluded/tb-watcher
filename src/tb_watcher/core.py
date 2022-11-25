"""
Houses the main logic for fetching data and interfacing with Selenium.
By: ProgrammingIncluded
"""
# std
import time

from typing import Callable

# bluebird watcher
from tb_watcher.logger import logger
from tb_watcher.pages import TwitterBio
from tb_watcher.threading import spawn_threads, threads_done, BUSY_LOCK, get_job, BUSY_THREADS

# selenium
from selenium import webdriver

def fetch_html(
    driver: webdriver,
    url: str,
    fpath: str,
    load_times: float,
    offset_func: Callable,
    fetch_threads: int,
    force: bool = False,
    number_posts_to_cap: int = 20,
    bio_only: bool = False,
    num_threads: int = 4):
    """Primary driver of the program."""

    spawn_threads(num_threads)

    # We add one to the fetch_threads as we need to include the thread id themselves.
    twitter_bio = TwitterBio(fpath, url, fetch_threads=fetch_threads, existing_driver=driver)
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

    driver.close()
    # Wait for any remaining pending jobs
    while not threads_done():
        time.sleep(1)

    # Daemon threads will terminate when main thread is terminated.
    logger.info("All jobs finished! Terminating main thread.")
