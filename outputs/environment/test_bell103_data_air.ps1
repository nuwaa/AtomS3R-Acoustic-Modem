param([string]$Caller='COM5',[string]$Answerer='COM6')
$ErrorActionPreference='Stop'
$settings=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'settings.json') -Raw | ConvertFrom-Json
$python=if($settings.python){[string]$settings.python}else{'python'}
& $python (Join-Path $PSScriptRoot 'test_bell103_data_air.py') --caller $Caller --answerer $Answerer
exit $LASTEXITCODE
