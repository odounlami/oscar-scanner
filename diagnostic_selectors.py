import argparse
import re
import sys
from collections import Counter
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def main():
    parser = argparse.ArgumentParser(description="Inspect JobBenin HTML and one offer card")
    parser.add_argument("url")
    args = parser.parse_args()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.google.com/",
    }
    try:
        response = requests.get(args.url, headers=headers, timeout=30)
        print(f"HTTP: {response.status_code}")
        print(f"Content-Type: {response.headers.get('content-type', '')}")
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"FETCH_ERROR: {type(exc).__name__}: {exc}")
        sys.exit(1)

    soup = BeautifulSoup(response.text, "html.parser")
    classes = Counter(cls for tag in soup.find_all(class_=True) for cls in tag.get("class", []))
    print(f"HTML length: {len(response.text)}")
    print("\nCSS classes:")
    for cls, count in sorted(classes.items()):
        print(f"{cls}\t{count}")

    cards = soup.select(".job-bx")
    print(f"\n.job-bx cards: {len(cards)}")
    if cards:
        print("\n===== FIRST .job-bx CARD: COMPLETE HTML =====\n")
        print(cards[0].prettify())
        print("\n===== END FIRST CARD =====")

    print("\nOffer-detail links:")
    pattern = re.compile(r"/(?:index\\.php/)?offres/", re.I)
    found = set()
    for tag in soup.find_all(["a", "area"]):
        href = tag.get("href", "")
        if pattern.search(href):
            absolute = urljoin(args.url, href)
            if absolute not in found:
                found.add(absolute)
                print(f"{tag.name}\t{tag.get('class', [])}\t{tag.get_text(' ', strip=True)[:160]}\t{absolute}")
    print(f"Total detail links: {len(found)}")


if __name__ == "__main__":
    main()
