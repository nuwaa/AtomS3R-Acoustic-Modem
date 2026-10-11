param([string]$Caller='COM5',[string]$Answerer='COM6',[double]$Minutes=30)
$ErrorActionPreference='Stop'
$settings=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'settings.json') -Raw | ConvertFrom-Json
$python=if($settings.python){[string]$settings.python}else{'python'}
& $python (Join-Path $PSScriptRoot 'test_bell103_soak.py') --caller $Caller --answerer $Answerer --minutes $Minutes
exit $LASTEXITCODE
