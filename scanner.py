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
# MOTS-CLÉS PROSPECTION
# ─────────────────────────────

BUSINESS_OPENING = [
    "ouvre", "ouverture", "opening", "grand opening", "inauguration",
    "nouveau restaurant", "nouvelle boutique", "nouveau magasin",
    "nouveau salon", "nouveau café", "lancement", "startup"
]

SERVICE_REQUEST = [
    "cherche graphiste", "logo", "community manager",
    "marketing", "communication", "branding"
]

RECRUITMENT = [
    "recrute", "recrutement", "hiring", "cherche", "emploi"
]

LOCAL_BUSINESS = [
    "restaurant", "maquis", "café", "bar", "snack",
    "salon", "spa", "coiffure", "pharmacie", "clinique",
    "agence immobilière", "boutique"
]

ALL_KEYWORDS = BUSINESS_OPENING + SERVICE_REQUEST + RECRUITMENT + LOCAL_BUSINESS


# ─────────────────────────────
# SOURCES
# ─────────────────────────────

INDEED_RSS = [
    ("Indeed dev", "https://fr.indeed.com/rss?q=d%C3%A9veloppeur+web&sort=date"),
    ("Indeed freelance", "https://fr.indeed.com/rss?q=freelance+react&sort=date"),
]

EXTRA_RSS = [
    ("Freelance Info", "https://www.freelance-informatique.fr/rss.php?type=mission"),
    ("Journal CM", "https://www.journalducm.com/feed/")
]


# ─────────────────────────────
# UTILS
# ─────────────────────────────

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)


def post_id(entry):
    return hashlib.md5(
        (entry.get("link", "") + entry.get("title", "")).encode()
    ).hexdigest()


def clean_text(entry):
    return f"{entry.get('title','')} {entry.get('summary','')} {entry.get('description','')}".lower()


# ─────────────────────────────
# SCORE SYSTEM
# ─────────────────────────────

def score(text):
    s = 0
    reasons = []

    def check(words, points, label):
        nonlocal s
        if any(w in text for w in words):
            s += points
            reasons.append(f"+{points} {label}")

    check(BUSINESS_OPENING, 10, "Business opening")
    check(SERVICE_REQUEST, 10, "Service request")
    check(RECRUITMENT, 6, "Recruitment")
    check(LOCAL_BUSINESS, 5, "Local business")

    return s, reasons


# ─────────────────────────────
# TELEGRAM
# ─────────────────────────────

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram non configuré")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }

    try:
        requests.post(url, json=payload, timeout=10).raise_for_status()
        return True
    except Exception as e:
        print(f"❌ Telegram error: {e}")
        return False


# ─────────────────────────────
# MESSAGES
# ─────────────────────────────

def send_start_message():
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    send_telegram(
        f"🚀 <b>Scanner lancé</b>\n\n🕐 {now}\n📡 Scan en cours..."
    )


def send_end_message(total):
    if total > 0:
        msg = f"✅ <b>Scan terminé</b>\n\n🎯 {total} prospect(s) trouvé(s)"
    else:
        msg = (
            "⚠️ <b>Scan terminé</b>\n\n"
            "Aucun prospect trouvé aujourd’hui.\n"
            "Le système fonctionne, mais rien de pertinent détecté."
        )

    send_telegram(msg)


# ─────────────────────────────
# SCAN
# ─────────────────────────────

def scan_feed(name, url, seen, min_score=6):
    if not url:
        return 0

    found = 0

    try:
        feed = feedparser.parse(url)
        print(f"→ {name} : {len(feed.entries)} entrées")

        for entry in feed.entries:
            pid = post_id(entry)
            if pid in seen:
                continue

            text = clean_text(entry)
            s, reasons = score(text)

            # DEBUG IMPORTANT
            print(f"\n[{name}] {entry.get('title','')[:60]}")
            print(f"SCORE: {s} | {reasons}")

            if s >= min_score:
                msg = (
                    f"🎯 <b>Prospect détecté</b>\n\n"
                    f"📌 {entry.get('title','')}\n\n"
                    f"⭐ Score: {s}\n"
                    f"{chr(10).join(reasons)}\n\n"
                    f"🔗 <a href='{entry.get('link','')}'>Voir</a>\n"
                    f"📡 {name}"
                )

                send_telegram(msg)
                found += 1

            seen.add(pid)

    except Exception as e:
        print(f"❌ Erreur {name}: {e}")

    return found


# ─────────────────────────────
# MAIN
# ─────────────────────────────

if __name__ == "__main__":
    print(f"\n🔍 Scan démarré — {datetime.now().strftime('%d/%m/%Y %H:%M')}")

    send_start_message()

    seen = load_seen()
    total = 0

    print("\n📡 Indeed...")
    for name, url in INDEED_RSS:
        total += scan_feed(name, url, seen)

    print("\n📡 Extra sources...")
    for name, url in EXTRA_RSS:
        total += scan_feed(name, url, seen)

    save_seen(seen)

    send_end_message(total)

    print(f"\n✅ Terminé — {total} prospect(s)")
