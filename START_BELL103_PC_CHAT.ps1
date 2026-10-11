$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$settings = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'outputs\environment\settings.json') -Raw | ConvertFrom-Json
$python = if ($settings.python) { $settings.python } else { 'python' }
$available = @((Get-ItemProperty 'HKLM:\HARDWARE\DEVICEMAP\SERIALCOMM' -ErrorAction SilentlyContinue).PSObject.Properties |
    Where-Object { $_.Name -like '\Device\*' -and $_.Value -match '^COM\d+$' } |
    ForEach-Object { $_.Value })
$defaultPort = if ($available.Count -eq 1) { $available[0] } else { 'COM6' }
Write-Host ('Available ports: ' + ($available -join ', '))
$port = Read-Host "PC-side ATOM COM port [$defaultPort]"
if (-not $port) { $port = $defaultPort }
if ($port -notmatch '^COM\d+$') { throw 'Enter a COM port, for example COM6.' }
Write-Host 'When ready, open http://127.0.0.1:8766/ in the PC browser.'
& $python 'outputs\usb_chat_web.py' --port $port
exit $LASTEXITCODE
