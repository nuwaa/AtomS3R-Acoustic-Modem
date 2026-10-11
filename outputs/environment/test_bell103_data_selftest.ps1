param([string]$Port='COM6')
$ErrorActionPreference='Stop'
$settings=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'settings.json') -Raw | ConvertFrom-Json
$python=if($settings.python){[string]$settings.python}else{'python'}
& $python (Join-Path $PSScriptRoot 'test_bell103_data_selftest.py') --port $Port
exit $LASTEXITCODE
