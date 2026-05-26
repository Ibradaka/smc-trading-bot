#!/usr/bin/env bash
# ============================================================
# SMC Bot — Health Check COMPLET (a lancer sur le VPS Linux)
# ============================================================
# Teste la chaine de bout en bout :
#   1. Bot local (uvicorn sur 127.0.0.1:8001)
#   2. Executor MT5 (45.128.152.242:9000) — accessible uniquement depuis ce VPS
#   3. Etat du bot via Cloudflare (smc.feelyoo.com — comme TradingView le voit)
#
# Utilisation (depuis Hostinger en SSH) :
#   bash /opt/smc-trading-bot/scripts/healthcheck-from-linux.sh
# ============================================================

BOT_LOCAL="http://127.0.0.1:8001"
BOT_PUBLIC="https://smc.feelyoo.com"
EXEC_URL="http://45.128.152.242:9000"

GREEN="\033[0;32m"
RED="\033[0;31m"
YEL="\033[1;33m"
CYA="\033[0;36m"
NC="\033[0m"

# --- 1. Bot local --------------------------------------------------------
echo -e "\n${CYA}--- Bot local (uvicorn 8001) ---${NC}"
if curl -fsS --max-time 5 "$BOT_LOCAL/health" > /tmp/_hc 2>&1; then
    echo -e "${GREEN}OK${NC}  $(cat /tmp/_hc)"
else
    echo -e "${RED}KO${NC}  bot local injoignable (verifier : systemctl status smc-bot)"
fi

# --- 2. Executor + MT5 + Compte (le vrai test de la chaine) -------------
echo -e "\n${CYA}--- Executor MT5 (VPS Windows) ---${NC}"
if curl -fsS --max-time 5 "$EXEC_URL/health" > /tmp/_hc 2>&1; then
    STATUS=$(grep -oP '"status":"\K[^"]+' /tmp/_hc || echo "?")
    if [ "$STATUS" = "ok" ]; then
        echo -e "${GREEN}OK${NC}  $(cat /tmp/_hc)"
    else
        echo -e "${RED}KO${NC}  MT5 down : $(cat /tmp/_hc)"
    fi
else
    echo -e "${RED}KO${NC}  executor injoignable"
    echo -e "${YEL}    -> RDP sur 45.128.152.242, verifier que MT5 est ouvert et que la tache 'SMC Executor' tourne${NC}"
fi

# --- 3. Bot vu depuis le public (comme TradingView) ---------------------
echo -e "\n${CYA}--- Bot public (Cloudflare -> Hostinger) ---${NC}"
if curl -fsS --max-time 5 "$BOT_PUBLIC/status" > /tmp/_hc 2>&1; then
    echo -e "${GREEN}OK${NC}  Cloudflare et nginx OK, voici l'etat metier :"
    cat /tmp/_hc | python3 -m json.tool 2>/dev/null || cat /tmp/_hc
else
    echo -e "${RED}KO${NC}  bot public injoignable (verifier : Cloudflare DNS, nginx)"
fi

echo ""
