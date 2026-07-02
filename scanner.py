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
# 🎯 INTENTIONS RÉELLES (PAS DE BRUIT)
# ─────────────────────────────

CLIENT_INTENTS = [
    "cherche développeur",
    "recherche développeur",
    "need a developer",
    "looking for developer",
    "hire developer",
    "freelance developer",
    "web developer needed",
    "need a website",
    "create website",
    "build website",
    "besoin site web",
    "créer site web",
    "développeur urgent",
    "react developer",
    "next.js developer"
]


# ─────────────────────────────
# 📡 SOURCES (RESTREINTES)
# ─────────────────────────────

RSS_SOURCES = [
    ("Google Dev FR", "https://news.google.com/rss/search?q=cherche+developpeur+site+web&hl=fr&gl=FR&ceid=FR:fr"),
    ("Google Freelance", "https://news.google.com/rss/search?q=need+website+developer+freelance&hl=en&gl=US&ceid=US:en"),
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


def is_client_intent(text):
    t = text.lower()
    return any(k in t for k in CLIENT_INTENTS)


# ─────────────────────────────
# 📲 TELEGRAM
# ─────────────────────────────

def send(msg):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram not configured")
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


# ─────────────────────────────
# 🧾 FORMAT PROSPECT
# ─────────────────────────────

def build_message(title, link, source):
    return (
        f"🔥 <b>LEAD DÉTECTÉ</b>\n\n"
        f"📌 {title}\n\n"
        f"💡 Besoin détecté : site web / développeur\n\n"
        f"🔗 {link}\n"
        f"📡 {source}\n\n"
        f"👉 Action : proposer site vitrine simple + rapide"
    )


# ─────────────────────────────
# 🚀 SCAN
# ─────────────────────────────

def scan(name, url, seen):
    feed = feedparser.parse(url)
    print(f"→ {name} : {len(feed.entries)} posts")

    found = 0

    for e in feed.entries:
        pid = post_id(e)
        if pid in seen:
            continue

        title = e.get("title", "")
        summary = e.get("summary", "")
        link = e.get("link", "")

        text = f"{title} {summary}"

        if is_client_intent(text):
            msg = build_message(title, link, name)
            send(msg)
            found += 1

        seen.add(pid)

    return found


# ─────────────────────────────
# 🚀 MAIN
# ─────────────────────────────

if __name__ == "__main__":
    print("\n🔍 Scanner lancé", datetime.now())

    send("🚀 Scanner lancé\nRecherche de vrais clients en cours...")

    seen = load_seen()
    total = 0

    for name, url in RSS_SOURCES:
        total += scan(name, url, seen)

    save_seen(seen)

    if total == 0:
        send("⚠️ Aucun client détecté aujourd’hui")
    else:
        send(f"✅ Terminé\n🎯 {total} leads détectés")

    print("Terminé:", total)
