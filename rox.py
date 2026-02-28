#!/usr/bin/env python3

import re
import html
import time
from urllib.parse import urljoin, quote
from datetime import datetime

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://roxiestreams.info/"
DOMAINS_URL = "https://roxiestreams.info/domains.txt"

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

TIMEOUT = 20

OUTPUT_VLC = "roxiestreams_all.m3u8"
OUTPUT_TIVIMATE = "roxiestreams_all_tivimate.m3u8"


# Match ALL possible getRandomStream calls
STREAM_REGEX = re.compile(
    r"getRandomStream\s*\(\s*['\"]([^'\"]+\.m3u8)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)",
    re.IGNORECASE
)


visited_pages = set()
found_streams = set()
domains = []


# --------------------------------------------------
# Load domains from website
# --------------------------------------------------

def load_domains():

    global domains

    print("Loading domains...")

    r = SESSION.get(DOMAINS_URL, timeout=TIMEOUT)

    domains = [d.strip() for d in r.text.splitlines() if d.strip()]

    print("Loaded", len(domains), "domains")


# --------------------------------------------------
# Fetch page safely
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
# Build ALL possible stream URLs
# --------------------------------------------------

def build_stream_urls(stream_path, subdomain):

    urls = []

    for domain in domains:

        urls.append(f"https://{subdomain}.{domain}/{stream_path}")

    return urls


# --------------------------------------------------
# Extract streams from ONE event page
# --------------------------------------------------

def extract_streams_from_event(url):

    if url in visited_pages:
        return []

    visited_pages.add(url)

    soup, html_text = fetch(url)

    if not soup:
        return []

    title = ""

    if soup.title:
        title = clean_title(soup.title.text)

    results = []

    matches = STREAM_REGEX.findall(html_text)

    for stream_path, subdomain in matches:

        urls = build_stream_urls(stream_path, subdomain)

        for stream_url in urls:

            if stream_url not in found_streams:

                found_streams.add(stream_url)

                print("Found stream:", stream_url)

                results.append((title, stream_url))

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

    links = set()

    for a in soup.find_all("a", href=True):

        href = urljoin(url, a["href"])

        if href.startswith(BASE_URL):

            if href != url:
                links.add(href)

    print("Found", len(links), "event pages")

    return links


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

            f.write(f'#EXTINF:-1 group-title="RoxieStreams",{title}\n')
            f.write(f'{url}\n\n')


    with open(OUTPUT_TIVIMATE, "w", encoding="utf-8") as f:

        f.write(header)

        for title, url in streams:

            f.write(f'#EXTINF:-1 group-title="RoxieStreams",{title}\n')
            f.write(f'{url}|referer={BASE_URL}|user-agent={ua_enc}\n\n')


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():

    print("Starting RoxieStreams scraper")

    load_domains()

    all_event_pages = set()

    for cat in CATEGORIES:

        pages = crawl_category(cat)

        all_event_pages |= pages

        time.sleep(0.5)


    print("\nTotal event pages:", len(all_event_pages))

    all_streams = []

    for page in all_event_pages:

        streams = extract_streams_from_event(page)

        all_streams.extend(streams)


    print("\nTotal streams found:", len(all_streams))

    write_playlist(all_streams)

    print("Playlist saved successfully")


if __name__ == "__main__":
    main()
