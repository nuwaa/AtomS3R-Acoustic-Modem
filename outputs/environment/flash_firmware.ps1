param([Parameter(Mandatory=$true)][string]$Port)
$ErrorActionPreference = 'Stop'
$settings = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'settings.json') -Raw | ConvertFrom-Json
$firmware = Join-Path $PSScriptRoot '..\firmware'
$images = @(
    @{ address = '0x0'; name = 'bootloader.bin' },
    @{ address = '0x8000'; name = 'partitions.bin' },
    @{ address = '0xe000'; name = 'boot_app0.bin' },
    @{ address = '0x10000'; name = 'application.bin' }
)
$arguments = @('--chip','esp32s3','--port',$Port,'--baud','921600','write-flash')
foreach ($image in $images) {
    $path = Join-Path $firmware $image.name
    if (-not (Test-Path -LiteralPath $path)) { Write-Error "Missing firmware: $path"; exit 2 }
    $arguments += $image.address
    $arguments += $path
}
& ([string]$settings.esptool) @arguments
exit $LASTEXITCODE
