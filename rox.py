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
    "ppv",
]

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
HEADERS = {"User-Agent": USER_AGENT, "Referer": BASE_URL}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)
TIMEOUT = 20

OUTPUT_VLC = "Roxiestreams_VLC.m3u8"
OUTPUT_TIVIMATE = "Roxiestreams_TiviMate.m3u8"

# Match ALL possible getRandomStream calls
STREAM_REGEX = re.compile(
    r"getRandomStream\s*\(\s*['\"]([^'\"]+\.m3u8)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)",
    re.IGNORECASE
)

visited_pages = set()
found_streams = set()
domains = []

# ---------------------------
# TV Info / Categories
# ---------------------------

TV_INFO = {
    "soccer": ("Soccer.Dummy.us", "https://i.postimg.cc/HsWHFvV0/Soccer.png", "Soccer"),
    "mlb": ("MLB.Baseball.Dummy.us", "https://i.postimg.cc/FsFmwC7K/Baseball3.png", "MLB"),
    "nba": ("NBA.Basketball.Dummy.us", "https://i.postimg.cc/jdqKB3LW/Basketball-2.png", "NBA"),
    "nfl": ("Football.Dummy.us", "https://i.postimg.cc/tRNpSGCq/Maxx.png", "NFL"),
    "nhl": ("NHL.Hockey.Dummy.us", "https://i.postimg.cc/mgMRQ7FR/nhl-logo-png-seeklogo-534236.png", "NHL"),
    "fighting": ("PPV.EVENTS.Dummy.us", "https://i.postimg.cc/8c4GjMnH/Combat-Sports.png", "Combat Sports"),
    "motorsports": ("Racing.Dummy.us", "https://i.postimg.cc/yY6B2pkv/F1.png", "Motorsports"),
    "ufc": ("UFC.Fight.Pass.Dummy.us", "https://i.postimg.cc/59Sb7W9D/Combat-Sports2.png", "UFC"),
    "ppv": ("PPV.EVENTS.Dummy.us", "https://i.postimg.cc/mkj4tC62/PPV.png", "PPV"),
    "wwe-streams": ("PPV.EVENTS.Dummy.us", "https://i.postimg.cc/wTxHn47J/WWE2.png", "WWE"),
    "f1": ("Racing.Dummy.us", "https://i.postimg.cc/yY6B2pkv/F1.png", "Formula 1"),
    "f1-streams": ("Racing.Dummy.us", "https://i.postimg.cc/yY6B2pkv/F1.png", "Formula 1"),
    "nascar": ("Racing.Dummy.us", "https://i.postimg.cc/m2dR43HV/Motorsports2.png", "NASCAR Cup Series"),
    "misc": ("Sports.Dummy.us", "https://i.postimg.cc/qMm0rc3L/247.png", "Random Events"),
}

# ---------------------------
# Domains Loader
# ---------------------------

def load_domains():
    global domains
    print("Loading domains...")
    try:
        r = SESSION.get(DOMAINS_URL, timeout=TIMEOUT)
        r.raise_for_status()
        domains = [d.strip() for d in r.text.splitlines() if d.strip()]
        print(f"Loaded {len(domains)} domains")
    except Exception as e:
        print(f"❌ Failed to load domains: {e}")
        domains = []

# ---------------------------
# Fetch page safely
# ---------------------------

def fetch(url):
    try:
        r = SESSION.get(url, timeout=TIMEOUT)
        if r.status_code != 200:
            return None, None
        soup = BeautifulSoup(r.text, "html.parser")
        return soup, r.text
    except:
        return None, None

# ---------------------------
# Clean title
# ---------------------------

def clean_title(title):
    if not title:
        return ""
    title = html.unescape(title)
    title = re.sub(r"\s+", " ", title)
    title = re.sub(r"Watch.*$", "", title, flags=re.I)
    title = re.sub(r"Roxiestreams.*$", "", title, flags=re.I)
    return title.strip(" -|")

# ---------------------------
# Build ALL possible stream URLs
# ---------------------------

def build_stream_urls(stream_path, subdomain):
    return [f"https://{subdomain}.{domain}/{stream_path}" for domain in domains]

# ---------------------------
# Extract streams from ONE event page
# ---------------------------

def extract_streams_from_event(url):
    if url in visited_pages:
        return []
    visited_pages.add(url)
    soup, html_text = fetch(url)
    if not soup:
        return []
    title = clean_title(soup.title.text) if soup.title else ""
    results = []
    matches = STREAM_REGEX.findall(html_text)
    for stream_path, subdomain in matches:
        urls = build_stream_urls(stream_path, subdomain)
        for stream_url in urls:
            if stream_url not in found_streams:
                found_streams.add(stream_url)
                results.append((title, stream_url))
                print(f"Found stream: {title} -> {stream_url}")
    return results

# ---------------------------
# Crawl category pages
# ---------------------------

def crawl_category(category):

    url = urljoin(BASE_URL, category)

    print("Scanning category:", url)

    soup, html_text = fetch(url)

    if not soup:
        return []

    links = []

    for a in soup.find_all("a", href=True):

        href = urljoin(url, a["href"])

        if href.startswith(BASE_URL) and href != url:

            links.append((href, category if category else "misc"))

    print("Found", len(links), "event pages")

    return links

# ---------------------------
# Get TV info for category
# ---------------------------

def get_tv_info(category):
    key = category.lower() if category else "misc"
    return TV_INFO.get(key, TV_INFO["misc"])

# ---------------------------
# Write playlist
# ---------------------------

def write_playlist(streams, categories_map):
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    header = "#EXTM3U\n# Generated {}\n\n".format(timestamp)
    ua_enc = quote(USER_AGENT)

    with open(OUTPUT_VLC, "w", encoding="utf-8") as f:
        f.write(header)
        for title, url, cat in streams:
            tvg_id, logo, group_name = get_tv_info(cat)
            f.write(f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-logo="{logo}" group-title="{group_name}",{title}\n')
            f.write(f'{url}\n\n')

    with open(OUTPUT_TIVIMATE, "w", encoding="utf-8") as f:
        f.write(header)
        for title, url, cat in streams:
            tvg_id, logo, group_name = get_tv_info(cat)
            f.write(f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-logo="{logo}" group-title="{group_name}",{title}\n')
            f.write(f'{url}|referer={BASE_URL}|user-agent={ua_enc}\n\n')

# ---------------------------
# MAIN
# ---------------------------

def main():

    print("▶️ Starting RoxieStreams playlist generation...")
    load_domains()

    all_event_pages = []

    for cat in CATEGORIES:

        pages = crawl_category(cat)

        all_event_pages.extend(pages)

        time.sleep(0.5)

    print(f"\nTotal event pages: {len(all_event_pages)}")

    all_streams = []

    for page, category in all_event_pages:

        streams = extract_streams_from_event(page)

        for title, url in streams:

            all_streams.append((title or "RoxieStream", url, category))

    print(f"\nTotal streams found: {len(all_streams)}")

    write_playlist(all_streams)

    print("✅ Playlists saved successfully.")


if __name__ == "__main__":
    main()
