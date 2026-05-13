"""
SMC Trading Bot — FastAPI entry point.

Endpoints :
  POST /webhook      — reçoit les signaux TradingView
  POST /trade/close  — notifie la clôture d'un trade (MT5 ou manuel)
  GET  /status       — état du bot (drawdown, trades ouverts)
  GET  /health       — liveness check

Lancement :
  uvicorn bot.main:app --host 0.0.0.0 --port 8000
"""

import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

# Ajouter le répertoire racine au PYTHONPATH pour les imports config/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from bot import webhook
from bot.filters.risk_filter import risk_state
from bot.notifications import telegram
from config.settings import (
    INITIAL_CAPITAL,
    RISK_AMOUNT,
    DAILY_DD_AMOUNT,
    WEEKLY_DD_AMOUNT,
    SESSIONS,
    ALLOWED_SYMBOLS,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
log_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s UTC | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            os.path.join(log_dir, "bot.log"),
            encoding="utf-8",
        ),
    ],
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Application lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("SMC Trading Bot démarré")
    logger.info("Capital : %.0f € | Risque/trade : %.0f €", INITIAL_CAPITAL, RISK_AMOUNT)
    logger.info("DD jour : %.0f € | DD semaine : %.0f €", DAILY_DD_AMOUNT, WEEKLY_DD_AMOUNT)
    logger.info("=" * 60)
    await telegram.notify_startup()
    yield
    logger.info("SMC Trading Bot arrêté")


app = FastAPI(
    title="SMC Trading Bot",
    description="Webhook receiver — TradingView → PineConnector → MT5",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,   # désactiver Swagger en prod (pas besoin d'exposition publique)
    redoc_url=None,
)


# ---------------------------------------------------------------------------
# Middleware : log chaque requête entrante
# ---------------------------------------------------------------------------

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.debug(
        "→ %s %s | IP: %s",
        request.method,
        request.url.path,
        request.client.host if request.client else "?",
    )
    response = await call_next(request)
    logger.debug("← %s %s | %d", request.method, request.url.path, response.status_code)
    return response


# ---------------------------------------------------------------------------
# POST /webhook — point d'entrée principal
# ---------------------------------------------------------------------------

@app.post("/webhook")
async def receive_webhook(request: Request):
    """
    Reçoit le payload JSON de TradingView et exécute la chaîne de filtres.
    Répond toujours HTTP 200 pour les décisions ALLOW/BLOCK (évite les retry TV).
    """
    # Lire le body brut
    try:
        payload = await request.json()
    except Exception:
        logger.warning("Payload reçu non parseable en JSON")
        raise HTTPException(
            status_code=422,
            detail={
                "status": "BLOCK",
                "reason": "PAYLOAD_INVALIDE",
                "detail": "Corps de la requête non parseable en JSON",
            },
        )

    logger.info(
        "Webhook reçu : event=%s | symbol=%s | direction=%s | price=%s",
        payload.get("event_type", "?"),
        payload.get("symbol", "?"),
        payload.get("direction", "?"),
        payload.get("price", "?"),
    )

    try:
        result = await webhook.process(payload)
    except Exception as exc:
        # Fail-safe : toute exception non gérée → BLOCK + alerte
        logger.error("Exception non gérée dans webhook.process", exc_info=True)
        await telegram.notify_error(
            context="webhook.process — exception non gérée",
            error=str(exc),
        )
        return JSONResponse(
            status_code=200,
            content={
                "status": "BLOCK",
                "reason": "ERREUR_TECHNIQUE",
                "detail": "Exception interne — trade bloqué par sécurité",
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )

    # Loguer dans le fichier signals dédié
    _log_signal(result, payload)

    return JSONResponse(status_code=200, content=result)


# ---------------------------------------------------------------------------
# GET /status — état du bot
# ---------------------------------------------------------------------------

@app.get("/status")
async def status():
    """
    Retourne l'état courant du bot : drawdown, trades ouverts, sessions.
    Endpoint de monitoring — ne pas exposer publiquement sans auth.
    """
    from bot.filters.session_filter import current_session

    now_utc = datetime.now(timezone.utc)
    active_session = current_session()

    return {
        "bot": "SMC Trading Bot",
        "version": "1.0.0",
        "timestamp": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "session_active": active_session,
        "risk": risk_state.summary(),
        "config": {
            "capital_eur": INITIAL_CAPITAL,
            "risk_per_trade_eur": RISK_AMOUNT,
            "daily_dd_limit_eur": DAILY_DD_AMOUNT,
            "weekly_dd_limit_eur": WEEKLY_DD_AMOUNT,
            "allowed_symbols": list(ALLOWED_SYMBOLS.keys()),
            "sessions_utc": {
                name: {
                    "start": w["start"].strftime("%H:%M"),
                    "end": w["end"].strftime("%H:%M"),
                }
                for name, w in SESSIONS.items()
            },
        },
    }


# ---------------------------------------------------------------------------
# GET /health — liveness probe (pour monitoring VPS / uptime robot)
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


# ---------------------------------------------------------------------------
# POST /trade/close — notifie la clôture d'un trade depuis MT5
# ---------------------------------------------------------------------------

@app.post("/trade/close")
async def trade_close(request: Request):
    """
    Appelé par MT5 (ou manuellement) quand un trade se ferme.
    Met à jour le RiskState en mémoire : décrémente les trades ouverts,
    cumule la perte si pnl_eur < 0, déclenche la pause weekly si seuil atteint.

    Payload JSON :
      {
        "secret":   "...",
        "trade_id": "12345",
        "symbol":   "EURUSD",
        "pnl_eur":  -25.50
      }

    Retourne le nouvel état du drawdown.
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=422, detail="Corps de la requête non parseable en JSON")

    # --- Auth ---
    expected_secret = os.environ.get("WEBHOOK_SECRET_KEY", "")
    if not expected_secret or payload.get("secret") != expected_secret:
        logger.warning("/trade/close — authentification échouée")
        raise HTTPException(status_code=401, detail="Clé secrète invalide")

    # --- Validation des champs obligatoires ---
    trade_id = payload.get("trade_id")
    symbol   = payload.get("symbol")
    pnl_eur  = payload.get("pnl_eur")

    if trade_id is None or symbol is None or pnl_eur is None:
        raise HTTPException(
            status_code=422,
            detail="Champs obligatoires manquants : trade_id, symbol, pnl_eur",
        )

    if not isinstance(pnl_eur, (int, float)):
        raise HTTPException(
            status_code=422,
            detail=f"pnl_eur doit être un nombre, reçu : {type(pnl_eur).__name__}",
        )

    # --- Mise à jour du RiskState ---
    risk_state.trade_closed(float(pnl_eur))
    summary = risk_state.summary()

    logger.info(
        "Trade clôturé via /trade/close | id=%s | %s | PnL=%.2f € | "
        "trades_ouverts=%d | perte_jour=%.2f € | perte_semaine=%.2f €",
        trade_id, symbol, pnl_eur,
        summary["open_trades"], summary["daily_loss_eur"], summary["weekly_loss_eur"],
    )

    # --- Alertes Telegram ---
    await telegram.notify_trade_closed(
        trade_id=str(trade_id),
        symbol=str(symbol),
        pnl_eur=float(pnl_eur),
        risk_summary=summary,
    )

    if summary["daily_loss_eur"] >= DAILY_DD_AMOUNT and float(pnl_eur) < 0:
        await telegram.notify_daily_dd_hit(
            loss_eur=summary["daily_loss_eur"],
            limit_eur=DAILY_DD_AMOUNT,
        )

    if summary["weekly_pause_active"] and float(pnl_eur) < 0:
        await telegram.notify_weekly_dd_hit(
            loss_eur=summary["weekly_loss_eur"],
            limit_eur=WEEKLY_DD_AMOUNT,
            resume_at=summary["weekly_pause_until"] or "",
        )

    return {
        "status": "ok",
        "trade_id": trade_id,
        "symbol": symbol,
        "pnl_eur": round(float(pnl_eur), 2),
        "risk": summary,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


# ---------------------------------------------------------------------------
# Signal logger (fichier dédié séparé du log applicatif)
# ---------------------------------------------------------------------------

_signal_logger = logging.getLogger("signals")
_signal_handler = logging.FileHandler(
    os.path.join(log_dir, "signals.log"),
    encoding="utf-8",
)
_signal_handler.setFormatter(
    logging.Formatter("%(asctime)s UTC | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
)
_signal_logger.addHandler(_signal_handler)
_signal_logger.setLevel(logging.INFO)
_signal_logger.propagate = False  # ne pas doubler dans le log principal


def _log_signal(result: dict, payload: dict) -> None:
    """Écrit une ligne structurée dans signals.log pour chaque signal traité."""
    status = result.get("status", "?")
    event = payload.get("event_type", "?")
    symbol = payload.get("symbol", "?")
    direction = payload.get("direction", "?")
    price = payload.get("price", "?")
    reason = result.get("reason", "-")
    rr = result.get("rr", "-")
    lot = result.get("lot_size", "-")
    sid = result.get("signal_id", "?")[:8]  # 8 premiers chars du UUID

    _signal_logger.info(
        "%s | %s | %s | %s | price=%s | rr=%s | lot=%s | reason=%s | id=%s",
        status, event, symbol, direction.upper(), price, rr, lot, reason, sid,
    )
