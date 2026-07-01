# Oscar Job Scanner 🎯

Script qui surveille automatiquement les opportunités freelance dev web
et t'envoie une alerte Telegram dès qu'une correspond à ton profil.

---

## Setup en 15 minutes

### Étape 1 — Créer ton bot Telegram (5 min)

1. Ouvre Telegram → cherche **@BotFather**
2. Envoie `/newbot`
3. Donne un nom au bot (ex: "Oscar Scanner")
4. Copie le **token** qu'il te donne (format : `123456:ABC-DEF...`)
5. Cherche **@userinfobot** → envoie n'importe quel message → copie ton **id** (ex: `123456789`)

### Étape 2 — Créer tes Google Alerts (5 min)

Va sur https://www.google.com/alerts et crée ces 5 alertes :

| Alerte | Mots-clés à entrer |
|--------|-------------------|
| 1 | `"cherche développeur web" OR "besoin développeur"` |
| 2 | `"besoin site web" OR "faire un site web" freelance` |
| 3 | `"mission freelance" développeur Afrique` |
| 4 | `"next.js" OR "react" freelance mission` |
| 5 | `"développeur" Cotonou OR Bénin OR "Côte d'Ivoire"` |

Pour chaque alerte :
- Clique **"Afficher les options"**
- Fréquence : **"Au fur et à mesure"**
- Sources : **"Toutes"**
- Livraison : **"Flux RSS"**
- Clique **Créer l'alerte**
- Clique l'icône RSS → copie l'URL (commence par `https://www.google.com/alerts/feeds/...`)

### Étape 3 — Mettre le projet sur GitHub (3 min)

```bash
git init
git add .
git commit -m "init scanner"
# Crée un repo sur github.com puis :
git remote add origin https://github.com/TON_USERNAME/oscar-scanner.git
git push -u origin main
```

### Étape 4 — Ajouter les secrets GitHub

Dans ton repo GitHub → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Ajoute ces secrets un par un :

| Nom | Valeur |
|-----|--------|
| `TELEGRAM_TOKEN` | le token de ton bot |
| `TELEGRAM_CHAT_ID` | ton id Telegram |
| `ALERT_RSS_1` | l'URL RSS de l'alerte 1 |
| `ALERT_RSS_2` | l'URL RSS de l'alerte 2 |
| `ALERT_RSS_3` | l'URL RSS de l'alerte 3 |
| `ALERT_RSS_4` | l'URL RSS de l'alerte 4 |
| `ALERT_RSS_5` | l'URL RSS de l'alerte 5 |

### Étape 5 — Activer et tester

1. Dans ton repo → onglet **Actions** → clique sur le workflow **"Oscar Job Scanner"**
2. Clique **"Run workflow"** pour tester manuellement
3. Vérifie que tu reçois un message Telegram de confirmation

---

## Comment ça marche

```
Google Alerts surveille le web 24h/24
        ↓
Dès qu'un post contient "cherche développeur"
sur Facebook, LinkedIn, forums, blogs...
        ↓
Google le capte dans le flux RSS
        ↓
Ton script tourne toutes les 2h sur GitHub Actions (gratuit)
        ↓
Si le post match tes mots-clés → Telegram 🔔
        ↓
Tu reçois : titre + extrait + lien direct
```

---

## Ajouter des mots-clés

Ouvre `scanner.py` → modifie la liste `KEYWORDS` :

```python
KEYWORDS = [
    "cherche développeur",
    "besoin site web",
    # ajoute ici ce que tu veux
]
```

---

## Coût total : 0 FCFA

- GitHub Actions : gratuit (2000 min/mois, tu en uses ~10/mois)
- Google Alerts : gratuit
- Telegram bot : gratuit
