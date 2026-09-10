import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

URL = "https://jobbenin.com/index.php/offres/categorie/informatique"
HEADERS = {"User-Agent": "Mozilla/5.0 OscarJobScanner/1.0"}


def clean(value):
    return re.sub(r"\s+", " ", value or "").strip()


def parse_date(value):
    match = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", clean(value))
    if not match:
        return None
    return datetime(
        int(match.group(3)), int(match.group(2)), int(match.group(1)), tzinfo=timezone.utc
    )


def main():
    response = requests.get(URL, headers=HEADERS, timeout=25)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    cards = soup.select(".job-bx")
    print(f"Cartes trouvées : {len(cards)}")

    for index, card in enumerate(cards, start=1):
        title_node = card.select_one(".job-contant h4 a")
        if not title_node:
            continue

        title = clean(title_node.get_text(" "))
        link = urljoin(URL, title_node.get("href", ""))
        detail_response = requests.get(link, headers=HEADERS, timeout=25)
        detail_response.raise_for_status()
        detail = BeautifulSoup(detail_response.text, "html.parser")
        text = clean(detail.get_text(" "))

        added_match = re.search(r"Date d'ajout\s+(\d{1,2}/\d{1,2}/\d{4})", text, re.I)
        deadline_match = re.search(r"Date limite\s*:\s*(\d{1,2}/\d{1,2}/\d{4})", text, re.I)
        city_match = re.search(r"Ville\s+([^D]+?)\s+Département", text, re.I)
        salary_match = re.search(r"Salaire offert\s+(.+?)\s+Tags populaires", text, re.I)

        print(f"\n--- Offre {index} ---")
        print("Titre :", title)
        print("Date publication :", added_match.group(1) if added_match else "inconnue")
        print("Date limite :", deadline_match.group(1) if deadline_match else "inconnue")
        print("Ville :", clean(city_match.group(1)) if city_match else "inconnue")
        print("Salaire :", clean(salary_match.group(1)) if salary_match else "inconnu")
        print("Lien :", link)


if __name__ == "__main__":
    main()
