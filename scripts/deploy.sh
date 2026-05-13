#!/bin/bash
# =============================================================================
# SMC Trading Bot — Script de déploiement automatisé
# Couvre les étapes 1 à 4 du guide docs/deployment.md
#
# Usage :
#   chmod +x scripts/deploy.sh
#   ./scripts/deploy.sh
#
# Ce script doit être lancé depuis le VPS, dans le répertoire /opt
# (ou depuis le dossier parent de l'installation souhaitée).
# =============================================================================

set -euo pipefail   # arrêt immédiat sur erreur, variable non définie, pipe échoué

# ---------------------------------------------------------------------------
# Configuration — modifier si nécessaire
# ---------------------------------------------------------------------------

INSTALL_DIR="/opt/smc-trading-bot"
VENV_DIR="$INSTALL_DIR/venv"
PYTHON="python3"
PORT=8001
SERVICE_NAME="smc-bot"
GIT_REPO=""   # Ex: https://github.com/TON_USER/smc-trading-bot.git
              # Laisser vide si tu transfères le dossier manuellement (scp)

# ---------------------------------------------------------------------------
# Couleurs
# ---------------------------------------------------------------------------

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERR]${NC}   $*"; exit 1; }
step()    { echo -e "\n${BOLD}${CYAN}==> $*${NC}"; }

# ---------------------------------------------------------------------------
# Vérifications préalables
# ---------------------------------------------------------------------------

step "Vérifications préalables"

# Python >= 3.10
PY_VERSION=$($PYTHON -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]); then
    error "Python >= 3.10 requis, version détectée : $PY_VERSION"
fi
success "Python $PY_VERSION détecté"

# pip3 disponible
if ! command -v pip3 &>/dev/null; then
    warn "pip3 introuvable — installation..."
    sudo apt-get update -qq && sudo apt-get install -y python3-pip
fi
success "pip3 disponible"

# ---------------------------------------------------------------------------
# Étape 1 — Récupérer le code
# ---------------------------------------------------------------------------

step "Étape 1 — Récupérer le code"

if [ -n "$GIT_REPO" ]; then
    if [ -d "$INSTALL_DIR/.git" ]; then
        info "Repo existant détecté — git pull"
        git -C "$INSTALL_DIR" pull
    else
        info "Clonage de $GIT_REPO vers $INSTALL_DIR"
        sudo git clone "$GIT_REPO" "$INSTALL_DIR"
        sudo chown -R "$USER:$USER" "$INSTALL_DIR"
    fi
    success "Code récupéré depuis Git"
elif [ -d "$INSTALL_DIR" ]; then
    success "Dossier $INSTALL_DIR déjà présent (transfert manuel détecté)"
else
    error "GIT_REPO non défini et $INSTALL_DIR absent.
    Soit :
      - Définis GIT_REPO dans ce script
      - Soit transfère le dossier manuellement vers $INSTALL_DIR via scp/FileZilla"
fi

cd "$INSTALL_DIR"

# ---------------------------------------------------------------------------
# Étape 2 — Environnement virtuel Python
# ---------------------------------------------------------------------------

step "Étape 2 — Environnement virtuel Python"

if [ ! -d "$VENV_DIR" ]; then
    info "Création du venv dans $VENV_DIR"
    $PYTHON -m venv "$VENV_DIR"
    success "venv créé"
else
    info "venv existant trouvé — mise à jour des dépendances"
fi

# Activer le venv
source "$VENV_DIR/bin/activate"

info "Mise à jour de pip..."
pip install --upgrade pip --quiet

info "Installation de bot/requirements.txt..."
pip install -r bot/requirements.txt --quiet

# Vérification rapide des imports critiques
python -c "import fastapi, uvicorn, httpx, dotenv; print('Imports OK')" || \
    error "Échec de l'import d'un module — vérifie bot/requirements.txt"

success "Dépendances installées et vérifiées"

# ---------------------------------------------------------------------------
# Étape 3 — Fichier .env
# ---------------------------------------------------------------------------

step "Étape 3 — Fichier .env"

if [ -f "$INSTALL_DIR/.env" ]; then
    warn ".env déjà présent — non écrasé."
    warn "Vérifie manuellement que toutes les variables sont correctes :"
    warn "  nano $INSTALL_DIR/.env"
else
    info "Création du .env depuis .env.example"
    cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"

    # Générer une clé secrète aléatoire automatiquement
    if command -v openssl &>/dev/null; then
        GENERATED_SECRET=$(openssl rand -hex 32)
        sed -i "s/^WEBHOOK_SECRET_KEY=.*/WEBHOOK_SECRET_KEY=$GENERATED_SECRET/" "$INSTALL_DIR/.env"
        success "WEBHOOK_SECRET_KEY générée automatiquement : $GENERATED_SECRET"
        echo ""
        warn "IMPORTANT : copie cette clé dans ton alerte TradingView (champ 'secret' du payload JSON)"
        echo ""
    fi

    chmod 600 "$INSTALL_DIR/.env"

    echo ""
    warn "Le fichier .env a été créé mais les variables suivantes sont VIDES :"
    warn "  TELEGRAM_BOT_TOKEN    — depuis @BotFather sur Telegram"
    warn "  TELEGRAM_CHAT_ID      — ton ID de chat Telegram"
    warn "  PINECONNECTOR_LICENSE_ID — depuis pineconnector.net"
    warn ""
    warn "Édite le fichier maintenant :"
    warn "  nano $INSTALL_DIR/.env"
    echo ""
    read -r -p "Appuie sur Entrée quand le .env est complété pour continuer..."
fi

# Vérifier les variables critiques
source "$INSTALL_DIR/.env" 2>/dev/null || true

MISSING_VARS=()
[ -z "${TELEGRAM_BOT_TOKEN:-}" ]       && MISSING_VARS+=("TELEGRAM_BOT_TOKEN")
[ -z "${TELEGRAM_CHAT_ID:-}" ]         && MISSING_VARS+=("TELEGRAM_CHAT_ID")
[ -z "${PINECONNECTOR_LICENSE_ID:-}" ] && MISSING_VARS+=("PINECONNECTOR_LICENSE_ID")
[ -z "${WEBHOOK_SECRET_KEY:-}" ]       && MISSING_VARS+=("WEBHOOK_SECRET_KEY")

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
    warn "Variables non renseignées dans .env : ${MISSING_VARS[*]}"
    warn "Le bot démarrera mais certaines fonctions seront désactivées."
else
    success "Toutes les variables .env sont renseignées"
fi

# ---------------------------------------------------------------------------
# Étape 4 — Service systemd
# ---------------------------------------------------------------------------

step "Étape 4 — Service systemd"

CURRENT_USER=$(whoami)
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

# Générer le fichier service
sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=SMC Trading Bot
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=$CURRENT_USER
Group=$CURRENT_USER
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$VENV_DIR/bin"
EnvironmentFile=$INSTALL_DIR/.env
ExecStart=$VENV_DIR/bin/uvicorn bot.main:app --host 127.0.0.1 --port $PORT --workers 1
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=$SERVICE_NAME

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

# Attendre 3 secondes que le bot démarre
sleep 3

# Vérifier que le service tourne
if sudo systemctl is-active --quiet "$SERVICE_NAME"; then
    success "Service $SERVICE_NAME actif et en cours d'exécution"
else
    error "Le service $SERVICE_NAME n'a pas démarré.
    Voir les logs : sudo journalctl -u $SERVICE_NAME -n 50"
fi

# Test /health en local
info "Test de l'endpoint /health..."
sleep 2
HEALTH=$(curl -s --max-time 5 "http://127.0.0.1:$PORT/health" 2>/dev/null || echo "ERREUR")

if echo "$HEALTH" | grep -q '"ok"'; then
    success "/health répond correctement : $HEALTH"
else
    warn "/health n'a pas répondu comme attendu : $HEALTH"
    warn "Vérifie les logs : sudo journalctl -u $SERVICE_NAME -n 30"
fi

# ---------------------------------------------------------------------------
# Résumé final
# ---------------------------------------------------------------------------

echo ""
echo -e "${BOLD}${GREEN}============================================================${NC}"
echo -e "${BOLD}${GREEN}   Déploiement terminé — SMC Trading Bot                   ${NC}"
echo -e "${BOLD}${GREEN}============================================================${NC}"
echo ""
echo -e "  ${CYAN}Bot actif sur :${NC}       http://127.0.0.1:$PORT"
echo -e "  ${CYAN}Service systemd :${NC}     $SERVICE_NAME"
echo -e "  ${CYAN}Logs applicatifs :${NC}    $INSTALL_DIR/bot/logs/bot.log"
echo -e "  ${CYAN}Logs signaux :${NC}        $INSTALL_DIR/bot/logs/signals.log"
echo ""
echo -e "  ${YELLOW}Étapes restantes (manuelles) :${NC}"
echo -e "  ${YELLOW}  5. Configurer nginx — voir docs/deployment.md §Étape 5${NC}"
echo -e "  ${YELLOW}  6. Tester le webhook avec curl — voir docs/deployment.md §Étape 7${NC}"
echo ""
echo -e "  ${CYAN}Commandes utiles :${NC}"
echo -e "    sudo journalctl -u $SERVICE_NAME -f       # logs temps réel"
echo -e "    sudo systemctl restart $SERVICE_NAME      # redémarrer"
echo -e "    sudo systemctl status $SERVICE_NAME       # statut"
echo ""
