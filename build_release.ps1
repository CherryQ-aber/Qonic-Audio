param(
    [switch]$SkipArchive,
    [switch]$IncludeSfx
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
$SpecPath = Join-Path $Root ((& python -c "from app_info import APP_SPEC_NAME; print(APP_SPEC_NAME)").Trim())
$ReadmePath = Join-Path $Root "README.md"
$ChangelogPath = Join-Path $Root "CHANGELOG.md"
$ReleaseNotesPath = Join-Path $Root ((& python -c "from app_info import APP_RELEASE_NOTES_NAME; print(APP_RELEASE_NOTES_NAME)").Trim())
$KnownIssuesPath = Join-Path $Root "Known_Issues.md"
$TestChecklistPath = Join-Path $Root "TEST_CHECKLIST.md"
$ExternalTestGuidePath = Join-Path $Root "EXTERNAL_TEST_GUIDE.md"
$ConfigExamplePath = Join-Path $Root "config.example.json"
$ProjectLicensePath = Join-Path $Root "LICENSE"
$LicensesPath = Join-Path $Root "LICENSES"
$VersionInfoPath = Join-Path $Root "windows_version_info.txt"

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

if ($SkipArchive -and $IncludeSfx) {
    throw "-IncludeSfx cannot be used together with -SkipArchive."
}

foreach ($requiredFile in @(
    $SpecPath,
    $ReadmePath,
    $ChangelogPath,
    $ReleaseNotesPath,
    $KnownIssuesPath,
    $TestChecklistPath,
    $ExternalTestGuidePath,
    $ConfigExamplePath,
    $ProjectLicensePath,
    $VersionInfoPath,
    (Join-Path $Root "Tools\ffmpeg\bin\ffmpeg.exe"),
    (Join-Path $Root "Tools\ffmpeg\bin\ffprobe.exe"),
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
Copy-Item -LiteralPath $TestChecklistPath -Destination (Join-Path $ReleasePath "TEST_CHECKLIST.md") -Force
Copy-Item -LiteralPath $ExternalTestGuidePath -Destination (Join-Path $ReleasePath "EXTERNAL_TEST_GUIDE.md") -Force
Copy-Item -LiteralPath $ConfigExamplePath -Destination (Join-Path $ReleasePath "config.example.json") -Force
Copy-Item -LiteralPath $ProjectLicensePath -Destination (Join-Path $ReleasePath "LICENSE") -Force

if (Test-Path -LiteralPath $LicensesPath) {
    Copy-Item -LiteralPath $LicensesPath -Destination (Join-Path $ReleasePath "LICENSES") -Recurse -Force
}

$ReleaseExe = Join-Path $ReleasePath "$AppName.exe"
$ReleaseQmlEntry = Join-Path $ReleasePath "_internal\ui_next\qml\AppShell.qml"
$ReleaseIcon = Join-Path $ReleasePath "_internal\Assets\icon.ico"
$ReleaseFfmpeg = Join-Path $ReleasePath "_internal\Tools\ffmpeg\bin\ffmpeg.exe"
$ReleaseFfprobe = Join-Path $ReleasePath "_internal\Tools\ffmpeg\bin\ffprobe.exe"
$ReleaseNcmdump = Join-Path $ReleasePath "_internal\Tools\ncmdump\ncmdump.exe"
$ReleaseLicense = Join-Path $ReleasePath "LICENSE"

Assert-FileExists -Path $ReleaseExe
Assert-FileExists -Path $ReleaseQmlEntry
Assert-FileExists -Path $ReleaseIcon
Assert-FileExists -Path $ReleaseFfmpeg
Assert-FileExists -Path $ReleaseFfprobe
Assert-FileExists -Path $ReleaseNcmdump
Assert-FileExists -Path $ReleaseLicense

$previousQtPlatform = [Environment]::GetEnvironmentVariable(
    "QT_QPA_PLATFORM",
    "Process"
)

try {
    $env:QT_QPA_PLATFORM = "offscreen"
    $smokeProcess = Start-Process `
        -FilePath $ReleaseExe `
        -ArgumentList @(
            "--qml-smoke-test",
            "--qml-open-module=audioEditor"
        ) `
        -WindowStyle Hidden `
        -Wait `
        -PassThru
}
finally {
    if ($null -eq $previousQtPlatform) {
        Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
    }
    else {
        $env:QT_QPA_PLATFORM = $previousQtPlatform
    }
}

if ($smokeProcess.ExitCode -ne 0) {
    throw "Packaged QML smoke test failed with exit code: $($smokeProcess.ExitCode)"
}

$ReleaseRuntimeLog = Join-Path $ReleasePath "logs\runtime.log"
if (Test-Path -LiteralPath $ReleaseRuntimeLog) {
    Remove-Item -LiteralPath $ReleaseRuntimeLog -Force
}

foreach ($forbiddenPath in @(
    (Join-Path $ReleasePath "config.json"),
    $ReleaseRuntimeLog,
    (Join-Path $ReleasePath "_internal\Tools\ffmpeg\bin\ffplay.exe")
)) {
    if (Test-Path -LiteralPath $forbiddenPath) {
        throw "Release contains forbidden file: $forbiddenPath"
    }
}

if (-not $SkipArchive) {
    $SevenZip = "C:\Program Files\7-Zip\7z.exe"
    $SevenZipSfx = "C:\Program Files\7-Zip\7z.sfx"
    Assert-FileExists -Path $SevenZip

    if ($IncludeSfx) {
        Assert-FileExists -Path $SevenZipSfx
    }

    $ArchivePath = Join-Path $ReleaseRoot "$AppName.7z"
    $SfxPath = Join-Path $ReleaseRoot "$AppName.exe"
    $ChecksumPath = Join-Path $ReleaseRoot "$AppName-SHA256SUMS.txt"

    foreach ($outputFile in @($ArchivePath, $SfxPath, $ChecksumPath)) {
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

    & $SevenZip t $ArchivePath

    if ($LASTEXITCODE -ne 0) {
        throw "7z integrity test failed with exit code: $LASTEXITCODE"
    }

    $artifactPaths = @($ArchivePath)

    if ($IncludeSfx) {
        Write-SfxArchive -SfxModule $SevenZipSfx -Archive $ArchivePath -Output $SfxPath
        & $SevenZip t $SfxPath

        if ($LASTEXITCODE -ne 0) {
            throw "SFX integrity test failed with exit code: $LASTEXITCODE"
        }

        $artifactPaths += $SfxPath
    }

    $checksumLines = foreach ($artifactPath in $artifactPaths) {
        $hash = Get-FileHash -Algorithm SHA256 -LiteralPath $artifactPath
        "$($hash.Hash)  $(Split-Path -Leaf $artifactPath)"
    }
    Set-Content -LiteralPath $ChecksumPath -Value $checksumLines -Encoding ascii
}

Write-Host "Release baseline build completed: $ReleasePath"
