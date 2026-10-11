param([string]$Port='')
$ErrorActionPreference='Stop'
Set-Location $PSScriptRoot
$settings=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'outputs/environment/settings.json') -Raw | ConvertFrom-Json
$python=if($settings.python){[string]$settings.python}else{'python'}
$dll=if($settings.wintun_dll){[string]$settings.wintun_dll}else{Join-Path $PSScriptRoot 'outputs/wintun/amd64/wintun.dll'}
if(!(Test-Path -LiteralPath $dll)){throw 'Wintun DLL was not found. Set wintun_dll in outputs/environment/settings.json.'}
if(!$Port){
  $serial=Get-ItemProperty 'HKLM:\HARDWARE\DEVICEMAP\SERIALCOMM' -ErrorAction SilentlyContinue
  $ports=@($serial.PSObject.Properties | Where-Object {$_.Name -like '\Device\*' -and $_.Value -match '^COM\d+$'} | ForEach-Object {[string]$_.Value} | Sort-Object -Unique)
  if($ports.Count -ne 1){throw ('Connect one PC-side ATOM. Ports: '+($ports -join ', '))}
  $Port=$ports[0]
}
if($Port -notmatch '^COM\d+$'){throw 'Specify a COM port such as COM5.'}
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
$principal=[Security.Principal.WindowsPrincipal]::new($identity)
if(!$principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){
  $arguments='-NoProfile -ExecutionPolicy Bypass -File "'+$PSCommandPath+'" -Port '+$Port
  Start-Process -Verb RunAs -FilePath 'powershell.exe' -ArgumentList $arguments
  exit
}
Write-Host ('Starting updated ATOM Peer Chat on '+$Port)
$logDirectory=Join-Path $PSScriptRoot 'outputs/operation'
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
$logFile=Join-Path $logDirectory ('peer-chat-'+(Get-Date -Format 'yyyyMMdd-HHmmss')+'.log')
Write-Host ('Log: '+$logFile)
& $python 'outputs/wintun_bridge.py' --port $Port --wintun-dll $dll --adapter 'ATOM Acoustic IP' --local-ip 10.77.0.1 --remote-ip 10.77.0.2 --pass-all --turnaround 15 --chat-native 2>&1 | Tee-Object -FilePath $logFile
exit $LASTEXITCODE
