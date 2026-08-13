[CmdletBinding()]
param(
    [string]$Destination = "Tools/ffmpeg/bin"
)

$ErrorActionPreference = "Stop"

$installerUrl = "https://github.com/CherryQ-aber/Qonic-Audio/releases/download/v5.0.0-beta.1/Qonic_Audio_v5.0.0-beta.1_Setup.exe"
$installerSha256 = "544F9762D07B3BEB3FD8C271D4558E6CD084BD3655C4FC631F605BBB97EE225C"
$ffmpegSha256 = "CA2BCCBF1A2A5A379AE484AD127D120CC3E394833B69767694A1E738F2D6BE55"
$ffprobeSha256 = "4EC2AC9385AACBAF927B7E8D031291059CEA2E02EE6BFAE0D708F78E1C528251"

if (-not $env:RUNNER_TEMP) {
    throw "RUNNER_TEMP is required; this helper is only for an isolated CI runner."
}

$runnerTemp = [IO.Path]::GetFullPath($env:RUNNER_TEMP)
$workspace = Join-Path $runnerTemp "qonic-core-ci-runtime"
$installer = Join-Path $workspace "Qonic_Audio_v5.0.0-beta.1_Setup.exe"
$installRoot = Join-Path $workspace "installed"

New-Item -ItemType Directory -Path $workspace -Force | Out-Null
Invoke-WebRequest -Uri $installerUrl -OutFile $installer

$actualInstallerHash = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash
if ($actualInstallerHash -ne $installerSha256) {
    throw "Installer SHA-256 mismatch: $actualInstallerHash"
}

$arguments = @(
    "/VERYSILENT",
    "/SUPPRESSMSGBOXES",
    "/NORESTART",
    "/NOICONS",
    "/TASKS=",
    "/DIR=$installRoot"
)
$process = Start-Process -FilePath $installer -ArgumentList $arguments -Wait -PassThru
if ($process.ExitCode -ne 0) {
    throw "Pinned Internal Beta installer exited with code $($process.ExitCode)."
}

$installedBin = Join-Path $installRoot "_internal/Tools/ffmpeg/bin"
$installedFfmpeg = Join-Path $installedBin "ffmpeg.exe"
$installedFfprobe = Join-Path $installedBin "ffprobe.exe"
if (-not (Test-Path -LiteralPath $installedFfmpeg -PathType Leaf)) {
    throw "Pinned installer did not provide ffmpeg.exe at the expected path."
}
if (-not (Test-Path -LiteralPath $installedFfprobe -PathType Leaf)) {
    throw "Pinned installer did not provide ffprobe.exe at the expected path."
}

$actualFfmpegHash = (Get-FileHash -LiteralPath $installedFfmpeg -Algorithm SHA256).Hash
$actualFfprobeHash = (Get-FileHash -LiteralPath $installedFfprobe -Algorithm SHA256).Hash
if ($actualFfmpegHash -ne $ffmpegSha256) {
    throw "FFmpeg SHA-256 mismatch: $actualFfmpegHash"
}
if ($actualFfprobeHash -ne $ffprobeSha256) {
    throw "FFprobe SHA-256 mismatch: $actualFfprobeHash"
}

$destinationPath = [IO.Path]::GetFullPath((Join-Path (Get-Location) $Destination))
New-Item -ItemType Directory -Path $destinationPath -Force | Out-Null
Copy-Item -LiteralPath $installedFfmpeg -Destination (Join-Path $destinationPath "ffmpeg.exe")
Copy-Item -LiteralPath $installedFfprobe -Destination (Join-Path $destinationPath "ffprobe.exe")

$ffmpegVersion = & (Join-Path $destinationPath "ffmpeg.exe") -version 2>&1
$ffmpegExitCode = $LASTEXITCODE
if ($ffmpegExitCode -ne 0) {
    throw "Pinned FFmpeg runtime could not execute."
}
$ffprobeVersion = & (Join-Path $destinationPath "ffprobe.exe") -version 2>&1
$ffprobeExitCode = $LASTEXITCODE
if ($ffprobeExitCode -ne 0) {
    throw "Pinned FFprobe runtime could not execute."
}
Write-Output ($ffmpegVersion | Select-Object -First 1)
Write-Output ($ffprobeVersion | Select-Object -First 1)
Write-Output "Pinned FFmpeg test runtime prepared from the verified Internal Beta installer."
