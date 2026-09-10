import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

URL = "https://www.goafricaonline.com/bj/emploi"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
}


def clean(value):
    return " ".join((value or "").split())


response = requests.get(URL, headers=HEADERS, timeout=30)
print("status:", response.status_code)
print("final_url:", response.url)
print("content_type:", response.headers.get("content-type"))
print("content_length:", len(response.content))
response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")
print("title:", clean(soup.title.get_text()) if soup.title else "")
print("links:", len(soup.select("a[href]")))
print("cards candidates:", {
    "article": len(soup.select("article")),
    "li": len(soup.select("li")),
    "div[class]": len(soup.select("div[class]")),
})

# Show likely job containers based on links containing employment/job paths.
seen = set()
candidates = []
for link in soup.select("a[href]"):
    href = urljoin(URL, link.get("href", ""))
    text = clean(link.get_text(" "))
    if len(text) < 8 or href in seen:
        continue
    lower = href.lower()
    if any(token in lower for token in ("emploi", "job", "offre", "recrut")):
        parent = link
        for _ in range(5):
            if not parent.parent:
                break
            candidate = parent.parent
            candidate_text = clean(candidate.get_text(" "))
            if 30 <= len(candidate_text) <= 2000:
                parent = candidate
            else:
                break
        candidates.append((text, href, parent))
        seen.add(href)

print("likely job links:", len(candidates))
for index, (title, href, card) in enumerate(candidates[:12], 1):
    print(f"\n=== CANDIDATE {index} ===")
    print("title:", title)
    print("href:", href)
    print("card_tag:", card.name)
    print("card_classes:", card.get("class"))
    print("card_id:", card.get("id"))
    print("card_text:", clean(card.get_text(" | "))[:1000])
    print("card_html:")
    print(str(card)[:4000])

print("\n=== COMMON SELECTOR COUNTS ===")
for selector in [
    "article", "main article", "[class*=job]", "[class*=emploi]", "[class*=offer]",
    "[class*=offre]", "[class*=card]", "[class*=listing]", "[class*=annonce]",
]:
    print(selector, ":", len(soup.select(selector)))
