param([string]$A='COM5',[string]$B='COM6')
$ErrorActionPreference='Stop'
$settings=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'settings.json') -Raw | ConvertFrom-Json
$python=if($settings.python){[string]$settings.python}else{'python'}
& $python (Join-Path (Split-Path $PSScriptRoot -Parent) 'group_chat_two_atom_test.py') --a $A --b $B --direct-only
exit $LASTEXITCODE
