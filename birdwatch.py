"""
Birdwatch snapshots a profile page when given a URL or an exported list of `following` from the official Twitter exporter.

Many thanks to: https://www.scrapingbee.com/blog/web-scraping-twitter/
for the inspiration.

Major adjustments to make UX a lot smoother.
"""
import re
import os
import json
import uuid
import glob
import urllib.parse as urlp
import argparse
import shutil
import time

from random import randint
from dataclasses import dataclass

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import WebDriverException

SCRAPE_N_TWEETS = 20

@dataclass(init=True, repr=True, unsafe_hash=True)
class Tweet:
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

def ensures_or(f, otherwise="NULL"):
    try:
        return f()
    except Exception as e:
        print("Could not obtain using {} instead. Error: {}".format(otherwise, str(e)))

    return otherwise

def remove_elements(driver, elements):
    elements = ["'{}'".format(v) for v in elements]
    driver.execute_script("""
    const values = [{}];
    for (let i = 0; i < values.length; ++i) {{
        var element = document.querySelector(`[data-testid='${{values[i]}}']`);
        if (element)
            element.parentNode.removeChild(element);
    }}
    """.format(",".join(elements)))

def fetch_html(driver, url, fpath, force=False, number_posts_to_cap=SCRAPE_N_TWEETS, bio_only=False):
    if not force and os.path.exists(fpath):
        return
    elif force:
        shutil.rmtree(fpath)

    os.makedirs(fpath)

    driver.get(url)
    state = ""
    while state != "complete":
        print("loading not complete")
        time.sleep(randint(3, 5))
        state = driver.execute_script("return document.readyState")

    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, '[data-testid="tweet"]')))
    except WebDriverException:
        print("Tweets did not appear!, Try setting headless=False to see what is happening")

    # Remove initial popups.
    remove_elements(driver, ["sheetDialog", "mask"])

    # delete bottom element
    remove_elements(driver, ["BottomBar"])

    metadata = {}
    metadata["bio"] = ensures_or(lambda: driver.find_element(By.CSS_SELECTOR,'div[data-testid="UserDescription"]').text)
    metadata["name"], metadata["username"] = ensures_or(lambda: driver.find_element(By.CSS_SELECTOR,'div[data-testid="UserName"]').text.split('\n'), ("NULL", "NULL"))
    metadata["location"] = ensures_or(lambda: driver.find_element(By.CSS_SELECTOR,'span[data-testid="UserLocation"]').text)
    metadata["website"] = ensures_or(lambda: driver.find_element(By.CSS_SELECTOR,'a[data-testid="UserUrl"]').text)
    metadata["join_date"] = ensures_or(driver.find_element(By.CSS_SELECTOR,'span[data-testid="UserJoinDate"]').text)
    metadata["following"] = ensures_or(driver.find_element(By.XPATH, "//span[contains(text(), 'Following')]/ancestor::a/span").text) 
    metadata["followers"] = ensures_or(driver.find_element(By.XPATH, "//span[contains(text(), 'Followers')]/ancestor::a/span").text)

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
    try:
        last_height = 0
        new_height = 0
        while True:
            if id_tracker >= number_posts_to_cap - 1:
                break
            elif last_id_count > 5:
                print("No more data to load?")
                break

            if last_id == id_tracker:
                last_id_count += 1
            else:
                last_id = id_tracker
                last_id_count = 0

            tweets = driver.find_elements(By.CSS_SELECTOR, '[data-testid="tweet"]')
            for tweet in tweets:
                # Try to scroll there first.
                driver.execute_script("return arguments[0].scrollIntoView();", tweet)
                time.sleep(1)
                driver.execute_script("window.scrollTo(0, window.pageYOffset - 50);")

                tm = {"id": id_tracker}
                tm["tag_text"] = ensures_or(lambda: tweet.find_element(By.CSS_SELECTOR,'div[data-testid="User-Names"]').text)
                try:
                    tm["name"], tm["handle"], _, tm["timestamp"] = ensures_or(lambda: tm["tag_text"].split('\n'), tuple(["UKNOWN" for _ in range(4)]))
                except Exception as e:
                    print("Unable to unpack name values. {}".format(e))
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
                    remove_elements(driver, ["sheetDialog", "mask"])
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
            # Scroll down to bottom
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    
            # Wait to load page
            time.sleep(randint(2, 4))
    
            # Calculate new scroll height and compare with last scroll height
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
    except Exception as e:
        raise e
    finally:
        # Dump all metadata
        with open(os.path.join(tweets_path, "tweets.json"), "w", encoding="utf-8") as f:
            json.dump(tweets_metadata, f, ensure_ascii=False)

def parse_args():
    parser = argparse.ArgumentParser(description="Process Twitter Account Metadata")
    parser.add_argument("--force", "-f", help="Force re-download everything. WARNING, will delete outputs.", action="store_true")
    parser.add_argument("--posts", "-p", help="Max number of posts to screenshot.", default=SCRAPE_N_TWEETS)
    parser.add_argument("--bio-only", "-b", help="Only store bio, no snapshots or tweets.", action="store_true")
    parser.add_argument("--disable-folder-rename", help="Disable the extra post-processing where folders are renamed to user-names. Useful for permissions issues.", action="store_true")

    group = parser.add_mutually_exclusive_group()
    group.add_argument("--input-json", "-i", help="Input json file", default="input.json")
    group.add_argument("--url", "-u", help="Specify a profile url directly.")
    return parser.parse_args()

def main():
    args = parse_args()
    output_folder = "snapshots"
    os.makedirs(output_folder, exist_ok=True)

    data = []
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    extra_args = {"force": args.force, "bio_only": args.bio_only}
    if args.url:
        path = urlp.urlparse(args.url).path
        filename = os.path.split(path)[-1]
        fetch_html(driver, args.url, fpath=os.path.join(output_folder, filename), **extra_args)
    else:
        weird_opening = "window\..* = (\[[\S\s]*)"
        with open(args.input_json) as f:
            txt = f.read()
            match = re.match(weird_opening, txt)
            if match.group(1):
                txt = match.group(1)
            # Remove the first line metadata
            data = json.loads(txt)
    
        for d in data:
            account = d["following"]
            fetch_html(driver, account["userLink"], fpath=os.path.join(output_folder, account["accountId"]), **extra_args)

    if not args.disable_folder_rename:
        all_folders = list(glob.glob(os.path.join(output_folder, "*")))
        all_folder_names = [os.path.split(fpath)[-1] for fpath in all_folders]
        for idx, fpath in enumerate(all_folders):
            cur_folder_path, cur_folder_name = os.path.split(fpath)

            # Check each metadata
            username = None
            with open(os.path.join(fpath, "metadata.json"), encoding="utf-8") as f:
                d = json.load(f)
                username = d["username"]

            if username.startswith("@"):
                username = username[1:]

            if username == cur_folder_name:
                print("Folder already properly named, skipping.")
                continue
            elif username in (all_folder_names[:idx] + all_folder_names[idx + 1:]):
                print("Folder already exists with this user, adding extra uuid.")
                username += str(uuid.uuid4())

            os.rename(fpath, os.path.join(cur_folder_path, username))

if __name__ == "__main__":
    main()
