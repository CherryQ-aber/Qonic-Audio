param(
    [string]$InnoCompiler,
    [string]$ApplicationSource
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$InstallerScript = Join-Path $Root "installer\Qonic_Audio_Internal_Beta.iss"
$ReleaseRoot = Join-Path $Root "Release"
$InstallerOutput = Join-Path $ReleaseRoot "Installer_Candidates"

function Assert-FileExists {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Missing required installer input: $Path"
    }
}

Set-Location -LiteralPath $Root
Assert-FileExists -Path $InstallerScript

$metadataLines = & python -c 'import app_info; print(app_info.APP_DISPLAY_NAME); print(app_info.APP_VERSION); print(app_info.APP_RELEASE_CHANNEL); print(app_info.APP_PACKAGE_BASENAME); print(app_info.APP_INSTALLER_BASENAME)'
if ($LASTEXITCODE -ne 0) {
    throw "Unable to read centralized app metadata."
}
if ($metadataLines.Count -ne 5) {
    throw "Centralized app metadata returned an unexpected number of fields."
}
$metadata = [pscustomobject]@{
    display_name = $metadataLines[0]
    version = $metadataLines[1]
    channel = $metadataLines[2]
    package = $metadataLines[3]
    installer = $metadataLines[4]
}

$versionMatch = [regex]::Match(
    $metadata.version,
    '^(?<major>\d+)\.(?<minor>\d+)\.(?<patch>\d+)(?:-beta\.(?<build>\d+))?$'
)
if (-not $versionMatch.Success) {
    throw "Unsupported app version for installer metadata: $($metadata.version)"
}
$versionBuild = if ($versionMatch.Groups['build'].Success) {
    $versionMatch.Groups['build'].Value
}
else {
    '0'
}
$versionNumeric = @(
    $versionMatch.Groups['major'].Value,
    $versionMatch.Groups['minor'].Value,
    $versionMatch.Groups['patch'].Value,
    $versionBuild
) -join '.'

if ($metadata.channel -ne "Internal Beta") {
    throw "Installer builds are restricted to the Internal Beta channel."
}

if ($ApplicationSource) {
    $appSource = [System.IO.Path]::GetFullPath($ApplicationSource)
}
else {
    $candidateRoot = Join-Path $ReleaseRoot "Internal_Beta_Candidates"
    $appSource = Get-ChildItem -LiteralPath $candidateRoot -Directory -Recurse `
        -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -eq $metadata.package } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1 -ExpandProperty FullName
    if (-not $appSource) {
        throw "No verified Internal Beta application candidate found. Build and verify the PyInstaller onedir and LGPL candidate before compiling an installer."
    }
}
$appExe = Join-Path $appSource ($metadata.package + ".exe")
Assert-FileExists -Path $appExe

$compilerAppSource = $appSource
$temporarySourceDrive = $null
$longestSourcePath = Get-ChildItem -LiteralPath $appSource -File -Recurse -Force |
    ForEach-Object { $_.FullName.Length } |
    Measure-Object -Maximum |
    Select-Object -ExpandProperty Maximum
if ($longestSourcePath -gt 240) {
    $driveLetter = 'Z','Y','X','W','V','U','T' |
        Where-Object { -not (Get-PSDrive -Name $_ -ErrorAction SilentlyContinue) } |
        Select-Object -First 1
    if (-not $driveLetter) {
        throw "No free temporary drive letter is available to shorten installer source paths."
    }
    $temporarySourceDrive = "${driveLetter}:"
    & subst.exe $temporarySourceDrive $appSource
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to map the installer source to $temporarySourceDrive."
    }
    $compilerAppSource = "$temporarySourceDrive\"
}

if (-not $InnoCompiler) {
    $knownCompilers = @(
        $(if ($env:LOCALAPPDATA) {
            Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"
        }),
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe"
    ) | Where-Object { $_ }
    $InnoCompiler = $knownCompilers |
        Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
        Select-Object -First 1
}

if (-not $InnoCompiler) {
    throw "Inno Setup 6 compiler not found. Installer build status: NOT RUN."
}
Assert-FileExists -Path $InnoCompiler

New-Item -ItemType Directory -Path $InstallerOutput -Force | Out-Null

$arguments = @(
    "/Q",
    "/DAppSource=$compilerAppSource",
    "/DAppDisplayName=$($metadata.display_name)",
    "/DAppVersion=$($metadata.version)",
    "/DAppVersionNumeric=$versionNumeric",
    "/DAppReleaseChannel=$($metadata.channel)",
    "/DAppExeName=$($metadata.package).exe",
    "/DInstallerBasename=$($metadata.installer)",
    "/DInstallerOutputDir=$InstallerOutput",
    "/DProjectLicense=$(Join-Path $Root 'LICENSE')",
    $InstallerScript
)

try {
    & $InnoCompiler @arguments
    $compilerExitCode = $LASTEXITCODE
}
finally {
    if ($temporarySourceDrive) {
        & subst.exe $temporarySourceDrive /D
    }
}
if ($compilerExitCode -ne 0) {
    throw "Inno Setup build failed with exit code: $compilerExitCode"
}

$installerPath = Join-Path $InstallerOutput ($metadata.installer + ".exe")
Assert-FileExists -Path $installerPath
$hash = (Get-FileHash -LiteralPath $installerPath -Algorithm SHA256).Hash
$checksumPath = Join-Path $InstallerOutput ($metadata.installer + "-SHA256SUMS.txt")
"$hash  $($metadata.installer).exe" |
    Set-Content -LiteralPath $checksumPath -Encoding ascii

Write-Host "Internal Beta installer candidate: $installerPath"
Write-Host "SHA-256: $hash"
Write-Host "SHA-256 file: $checksumPath"
