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

INTENT_PATTERNS = [
    "looking for", "we are looking", "need", "hire", "hiring",
    "seeking", "freelancer needed", "require", "wanted",
    "cherche", "recherche", "besoin", "recrute",
    "need a developer", "need a website", "build a website",
    "web developer", "freelance developer", "create website",
    "développeur", "développeur web", "développeur logiciel",
    "recrutement", "offre d'emploi", "emploi"
]

NOISE_PATTERNS = [
    "top", "skills", "how to", "guide", "tutorial",
    "learn", "become", "roadmap", "tips", "trends",
    "future", "career", "market", "analysis", "report", "study"
]

RSS_SOURCES = [
    ("Google Dev Intent", "https://news.google.com/rss/search?q=looking+for+developer+website&hl=en&gl=US&ceid=US:en"),
    ("Google Hire Dev", "https://news.google.com/rss/search?q=hire+freelance+developer+website&hl=en&gl=US&ceid=US:en"),
    ("Google FR Intent", "https://news.google.com/rss/search?q=besoin+site+web+developpeur&hl=fr&gl=FR&ceid=FR:fr"),
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


def is_noise(text):
    return any(n in text.lower() for n in NOISE_PATTERNS)


def is_intent(text):
    return any(p in text.lower() for p in INTENT_PATTERNS)


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


def is_valid_lead(text):
    return is_intent(text) and not is_noise(text)


def send(msg):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram non configuré")
        return
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"},
        timeout=10
    )


def format_lead(title, link, source, age):
    date_label = f"il y a {age} jour(s)" if age is not None else "date inconnue"
    return (
        f"🔥 <b>LEAD QUALIFIÉ</b>\n\n"
        f"📌 {title}\n\n"
        f"💡 Intention détectée : besoin de développeur / site web\n"
        f"📅 Publiée {date_label}\n\n"
        f"🔗 {link}\n"
        f"📡 {source}\n\n"
        f"👉 Action : proposer site vitrine simple + rapide"
    )


def scan(name, url, seen):
    feed = feedparser.parse(url)
    print(f"→ {name} : {len(feed.entries)} entries")
    found = 0

    for entry in feed.entries:
        pid = post_id(entry)
        if pid in seen:
            continue
        seen.add(pid)

        title = entry.get("title", "").strip()
        summary = entry.get("summary", "")
        link = entry.get("link", "")
        text = f"{title} {summary}"
        age = age_in_days(entry)

        if not is_recent(entry):
            continue
        if is_valid_lead(text):
            send(format_lead(title, link, name, age))
            found += 1

    return found


if __name__ == "__main__":
    print("\n🔍 Scanner lancé", datetime.now())
    send("🚀 Scanner lancé\nRecherche de leads qualifiés...")

    seen = load_seen()
    total = sum(scan(name, url, seen) for name, url in RSS_SOURCES)
    save_seen(seen)

    if total == 0:
        send("⚠️ Aucun lead qualifié détecté aujourd’hui")
    else:
        send(f"✅ Terminé\n🎯 {total} leads qualifiés")

    print("Terminé:", total)
