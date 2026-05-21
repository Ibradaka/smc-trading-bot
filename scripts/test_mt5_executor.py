"""
Test local de l'executor MT5 — PHASE 1
======================================
A lancer sur la machine Windows ou tournent MetaTrader 5 + l'executor.

Procedure :
  1. Ouvre MetaTrader 5, connecte-toi au compte DEMO, AutoTrading active (bouton vert)
  2. Definis la cle :  $env:MT5_EXECUTOR_SECRET="ta_cle"  (PowerShell)
  3. Lance l'executor :   python bot/execution/mt5_executor_service.py
  4. Dans un autre terminal :  python scripts/test_mt5_executor.py [SYMBOLE]

Exemples :
  python scripts/test_mt5_executor.py            -> teste EURUSDs
  python scripts/test_mt5_executor.py XAUUSDs     -> teste le gold
  python scripts/test_mt5_executor.py USTECs      -> teste le nasdaq

Place un MICRO ordre de test (0.01 lot) sur le compte demo et affiche le resultat.
"""

import os
import sys

import httpx

EXECUTOR_URL    = os.environ.get("MT5_EXECUTOR_URL", "http://127.0.0.1:9000/order")
EXECUTOR_HEALTH = EXECUTOR_URL.replace("/order", "/health")
SECRET          = os.environ.get("MT5_EXECUTOR_SECRET", "")

# Reglages de test par symbole — sl_pips / tp_pips dans l'unite "pip" de la strategie
DEFAULTS = {
    "EURUSDs": {"sl_pips": 30,  "tp_pips": 60},    # pip = 0.0001
    "XAUUSDs": {"sl_pips": 200, "tp_pips": 400},   # pip = 0.1  -> SL 20$, TP 40$
    "USTECs":  {"sl_pips": 100, "tp_pips": 200},   # pip = 1.0  -> SL 100 pts, TP 200 pts
}

# Symbole passe en argument, sinon EURUSDs par defaut
symbol = sys.argv[1] if len(sys.argv) > 1 else "EURUSDs"
cfg    = DEFAULTS.get(symbol, {"sl_pips": 30, "tp_pips": 60})

test_order = {
    "secret":    SECRET,
    "symbol":    symbol,
    "direction": "bear",     # vente
    "lot":       0.01,
    "sl_pips":   cfg["sl_pips"],
    "tp_pips":   cfg["tp_pips"],
    "comment":   "SMC TEST",
}

print("=" * 55)
print(f" TEST EXECUTOR MT5 — Phase 1 — symbole : {symbol}")
print("=" * 55)

print("\n1) Sante de l'executor...")
try:
    h = httpx.get(EXECUTOR_HEALTH, timeout=10).json()
    print("   ", h)
    if h.get("status") != "ok":
        print("   ⚠️  MT5 ne repond pas — verifie que le terminal est ouvert et connecte.")
        raise SystemExit(1)
except Exception as exc:
    print("   ❌ ECHEC — l'executor ne repond pas :", exc)
    print("      Verifie que 'python bot/execution/mt5_executor_service.py' tourne.")
    raise SystemExit(1)

print(f"\n2) Envoi d'un ordre de test ({symbol}, 0.01 lot, vente, "
      f"SL {cfg['sl_pips']} / TP {cfg['tp_pips']})...")
try:
    resp = httpx.post(EXECUTOR_URL, json=test_order, timeout=15)
    data = resp.json()
except Exception as exc:
    print("   ❌ ECHEC envoi :", exc)
    raise SystemExit(1)

print("   Statut HTTP :", resp.status_code)
print("   Reponse     :", data)

if data.get("success"):
    print(f"\n✅ SUCCES — ordre place sur {symbol}, ticket {data.get('ticket')}.")
    print("   Ouvre MT5 -> onglet 'Trade' : la position doit etre visible.")
    print("   (Tu peux la fermer manuellement, c'etait juste un test.)")
else:
    print(f"\n❌ ECHEC — {data.get('error')}")
