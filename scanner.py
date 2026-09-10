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
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ENABLE_REJECTED_NOTIFICATIONS = os.getenv("ENABLE_REJECTED_NOTIFICATIONS", "true").lower() == "true"
SEEN_FILE = "seen_posts.json"
MAX_AGE_DAYS = 14
BACKFILL_MODE = os.getenv("BACKFILL_MODE", "false").lower() == "true"
EMPLOIBENIN_URL = "https://www.emploibenin.com/recherche-jobs-benin/informatique"
JOBBENIN_URL = "https://jobbenin.com/index.php/offres/categorie/informatique"
SOURCES = [("EmploiBenin", EMPLOIBENIN_URL), ("JobBenin", JOBBENIN_URL)]


def load_seen():
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
    months = {"janvier":"01", "février":"02", "fevrier":"02", "mars":"03", "avril":"04", "mai":"05", "juin":"06", "juillet":"07", "août":"08", "aout":"08", "septembre":"09", "octobre":"10", "novembre":"11", "décembre":"12", "decembre":"12"}
    for name, number in months.items():
        value = value.replace(name, number)
    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d %m %Y"):
        try:
            return datetime.strptime(value[:10], fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    match = re.search(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", value)
    if match:
        try:
            return datetime(*map(int, (match.group(3), match.group(2), match.group(1))), tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


def fetch_soup(url):
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0 OscarJobScanner/1.0"}, timeout=25)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def node_value(node, selectors):
    for selector in selectors:
        found = node.select_one(selector)
        if found:
            return clean(found.get("datetime") or found.get_text(" "))
    return ""


def extract_jobbenin(soup, url):
    jobs = []
    cards = soup.select("article, .job-card, .job-item, .offre, .offer, .card")
    for card in cards:
        link = card.select_one("a[href]")
        title_node = card.select_one("h1, h2, h3, h4, .title, .job-title, .offer-title")
        if not link or not title_node:
            continue
        title = clean(title_node.get_text(" "))
        if len(title) < 8:
            continue
        href = urljoin(url, link.get("href"))
        date_text = node_value(card, ["time", ".date", ".job-date", ".date-posted", "[class*=date]"])
        published = parse_date(date_text or card.get_text(" "))
        jobs.append({"title": title, "link": href, "source": "JobBenin", "ville": node_value(card, [".ville", ".city", "[class*=ville]", "[class*=city]"]), "diplome": node_value(card, [".diplome", ".education", "[class*=diplome]", "[class*=education]"]), "salaire": node_value(card, [".salaire", ".salary", "[class*=salaire]", "[class*=salary]"]), "published": published, "date_inconnue": published is None, "summary": clean(card.get_text(" "))[:1000]})
    return jobs


def extract_emploibenin(soup, url):
    jobs, seen = [], set()
    cards = soup.select("article, .views-row, .job-listing, .list-offer, .offre, .offer, .job-item")
    for card in cards:
        link = card.select_one("a[href]")
        title_node = card.select_one("h1, h2, h3, h4, .title, .job-title, .offer-title, .views-field-title")
        if not link or not title_node:
            continue
        title = clean(title_node.get_text(" "))
        href = urljoin(url, link.get("href"))
        if len(title) < 8 or href in seen:
            continue
        text = clean(card.get_text(" "))
        published = parse_date(node_value(card, ["time", ".date", ".job-date", ".date-posted", "[class*=date]"]) or text)
        jobs.append({"title": title, "link": href, "source": "EmploiBenin", "ville": node_value(card, [".ville", ".city", ".field-name-field-offre-region", "[class*=region]"]) or ("Cotonou" if "cotonou" in text.lower() else ""), "diplome": node_value(card, [".diplome", ".education", "[class*=etude]", "[class*=diplome]"]), "salaire": node_value(card, [".salaire", ".salary", "[class*=salaire]"]), "published": published, "date_inconnue": published is None, "summary": text[:1000]})
        seen.add(href)
    return jobs


def extract_generic(soup, source, url):
    jobs, seen = [], set()
    for link in soup.select("a[href]"):
        title = clean(link.get_text(" "))
        href = urljoin(url, link.get("href"))
        if len(title) < 8 or href in seen or href.startswith("javascript:"):
            continue
        parent = link
        for _ in range(4):
            if not parent.parent:
                break
            candidate = parent.parent
            candidate_text = clean(candidate.get_text(" "))
            if len(candidate_text) > 2500:
                break
            parent = candidate
        text = clean(parent.get_text(" "))
        if len(text) < len(title) + 10:
            continue
        published = parse_date(node_value(parent, ["time", ".date", ".job-date", ".date-posted", "[class*=date]"]) or text)
        seen.add(href)
        jobs.append({"title": title, "link": href, "source": source, "ville": "", "diplome": "", "salaire": "", "published": published, "date_inconnue": published is None, "summary": text[:1000]})
    return jobs


def extract_jobs(source, url):
    soup = fetch_soup(url)
    if source == "JobBenin":
        return extract_jobbenin(soup, url)
    if source == "EmploiBenin":
        return extract_emploibenin(soup, url)
    return extract_generic(soup, source, url)


def is_recent(job):
    if job["date_inconnue"]:
        return True
    now = datetime.now(timezone.utc)
    return now - timedelta(days=MAX_AGE_DAYS) <= job["published"] <= now + timedelta(days=1)


def post_id(job):
    return hashlib.sha256(job["link"].encode("utf-8")).hexdigest()


def gemini_classify(job):
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY manquante")
    prompt = f'''Classe cette annonce pour un développeur web/IT au Bénin. Réponds uniquement en JSON avec score (0 à 10), qualifie (true/false) et raison courte. Score >= 6 = qualifiée.\nTitre: {job["title"]}\nVille: {job.get("ville", "")}\nDiplôme: {job.get("diplome", "")}\nSalaire: {job.get("salaire", "")}\nRésumé: {job.get("summary", "")}'''
    response = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}", json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json"}}, timeout=30)
    response.raise_for_status()
    result = json.loads(response.json()["candidates"][0]["content"]["parts"][0]["text"])
    result["score"] = float(result.get("score", 0))
    result["qualifie"] = result["score"] >= 6
    return result


def send(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram non configuré")
        return
    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML", "disable_web_page_preview": False}, timeout=15).raise_for_status()


def format_job(job, result):
    date = job["published"].strftime("%d/%m/%Y") if job["published"] else "date_inconnue"
    extra = f"\n🏙 Ville : {job['ville']}" if job.get("ville") else ""
    return f"💼 <b>OFFRE D’EMPLOI</b>\n\n📌 {job['title']}\n📅 {date}{extra}\n📡 Source : {job['source']}\n\n🔗 {job['link']}\n\n🤖 Score Gemini : {result['score']}/10"


def format_rejected(job, result):
    date = job["published"].strftime("%d/%m/%Y") if job["published"] else "date_inconnue"
    return f"🗑 <b>REJETÉ</b>\n\n📌 {job['title']}\n📅 {date}\n📡 Source : {job['source']}\n🤖 Score Gemini : {result['score']}/10\n📝 Raison : {result.get('raison', 'Non précisée')}\n\n🔗 {job['link']}"


def main():
    print(f"🔍 Scanner lancé | backfill: {BACKFILL_MODE} | rejected: {ENABLE_REJECTED_NOTIFICATIONS}")
    seen, total = load_seen(), 0
    for source, url in SOURCES:
        try:
            jobs = extract_jobs(source, url)
            recent = [job for job in jobs if is_recent(job)]
            print(f"→ {source}: {len(jobs)} annonces, {len(recent)} dans la fenêtre")
            for job in recent:
                pid = post_id(job)
                if not BACKFILL_MODE and pid in seen:
                    continue
                try:
                    result = gemini_classify(job)
                except Exception as exc:
                    print(f"⚠️ Classification échouée ({source}): {job['title']} — {type(exc).__name__}: {exc}")
                    seen.add(pid + ":erreur_classification")
                    continue
                if result["qualifie"]:
                    send(format_job(job, result))
                elif ENABLE_REJECTED_NOTIFICATIONS:
                    send(format_rejected(job, result))
                seen.add(pid)
                total += 1
        except Exception as exc:
            print(f"❌ {source}: {type(exc).__name__}: {exc}")
    save_seen(seen)
    send(f"✅ Terminé\n💼 {total} annonces analysées par Gemini")
    print(f"Terminé: {total}")


if __name__ == "__main__":
    main()
