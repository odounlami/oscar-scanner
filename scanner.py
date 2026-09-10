import json
import os
import re
import hashlib
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SEEN_FILE = "seen_posts.json"
MAX_AGE_DAYS = 14
BACKFILL_MODE = os.getenv("BACKFILL_MODE", "false").lower() == "true"

SOURCES = [
    ("EmploiBenin", "https://www.emploibenin.com/recherche-jobs-benin/cotonou"),
    ("JobBenin", "https://jobbenin.com/index.php/offres"),
    ("Offresdemplois.bj", "https://www.offresdemplois.bj/recherches/pays/Benin"),
]

JOB_TERMS = (
    "emploi", "offre", "recrut", "développeur", "developpeur", "developer",
    "devops", "frontend", "front-end", "backend", "back-end", "fullstack",
    "full-stack", "angular", "react", "laravel", "python", "javascript",
    "informatique", "technicien", "ingénieur", "ingenieur", "stage", "stagiaire",
    "software", "web", "mobile", "réseau", "reseau", "système", "system"
)


def load_seen():
    if not os.path.exists(SEEN_FILE):
        return set()
    try:
        with open(SEEN_FILE, encoding="utf-8") as f:
            return set(json.load(f))
    except (OSError, ValueError):
        return set()


def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f, ensure_ascii=False, indent=2)


def clean(value):
    return re.sub(r"\s+", " ", BeautifulSoup(value or "", "html.parser").get_text(" ")).strip()


def parse_date(value):
    if not value:
        return None
    value = clean(value).lower()
    value = value.replace("janvier", "01").replace("février", "02").replace("fevrier", "02")
    value = value.replace("mars", "03").replace("avril", "04").replace("mai", "05")
    value = value.replace("juin", "06").replace("juillet", "07").replace("août", "08").replace("aout", "08")
    value = value.replace("septembre", "09").replace("octobre", "10").replace("novembre", "11").replace("décembre", "12").replace("decembre", "12")
    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d %m %Y"):
        try:
            return datetime.strptime(value[:10], fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    match = re.search(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", value)
    if match:
        day, month, year = map(int, match.groups())
        try:
            return datetime(year, month, day, tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def extract_date(node):
    for item in node.select("time, .date, .job-date, .date-posted, [class*=date], [class*=Date]"):
        value = item.get("datetime") or item.get_text(" ")
        parsed = parse_date(value)
        if parsed:
            return parsed
    parsed = parse_date(node.get_text(" "))
    return parsed


def fetch(url):
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0 OscarJobScanner/1.0"}, timeout=25)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def extract_jobs(source, url):
    soup = fetch(url)
    jobs = []
    seen_links = set()
    for link in soup.select("a[href]"):
        title = clean(link.get_text(" "))
        href = urljoin(url, link.get("href"))
        if len(title) < 8 or href in seen_links or href.startswith("javascript:"):
            continue
        parent = link
        for _ in range(4):
            if parent.parent:
                parent = parent.parent
            text = clean(parent.get_text(" "))
            if len(text) > len(title) + 20:
                break
        text = clean(parent.get_text(" "))
        if not any(term in text.lower() or term in title.lower() for term in JOB_TERMS):
            continue
        published = extract_date(parent)
        if not published:
            continue
        seen_links.add(href)
        jobs.append({"title": title, "link": href, "source": source, "published": published, "summary": text[:500]})
    return jobs


def is_recent(job):
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)
    return cutoff <= job["published"] <= datetime.now(timezone.utc) + timedelta(days=1)


def post_id(job):
    return hashlib.sha256(job["link"].encode("utf-8")).hexdigest()


def send(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram non configuré")
        return
    response = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML", "disable_web_page_preview": False}, timeout=15)
    response.raise_for_status()


def format_job(job):
    age = max(0, (datetime.now(timezone.utc) - job["published"]).days)
    return f"💼 <b>OFFRE D’EMPLOI</b>\n\n📌 {job['title']}\n\n📅 Publiée il y a {age} jour(s)\n📡 Source : {job['source']}\n\n🔗 {job['link']}"


def main():
    print(f"🔍 Scanner lancé | backfill: {BACKFILL_MODE}")
    send("🚀 Scanner lancé\nRecherche des offres d’emploi béninoises des 14 derniers jours...")
    seen = load_seen()
    total = 0
    for source, url in SOURCES:
        try:
            jobs = extract_jobs(source, url)
            recent = [job for job in jobs if is_recent(job)]
            print(f"→ {source}: {len(jobs)} annonces trouvées, {len(recent)} récentes")
            for job in recent:
                pid = post_id(job)
                if not BACKFILL_MODE and pid in seen:
                    continue
                send(format_job(job))
                seen.add(pid)
                total += 1
        except Exception as exc:
            print(f"❌ {source}: {type(exc).__name__}: {exc}")
    save_seen(seen)
    send(f"✅ Terminé\n💼 {total} offres d’emploi détectées" if total else "⚠️ Aucune offre d’emploi béninoise récente détectée")
    print(f"Terminé: {total}")


if __name__ == "__main__":
    main()
