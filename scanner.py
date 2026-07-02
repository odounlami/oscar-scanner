import feedparser
import requests
import json
import os
import hashlib
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SEEN_FILE = "seen_posts.json"


# ─────────────────────────────
# 🎯 INTENTIONS RÉELLES CLIENTS
# ─────────────────────────────

INTENT_PATTERNS = [
    "looking for", "we are looking", "need", "hire", "hiring",
    "seeking", "freelancer needed", "require", "wanted",
    "cherche", "recherche", "besoin", "recrute",
    "need a developer", "need a website", "build a website",
    "web developer", "freelance developer", "create website"
]


# ─────────────────────────────
# 🚫 BRUIT (ARTICLES / CONTENU ÉDUCATIF)
# ─────────────────────────────

NOISE_PATTERNS = [
    "top", "skills", "how to", "guide", "tutorial",
    "learn", "become", "roadmap", "tips",
    "trends", "future", "career", "market",
    "analysis", "report", "study"
]


# ─────────────────────────────
# 📡 SOURCES (RESTREINTES ET PROPRES)
# ─────────────────────────────

RSS_SOURCES = [
    ("Google Dev Intent", "https://news.google.com/rss/search?q=looking+for+developer+website&hl=en&gl=US&ceid=US:en"),
    ("Google Hire Dev", "https://news.google.com/rss/search?q=hire+freelance+developer+website&hl=en&gl=US&ceid=US:en"),
    ("Google FR Intent", "https://news.google.com/rss/search?q=besoin+site+web+developpeur&hl=fr&gl=FR&ceid=FR:fr"),
]


# ─────────────────────────────
# 🧠 UTILS
# ─────────────────────────────

def load_seen():
    if os.path.exists(SEEN_FILE):
        return set(json.load(open(SEEN_FILE)))
    return set()


def save_seen(seen):
    json.dump(list(seen), open(SEEN_FILE, "w"))


def post_id(entry):
    return hashlib.md5(
        (entry.get("link", "") + entry.get("title", "")).encode()
    ).hexdigest()


def is_noise(text):
    t = text.lower()
    return any(n in t for n in NOISE_PATTERNS)


def is_intent(text):
    t = text.lower()
    return any(p in t for p in INTENT_PATTERNS)


def is_valid_lead(text):
    """
    Règle stricte :
    - doit contenir une intention
    - ne doit pas être un article éducatif
    """
    return is_intent(text) and not is_noise(text)


# ─────────────────────────────
# 📲 TELEGRAM
# ─────────────────────────────

def send(msg):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram non configuré")
        return

    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
            "parse_mode": "HTML"
        },
        timeout=10
    )


def format_lead(title, link, source):
    return (
        f"🔥 <b>LEAD QUALIFIÉ</b>\n\n"
        f"📌 {title}\n\n"
        f"💡 Intention détectée : besoin de développeur / site web\n\n"
        f"🔗 {link}\n"
        f"📡 {source}\n\n"
        f"👉 Action : proposer site vitrine simple + rapide"
    )


# ─────────────────────────────
# 🚀 SCAN
# ─────────────────────────────

def scan(name, url, seen):
    feed = feedparser.parse(url)
    print(f"→ {name} : {len(feed.entries)} entries")

    found = 0

    for e in feed.entries:
        pid = post_id(e)
        if pid in seen:
            continue

        title = e.get("title", "")
        summary = e.get("summary", "")
        link = e.get("link", "")

        text = f"{title} {summary}"

        if is_valid_lead(text):
            send(format_lead(title, link, name))
            found += 1

        seen.add(pid)

    return found


# ─────────────────────────────
# 🧾 MAIN
# ─────────────────────────────

if __name__ == "__main__":
    print("\n🔍 Scanner lancé", datetime.now())

    send("🚀 Scanner lancé\nRecherche de leads qualifiés...")

    seen = load_seen()
    total = 0

    for name, url in RSS_SOURCES:
        total += scan(name, url, seen)

    save_seen(seen)

    if total == 0:
        send("⚠️ Aucun lead qualifié détecté aujourd’hui")
    else:
        send(f"✅ Terminé\n🎯 {total} leads qualifiés")

    print("Terminé:", total)
