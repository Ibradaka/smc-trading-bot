"""
SMC MT5 Executor Service
========================
Tourne sur la machine Windows qui heberge MetaTrader 5 (PC en test, VPS en prod).
Recoit les ordres du bot via HTTP et les place avec le package officiel MetaTrader5.
Remplace PineConnector — gratuit, sans intermediaire.

PREREQUIS (machine Windows) :
  - MetaTrader 5 installe, OUVERT et connecte au compte
  - pip install MetaTrader5 fastapi uvicorn httpx

LANCER :
  python bot/execution/mt5_executor_service.py
  (ecoute sur le port 9000)

VARIABLES D'ENVIRONNEMENT (optionnelles) :
  MT5_EXECUTOR_SECRET : cle partagee avec le bot (auth des requetes)
  MT5_EXECUTOR_PORT   : port d'ecoute (defaut 9000)
  MT5_LOGIN / MT5_PASSWORD / MT5_SERVER : si presents -> auto-login MT5
"""

import logging
import os

import MetaTrader5 as mt5
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("mt5_executor")

# --- Configuration ---------------------------------------------------------

EXECUTOR_SECRET = os.environ.get("MT5_EXECUTOR_SECRET", "")
EXECUTOR_PORT   = int(os.environ.get("MT5_EXECUTOR_PORT", "9000"))
MT5_LOGIN       = os.environ.get("MT5_LOGIN", "")
MT5_PASSWORD    = os.environ.get("MT5_PASSWORD", "")
MT5_SERVER      = os.environ.get("MT5_SERVER", "")
MT5_PATH        = os.environ.get("MT5_PATH", "")

# Chemins ou MT5 peut etre installe — essayes si MT5_PATH non defini.
# Le package MetaTrader5 ne trouve pas toujours le terminal seul (VPS, install
# non standard) -> on lui passe le chemin explicite du terminal64.exe.
_COMMON_MT5_PATHS = [
    r"C:\Program Files\Switch Markets MT5\terminal64.exe",
    r"C:\Program Files\Switch Markets MetaTrader 5\terminal64.exe",
    r"C:\Program Files\MetaTrader 5\terminal64.exe",
]

MAGIC = 13013   # identifiant des ordres places par ce bot (visible dans MT5)

# Taille d'un "pip" par symbole — DOIT matcher le 'pip' hardcode des scripts Pine
PIP_SIZE = {
    "XAUUSDs": 0.1,
    "EURUSDs": 0.0001,
    "USTECs":  1.0,
}

app = FastAPI(title="SMC MT5 Executor")


# --- Connexion MT5 ---------------------------------------------------------

def ensure_mt5() -> tuple[bool, str]:
    """Garantit une connexion MT5 active. (Re)initialise si besoin."""
    if mt5.terminal_info() is not None:
        return True, ""

    # Resoudre le chemin du terminal MT5 (explicite ou auto-detecte)
    path = MT5_PATH
    if not path:
        for p in _COMMON_MT5_PATHS:
            if os.path.exists(p):
                path = p
                break

    kwargs = {}
    if path:
        kwargs["path"] = path
    if MT5_LOGIN and MT5_PASSWORD and MT5_SERVER:
        kwargs["login"]    = int(MT5_LOGIN)
        kwargs["password"] = MT5_PASSWORD
        kwargs["server"]   = MT5_SERVER

    ok = mt5.initialize(**kwargs)
    if not ok:
        return False, (f"mt5.initialize() echec (path={path or 'auto'}) : "
                       f"{mt5.last_error()}")
    return True, ""


# --- Mode de remplissage ---------------------------------------------------

def _filling_order(info) -> list:
    """
    Ordre des modes de remplissage a tenter, deduit de la spec du symbole.
    info.filling_mode est un bitmask : bit 1 = FOK autorise, bit 2 = IOC.
    On tente d'abord le mode supporte, puis les autres en filet de securite.
    """
    fm = info.filling_mode
    order = []
    if fm & 2:
        order.append(mt5.ORDER_FILLING_IOC)
    if fm & 1:
        order.append(mt5.ORDER_FILLING_FOK)
    for extra in (mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_RETURN):
        if extra not in order:
            order.append(extra)
    return order


# --- Modeles de requete ----------------------------------------------------

class OrderRequest(BaseModel):
    secret: str
    symbol: str
    direction: str          # "bull" ou "bear"
    lot: float
    sl_pips: float
    tp_pips: float
    comment: str = "SMC bot"


class CloseRequest(BaseModel):
    secret: str
    symbol: str


class PositionsRequest(BaseModel):
    secret: str


# --- Endpoints -------------------------------------------------------------

@app.get("/health")
def health():
    """Verifie que MT5 repond — pour le monitoring."""
    ok, err = ensure_mt5()
    acc = mt5.account_info() if ok else None
    return {
        "status":  "ok" if ok else "mt5_down",
        "error":   err,
        "account": acc.login if acc else None,
        "balance": acc.balance if acc else None,
    }


@app.post("/order")
def place_order(req: OrderRequest):
    """Place un ordre marche avec SL et TP sur le compte MT5 connecte."""

    # 1. Authentification
    if not EXECUTOR_SECRET or req.secret != EXECUTOR_SECRET:
        logger.warning("Requete refusee : secret invalide")
        return {"success": False, "error": "secret invalide"}

    # 2. Connexion MT5
    ok, err = ensure_mt5()
    if not ok:
        return {"success": False, "error": err}

    symbol = req.symbol

    # 3. Symbole present dans le Market Watch
    if not mt5.symbol_select(symbol, True):
        return {"success": False, "error": f"symbole {symbol} introuvable chez le broker"}

    info = mt5.symbol_info(symbol)
    tick = mt5.symbol_info_tick(symbol)
    if info is None or tick is None:
        return {"success": False, "error": f"pas de cotation pour {symbol}"}

    pip = PIP_SIZE.get(symbol)
    if pip is None:
        return {"success": False, "error": f"PIP_SIZE non defini pour {symbol}"}

    # 4. Sens, prix d'entree, SL, TP
    is_buy     = req.direction == "bull"
    order_type = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL
    price      = tick.ask if is_buy else tick.bid

    sl_dist = req.sl_pips * pip
    tp_dist = req.tp_pips * pip
    sl = price - sl_dist if is_buy else price + sl_dist
    tp = price + tp_dist if is_buy else price - tp_dist

    digits = info.digits
    price = round(price, digits)
    sl    = round(sl, digits)
    tp    = round(tp, digits)

    # 5. Volume cale sur le pas du broker (volume_step)
    step = info.volume_step or 0.01
    lot  = round(req.lot / step) * step
    lot  = max(info.volume_min, min(lot, info.volume_max))
    lot  = round(lot, 2)

    # 6. Mode de remplissage — determine d'apres la spec du symbole.
    fm = info.filling_mode
    fill_order = _filling_order(info)

    sym_diag = (f"filling_mode={fm}, trade_mode={info.trade_mode}, "
                f"exemode={info.trade_exemode}, vol_min={info.volume_min}, "
                f"vol_step={info.volume_step}")

    base = {
        "action":    mt5.TRADE_ACTION_DEAL,
        "symbol":    symbol,
        "volume":    lot,
        "type":      order_type,
        "price":     price,
        "sl":        sl,
        "tp":        tp,
        "deviation": 30,
        "magic":     MAGIC,
        "comment":   req.comment[:31],
        "type_time": mt5.ORDER_TIME_GTC,
    }

    # 7. Envoi — tente chaque mode de remplissage jusqu'au succes
    result = None
    attempts = []
    for filling in fill_order:
        result = mt5.order_send(dict(base, type_filling=filling))
        rc = result.retcode if result is not None else "None"
        attempts.append(f"fill{filling}->{rc}")
        if result is not None and result.retcode == mt5.TRADE_RETCODE_DONE:
            break

    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        rc = result.retcode if result else "None"
        cm = result.comment if result else str(mt5.last_error())
        logger.warning("Ordre %s rejete : retcode=%s | %s | tentatives=%s",
                        symbol, rc, sym_diag, attempts)
        return {
            "success":  False,
            "error":    f"ordre rejete (retcode {rc}) : {cm}",
            "diag":     sym_diag,
            "attempts": attempts,
        }

    logger.info("Ordre place : %s %s lot=%.2f ticket=%s prix=%s sl=%s tp=%s",
                req.direction, symbol, lot, result.order, result.price, sl, tp)
    return {
        "success":   True,
        "ticket":    result.order,
        "symbol":    symbol,
        "direction": req.direction,
        "volume":    result.volume,
        "price":     result.price,
        "sl":        sl,
        "tp":        tp,
    }


@app.post("/close")
def close_positions(req: CloseRequest):
    """
    Ferme toutes les positions du bot (magic 13013) sur un symbole.
    Utilise par le flat de fin de session (anti-gap NASDAQ).

    Renvoie success=True meme si 0 position a fermer : l'objectif "etre flat"
    est alors deja atteint (le trade a pu toucher son TP/SL avant la cloture).
    """

    # 1. Authentification
    if not EXECUTOR_SECRET or req.secret != EXECUTOR_SECRET:
        logger.warning("Requete /close refusee : secret invalide")
        return {"success": False, "error": "secret invalide"}

    # 2. Connexion MT5
    ok, err = ensure_mt5()
    if not ok:
        return {"success": False, "error": err}

    symbol = req.symbol

    # 3. Symbole present dans le Market Watch
    if not mt5.symbol_select(symbol, True):
        return {"success": False, "error": f"symbole {symbol} introuvable chez le broker"}

    info = mt5.symbol_info(symbol)
    if info is None:
        return {"success": False, "error": f"pas d'info pour {symbol}"}

    positions = mt5.positions_get(symbol=symbol) or ()
    fill_order = _filling_order(info)

    closed = 0
    errors = []
    for pos in positions:
        if pos.magic != MAGIC:
            continue   # on ne touche QUE les positions placees par ce bot

        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            errors.append(f"ticket {pos.ticket} : pas de cotation")
            continue

        is_buy     = pos.type == mt5.POSITION_TYPE_BUY
        close_type = mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY
        price      = tick.bid if is_buy else tick.ask

        base = {
            "action":    mt5.TRADE_ACTION_DEAL,
            "symbol":    symbol,
            "volume":    pos.volume,
            "type":      close_type,
            "position":  pos.ticket,
            "price":     round(price, info.digits),
            "deviation": 30,
            "magic":     MAGIC,
            "comment":   "SMC close",
            "type_time": mt5.ORDER_TIME_GTC,
        }

        result = None
        for filling in fill_order:
            result = mt5.order_send(dict(base, type_filling=filling))
            if result is not None and result.retcode == mt5.TRADE_RETCODE_DONE:
                break

        if result is not None and result.retcode == mt5.TRADE_RETCODE_DONE:
            closed += 1
            logger.info("Position fermee : %s ticket=%s vol=%.2f",
                        symbol, pos.ticket, pos.volume)
        else:
            rc = result.retcode if result else "None"
            errors.append(f"ticket {pos.ticket} : retcode {rc}")

    if errors:
        logger.warning("Cloture %s incomplete : %s", symbol, "; ".join(errors))
        return {"success": False, "closed": closed, "error": "; ".join(errors)}

    logger.info("Cloture %s OK — %d position(s) fermee(s)", symbol, closed)
    return {"success": True, "closed": closed, "symbol": symbol}


@app.post("/positions")
def open_positions(req: PositionsRequest):
    """
    Renvoie le nombre de positions ouvertes placees par ce bot (magic 13013).
    Utilise par la reconciliation : le bot resynchronise son compteur de
    trades ouverts sur cette verite MT5 avant le filtre RISK.
    """
    if not EXECUTOR_SECRET or req.secret != EXECUTOR_SECRET:
        logger.warning("Requete /positions refusee : secret invalide")
        return {"success": False, "error": "secret invalide"}

    ok, err = ensure_mt5()
    if not ok:
        return {"success": False, "error": err}

    positions = mt5.positions_get() or ()
    bot_positions = [p for p in positions if p.magic == MAGIC]

    return {
        "success": True,
        "count":   len(bot_positions),
        "tickets": [p.ticket for p in bot_positions],
        "symbols": [p.symbol for p in bot_positions],
    }


if __name__ == "__main__":
    logger.info("Demarrage SMC MT5 Executor — port %d", EXECUTOR_PORT)
    started, err = ensure_mt5()
    if started:
        acc = mt5.account_info()
        logger.info("MT5 connecte — compte %s, solde %.2f %s",
                    acc.login if acc else "?",
                    acc.balance if acc else 0,
                    acc.currency if acc else "")
    else:
        logger.warning("MT5 pas encore connecte : %s "
                        "(verifie que le terminal MT5 est ouvert et connecte)", err)
    if not EXECUTOR_SECRET:
        logger.warning("MT5_EXECUTOR_SECRET non defini — toute requete sera refusee. "
                        "Definis-le avant utilisation reelle.")
    uvicorn.run(app, host="0.0.0.0", port=EXECUTOR_PORT)
