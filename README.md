# ✈️ Air France Helpine - Bot Discord Tickets MP

Bot Discord **full-stack** pour gérer les tickets via **MP au bot**.

> Un utilisateur envoie un MP au bot → un salon ticket est créé automatiquement dans la catégorie configurée sur ton seul serveur → le staff répond depuis le salon, le bot relaie en MP (et inversement). Survit au redémarrage, stockage optimisé.

**IDs déjà configurés :**
- Serveur : `1553129363858530465`
- Catégorie tickets : `1560529185880154263`
- Rôle staff : `1564261898935992382`

Langage choisi : **Python** (`discord.py` + `aiosqlite`) — async, léger, parfait pour ce use-case temps réel + persistance.

---

## 🚀 Fonctionnalités "au max"

### 🎫 Système Ticket MP
- **MP → Ticket** : premier MP crée un salon `ticket-nom-xxxx` dans la bonne catégorie
- **Anti-doublon** : 1 ticket ouvert max par utilisateur, sinon relay vers ticket existant
- **Permissions** : `@everyone` invisible, seuls `Staff` + `Bot` voient le ticket
- **Relay bidirectionnel** :
  - DM user → salon staff (embed + fichiers ré-uploadés si <8MB)
  - Salon staff → DM user (embed staff + fichiers)
- **Boutons persistants** (survivent au reboot via `custom_id`) :
  - ✉️ Répondre (modal)
  - 👤 Claim
  - 📋 Transcript
  - 🔒 Fermer (avec confirmation)
- **Commandes** : `/fermer`, `/claim`, `/transcript`, `/ticket-stats`, `/ban-ticket`, `/unban-ticket`
- **Fermeture** : transcript HTML + gzip, log channel, DM de notification, suppression auto après 10s
- **!fermer en DM** : l'utilisateur peut fermer son propre ticket
- **Anti-spam** : cooldown 3s DM + cooldown création ticket configurable

### 📢 Annonces
- **`/annonce`** : Admin uniquement → ouvre **modal** qui demande :
  - Titre (256c)
  - Description (4000c, support markdown/mentions)
  - Couleur hex ou `bleu/rouge/blanc`
  - URL image (banner)
  - Mention (`@everyone`, rôle, etc.)
  - Envoi dans salon choisi ou salon actuel, preview ephemeral + vrai envoi
- **`/annonce-rapide`** : version slash directe sans modal (texte + mention @everyone bool)
- Embed aux couleurs Air France (`#002395` bleu, `#ED2939` rouge) + footer

### ⚙️ Admin & Optimisations
- `/setup-tickets` : reconfigure catégorie/rôle/logs/annonces sans redémarrer (stocké en DB)
- `/bot-info` : latence, stats DB, config
- `/purge-transcripts` : supprime vieux transcripts > X jours
- `/sync` : resync slash commands
- **Stockage optimisé** :
  - SQLite en `WAL` + `synchronous=NORMAL` + `cache_size=-16000`
  - Transcripts HTML → `gzip -9` (≈70% économisé), fichiers légers, pas d'avatar stocké
  - Messages loggés en DB seulement (pas de duplication fichiers)
  - `VACUUM` manuel possible, purge auto
  - Pièces jointes non dupliquées sur disque, re-upload via Discord CDN
- **Survit au redémarrage** :
  - DB SQLite persistante (`data/tickets.db`)
  - `TicketControlView` avec `timeout=None` + `custom_id` + `bot.add_view()` au `setup_hook`
  - Restauration tickets ouverts au `on_ready` (vérif salon existe)
  - Config guild en DB (pas seulement env)
- Presence `MP pour ouvrir un ticket ✈️`

---

## 📦 Installation

### 1. Prérequis
- Python 3.10+ (ou Docker)
- Token bot Discord avec intents privilégiés **Message Content** + **Server Members** activés sur https://discord.com/developers/applications → Bot

### 2. Config
Edite simplement `config.json` (tout est dedans, plus de `.env`) :
```bash
nano config.json
```
Exemple `config.json` :
```json
{
  "DISCORD_TOKEN": "MTxxxx...",
  "GUILD_ID": "1553129363858530465",
  "TICKET_CATEGORY_ID": "1560529185880154263",
  "STAFF_ROLE_ID": "1564261898935992382",
  "LOG_CHANNEL_ID": null,
  "ANNOUNCE_CHANNEL_ID": null,
  "TICKET_COOLDOWN_SECONDS": 300,
  "AUTO_CLOSE_DAYS": 7,
  "TRANSCRIPT_COMPRESSION": true,
  "LOG_LEVEL": "INFO",
  "BOT_ACTIVITY": "MP pour ouvrir un ticket ✈️"
}
```
Le bot log `Config source : config.json` au démarrage.

### 3. Lancement local
```bash
chmod +x run.sh
./run.sh
# ou manuel :
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python bot.py
```

### 3b. Docker (prod)
```bash
docker compose up --build -d
docker logs -f airfrance-helpine
```

### 4. Invitation bot
Invite avec scopes `bot` + `applications.commands` et perms :
- Gérer les salons, Gérer les messages, Voir les salons, Envoyer messages, Intégrer liens, Attacher fichiers, Lire historique, Utiliser slash commands

Vérifie que le bot est bien sur **1 seul serveur** (celui de l'ID) et que la catégorie existe.

---

## 🔧 Structure

```
bot.py              # Entrée, intents, setup_hook + views persistantes
config.py           # Charge config.json + constantes Air France
database.py         # SQLite async (tickets, messages, bans, config)
cogs/
  tickets.py        # Coeur : relay DM↔salon, création, fermeture, transcript
  annonce.py        # /annonce modal + /annonce-rapide
  admin.py          # /setup-tickets, /sync, /bot-info, /purge
utils/
  embeds.py         # Embeds AF
  transcript.py     # HTML + gzip
  permissions.py    # Helpers staff/admin
data/
  tickets.db        # WAL
  transcripts/      # HTML.gz
```

---

## 🛡️ Permissions

- `/annonce` : `Administrateur` uniquement (check `guild_permissions.administrator`)
- Ticket staff : rôle `1564261898935992382` OU admin
- `/setup-tickets`, `/ban-ticket`, `/sync` : admin

---

## 💾 Stockage & survie reboot - détails techniques

- **WAL** : écritures non bloquantes, survit à un crash sans corruption
- **Transcript gzip** : `data/transcripts/ticket-xxxx-123-171234.html.gz` (≈15KB vs 60KB)
- **Pas de cache RAM** : tout en DB, cooldowns en `dict` léger nettoyé au restart
- **Views persistantes** : `custom_id="ticket:xxx"` + `bot.add_view()` → boutons actifs même après `docker restart`
- **Restauration** : au `on_ready`, on liste `tickets WHERE status='open'` et on vérifie `fetch_channel`

---

## 📝 Exemple flux

1. User `Jean` MP : "Bonjour mon vol est annulé"
2. Bot crée `#ticket-jean-0465` dans catégorie `1560529185880154263`, ping `<@&1564261898935992382>`
3. Staff répond dans le salon : "Bonjour Jean, quel vol ?" → Jean reçoit DM embed
4. Jean répond en MP → staff voit embed dans ticket
5. Staff clique **Fermer** → transcript généré + envoyé en logs + DM "ticket fermé" + salon supprimé en 10s

---

## 🆘 Debug

- Logs `INFO` par défaut (`LOG_LEVEL=INFO` dans `config.json`)
- Vérifie catégorie/role IDs : `/bot-info` ou logs au démarrage
- Si bouton ne répond plus après reboot : normal si ID salon changé, mais `add_view` garantit la survie sinon

---

Fait avec ✈️ pour Air France Helpine
