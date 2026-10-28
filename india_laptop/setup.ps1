# One-time setup of the India trader on this laptop.
# Run from an ADMINISTRATOR PowerShell inside the tsx-trader folder:
#   powershell -ExecutionPolicy Bypass -File .\india_laptop\setup.ps1
# Safe to run again: it skips what is already done and re-creates the tasks.

$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
Set-Location $Repo

function Step($msg) { Write-Host "`n=== $msg" -ForegroundColor Cyan }
function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [Environment]::GetEnvironmentVariable("Path", "User")
}

$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { throw "Open PowerShell with 'Run as administrator' and run this again." }

Step "1/7 Time zone"
$tz = (Get-TimeZone).Id
if ($tz -ne "India Standard Time") {
    throw "This laptop's time zone is '$tz'. Set it to (UTC+05:30) Chennai, Kolkata, Mumbai, New Delhi in Settings > Time & language, then run again."
}
Write-Host "India Standard Time - OK"

Step "2/7 Python and Git"
$pyOk = $false
try { $pyOk = "$(& python --version 2>$null)" -match "Python 3\.1[1-3]" } catch {}
if (-not $pyOk) {
    winget install --id Python.Python.3.12 -e --scope machine --accept-source-agreements --accept-package-agreements
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    winget install --id Git.Git -e --accept-source-agreements --accept-package-agreements
}
Refresh-Path
python --version; git --version

Step "3/7 Python packages (takes a few minutes)"
if (-not (Test-Path ".venv\Scripts\python.exe")) { python -m venv .venv }
$Py = Join-Path $Repo ".venv\Scripts\python.exe"
& $Py -m pip install -q --upgrade pip
& $Py -m pip install -q kiteconnect anthropic requests pandas "yfinance>=0.2.61" playwright pyotp PyNaCl
& $Py -m playwright install chromium

Step "4/7 Your keys (.env)"
if (-not (Test-Path ".env")) {
    Copy-Item "india_laptop\.env.example" ".env"
    Write-Host "Notepad will open. Fill in every value, SAVE, and CLOSE Notepad to continue." -ForegroundColor Yellow
    Start-Process notepad ".env" -Wait
} else {
    Write-Host ".env already exists - keeping it (edit with: notepad .env)"
}
$missing = Get-Content ".env" | Where-Object { $_ -match "^(KITE_\w+|TELEGRAM_\w+|ANTHROPIC_API_KEY)=\s*$" }
if ($missing) { throw "These are still empty in .env: $($missing -join ', '). Run: notepad .env, fill them, run setup again." }

Step "5/7 Keep the laptop awake when plugged in"
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
powercfg /setacvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 0   # closing the lid does nothing
powercfg /setactive SCHEME_CURRENT
Write-Host "Sleep off on charger; closing the lid no longer sleeps."

Step "6/7 Scheduled tasks (Mon-Fri, India time)"
$runner = Join-Path $PSScriptRoot "run_task.ps1"
$days = "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType S4U -RunLevel Limited

function Add-TraderTask($name, $job, $at, $limit, $everyMin, $forTime) {
    $action = New-ScheduledTaskAction -Execute "powershell.exe" `
        -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$runner`" -Job $job" -WorkingDirectory $Repo
    $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $days -At $at
    if ($everyMin) {
        $rep = New-ScheduledTaskTrigger -Once -At $at -RepetitionInterval (New-TimeSpan -Minutes $everyMin) -RepetitionDuration $forTime
        $trigger.Repetition = $rep.Repetition
    }
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries -ExecutionTimeLimit $limit -MultipleInstances IgnoreNew
    Register-ScheduledTask -TaskPath "\TSX Trader\" -TaskName $name -Action $action -Trigger $trigger `
        -Settings $settings -Principal $principal -Force | Out-Null
    Write-Host "  $name - $at$(if ($everyMin) { ", every $everyMin min" })"
}
Add-TraderTask "1 Zerodha token refresh" "refresh" "08:15" (New-TimeSpan -Minutes 15) $null $null
Add-TraderTask "2 India order monitor"   "orders"  "09:10" (New-TimeSpan -Hours 6 -Minutes 30) $null $null
Add-TraderTask "3 India auto-trader"     "monitor" "09:15" (New-TimeSpan -Minutes 4) 5 (New-TimeSpan -Hours 6 -Minutes 20)

Step "7/7 Test: token refresh + read-only Zerodha check (no orders)"
& $runner -Job refresh
Get-Content (Get-ChildItem "india_laptop\logs\refresh-*.log" | Sort-Object LastWriteTime | Select-Object -Last 1) -Tail 6
& $Py india_laptop\check_kite.py

Write-Host "`nDone. Leave the laptop plugged in, on, and connected to the internet on weekdays 8:00 AM - 3:45 PM." -ForegroundColor Green
Write-Host "Logs: $Repo\india_laptop\logs"
