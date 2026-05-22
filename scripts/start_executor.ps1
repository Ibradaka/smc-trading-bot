# ============================================================
# Lanceur robuste de l'executor MT5 — VPS Windows
# ============================================================
# Demarre MT5 si besoin, lance l'executor, le relance s'il s'arrete.
# Concu pour etre declenche automatiquement au demarrage du VPS
# (via le Planificateur de taches Windows).
#
# A ADAPTER si les chemins different sur le VPS :
#   $Mt5Path  : chemin du terminal MT5
#   $RepoPath : dossier ou le repo a ete extrait
# ============================================================

# --- Configuration -------------------------------------------------------
$env:MT5_EXECUTOR_SECRET = "smc-exec-k7m2p9x4"

$Mt5Path  = "C:\Program Files\Switch Markets MT5\terminal64.exe"
$RepoPath = "C:\Users\Administrator\Desktop\smc-trading-bot-main"

# --- 1. Demarrer MT5 s'il n'est pas deja ouvert --------------------------
if (-not (Get-Process terminal64 -ErrorAction SilentlyContinue)) {
    Write-Host "MT5 non lance -> demarrage..."
    Start-Process $Mt5Path
    Write-Host "Attente 40s que MT5 se connecte au compte..."
    Start-Sleep -Seconds 40
} else {
    Write-Host "MT5 deja en cours d'execution."
}

# --- 2. Lancer l'executor, le relancer s'il s'arrete ---------------------
Set-Location $RepoPath
while ($true) {
    Write-Host "=== Demarrage de l'executor MT5 ($(Get-Date)) ==="
    python bot\execution\mt5_executor_service.py
    Write-Host "!!! Executor arrete -- relance dans 15s ($(Get-Date)) ==="
    Start-Sleep -Seconds 15
}
