# Runs one India trader job. Called by the scheduled tasks setup.ps1 creates.
#   refresh  8:15 AM  - update code (git pull), then get today's Zerodha token
#   monitor  every 5 min 9:15-3:35 - auto_trader.py monitor (GTT exits, legacy sells)
#   orders   9:10 AM, runs all session - india_monitor.py (Claude check on your Kite orders)
param([Parameter(Mandatory = $true)][ValidateSet("refresh", "monitor", "orders")][string]$Job)

$ErrorActionPreference = "Continue"   # git/python write progress to stderr; that is not a failure
$Repo = Split-Path -Parent $PSScriptRoot
$Py   = Join-Path $Repo ".venv\Scripts\python.exe"
$Logs = Join-Path $PSScriptRoot "logs"
New-Item -ItemType Directory -Force $Logs | Out-Null
$Log  = Join-Path $Logs ("{0}-{1}.log" -f $Job, (Get-Date -Format "yyyy-MM-dd"))

Set-Location $Repo
$env:PYTHONIOENCODING = "utf-8"
"==== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $Job" | Out-File $Log -Append -Encoding utf8

switch ($Job) {
    "refresh" {
        git pull --ff-only *>> $Log
        & $Py zerodha_token_refresh.py *>> $Log
    }
    "monitor" { & $Py auto_trader.py monitor *>> $Log }
    "orders"  { & $Py india_monitor.py *>> $Log }
}

# keep two weeks of logs
Get-ChildItem $Logs -Filter *.log | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-14) } | Remove-Item
