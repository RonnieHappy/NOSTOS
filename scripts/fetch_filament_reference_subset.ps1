param(
    [Parameter(Mandatory = $false)]
    [string]$Destination = "<DATA_ROOT>\data\public\myceliumseg-zenodo-15224240"
)

$ErrorActionPreference = "Stop"
$resolvedDestination = [System.IO.Path]::GetFullPath($Destination)
New-Item -ItemType Directory -Force -Path $resolvedDestination | Out-Null
$archive = Join-Path $resolvedDestination "labeled-GS_PO_TS.zip"
$source = "https://zenodo.org/api/records/15224240/files/labeled-GS_PO_TS.zip/content"
$expected = "dc7b89e8853911bc8a7dda12c0ac230f"
if (-not (Test-Path -LiteralPath $archive) -or (Get-FileHash -LiteralPath $archive -Algorithm MD5).Hash.ToLower() -ne $expected) {
    Start-BitsTransfer -Source $source -Destination $archive -DisplayName "NOSTOS MyceliumSeg reference"
}
$actual = (Get-FileHash -LiteralPath $archive -Algorithm MD5).Hash.ToLower()
if ($actual -ne $expected) {
    throw "Checksum mismatch for labeled-GS_PO_TS.zip: expected $expected, received $actual"
}
$extracted = Join-Path $resolvedDestination "extracted"
New-Item -ItemType Directory -Force -Path $extracted | Out-Null
tar.exe -xf $archive -C $extracted
Write-Output "Verified and extracted MyceliumSeg cross-species subset in $resolvedDestination"
