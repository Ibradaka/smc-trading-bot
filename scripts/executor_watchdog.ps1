# ============================================================
# Watchdog de l'executor MT5 — VPS Windows
# ============================================================
# Declenche toutes les 5 minutes par le Planificateur de taches.
# - Si l'executor repond sur le port 9000 -> ne fait rien.
# - Sinon -> (re)lance MT5 si besoin, puis relance l'executor.
#
# Peu importe la cause de la panne (crash, reboot, RDP, coupure),
# l'executor est repare en 5 minutes maximum, sans intervention.
#
# A ADAPTER si les chemins different sur le VPS :
#   $Mt5Path  : chemin du terminal MT5
#   $RepoPath : dossier ou le repo a ete extrait
# ============================================================

$env:MT5_EXECUTOR_SECRET = "smc-exec-k7m2p9x4"

$Mt5Path  = "C:\Program Files\Switch Markets MT5\terminal64.exe"
$RepoPath = "C:\Users\Administrator\Desktop\smc-trading-bot-main"

# --- 1. L'executor repond-il deja ? --------------------------------------
try {
    $r = Invoke-WebRequest "http://localhost:9000/health" -UseBasicParsing -TimeoutSec 5
    if ($r.StatusCode -eq 200) {
        # Tout va bien, rien a faire.
        exit 0
    }
} catch {
    # Pas de reponse -> on continue, il faut le relancer.
}

# --- 2. MT5 est-il lance ? -----------------------------------------------
if (-not (Get-Process terminal64 -ErrorAction SilentlyContinue)) {
    Start-Process $Mt5Path
    Start-Sleep -Seconds 40
}

# --- 3. (Re)lancer l'executor, detache et en fenetre cachee --------------
Set-Location $RepoPath
Start-Process python `
    -ArgumentList "bot\execution\mt5_executor_service.py" `
    -WindowStyle Hidden
