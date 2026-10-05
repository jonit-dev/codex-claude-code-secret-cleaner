<#
.SYNOPSIS
Installs codex-claude-code-secret-cleaner for the current Windows user and,
optionally, registers a weekly Task Scheduler job.

.EXAMPLE
.\install-windows.ps1
.\install-windows.ps1 -Schedule
.\install-windows.ps1 -Uninstall
#>
[CmdletBinding()]
param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA 'Programs\codex-claude-code-secret-cleaner'),
    [switch]$Schedule,
    [string]$At = '01:17',
    [System.DayOfWeek]$Day = 'Sunday',
    [switch]$Uninstall
)

$ErrorActionPreference = 'Stop'
$TaskName = 'codex-claude-code-secret-cleaner'
$Name = 'codex-claude-code-secret-cleaner'

function Get-UserPath {
    [Environment]::GetEnvironmentVariable('Path', 'User') -split ';' | Where-Object { $_ }
}

if ($Uninstall) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    $remaining = Get-UserPath | Where-Object { $_.TrimEnd('\') -ne $InstallDir.TrimEnd('\') }
    [Environment]::SetEnvironmentVariable('Path', ($remaining -join ';'), 'User')
    if (Test-Path $InstallDir) { Remove-Item -Recurse -Force $InstallDir }
    Write-Host "Removed $InstallDir and the scheduled task (logs in $env:LOCALAPPDATA\$Name are kept)."
    return
}

$python = Get-Command py -ErrorAction SilentlyContinue
$pythonArgs = @('-3')
if (-not $python) {
    $python = Get-Command python -ErrorAction SilentlyContinue
    $pythonArgs = @()
}
if (-not $python) { throw 'Python 3.9+ is required. Install it from https://www.python.org/ or with: winget install Python.Python.3.13' }
& $python.Source @pythonArgs -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)'
if ($LASTEXITCODE -ne 0) { throw 'Python 3.9 or newer is required.' }
if (-not (Get-Command rg -ErrorAction SilentlyContinue)) {
    Write-Warning 'ripgrep (rg) not found. The cleaner still works but full scans are slower. Install with: winget install BurntSushi.ripgrep.MSVC'
}

New-Item -ItemType Directory -Force $InstallDir | Out-Null
Copy-Item -Force (Join-Path $PSScriptRoot $Name) $InstallDir
Copy-Item -Force (Join-Path $PSScriptRoot "$Name.cmd") $InstallDir

if ((Get-UserPath) -notcontains $InstallDir) {
    $newPath = (@(Get-UserPath) + $InstallDir) -join ';'
    [Environment]::SetEnvironmentVariable('Path', $newPath, 'User')
    Write-Host "Added $InstallDir to your user PATH. Open a new terminal to use it."
}
Write-Host "Installed to $InstallDir"

if ($Schedule) {
    # pythonw.exe runs without flashing a console window.
    $pyw = Join-Path (Split-Path (& $python.Source @pythonArgs -c 'import sys; print(sys.executable)')) 'pythonw.exe'
    if (-not (Test-Path $pyw)) { $pyw = (& $python.Source @pythonArgs -c 'import sys; print(sys.executable)') }
    $script = Join-Path $InstallDir $Name
    $action = New-ScheduledTaskAction -Execute $pyw -Argument "`"$script`" --incremental --quiet"
    $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $Day -At $At
    # StartWhenAvailable catches up a run missed while the machine was off or asleep.
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -Priority 7 -ExecutionTimeLimit (New-TimeSpan -Hours 2) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
        -Description 'Redacts secrets from local Codex and Claude Code history.' -Force | Out-Null
    Write-Host "Scheduled weekly run: $Day at $At (task '$TaskName'). Check with: Get-ScheduledTaskInfo $TaskName"
}
