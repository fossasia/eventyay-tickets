#!/bin/env python3
import os
import subprocess

from twitter_ads.client import Client
from twitter_ads.creative import DraftTweet
from twitter_ads.restapi import UserIdLookup

CONSUMER_KEY = os.environ.get("TWITTER_CONSUMER_KEY")
CONSUMER_SECRET_KEY = os.environ.get("TWITTER_CONSUMER_SECRET_KEY")
ACCESS_TOKEN = os.environ.get("TWITTER_ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET")
ADS_ACCOUNT_ID = os.environ.get("TWITTER_ADS_ACCOUNT_ID")


def get_diff_lines():
    result = subprocess.check_output(
        "git diff -U0 ../../doc/changelog.rst", shell=True
    ).decode()
    return [d for d in result.split("\n")[5:] if d]


def get_new_features(diff_lines):
    result = []
    for line in diff_lines:
        if line.startswith("+- :feature:`"):
            result.append(line.split("`", maxsplit=2)[-1].strip())
    return result


def post_draft_tweet(text):
    print(f"Attempting to post draft tweet: {text}")
    client = Client(
        CONSUMER_KEY, CONSUMER_SECRET_KEY, ACCESS_TOKEN, ACCESS_TOKEN_SECRET
    )
    account = client.accounts(ADS_ACCOUNT_ID)
    user_id = UserIdLookup.load(account, screen_name="pretalx").id
    draft_tweet = DraftTweet(account)
    draft_tweet.text = text[:240]
    draft_tweet.as_user_id = user_id
    draft_tweet = draft_tweet.save()
    print(draft_tweet.id_str)
    print(draft_tweet.text)


def main():
    diff_lines = get_diff_lines()
    new_features = get_new_features(diff_lines)
    for feature in new_features:
        post_draft_tweet(feature)


if __name__ == "__main__":
    main()
