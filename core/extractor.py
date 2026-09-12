import re
import time
import html as html_lib
from urllib.parse import urlparse, parse_qs
import requests
from database import insert_proxy

MTPROTO_PATTERN = re.compile(r"(?:tg://proxy|https?://t\.me/proxy)\?[^\s\"<]+")
SOCKS5_PATTERN = re.compile(r"(?:tg://socks|https?://t\.me/socks)\?[^\s\"<]+")

OPERATOR_KEYWORDS = {
    "mci": ["همراه اول", "همراه‌اول", "hamrah", "mci"],
    "irancell": ["ایرانسل", "irancell"],
    "rightel": ["رایتل", "rightel"],
    "wifi": ["وای فای", "وایفای", "wi-fi", "wifi"],
}


def detect_operator(text: str):
    text_lower = text.lower()
    for operator, keywords in OPERATOR_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in text_lower:
                return operator
    return "unknown"


def parse_proxy_link(url: str):
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    server = params.get("server", [None])[0]
    port = params.get("port", [None])[0]
    if not server or not port:
        return None
    try:
        port = int(port)
    except ValueError:
        return None
    if "secret" in params:
        proxy_type = "mtproto"
    elif "user" in params or "pass" in params:
        proxy_type = "socks5"
    else:
        return None
    return {"proxy_url": url, "proxy_type": proxy_type, "server": server, "port": port}


def extract_proxies_from_text(text: str):
    if not text:
        return []
    previous = None
    while text != previous:
        previous = text
        text = html_lib.unescape(text)
    operator = detect_operator(text)
    raw_links = MTPROTO_PATTERN.findall(text) + SOCKS5_PATTERN.findall(text)
    proxies = []
    for link in raw_links:
        parsed = parse_proxy_link(link)
        if parsed:
            parsed["operator"] = operator
            proxies.append(parsed)
    return proxies


def split_into_message_blocks(html: str) -> list:
    blocks = re.split(r'(?=data-post="[^"]+/\d+")', html)
    return blocks[1:] if len(blocks) > 1 else blocks


def fetch_channel_page(channel: str, before: int = None, retries: int = 3):
    url = f"https://t.me/s/{channel}"
    params = {}
    if before:
        params = {"before": before}
    last_error = None
    for attempt in range(retries):
        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            last_error = e
            print(f"[fetch] attempt {attempt + 1}/{retries} for {channel} failed: {e}")
            time.sleep(2)
    raise last_error


def extract_from_channel(channel: str, pages: int = 2):
    count = 0
    before = None
    for _ in range(pages):
        html = fetch_channel_page(channel, before)
        message_ids = re.findall(r'data-post="[^"]+/(\d+)"', html)
        if not message_ids:
            break
        blocks = split_into_message_blocks(html)
        for block in blocks:
            proxies = extract_proxies_from_text(block)
            for proxy in proxies:
                insert_proxy(
                    proxy_url=proxy["proxy_url"],
                    proxy_type=proxy["proxy_type"],
                    server=proxy["server"],
                    port=proxy["port"],
                    operator=proxy["operator"],
                )
                count += 1
        before = min(int(i) for i in message_ids)
        time.sleep(1.5)
    return count


def extract_from_all_channels(channels: list, pages: int = 2):
    total = 0
    for channel in channels:
        clean_channel = channel.strip().lstrip("@")
        if not clean_channel:
            continue
        try:
            found = extract_from_channel(clean_channel, pages)
            print(f"{clean_channel}: {found} proxy have been found")
            total += found
        except Exception as e:
            print(f"Error in channel {clean_channel}: {e}")
            continue
        time.sleep(2)
    return total