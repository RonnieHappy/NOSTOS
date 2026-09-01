param(
  [string]$Root = '<DATA_ROOT>\data\public\bone-contract-benchmark'
)

$ErrorActionPreference = 'Stop'
$receiptPath = Join-Path $Root 'download_receipt.json'
if(-not (Test-Path -LiteralPath $receiptPath)){ throw "Missing receipt: $receiptPath" }
$receipt = Get-Content -LiteralPath $receiptPath -Raw | ConvertFrom-Json
$rows = @()
foreach($item in $receipt){
  $path = Join-Path (Join-Path (Join-Path $Root $item.dataset) 'files') $item.file
  if(-not (Test-Path -LiteralPath $path)){ throw "Missing downloaded file: $path" }
  $bytes = (Get-Item -LiteralPath $path).Length
  if($bytes -ne [int64]$item.bytes){ throw "Receipt-size mismatch: $path" }
  $sha256 = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
  if($sha256 -ne ([string]$item.local_sha256).ToLowerInvariant()){ throw "SHA-256 mismatch: $path" }
  $md5 = ''
  $deposited = [string]$item.deposited_checksum
  if($deposited -match '^md5:(.+)$'){
    $md5 = (Get-FileHash -LiteralPath $path -Algorithm MD5).Hash.ToLowerInvariant()
    if($md5 -ne $Matches[1].ToLowerInvariant()){ throw "Deposited MD5 mismatch: $path" }
  }
  $rows += [pscustomobject]@{dataset=$item.dataset;file=$item.file;bytes=$bytes;sha256=$sha256;md5=$md5;verified=$true}
}
$payload = [ordered]@{
  protocol_version = 'nostos-bone-download-integrity/1.0'
  status = 'pass'
  files = $rows.Count
  bytes = [int64](($rows | Measure-Object -Property bytes -Sum).Sum)
  rows = $rows
}
$output = Join-Path $Root 'integrity_verification.json'
$payload | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $output -Encoding utf8
Write-Output $output
