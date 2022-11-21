# Birdwatch: A Twitter Profile Snapshot Tool

Birdwatch snapshots a profile page when given a URL or an exported list of `following` from the official Twitter exporter.
This script is purely for the purposes of archival use-only.

**Note, without logging in, you can only fetch a few posts from the profile.**

## Usage

```bash
python -m pip install -r requirements.py
python birdwatch.py

# For more help use:
python birdwatch.py --help
```

### Output

Birdwatch generates the following in the snapshots folder:

```
└───snapshots
    └───<user_id>           # Username
        │   metadata.json   # profile metadata
        │   profile.png     # snapshot of profile page
        │
        └───tweets
                0.png       # snapshot of latest tweet
                1.png
                ...
                9.png
                tweets.json # Metadata of each screen-capped tweet.
```
