import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

URL = "https://jobbenin.com/index.php/offres/categorie/informatique"
HEADERS = {"User-Agent": "Mozilla/5.0 OscarJobScanner/1.0"}


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def inspect_page(url, label):
    print(f"\n===== {label} =====")
    print("URL:", url)
    try:
        response = requests.get(url, headers=HEADERS, timeout=25)
        print("HTTP:", response.status_code)
        soup = BeautifulSoup(response.text, "html.parser")
        print("TITLE:", clean(soup.title.get_text(" ")) if soup.title else "")

        keywords = re.compile(
            r"date|publication|publi|limite|deadline|expire|postul|cl[oô]ture",
            re.I,
        )
        matches = []
        for node in soup.find_all(["p", "span", "div", "li", "td", "h1", "h2", "h3", "h4"]):
            text = clean(node.get_text(" "))
            if text and keywords.search(text) and len(text) < 500:
                if text not in matches:
                    matches.append(text)
        print("DATE-RELATED TEXT:")
        for text in matches[:30]:
            print("-", text)

        print("BODY PREVIEW:")
        print(clean(soup.get_text(" "))[:2500])
    except Exception as exc:
        print("ERROR:", type(exc).__name__, str(exc))


def main():
    response = requests.get(URL, headers=HEADERS, timeout=25)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    card = soup.select_one(".job-bx")
    if not card:
        raise RuntimeError("Aucune carte .job-bx trouvée")

    title_link = card.select_one(".job-contant h4 a")
    button_link = card.select_one("a.btn")
    title_href = urljoin(URL, title_link.get("href", "")) if title_link else ""
    button_href = urljoin(URL, button_link.get("href", "")) if button_link else ""

    print("===== CARTE TEST =====")
    print("TITLE:", clean(title_link.get_text(" ")) if title_link else "")
    print("TITLE HREF:", title_href)
    print("BUTTON HREF:", button_href)
    print("VISIBLE DATE:", clean(card.select_one(".job-day").get_text(" ")) if card.select_one(".job-day") else "")

    if title_href:
        inspect_page(title_href, "LIEN DU TITRE")
    if button_href and button_href != title_href:
        inspect_page(button_href, "LIEN DU BOUTON")


if __name__ == "__main__":
    main()
