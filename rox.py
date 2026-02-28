#!/usr/bin/env python3

import re
import html
import time
from urllib.parse import urljoin, urlparse, quote
from datetime import datetime

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://roxiestreams.info/"

CATEGORIES = [
    "",
    "soccer",
    "nba",
    "nfl",
    "mlb",
    "nhl",
    "fighting",
    "ufc",
    "wwe-streams",
    "f1",
    "nascar",
    "motorsports",
    "ppv-streams-1",
    "ppv-streams-2"
]

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
HEADERS = {
    "User-Agent": USER_AGENT,
    "Referer": BASE_URL
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

TIMEOUT = 15

OUTPUT_VLC = "roxiestreams_all.m3u8"
OUTPUT_TIVIMATE = "roxiestreams_all_tivimate.m3u8"

M3U8_REGEX = re.compile(r"https?://[^\"'\s<>]+\.m3u8[^\"'\s<>]*", re.IGNORECASE)

visited_pages = set()
found_streams = set()


# --------------------------------------------------
# Fetch page
# --------------------------------------------------

def fetch(url):

    try:

        r = SESSION.get(url, timeout=TIMEOUT)

        if r.status_code != 200:
            return None, None

        soup = BeautifulSoup(r.text, "html.parser")

        return soup, r.text

    except:
        return None, None


# --------------------------------------------------
# Clean title
# --------------------------------------------------

def clean_title(title):

    if not title:
        return ""

    title = html.unescape(title)

    title = re.sub(r"\s+", " ", title)

    title = re.sub(r"Watch.*$", "", title, flags=re.I)

    title = re.sub(r"Roxiestreams.*$", "", title, flags=re.I)

    return title.strip(" -|")


# --------------------------------------------------
# Extract streams from text
# --------------------------------------------------

def extract_streams_from_text(text):

    streams = set()

    matches = M3U8_REGEX.findall(text)

    for m in matches:

        streams.add(m.strip())

    return streams


# --------------------------------------------------
# Crawl iframe recursively
# --------------------------------------------------

def crawl_iframe(url, depth=0):

    if depth > 3:
        return set()

    soup, html = fetch(url)

    if not soup:
        return set()

    streams = extract_streams_from_text(html)

    for iframe in soup.find_all("iframe", src=True):

        iframe_url = urljoin(url, iframe["src"])

        streams |= crawl_iframe(iframe_url, depth+1)

    return streams


# --------------------------------------------------
# Extract streams from event page
# --------------------------------------------------

def extract_streams_from_event(url):

    if url in visited_pages:
        return []

    visited_pages.add(url)

    soup, html = fetch(url)

    if not soup:
        return []

    title = ""

    if soup.title:
        title = clean_title(soup.title.text)

    streams = set()

    # direct matches
    streams |= extract_streams_from_text(html)

    # video/source tags
    for tag in soup.find_all(["video", "source"]):

        src = tag.get("src")

        if src and ".m3u8" in src:
            streams.add(src)

    # iframe streams
    for iframe in soup.find_all("iframe", src=True):

        iframe_url = urljoin(url, iframe["src"])

        streams |= crawl_iframe(iframe_url)

    results = []

    for s in streams:

        results.append((title, s))

    return results


# --------------------------------------------------
# Crawl category pages
# --------------------------------------------------

def crawl_category(category):

    url = urljoin(BASE_URL, category)

    print("Scanning category:", url)

    soup, html = fetch(url)

    if not soup:
        return []

    event_pages = set()

    for a in soup.find_all("a", href=True):

        href = urljoin(url, a["href"])

        if BASE_URL not in href:
            continue

        if any(x in href for x in CATEGORIES):
            if href.rstrip("/") == url.rstrip("/"):
                continue

        event_pages.add(href)

    print("Found", len(event_pages), "event links")

    return event_pages


# --------------------------------------------------
# Write playlist
# --------------------------------------------------

def write_playlist(streams):

    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    header = "#EXTM3U\n# Generated {}\n\n".format(timestamp)

    ua_enc = quote(USER_AGENT)


    with open(OUTPUT_VLC, "w", encoding="utf-8") as f:

        f.write(header)

        for title, url in streams:

            f.write(f'#EXTINF:-1,{title}\n')

            f.write(f'{url}\n\n')


    with open(OUTPUT_TIVIMATE, "w", encoding="utf-8") as f:

        f.write(header)

        for title, url in streams:

            f.write(f'#EXTINF:-1,{title}\n')

            f.write(f'{url}|referer={BASE_URL}|user-agent={ua_enc}\n\n')


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():

    print("Starting Roxiestreams scraper...")

    all_event_pages = set()

    for cat in CATEGORIES:

        pages = crawl_category(cat)

        all_event_pages |= pages

        time.sleep(1)


    print("\nTotal event pages:", len(all_event_pages))

    all_streams = []


    for page in all_event_pages:

        streams = extract_streams_from_event(page)

        for title, url in streams:

            if url not in found_streams:

                found_streams.add(url)

                all_streams.append((title, url))

                print("Found stream:", title)


    print("\nTotal streams found:", len(all_streams))

    write_playlist(all_streams)

    print("Playlist saved.")


if __name__ == "__main__":
    main()
