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

# ─── Mots-clés ────────────────────────────────────────────────────────────────

KEYWORDS = [
    # Demandes directes
    "cherche développeur", "cherche un développeur", "besoin développeur",
    "besoin d'un dev", "cherche dev web", "recherche développeur web",
    "besoin site web", "créer site web", "faire un site", "refaire site",
    "application mobile", "cherche freelance", "mission freelance",
    "développeur freelance", "dev freelance", "next.js", "react freelance",
    # Anglais
    "looking for developer", "need a developer", "hire developer",
    "web developer needed", "freelance developer", "build website",
    # Contexte local
    "site web Bénin", "développeur Cotonou", "dev Abidjan", "site web Afrique",
    "application Dakar", "développeur Lomé",
]

# ─── Sources Google Alerts RSS ─────────────────────────────────────────────────
# Instructions pour générer tes propres alertes :
# 1. Va sur https://www.google.com/alerts
# 2. Crée une alerte pour chaque mot-clé important
# 3. Choisis "Flux RSS" comme mode de livraison
# 4. Copie l'URL RSS et ajoute-la ici

GOOGLE_ALERTS_RSS = [
    # Remplace ces URLs par tes vraies URLs Google Alerts
    # Exemple : "https://www.google.com/alerts/feeds/XXXXX/XXXXX"
    os.getenv("ALERT_RSS_1", ""),
    os.getenv("ALERT_RSS_2", ""),
    os.getenv("ALERT_RSS_3", ""),
    os.getenv("ALERT_RSS_4", ""),
    os.getenv("ALERT_RSS_5", ""),
]

# Sources RSS publiques supplémentaires (forums, blogs tech Afrique)
EXTRA_RSS = [
    "https://www.journalducm.com/feed/",           # Marketing digital Cameroun
    "https://www.abidjan.net/rss.asp",             # Petites annonces Côte d'Ivoire
    "https://bj.jolome.com/rss/annonces.xml",      # Annonces Bénin
]

# ─── Utilitaires ──────────────────────────────────────────────────────────────

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)

def post_id(entry):
    return hashlib.md5((entry.get("link", "") + entry.get("title", "")).encode()).hexdigest()

def matches(text):
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in KEYWORDS)

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️  Telegram non configuré — affichage console :")
        print(message)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
    except Exception as e:
        print(f"Erreur Telegram : {e}")

def format_message(entry, source_name):
    title = entry.get("title", "Sans titre")[:120]
    link = entry.get("link", "")
    summary = entry.get("summary", "")[:200].replace("<b>", "").replace("</b>", "").replace("<br>", " ")
    date = entry.get("published", datetime.now().strftime("%d/%m/%Y"))

    return (
        f"🎯 <b>Nouvelle opportunité</b>\n"
        f"📌 <b>{title}</b>\n\n"
        f"📝 {summary}...\n\n"
        f"🔗 <a href='{link}'>Voir le post</a>\n"
        f"📡 Source : {source_name}\n"
        f"🕐 {date}"
    )

# ─── Scanner ──────────────────────────────────────────────────────────────────

def scan_feed(url, source_name, seen):
    if not url:
        return 0
    found = 0
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            pid = post_id(entry)
            if pid in seen:
                continue
            text = f"{entry.get('title', '')} {entry.get('summary', '')}"
            if matches(text):
                msg = format_message(entry, source_name)
                send_telegram(msg)
                found += 1
            seen.add(pid)
    except Exception as e:
        print(f"Erreur sur {source_name} : {e}")
    return found

def run():
    print(f"\n🔍 Scan démarré — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    seen = load_seen()
    total = 0

    # Google Alerts
    alerts = [
        ("cherche développeur web", os.getenv("ALERT_RSS_1", "")),
        ("besoin site web freelance", os.getenv("ALERT_RSS_2", "")),
        ("mission dev Afrique", os.getenv("ALERT_RSS_3", "")),
        ("next.js freelance", os.getenv("ALERT_RSS_4", "")),
        ("développeur Cotonou Bénin", os.getenv("ALERT_RSS_5", "")),
    ]
    for name, url in alerts:
        total += scan_feed(url, f"Google Alerts — {name}")

    # Sources RSS extra
    for url in EXTRA_RSS:
        total += scan_feed(url, url.split("/")[2], seen)

    save_seen(seen)
    print(f"✅ Scan terminé — {total} nouvelle(s) opportunité(s) envoyée(s)")

    if total == 0:
        print("   (Rien de nouveau pour l'instant — normal les premières heures)")

if __name__ == "__main__":
    # Correction du bug : seen manquait dans les appels scan_feed
    print(f"\n🔍 Scan démarré — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    seen = load_seen()
    total = 0

    alerts = [
        ("cherche développeur web", os.getenv("ALERT_RSS_1", "")),
        ("besoin site web freelance", os.getenv("ALERT_RSS_2", "")),
        ("mission dev Afrique", os.getenv("ALERT_RSS_3", "")),
        ("next.js freelance", os.getenv("ALERT_RSS_4", "")),
        ("développeur Cotonou Bénin", os.getenv("ALERT_RSS_5", "")),
    ]
    for name, url in alerts:
        total += scan_feed(url, f"Google Alerts — {name}", seen)

    for url in EXTRA_RSS:
        total += scan_feed(url, url.split("/")[2], seen)

    save_seen(seen)
    print(f"✅ Scan terminé — {total} nouvelle(s) opportunité(s) envoyée(s)")
