#!/usr/bin/env python3

import re
import html
import time
from urllib.parse import urljoin, quote
from datetime import datetime

import requests
from bs4 import BeautifulSoup
#!/usr/bin/env python3

import re
import html
import time
from urllib.parse import urljoin, urlparse, quote
from datetime import datetime
import requests
from bs4 import BeautifulSoup

# ---------------------------
# Configuration
# ---------------------------

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
HEADERS = {"User-Agent": USER_AGENT, "Referer": BASE_URL}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)
TIMEOUT = 15

OUTPUT_VLC = "Roxiestreams_VLC.m3u8"
OUTPUT_TIVIMATE = "Roxiestreams_TiviMate.m3u8"

M3U8_REGEX = re.compile(r"https?://[^\"'\s<>]+\.m3u8[^\"'\s<>]*", re.IGNORECASE)

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
    "ppv-streams-1": ("PPV.EVENTS.Dummy.us", "https://i.postimg.cc/mkj4tC62/PPV.png", "PPV"),
    "ppv-streams-2": ("PPV.EVENTS.Dummy.us", "https://i.postimg.cc/mkj4tC62/PPV.png", "PPV"),
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
    try:
        with open("domains.txt", "r", encoding="utf-8") as f:
            domains = [d.strip() for d in f.readlines() if d.strip()]
            print(f"✅ Loaded {len(domains)} domains from local file.")
            return
    except FileNotFoundError:
        print("Local domains.txt not found, fetching from RoxieStreams...")

    try:
        url = "https://roxiestreams.info/domains.txt"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        domains = [d.strip() for d in r.text.splitlines() if d.strip()]
        print(f"✅ Loaded {len(domains)} domains from {url}")
    except Exception as e:
        print(f"❌ Failed to load domains: {e}")
        domains = []

# ---------------------------
# Utility functions
# ---------------------------

def fetch(url):
    try:
        r = SESSION.get(url, timeout=TIMEOUT)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        return soup, r.text
    except:
        return None, None

def clean_title(title):
    if not title:
        return ""
    title = html.unescape(title)
    title = re.sub(r"\s+", " ", title)
    title = re.sub(r"Watch.*$", "", title, flags=re.I)
    title = re.sub(r"Roxiestreams.*$", "", title, flags=re.I)
    return title.strip(" -|")

def extract_streams_from_text(text):
    streams = set()
    matches = M3U8_REGEX.findall(text)
    for m in matches:
        streams.add(m.strip())
    return streams

def crawl_iframe(url, depth=0):
    if depth > 3:
        return set()
    soup, html_text = fetch(url)
    if not soup:
        return set()
    streams = extract_streams_from_text(html_text)
    for iframe in soup.find_all("iframe", src=True):
        iframe_url = urljoin(url, iframe["src"])
        streams |= crawl_iframe(iframe_url, depth+1)
    return streams

def extract_streams_from_event(url):
    if url in visited_pages:
        return []
    visited_pages.add(url)
    soup, html_text = fetch(url)
    if not soup:
        return []
    title = clean_title(soup.title.text) if soup.title else ""
    streams = extract_streams_from_text(html_text)
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

def crawl_category(category):
    url = urljoin(BASE_URL, category)
    print(f"Scanning: {url}")
    soup, html_text = fetch(url)
    if not soup:
        return []
    event_pages = set()
    for a in soup.find_all("a", href=True):
        href = urljoin(url, a["href"])
        if BASE_URL not in href:
            continue
        if any(x in href for x in CATEGORIES) and href.rstrip("/") != url.rstrip("/"):
            continue
        event_pages.add(href)
    print(f"Found {len(event_pages)} event links")
    return event_pages

def get_tv_data_for_category(cat):
    key = (cat or "misc").lower()
    if key in TV_INFO:
        return TV_INFO[key]
    for k in TV_INFO:
        if k in key:
            return TV_INFO[k]
    return TV_INFO["misc"]

# ---------------------------
# Playlist Writer
# ---------------------------

def write_playlist(streams):
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    header = "#EXTM3U\n# Generated {}\n\n".format(timestamp)
    ua_enc = quote(USER_AGENT)

    with open(OUTPUT_VLC, "w", encoding="utf-8") as f:
        f.write(header)
        for title, url, cat in streams:
            tvg_id, logo, group_name = get_tv_data_for_category(cat)
            f.write(f'#EXTINF:-1 tvg-logo="{logo}" tvg-id="{tvg_id}" group-title="{group_name}",{title}\n')
            f.write(f'{url}\n\n')

    with open(OUTPUT_TIVIMATE, "w", encoding="utf-8") as f:
        f.write(header)
        for title, url, cat in streams:
            tvg_id, logo, group_name = get_tv_data_for_category(cat)
            f.write(f'#EXTINF:-1 tvg-logo="{logo}" tvg-id="{tvg_id}" group-title="{group_name}",{title}\n')
            f.write(f'{url}|referer={BASE_URL}|user-agent={ua_enc}\n\n')

# ---------------------------
# Main
# ---------------------------

def main():
    print("▶️ Starting RoxieStreams playlist generation...")
    load_domains()

    all_event_pages = set()
    for cat in CATEGORIES:
        pages = crawl_category(cat)
        all_event_pages |= pages
        time.sleep(0.5)

    print(f"\nTotal event pages: {len(all_event_pages)}")
    all_streams = []

    for page in all_event_pages:
        # Determine category from URL
        cat = next((c for c in CATEGORIES if f"/{c}" in page), "misc")
        streams = extract_streams_from_event(page)
        for title, url in streams:
            if url not in found_streams:
                found_streams.add(url)
                all_streams.append((title or "RoxieStream", url, cat))
                print(f"Found stream: {title or 'RoxieStream'} [{cat}]")

    print(f"\nTotal streams found: {len(all_streams)}")
    write_playlist(all_streams)
    print("✅ Playlists saved successfully.")

if __name__ == "__main__":
    main()

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
# Write playlist (FIXED)
# --------------------------------------------------

def write_playlist(streams):

    import os

    if not streams:
        print("ERROR: No streams to save")
        return

    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    header = "#EXTM3U\n# Generated {}\n\n".format(timestamp)

    ua_enc = quote(USER_AGENT)

    vlc_path = os.path.abspath(OUTPUT_VLC)
    tivimate_path = os.path.abspath(OUTPUT_TIVIMATE)

    print("\nSaving playlists...")
    print("VLC:", vlc_path)
    print("Tivimate:", tivimate_path)

    # remove duplicates safely
    unique = {}
    for title, url in streams:

        if not url:
            continue

        title = title.strip() if title else "RoxieStreams"

        unique[url] = title

    print("Unique streams:", len(unique))

    try:

        with open(vlc_path, "w", encoding="utf-8", newline="\n") as f:

            f.write(header)

            for url, title in unique.items():

                f.write(f'#EXTINF:-1 group-title="RoxieStreams",{title}\n')
                f.write(f'{url}\n\n')

        print("VLC playlist saved OK")

    except Exception as e:

        print("ERROR saving VLC playlist:", e)


    try:

        with open(tivimate_path, "w", encoding="utf-8", newline="\n") as f:

            f.write(header)

            for url, title in unique.items():

                f.write(f'#EXTINF:-1 group-title="RoxieStreams",{title}\n')
                f.write(f'{url}|referer={BASE_URL}|user-agent={ua_enc}\n\n')

        print("Tivimate playlist saved OK")

    except Exception as e:

        print("ERROR saving Tivimate playlist:", e)


# --------------------------------------------------
# MAIN (FIXED)
# --------------------------------------------------

def main():

    import os

    print("Starting RoxieStreams scraper")
    print("Working directory:", os.getcwd())

    load_domains()

    all_event_pages = set()

    for cat in CATEGORIES:

        pages = crawl_category(cat)

        all_event_pages |= pages

        time.sleep(0.5)


    print("\nTotal event pages found:", len(all_event_pages))

    all_streams = []

    for page in all_event_pages:

        streams = extract_streams_from_event(page)

        if streams:

            print("Found", len(streams), "streams in", page)

            all_streams.extend(streams)


    print("\nTotal raw streams:", len(all_streams))

    write_playlist(all_streams)

    print("\nDone.")


if __name__ == "__main__":
    main()
