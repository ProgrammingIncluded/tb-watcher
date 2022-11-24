"""
BTWatcher snapshots a profile page when given a URL or an exported list of `following` from the official Twitter exporter.
By: ProgrammingIncluded
"""

import re
import os
import sys
import json
import argparse

# Load the source root directory
FILE_PATH = os.path.dirname(__file__)
SRC_ROOT = os.path.join(FILE_PATH, os.pardir, "src")
sys.path.append(SRC_ROOT)

# tb_watcher
import tb_watcher.swag as swag

from tb_watcher.core import fetch_html
from tb_watcher.logger import logger 
from tb_watcher.driver_utils import create_chrome_driver
from tb_watcher.math_utils import calc_average_percentile, window_average, constant

# selenium
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


def parse_args():
    parser = argparse.ArgumentParser(description="Twitter Bird Watcher. Taking a snapshot of a Twitter Profile.")

    runtime_group = parser.add_argument_group("runtime states")
    runtime_group.add_argument("--force", "-f", help="Force re-download everything. WARNING, will delete outputs.", action="store_true")
    runtime_group.add_argument("--posts", "-p", help="Max number of posts to screenshot.", default=20, type=int)
    runtime_group.add_argument("--bio-only", "-b", help="Only store bio, no snapshots of tweets.", action="store_true")
    runtime_group.add_argument("--debug", help="Print debug output.", action="store_true")

    verification_group = parser.add_argument_group("verification")
    verification_group.add_argument("--login", help="Prompt user login to remove limits / default filters. USE AT OWN RISK.", action="store_true")

    scroll_group = parser.add_argument_group("scrolling related")
    scroll_group.add_argument("--scroll-load-time", "-s", help="Number of seconds (float). The higher, the stabler the fetch.", default=5, type=int)
    scroll_group.add_argument("--scroll-algorithm", help="Type of algorithm to calculate scroll offset.", choices=["percentile", "window", "constant"], default="window")
    scroll_group.add_argument("--scroll-value", default=5, type=float, help=("Value used by --scroll-algorithm."
                                                                        "If percentile, percentage of percentile calculated. "
                                                                        "If window, the size of window average."
                                                                        "If constant, size of pixel to scroll by."))

    group = parser.add_mutually_exclusive_group()
    group.add_argument("--input-json", "-i", help="Input json file", default="input.json")
    group.add_argument("--url", "-u", help="Specify a profile url directly.")

    group.add_argument("--output_fpath", "-o", help="Output folder to generate results.", default="snapshots")
    return parser.parse_args()

def main():
    args = parse_args()

    print(swag.LOGO)
    print(swag.TITLE)

    logger.info("Initializing...")
    # Create output folder if DNE.
    os.makedirs(args.output_fpath, exist_ok=True)

    extra_args = {
        "force": args.force,
        "bio_only": args.bio_only,
        "load_times": args.scroll_load_time,
        "number_posts_to_cap": args.posts
    }

    args.output_fpath = args.output_fpath.strip()

    if args.debug:
        logger.setLevel(logger.DEBUG)
        logger.debug("Debug mode set.")

    # Select a scrolling algorithm before starting any drivers.
    f = None
    if args.scroll_algorithm == "percentile":
        assert args.scroll_value <= 1.0 and args.scroll_value >= 0.0
        f = calc_average_percentile(args.scroll_value)
    elif args.scroll_algorithm == "window":
        f = window_average(args.scroll_value)
    else:
        f = constant(args.scroll_value)

    extra_args["offset_func"] = f

    driver = create_chrome_driver()
    if args.login:
        driver.get("https://twitter.com/login")
        input("Please logging then press any key in CLI to continue...")

    data = []
    if args.url:
        logger.info("Watching: {}".format(args.url))
        fetch_html(driver, args.url, fpath=args.output_fpath, **extra_args)
    else:
        weird_opening = "window\..* = (\[[\S\s]*)"
        with open(args.input_json) as f:
            txt = f.read()
            match = re.match(weird_opening, txt)

            if match and match.group(1):
                txt = match.group(1)

            # Remove the first line metadata
            data = json.loads(txt)
    
        for d in data:
            account = d["following"]
            url = account["userLink"]
            logger.info("Watching: {}".format(url))
            fetch_html(driver, url, fpath=args.output_fpath, **extra_args)

    logger.info("ALL SNAPSHOTS COMPLETED!")

if __name__ == "__main__":
    main()
