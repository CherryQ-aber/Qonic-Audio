param(
    [switch]$SkipArchive
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppName = (& python -c "from app_info import APP_PACKAGE_BASENAME; print(APP_PACKAGE_BASENAME)").Trim()
$BuildRoot = Join-Path $Root "build\release"
$WorkPath = Join-Path $BuildRoot "work"
$DistPath = Join-Path $BuildRoot "dist"
$ReleaseRoot = Join-Path $Root "Release"
$ReleasePath = Join-Path $ReleaseRoot $AppName
$SpecPath = Join-Path $Root "CherryQ_Audio_Converter.spec"
$ReadmePath = Join-Path $Root "README.md"
$ChangelogPath = Join-Path $Root "CHANGELOG.md"
$ReleaseNotesPath = Join-Path $Root ((& python -c "from app_info import APP_RELEASE_NOTES_NAME; print(APP_RELEASE_NOTES_NAME)").Trim())
$KnownIssuesPath = Join-Path $Root "Known_Issues.md"
$ConfigExamplePath = Join-Path $Root "config.example.json"
$LicensesPath = Join-Path $Root "LICENSES"

function Get-SafeChildPath {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Parent
    )

    $fullPath = [System.IO.Path]::GetFullPath($Path)
    $fullParent = [System.IO.Path]::GetFullPath($Parent).TrimEnd("\") + "\"

    if (-not $fullPath.StartsWith(
        $fullParent,
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Refusing to operate outside workspace: $fullPath"
    }

    return $fullPath
}

function Reset-SafeDirectory {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Parent
    )

    $safePath = Get-SafeChildPath -Path $Path -Parent $Parent

    if (Test-Path -LiteralPath $safePath) {
        Remove-Item -LiteralPath $safePath -Recurse -Force
    }

    New-Item -ItemType Directory -Path $safePath -Force | Out-Null
}

function Assert-FileExists {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Missing required release file: $Path"
    }
}

function Write-SfxArchive {
    param(
        [Parameter(Mandatory = $true)][string]$SfxModule,
        [Parameter(Mandatory = $true)][string]$Archive,
        [Parameter(Mandatory = $true)][string]$Output
    )

    $outputStream = [System.IO.File]::Create($Output)

    try {
        foreach ($sourcePath in @($SfxModule, $Archive)) {
            $inputStream = [System.IO.File]::OpenRead($sourcePath)

            try {
                $inputStream.CopyTo($outputStream)
            }
            finally {
                $inputStream.Dispose()
            }
        }
    }
    finally {
        $outputStream.Dispose()
    }
}

Set-Location -LiteralPath $Root

foreach ($requiredFile in @(
    $SpecPath,
    $ReadmePath,
    $ChangelogPath,
    $ReleaseNotesPath,
    $KnownIssuesPath,
    $ConfigExamplePath,
    (Join-Path $Root "Tools\ffmpeg\bin\ffmpeg.exe"),
    (Join-Path $Root "Tools\ncmdump\ncmdump.exe")
)) {
    Assert-FileExists -Path $requiredFile
}

Reset-SafeDirectory -Path $BuildRoot -Parent $Root
New-Item -ItemType Directory -Path $ReleaseRoot -Force | Out-Null

Write-Host "Building PyInstaller directory release..."
& pyinstaller `
    --noconfirm `
    --clean `
    --distpath $DistPath `
    --workpath $WorkPath `
    $SpecPath

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed with exit code: $LASTEXITCODE"
}

$BuiltAppPath = Join-Path $DistPath $AppName
Reset-SafeDirectory -Path $ReleasePath -Parent $Root
Copy-Item -Path (Join-Path $BuiltAppPath "*") -Destination $ReleasePath -Recurse -Force

New-Item -ItemType Directory -Path (Join-Path $ReleasePath "logs") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $ReleasePath "Music_Output") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $ReleasePath "AudioEditor_Output") -Force | Out-Null
Copy-Item -LiteralPath $ReadmePath -Destination (Join-Path $ReleasePath "README.md") -Force
Copy-Item -LiteralPath $ChangelogPath -Destination (Join-Path $ReleasePath "CHANGELOG.md") -Force
Copy-Item -LiteralPath $ReleaseNotesPath -Destination (Join-Path $ReleasePath (Split-Path -Leaf $ReleaseNotesPath)) -Force
Copy-Item -LiteralPath $KnownIssuesPath -Destination (Join-Path $ReleasePath "Known_Issues.md") -Force
Copy-Item -LiteralPath $ConfigExamplePath -Destination (Join-Path $ReleasePath "config.example.json") -Force

if (Test-Path -LiteralPath $LicensesPath) {
    Copy-Item -LiteralPath $LicensesPath -Destination (Join-Path $ReleasePath "LICENSES") -Recurse -Force
}

$ReleaseExe = Join-Path $ReleasePath "$AppName.exe"
$ReleaseFfmpeg = Join-Path $ReleasePath "_internal\Tools\ffmpeg\bin\ffmpeg.exe"
$ReleaseNcmdump = Join-Path $ReleasePath "_internal\Tools\ncmdump\ncmdump.exe"

Assert-FileExists -Path $ReleaseExe
Assert-FileExists -Path $ReleaseFfmpeg
Assert-FileExists -Path $ReleaseNcmdump

foreach ($forbiddenPath in @(
    (Join-Path $ReleasePath "config.json"),
    (Join-Path $ReleasePath "_internal\Tools\ffmpeg\bin\ffplay.exe"),
    (Join-Path $ReleasePath "_internal\Tools\ffmpeg\bin\ffprobe.exe")
)) {
    if (Test-Path -LiteralPath $forbiddenPath) {
        throw "Release contains forbidden file: $forbiddenPath"
    }
}

if (-not $SkipArchive) {
    $SevenZip = "C:\Program Files\7-Zip\7z.exe"
    $SevenZipSfx = "C:\Program Files\7-Zip\7z.sfx"
    Assert-FileExists -Path $SevenZip
    Assert-FileExists -Path $SevenZipSfx

    $ArchivePath = Join-Path $ReleaseRoot "$AppName.7z"
    $SfxPath = Join-Path $ReleaseRoot "$AppName.exe"

    foreach ($outputFile in @($ArchivePath, $SfxPath)) {
        if (Test-Path -LiteralPath $outputFile) {
            Remove-Item -LiteralPath $outputFile -Force
        }
    }

    Push-Location -LiteralPath $ReleaseRoot

    try {
        & $SevenZip a -t7z -mx=7 $ArchivePath $AppName
    }
    finally {
        Pop-Location
    }

    if ($LASTEXITCODE -ne 0) {
        throw "7z compression failed with exit code: $LASTEXITCODE"
    }

    Write-SfxArchive -SfxModule $SevenZipSfx -Archive $ArchivePath -Output $SfxPath

    & $SevenZip t $ArchivePath

    if ($LASTEXITCODE -ne 0) {
        throw "7z integrity test failed with exit code: $LASTEXITCODE"
    }

    & $SevenZip t $SfxPath

    if ($LASTEXITCODE -ne 0) {
        throw "SFX integrity test failed with exit code: $LASTEXITCODE"
    }
}

Write-Host "Release baseline build completed: $ReleasePath"
