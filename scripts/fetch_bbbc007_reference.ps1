param([string]$Destination = "BBBC007v1")
$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $Destination | Out-Null
$files = @{
    "images.zip" = "https://data.broadinstitute.org/bbbc/BBBC007/BBBC007_v1_images.zip"
    "outlines.zip" = "https://data.broadinstitute.org/bbbc/BBBC007/BBBC007_v1_outlines.zip"
}
$expected = @{
    "images.zip" = "B7009E2FCE0A3152A5C9ADDA916EAA699D09696F4BD02A7D05D12D041E30C6D1"
    "outlines.zip" = "6A5246F9A9D743D22EAFDB409FAE638A8461AF97E9FF9C4A92F25EBA236224D3"
}
foreach ($name in $files.Keys) {
    $path = Join-Path $Destination $name
    Invoke-WebRequest -UseBasicParsing $files[$name] -OutFile $path
    $observed = (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash
    if ($observed -ne $expected[$name]) { throw "Checksum mismatch for $name" }
}
Expand-Archive -LiteralPath (Join-Path $Destination "images.zip") -DestinationPath (Join-Path $Destination "images") -Force
Expand-Archive -LiteralPath (Join-Path $Destination "outlines.zip") -DestinationPath (Join-Path $Destination "outlines") -Force
Write-Output "BBBC007 reference ready at $Destination"
