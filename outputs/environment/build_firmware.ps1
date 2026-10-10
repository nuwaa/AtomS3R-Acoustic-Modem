$ErrorActionPreference = 'Stop'
$settingsPath = Join-Path $PSScriptRoot 'settings.json'
if (-not (Test-Path -LiteralPath $settingsPath)) {
    Write-Error "Missing settings.json. Copy build.settings.example.json and set local tool paths."
    exit 2
}
$settings = Get-Content -LiteralPath $settingsPath -Raw | ConvertFrom-Json
$python = if ($settings.python) { [string]$settings.python } else { 'python' }
& $python (Join-Path $PSScriptRoot 'build.py')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
exit 0
