param(
  [string]$DataRoot = '<DATA_ROOT>\data\public\bone-contract-benchmark',
  [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
  [switch]$SkipIntegrityVerification
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$DataRoot = (Resolve-Path -LiteralPath $DataRoot).Path
$python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if(-not (Test-Path -LiteralPath $python)){ throw "Missing project interpreter: $python" }

$figshare = Join-Path $DataRoot 'figshare-20765659\extracted'
$shgImages = Join-Path $DataRoot 'zenodo-3355937\extracted\images\shg-ce-de'
$shgMasks = Join-Path $DataRoot 'zenodo-3355937\extracted\masks\shg-masks'
$ratTiffs = Join-Path $DataRoot 'zenodo-11061868\files'
$humanRaw = Join-Path $DataRoot 'zenodo-17909733\extracted\raw'
$uvpam = Join-Path $DataRoot 'zenodo-6345772\files\cycleGAN-UVPAM.zip'

foreach($required in @($figshare,$shgImages,$shgMasks,$ratTiffs,$humanRaw,$uvpam)){
  if(-not (Test-Path -LiteralPath $required)){ throw "Missing required public-data path: $required" }
}

Push-Location $ProjectRoot
try {
  $env:PYTHONPATH = (Join-Path $ProjectRoot 'src')
  function Invoke-NostosPython {
    & $python @args
    if($LASTEXITCODE -ne 0){ throw "Python command failed with exit code ${LASTEXITCODE}: $($args -join ' ')" }
  }
  if(-not $SkipIntegrityVerification){
    & (Join-Path $ProjectRoot 'scripts\verify_bone_contract_downloads.ps1') -Root $DataRoot
    $integrityOutput = Join-Path $ProjectRoot 'outputs\nostos0-bone-download-integrity'
    New-Item -ItemType Directory -Force -Path $integrityOutput | Out-Null
    Copy-Item -LiteralPath (Join-Path $DataRoot 'integrity_verification.json') -Destination (Join-Path $integrityOutput 'integrity_verification.json') -Force
  }

  Invoke-NostosPython scripts\run_bone_contract_orientation.py --data $figshare --config configs\bone_contract_orientation.locked.json --output outputs\nostos0-bone-contract-orientation-confirmation-v1
  Invoke-NostosPython scripts\run_bone_orientation_v2.py --images $shgImages --masks $shgMasks --config configs\bone_contract_orientation_v2.locked.json --output outputs\nostos0-bone-orientation-v2
  Invoke-NostosPython scripts\run_bone_network_3d.py --data $ratTiffs --config configs\bone_3d_network_contract.locked.json --output outputs\nostos0-bone-network-3d
  Invoke-NostosPython scripts\run_bone_network_3d.py --data $ratTiffs --config configs\bone_3d_network_contract_v2.locked.json --output outputs\nostos0-bone-network-3d-v2
  Invoke-NostosPython scripts\run_human_nanoct_transfer.py --data $humanRaw --config configs\human_nanoct_transfer.locked.json --output outputs\nostos0-human-nanoct-transfer
  Invoke-NostosPython scripts\run_human_nanoct_scale_response.py --data $humanRaw --config configs\human_nanoct_scale_response_v2.locked.json --output outputs\nostos0-human-nanoct-scale-response-v2
  Invoke-NostosPython scripts\run_uvpam_abstention.py --archive $uvpam --config configs\uvpam_abstention.locked.json --output outputs\nostos0-uvpam-abstention
  Invoke-NostosPython scripts\build_bone_contract_summary.py --project-root $ProjectRoot --output outputs\nostos0-bone-contract-summary
  Invoke-NostosPython scripts\build_bone_contract_figure.py --data-root $DataRoot
  Invoke-NostosPython -m nostos.cli build-evidence-bundle --project-root $ProjectRoot --output outputs\nostos0-evidence-bundle-v26
  Invoke-NostosPython -m pytest tests\test_bone_contract_orientation.py tests\test_bone_orientation_v2.py tests\test_bone_network_3d.py tests\test_human_nanoct_transfer.py tests\test_human_nanoct_scale_response.py tests\test_uvpam_abstention.py tests\test_bone_program_summary.py -q
} finally {
  Pop-Location
}
