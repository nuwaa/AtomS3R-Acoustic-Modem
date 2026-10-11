$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$settings = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'outputs\environment\settings.json') -Raw | ConvertFrom-Json
$python = if ($settings.python) { $settings.python } else { 'python' }
$port = Read-Host 'PC-side ATOM COM port [COM6]'
if (-not $port) { $port = 'COM6' }
if ($port -notmatch '^COM\d+$') { throw 'Enter a COM port, for example COM6.' }
Write-Host 'When ready, open http://127.0.0.1:8766/ in the PC browser.'
& $python 'outputs\usb_chat_web.py' --port $port
exit $LASTEXITCODE
