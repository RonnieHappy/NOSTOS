param(
  [string]$Destination = '<DATA_ROOT>\data\public\bone-contract-benchmark'
)

$ErrorActionPreference = 'Stop'
$records = @(
  @{Id='zenodo-3355937'; Api='https://zenodo.org/api/records/3355937'},
  @{Id='figshare-20765659'; Api='https://api.figshare.com/v2/articles/20765659'},
  @{Id='zenodo-11061868'; Api='https://zenodo.org/api/records/11061868'},
  @{Id='zenodo-17909733'; Api='https://zenodo.org/api/records/17909733'},
  @{Id='zenodo-6345772'; Api='https://zenodo.org/api/records/6345772'}
)

New-Item -ItemType Directory -Path $Destination -Force | Out-Null
$manifest = @()
foreach($record in $records){
  $datasetDir = Join-Path $Destination $record.Id
  $fileDir = Join-Path $datasetDir 'files'
  New-Item -ItemType Directory -Path $fileDir -Force | Out-Null
  $metadata = Invoke-RestMethod -Uri $record.Api -TimeoutSec 120
  $metadata | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath (Join-Path $datasetDir 'api_metadata.json') -Encoding utf8
  foreach($file in $metadata.files){
    $name = if($file.key){$file.key}else{$file.name}
    $url = if($file.download_url){$file.download_url}elseif($file.links.download){$file.links.download}else{$file.links.self}
    $target = Join-Path $fileDir $name
    New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
    & curl.exe --location --fail --retry 8 --retry-all-errors --continue-at - --output $target $url
    if($LASTEXITCODE -ne 0){ throw "download failed: $url" }
    $expectedBytes = if($file.size){[int64]$file.size}else{0}
    $localBytes = (Get-Item -LiteralPath $target).Length
    if($expectedBytes -gt 0 -and $localBytes -ne $expectedBytes){
      throw "size mismatch for $target`: expected $expectedBytes, observed $localBytes"
    }
    $depositedChecksum = if($file.checksum){[string]$file.checksum}elseif($file.computed_md5){"md5:$($file.computed_md5)"}elseif($file.supplied_md5){"md5:$($file.supplied_md5)"}else{''}
    $localMd5 = ''
    if($depositedChecksum -match '^md5:(.+)$'){
      $localMd5 = (Get-FileHash -Algorithm MD5 -LiteralPath $target).Hash.ToLowerInvariant()
      if($localMd5 -ne $Matches[1].ToLowerInvariant()){ throw "MD5 mismatch for $target" }
    }
    $hash=(Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash.ToLowerInvariant()
    $manifest += [pscustomobject]@{
      dataset=$record.Id; file=$name; source_url=$url; bytes=$localBytes; expected_bytes=$expectedBytes
      deposited_checksum=$depositedChecksum; local_md5=$localMd5; local_sha256=$hash; integrity_verified=$true
    }
    $manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $Destination 'download_receipt.partial.json') -Encoding utf8
  }
}
$manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $Destination 'download_receipt.json') -Encoding utf8
Write-Output (Join-Path $Destination 'download_receipt.json')
