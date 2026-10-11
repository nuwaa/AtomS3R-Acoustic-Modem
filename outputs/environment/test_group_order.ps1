$ErrorActionPreference='Stop'
$settings=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'settings.json') -Raw | ConvertFrom-Json
$python=if($settings.python){[string]$settings.python}else{'python'}
& $python (Join-Path $PSScriptRoot '..\group_chat_two_atom_test.py') --a COM5 --b COM6 --ordering-loss
exit $LASTEXITCODE
