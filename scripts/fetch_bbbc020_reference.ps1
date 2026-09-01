param([string]$Destination = "BBBC020v1")
$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $Destination | Out-Null
$files = @{
    "images.zip" = "https://data.broadinstitute.org/bbbc/BBBC020/BBBC020_v1_images.zip"
    "outlines_nuclei.zip" = "https://data.broadinstitute.org/bbbc/BBBC020/BBBC020_v1_outlines_nuclei.zip"
}
$expected = @{
    "images.zip" = "EDF4A87BE957EC2B7AB268BEF92C2EFAE8E098DC0855A4FA9DF80895FF7062E4"
    "outlines_nuclei.zip" = "B212F10013AE2A0260976CFF2134204ECBA226853922AEA2AB5289051A47CEB7"
}
foreach ($name in $files.Keys) {
    $path = Join-Path $Destination $name
    Invoke-WebRequest -UseBasicParsing $files[$name] -OutFile $path
    $observed = (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash
    if ($observed -ne $expected[$name]) { throw "Checksum mismatch for $name" }
}
Expand-Archive -LiteralPath (Join-Path $Destination "images.zip") -DestinationPath (Join-Path $Destination "images") -Force
Expand-Archive -LiteralPath (Join-Path $Destination "outlines_nuclei.zip") -DestinationPath (Join-Path $Destination "outlines_nuclei") -Force
Write-Output "BBBC020 reference ready at $Destination"
