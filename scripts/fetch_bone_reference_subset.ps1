param(
    [Parameter(Mandatory = $false)]
    [string]$Destination = "<DATA_ROOT>\data\public\trabecular-bone-zenodo-11061947"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$manifestPath = Join-Path $projectRoot "manifests\external_bone_subset.json"
$manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json
$resolvedDestination = [System.IO.Path]::GetFullPath($Destination)
New-Item -ItemType Directory -Force -Path $resolvedDestination | Out-Null

foreach ($file in $manifest.files) {
    $target = Join-Path $resolvedDestination $file.name
    $url = "https://zenodo.org/api/records/11061947/files/$($file.name)/content"
    if (-not (Test-Path -LiteralPath $target) -or (Get-FileHash -LiteralPath $target -Algorithm MD5).Hash.ToLower() -ne $file.md5) {
        Invoke-WebRequest -Uri $url -OutFile $target
    }
    $actual = (Get-FileHash -LiteralPath $target -Algorithm MD5).Hash.ToLower()
    if ($actual -ne $file.md5) {
        throw "Checksum mismatch for $($file.name): expected $($file.md5), received $actual"
    }
}

Write-Output "Verified $($manifest.files.Count) files in $resolvedDestination"
