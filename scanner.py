import feedparser
import requests
import json
import os
import hashlib
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SEEN_FILE = "seen_posts.json"
MAX_AGE_DAYS = 14
BACKFILL_MODE = os.getenv("BACKFILL_MODE", "false").lower() == "true"

NOISE_PATTERNS = [
    "top", "skills", "how to", "guide", "tutorial", "learn", "become",
    "roadmap", "tips", "trends", "future", "career", "market", "analysis",
    "report", "study", "formation", "cours", "astuce"
]

RSS_SOURCES = [
    ("EmploiBenin", "https://www.emploibenin.com/rss"),
    ("JobBenin", "https://www.jobbenin.com/rss"),
    ("Offresdemplois.bj", "https://offresdemplois.bj/rss"),
]


def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f, ensure_ascii=False, indent=2)


def post_id(entry):
    return hashlib.sha256(
        (entry.get("link", "") + entry.get("title", "")).encode("utf-8")
    ).hexdigest()


def parse_date(entry):
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    try:
        return datetime(*parsed[:6], tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def age_in_days(entry):
    published = parse_date(entry)
    if published is None:
        return None
    return max(0, (datetime.now(timezone.utc) - published).days)


def is_recent(entry):
    age = age_in_days(entry)
    return age is not None and age <= MAX_AGE_DAYS


def is_valid_job(entry):
    title = entry.get("title", "").lower()
    summary = entry.get("summary", "").lower()
    text = f"{title} {summary}"

    job_terms = [
        "emploi", "offre", "recrutement", "recrute", "recherche",
        "développeur", "developpeur", "developer", "devops", "frontend",
        "front-end", "backend", "back-end", "fullstack", "full-stack",
        "angular", "react", "laravel", "python", "javascript", "informatique",
        "technicien", "ingénieur", "ingenieur", "stage", "stagiaire"
    ]

    return (
        any(term in text for term in job_terms)
        and not any(noise in text for noise in NOISE_PATTERNS)
    )


def send(msg):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram non configuré")
        return
    response = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"},
        timeout=10
    )
    response.raise_for_status()


def format_job(title, link, source, age):
    date_label = f"il y a {age} jour(s)" if age is not None else "date inconnue"
    return (
        f"💼 <b>OFFRE D’EMPLOI</b>\n\n"
        f"📌 {title}\n\n"
        f"📅 Publiée {date_label}\n"
        f"📡 Source : {source}\n\n"
        f"🔗 {link}"
    )


def scan(name, url, seen):
    feed = feedparser.parse(url)
    print(f"→ {name} : {len(feed.entries)} entries")
    found = 0

    for entry in feed.entries:
        pid = post_id(entry)
        age = age_in_days(entry)

        if not is_recent(entry):
            continue
        if not is_valid_job(entry):
            continue
        if not BACKFILL_MODE and pid in seen:
            continue

        send(format_job(entry.get("title", "Offre d’emploi"), entry.get("link", ""), name, age))
        found += 1
        seen.add(pid)

    return found


if __name__ == "__main__":
    print("\n🔍 Scanner lancé", datetime.now(), "| backfill:", BACKFILL_MODE)
    send("🚀 Scanner lancé\nRecherche des offres d’emploi béninoises des 14 derniers jours...")

    seen = load_seen()
    total = sum(scan(name, url, seen) for name, url in RSS_SOURCES)
    save_seen(seen)

    if total == 0:
        send("⚠️ Aucune offre d’emploi béninoise récente détectée")
    else:
        send(f"✅ Terminé\n💼 {total} offres d’emploi détectées")

    print("Terminé:", total)
