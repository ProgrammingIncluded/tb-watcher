# CHANGELOG: Twitter Bird Watcher

## Guiding Principles

* Changelogs are for humans.
* This changelog attempts to adhere to [Keep a Changlog](https://keepachangelog.com/en/1.0.0/)
* Our project uses [Semantic Versioning](https://semver.org/)
* Contributions by community will be credited via their userhandle.

### Types of Changes

* `Added` for new features.
* `Changed` for changes in existing functionality.
* `Deprecated` for soon-to-be removed features.
* `Removed` for now removed features.
* `Fixed` for any bug fixes.
* `Security` in case of vulnerabilities.

# Changes

## 0.6.0: Twitter Thread Support

* Added `--depth` and `-d` for archiving threads.
* Added `TwitterPageInterface` used for representing a page in Twitter.
* Added `TwitterBio` which is used for fetching and obtaining bio pages.
* Added `TweetFetcher` which attempts to fetch all available Tweets on a page.
* Added `Scroller` which abstracts away scrolling metrics.
* Changed random messages from ChromeDriver, makes logs cleaner.
* Fixed potential for some posts to be skipped on ad removal.
* Fixed logger not outputting any info.
* Fixed logger not printing debug.

## 0.5.0: Supporting Our Community

* Added modularization of code in `src/`.
* Added binaries in `bin/`.
* Changed project name from `BirdWatch` -> `Twitter Bird Watcher` (`TBWatcher`)
* Added better logging support via `logging` module.
* Added standardization for CHANGELOG.
* Added better CLI help groups.
* Fixed README Typos and Divide by Zero Error (@jmallone).

## 0.4.0: More Algorithms

* Added example README.
* Changed README.
* Added scroll algorithm selection.

## 0.3.0: Remove Ads and Average Scrolling

* Added average scrolling to compensate for scroll heights.
* Added Ad removal logic.
* Fixed bug where post length was not respected.

## 0.2.0: Enable Login and New Scroll Method

* Added `--login` for giving users login.
* Added new aglorithm for scrolling down content to prevent duplications.

## 0.1.1: Better Folder Renames

* Added some code-cleanup.
* Added better pop-up removal support.
* Added `--url` support for single profile scraping.
* Added folder renaming to username functionality.
* Added tweet without login limit check.
* Added faster scrolling for centering content.

## 0.1.0: Initial Release

* Added support for bio-only.
* Added snapshots of Twitter posts.
* Added max Twitter info.
