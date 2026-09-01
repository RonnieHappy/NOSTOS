param(
    [Parameter(Mandatory = $false)]
    [string]$Destination = "data/reference/BBBC039v1"
)

$ErrorActionPreference = "Stop"
$resolvedDestination = [System.IO.Path]::GetFullPath($Destination)
New-Item -ItemType Directory -Force -Path $resolvedDestination | Out-Null
$archives = @(
    @{ Name = "images.zip"; Url = "https://data.broadinstitute.org/bbbc/BBBC039/images.zip"; Sha256 = "6f30a5d4fe38c928ded972704f085975f8dc0d65d9aa366df00e5a9d449fddd7" },
    @{ Name = "masks.zip"; Url = "https://data.broadinstitute.org/bbbc/BBBC039/masks.zip"; Sha256 = "f9e6043d8ca56344a4886f96a700d804d6ee982f31e2b2cd3194af2a053c2710" },
    @{ Name = "metadata.zip"; Url = "https://data.broadinstitute.org/bbbc/BBBC039/metadata.zip"; Sha256 = "a2c1f900bed9ba92a99553efd4c2ae98598433691c7401d818653ab61110deb2" }
)
foreach ($item in $archives) {
    $archive = Join-Path $resolvedDestination $item.Name
    if (-not (Test-Path -LiteralPath $archive)) {
        Invoke-WebRequest -Uri $item.Url -OutFile $archive
    }
    $actual = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLower()
    if ($actual -ne $item.Sha256) {
        throw "Checksum mismatch for $($item.Name): expected $($item.Sha256), received $actual"
    }
    $folder = Join-Path $resolvedDestination ([System.IO.Path]::GetFileNameWithoutExtension($item.Name))
    if (-not (Test-Path -LiteralPath $folder)) {
        Expand-Archive -LiteralPath $archive -DestinationPath $folder
    }
}
Write-Output "Verified and extracted BBBC039v1 in $resolvedDestination"
