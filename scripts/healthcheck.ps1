# ============================================================
# SMC Bot — Health Check depuis ton PC (Windows PowerShell)
# ============================================================
# Verifie ce qui est visible depuis l'internet public :
#   1. Bot Linux (Hostinger via Cloudflare) -> /health + /status
#   2. Executor MT5 -> tentative (echec attendu, port ferme depuis l'exterieur)
#
# Pour le test COMPLET de la chaine (bot + executor + MT5), utiliser
# scripts/healthcheck-from-linux.sh depuis le VPS Hostinger en SSH.
#
# Utilisation :
#   powershell -File scripts\healthcheck.ps1
# ============================================================

$BotUrl  = "https://smc.feelyoo.com"
$ExecUrl = "http://45.128.152.242:9000"

# --- 1. Bot Linux --------------------------------------------------------
Write-Host "`n--- Bot Linux (Hostinger via Cloudflare) ---" -ForegroundColor Cyan
try {
    $bot = Invoke-RestMethod "$BotUrl/health" -TimeoutSec 5
    Write-Host "OK  bot repond a $($bot.timestamp)" -ForegroundColor Green
} catch {
    Write-Host "KO  bot injoignable : $_" -ForegroundColor Red
}

# --- 2. Executor (depuis ton PC = echec attendu, port filtre) -----------
Write-Host "`n--- Executor MT5 (test depuis ton PC) ---" -ForegroundColor Cyan
try {
    $exec = Invoke-RestMethod "$ExecUrl/health" -TimeoutSec 5
    if ($exec.status -eq "ok") {
        Write-Host ("OK  MT5 connecte - compte {0} - balance {1}" -f $exec.account, $exec.balance) -ForegroundColor Green
    } else {
        Write-Host "KO  MT5 down : $($exec.error)" -ForegroundColor Red
    }
} catch {
    Write-Host "Timeout attendu : le port 9000 n'accepte que l'IP Hostinger (187.124.32.79)." -ForegroundColor DarkYellow
    Write-Host "Pour tester reellement l'executor : healthcheck-from-linux.sh depuis le VPS Linux." -ForegroundColor DarkYellow
}

# --- 3. Etat du bot (risk, sessions, config) ----------------------------
Write-Host "`n--- Etat du bot ---" -ForegroundColor Cyan
try {
    $status = Invoke-RestMethod "$BotUrl/status" -TimeoutSec 5
    Write-Host ("Session active : {0}" -f $status.session_active)
    Write-Host ("Trades ouverts : {0} / {1}" -f $status.risk.open_trades, $status.config.allowed_symbols.Count)
    Write-Host ("DD jour        : {0} / {1} EUR" -f $status.risk.daily_loss, $status.config.daily_dd_limit_eur)
    Write-Host ("Symboles       : {0}" -f ($status.config.allowed_symbols -join ', '))
} catch {
    Write-Host "KO  /status injoignable : $_" -ForegroundColor Red
}

Write-Host ""
