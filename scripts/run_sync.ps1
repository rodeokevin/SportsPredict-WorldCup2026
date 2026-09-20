# Run from project root:  powershell -File scripts/run_sync.ps1
# Add -Update to refresh existing predictions, -DryRun to preview only.

param(
    [switch]$Update,
    [switch]$DryRun,
    [switch]$Verbose
)

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$argsList = @("sync_odds.py", "--source", "auto")
if ($Update) { $argsList += "--update" }
if ($DryRun) { $argsList += "--dry-run" }
if ($Verbose) { $argsList += "--verbose" }

python @argsList
exit $LASTEXITCODE
