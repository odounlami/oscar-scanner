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
# 🎯 2 TYPES DE PROSPECTS UNIQUEMENT
# ─────────────────────────────

BUSINESS_SIGNALS = [
    "ouverture", "ouvre", "opening", "nouveau restaurant",
    "nouvelle boutique", "lancement", "startup",
    "restaurant", "café", "bar", "salon", "boutique"
]

CLIENT_SIGNALS = [
    "cherche développeur", "besoin développeur", "hire developer",
    "looking for developer", "freelance developer",
    "besoin site web", "créer site web", "web developer",
    "react developer", "next.js", "frontend developer",
    "freelance", "developer needed", "need a website"
]


# ─────────────────────────────
# 📡 SOURCES PROPRES (PAS DE BRUIT AFRIQUE NEWS)
# ─────────────────────────────

GOOGLE_NEWS_RSS = [
    ("Bénin business", "https://news.google.com/rss/search?q=ouverture+restaurant+B%C3%A9nin&hl=fr&gl=FR&ceid=FR:fr"),
    ("CI business", "https://news.google.com/rss/search?q=nouveau+restaurant+Abidjan&hl=fr&gl=FR&ceid=FR:fr"),
    ("Dev request", "https://news.google.com/rss/search?q=cherche+developpeur+site+web&hl=fr&gl=FR&ceid=FR:fr"),
    ("Freelance demand", "https://news.google.com/rss/search?q=need+website+developer+freelance&hl=fr&gl=FR&ceid=FR:fr"),
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


def is_business(text):
    t = text.lower()
    return any(k in t for k in BUSINESS_SIGNALS)


def is_client_request(text):
    t = text.lower()
    return any(k in t for k in CLIENT_SIGNALS)


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
# 🚀 SCAN LOGIC
# ─────────────────────────────

def scan(name, url, seen):
    feed = feedparser.parse(url)

    print(f"→ {name} : {len(feed.entries)} entries")

    found = 0

    for e in feed.entries:
        pid = post_id(e)
        if pid in seen:
            continue

        text = f"{e.get('title','')} {e.get('summary','')}"

        title = e.get("title", "")
        link = e.get("link", "")

        # 🟢 TYPE 1 : BUSINESS LOCAL
        if is_business(text):
            send(
                f"🏪 <b>Business détecté</b>\n\n"
                f"📌 {title}\n"
                f"🔗 {link}\n"
                f"📡 {name}"
            )
            found += 1

        # 🔵 TYPE 2 : CLIENT DIRECT (plus important)
        elif is_client_request(text):
            send(
                f"🔥 <b>Client potentiel (DEV)</b>\n\n"
                f"📌 {title}\n"
                f"🔗 {link}\n"
                f"💡 besoin détecté\n"
                f"📡 {name}"
            )
            found += 1

        seen.add(pid)

    return found


# ─────────────────────────────
# 🧾 MAIN
# ─────────────────────────────

if __name__ == "__main__":
    print("\n🔍 Scanner lancé", datetime.now())

    send("🚀 Scanner lancé\nRecherche de prospects actifs...")

    seen = load_seen()
    total = 0

    for name, url in GOOGLE_NEWS_RSS:
        total += scan(name, url, seen)

    save_seen(seen)

    if total == 0:
        send("⚠️ Aucun prospect détecté aujourd’hui")
    else:
        send(f"✅ Scan terminé\n🎯 {total} prospects trouvés")

    print("Terminé:", total)
