# Guide de déploiement VPS — SMC Trading Bot

**Environnement cible :** Hostinger Linux Ubuntu, n8n en Docker, Python installé.  
**Port choisi :** 8001 (évite le conflit avec n8n qui utilise généralement 5678).

---

## Vue d'ensemble

```
TradingView ──HTTPS──► nginx :443 ──► uvicorn :8001 ──► PineConnector ──► MT5
                              (reverse proxy)   (FastAPI bot)
```

---

## Prérequis VPS

Connecte-toi en SSH à ton VPS puis vérifie les versions :

```bash
python3 --version      # doit être >= 3.10
pip3 --version
nginx -v
systemctl --version
```

Si nginx n'est pas installé :
```bash
sudo apt update && sudo apt install -y nginx
```

---

## Étape 1 — Cloner le repo Git

```bash
# Choisir le répertoire d'installation
cd /opt
sudo git clone https://github.com/TON_USER/smc-trading-bot.git
sudo chown -R $USER:$USER /opt/smc-trading-bot
cd /opt/smc-trading-bot
```

> **Si pas encore de repo Git :** zippe le dossier local, transfère avec `scp` ou FileZilla,
> décompresse dans `/opt/smc-trading-bot`.
> ```bash
> scp -r "C:/CLAUDE CODE/smc-trading-bot" user@TON_VPS_IP:/opt/
> ```

---

## Étape 2 — Environnement Python (venv)

```bash
cd /opt/smc-trading-bot

# Créer l'environnement virtuel
python3 -m venv venv

# Activer
source venv/bin/activate

# Installer les dépendances
pip install --upgrade pip
pip install -r bot/requirements.txt

# Vérifier
python -c "import fastapi, uvicorn, httpx; print('OK')"
```

---

## Étape 3 — Fichier .env

```bash
cd /opt/smc-trading-bot
cp .env.example .env
nano .env
```

Remplir avec les vraies valeurs :

```env
# Telegram — obtenu via @BotFather sur Telegram
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=987654321

# PineConnector — visible dans ton compte pineconnector.net
PINECONNECTOR_LICENSE_ID=TON_LICENSE_ID

# Clé secrète webhook — génère une chaîne aléatoire forte (min 32 chars)
# Commande pour générer : openssl rand -hex 32
WEBHOOK_SECRET_KEY=CHANGE_MOI_AVEC_UNE_CLE_ALEATOIRE_FORTE

# Adresse publique du VPS (optionnel, pour documentation)
VPS_HOST=TON_IP_VPS

# Niveau de log : DEBUG pour diagnostiquer, INFO en prod, WARNING pour le minimum
LOG_LEVEL=INFO
```

> **Générer une clé secrète robuste :**
> ```bash
> openssl rand -hex 32
> # Exemple de sortie : a3f8c2d1e4b5a6f7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1
> ```
> Copie cette valeur dans `WEBHOOK_SECRET_KEY` ET dans l'alerte TradingView (champ `secret` du payload JSON).

Sécuriser le fichier :
```bash
chmod 600 .env
```

---

## Étape 4 — Service systemd

Ce service démarre automatiquement le bot au boot du VPS et le redémarre en cas de crash.

```bash
sudo nano /etc/systemd/system/smc-bot.service
```

Coller ce contenu (remplace `ton_user` par ton nom d'utilisateur Linux) :

```ini
[Unit]
Description=SMC Trading Bot
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=ton_user
Group=ton_user
WorkingDirectory=/opt/smc-trading-bot
Environment="PATH=/opt/smc-trading-bot/venv/bin"
EnvironmentFile=/opt/smc-trading-bot/.env
ExecStart=/opt/smc-trading-bot/venv/bin/uvicorn bot.main:app --host 127.0.0.1 --port 8001 --workers 1
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=smc-bot

[Install]
WantedBy=multi-user.target
```

> **Important :** `--host 127.0.0.1` — le bot écoute uniquement en local.
> Nginx fait le pont vers l'extérieur. Ne jamais exposer le port 8001 directement.

Activer et démarrer :

```bash
sudo systemctl daemon-reload
sudo systemctl enable smc-bot
sudo systemctl start smc-bot

# Vérifier le statut
sudo systemctl status smc-bot
```

Voir les logs en temps réel :
```bash
sudo journalctl -u smc-bot -f
```

---

## Étape 5 — Nginx reverse proxy

### Option A — Sans SSL (test local ou IP directe)

```bash
sudo nano /etc/nginx/sites-available/smc-bot
```

```nginx
server {
    listen 80;
    server_name TON_IP_VPS;  # ou ton domaine ex: bot.mondomaine.com

    # Bloquer toutes les routes sauf les endpoints du bot
    location /webhook {
        proxy_pass         http://127.0.0.1:8001;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_read_timeout 30s;
    }

    location /trade/close {
        proxy_pass         http://127.0.0.1:8001;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_read_timeout 30s;
    }

    location /health {
        proxy_pass         http://127.0.0.1:8001;
        proxy_set_header   Host $host;
    }

    location /status {
        # Restreindre l'accès au status (optionnel : ajouter allow/deny par IP)
        proxy_pass         http://127.0.0.1:8001;
        proxy_set_header   Host $host;
    }

    # Bloquer tout le reste (sécurité)
    location / {
        return 404;
    }
}
```

### Option B — Avec SSL Let's Encrypt (recommandé en production)

```bash
# Installer certbot
sudo apt install -y certbot python3-certbot-nginx

# Obtenir le certificat (remplace par ton domaine)
sudo certbot --nginx -d bot.mondomaine.com

# certbot modifie automatiquement la config nginx pour HTTPS
```

Activer la config et redémarrer :

```bash
sudo ln -s /etc/nginx/sites-available/smc-bot /etc/nginx/sites-enabled/
sudo nginx -t          # vérifier la syntaxe
sudo systemctl reload nginx
```

---

## Étape 6 — Test /health

```bash
# Depuis le VPS (local)
curl http://127.0.0.1:8001/health

# Depuis l'extérieur (remplace par ton IP ou domaine)
curl http://TON_IP_VPS/health

# Avec SSL
curl https://bot.mondomaine.com/health
```

Réponse attendue :
```json
{"status": "ok", "timestamp": "2024-01-15T09:00:00.123456+00:00"}
```

Tester le /status :
```bash
curl http://TON_IP_VPS/status | python3 -m json.tool
```

---

## Étape 7 — Test webhook simulé (curl)

### Signal valide — doit retourner ALLOW

```bash
curl -s -X POST http://TON_IP_VPS/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "secret":       "TA_CLE_WEBHOOK_SECRET_KEY",
    "event_type":   "BOS_BULL",
    "symbol":       "EURUSD",
    "timeframe":    "15",
    "price":        1.09500,
    "direction":    "bull",
    "timestamp":    "2024-01-15T09:15:00Z",
    "sl_pips":      20,
    "tp_pips":      50,
    "ema_50_value": 1.09000,
    "session":      "london"
  }' | python3 -m json.tool
```

Réponse attendue (si en session London et filtres passés) :
```json
{
    "status": "ALLOW",
    "event_type": "BOS_BULL",
    "symbol": "EURUSD",
    "direction": "bull",
    "lot_size": 0.15,
    "rr": 2.5,
    "pineconnector_cmd": "TON_LICENSE,buy,EURUSD,contracts=0.15,sl=20,tp=50",
    ...
}
```

### Signal hors session — doit retourner BLOCK

```bash
# Envoie un signal à 03:00 UTC (le bot utilise l'heure réelle du VPS)
# Si le test est fait hors session London/NY, le filtre SESSION bloquera
curl -s -X POST http://TON_IP_VPS/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "secret":       "TA_CLE_WEBHOOK_SECRET_KEY",
    "event_type":   "BOS_BULL",
    "symbol":       "EURUSD",
    "timeframe":    "15",
    "price":        1.09500,
    "direction":    "bull",
    "timestamp":    "2024-01-15T03:00:00Z",
    "sl_pips":      20,
    "tp_pips":      50,
    "ema_50_value": 1.09000,
    "session":      "london"
  }' | python3 -m json.tool
```

### Test /trade/close — clôture manuelle d'un trade

```bash
curl -s -X POST http://TON_IP_VPS/trade/close \
  -H "Content-Type: application/json" \
  -d '{
    "secret":   "TA_CLE_WEBHOOK_SECRET_KEY",
    "trade_id": "TEST-001",
    "symbol":   "EURUSD",
    "pnl_eur":  -25.50
  }' | python3 -m json.tool
```

Réponse attendue :
```json
{
    "status": "ok",
    "trade_id": "TEST-001",
    "symbol": "EURUSD",
    "pnl_eur": -25.5,
    "risk": {
        "open_trades": 0,
        "daily_loss_eur": 25.5,
        "daily_limit_eur": 90.0,
        "daily_remaining_eur": 64.5,
        ...
    }
}
```

---

## Commandes de maintenance courantes

```bash
# Voir les logs du bot
sudo journalctl -u smc-bot -f

# Voir les 100 dernières lignes
sudo journalctl -u smc-bot -n 100

# Voir les logs applicatifs
tail -f /opt/smc-trading-bot/bot/logs/bot.log
tail -f /opt/smc-trading-bot/bot/logs/signals.log

# Redémarrer le bot (ex: après modif du .env)
sudo systemctl restart smc-bot

# Arrêter le bot manuellement
sudo systemctl stop smc-bot

# Vérifier que le port 8001 est bien en écoute
ss -tlnp | grep 8001

# Mettre à jour le code (depuis Git)
cd /opt/smc-trading-bot
git pull
sudo systemctl restart smc-bot
```

---

## Sécurité — Points importants

| Point | Action |
|-------|--------|
| `WEBHOOK_SECRET_KEY` | Minimum 32 caractères aléatoires — ne jamais committer dans Git |
| Port 8001 | Bloqué par le firewall, uniquement accessible via nginx |
| `.env` | Permissions 600, jamais dans le repo |
| Swagger UI | Désactivé en prod (`docs_url=None`) |
| /status | Envisager un allow/deny par IP dans nginx si VPS partagé |

Bloquer le port 8001 depuis l'extérieur (UFW) :
```bash
sudo ufw allow 80
sudo ufw allow 443
sudo ufw allow 22
sudo ufw deny 8001    # le bot n'est accessible que via nginx
sudo ufw enable
```

---

## Intégration avec n8n existant

N8n tourne déjà en Docker sur ce VPS. Pas de conflit si :
- n8n utilise le port 5678 (standard Docker)
- Le bot utilise le port 8001
- Nginx redirige selon le domaine ou le path

Si tu veux que n8n reçoive aussi des webhooks TradingView à l'avenir, tu peux utiliser
des sous-domaines différents dans nginx (`bot.mondomaine.com` vs `n8n.mondomaine.com`).
