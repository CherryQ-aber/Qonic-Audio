[CmdletBinding()]
param(
    [ValidateSet("auto", "docker", "podman")]
    [string]$Runtime = "auto"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$dockerfile = Join-Path $PSScriptRoot "config\Dockerfile"
$imageName = "qonic-ffmpeg-build:2026-07-26"
$runtimeCommand = $null
$userDocker = Join-Path $env:LOCALAPPDATA "Programs\DockerDesktop\resources\bin\docker.exe"

if ($Runtime -eq "auto") {
    $dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
    $podmanCommand = Get-Command podman -ErrorAction SilentlyContinue
    if ($dockerCommand) {
        $Runtime = "docker"
        $runtimeCommand = $dockerCommand.Source
    } elseif (Test-Path -LiteralPath $userDocker -PathType Leaf) {
        $Runtime = "docker"
        $runtimeCommand = $userDocker
    } elseif ($podmanCommand) {
        $Runtime = "podman"
        $runtimeCommand = $podmanCommand.Source
    } else {
        throw "未找到 Docker 或 Podman；未开始候选构建，也未修改正式 FFmpeg。"
    }
}

if (-not $runtimeCommand) {
    $runtime = Get-Command $Runtime -ErrorAction SilentlyContinue
    if ($runtime) {
        $runtimeCommand = $runtime.Source
    } elseif ($Runtime -eq "docker" -and (Test-Path -LiteralPath $userDocker -PathType Leaf)) {
        $runtimeCommand = $userDocker
    } else {
        throw "未找到指定的容器运行时：$Runtime"
    }
}

$runtimeBin = Split-Path -Parent $runtimeCommand
if ($Runtime -eq "docker" -and ($env:PATH -split ";" -notcontains $runtimeBin)) {
    # Per-user Docker Desktop installations do not always update an already
    # running Codex process. Keep the fix local to this build process so the
    # CLI can also locate docker-credential-desktop.exe.
    $env:PATH = "$runtimeBin;$env:PATH"
}

& $runtimeCommand build --pull=false --file $dockerfile --tag $imageName $root
if ($LASTEXITCODE -ne 0) { throw "固定构建容器创建失败。" }

& $runtimeCommand run --rm `
    --platform linux/amd64 `
    --volume "${root}:/repo" `
    $imageName
if ($LASTEXITCODE -ne 0) { throw "候选构建失败；正式 FFmpeg 未修改。" }

$candidate = Join-Path $PSScriptRoot "output\candidate"
$ffmpeg = Join-Path $candidate "ffmpeg.exe"
$ffprobe = Join-Path $candidate "ffprobe.exe"
if (-not (Test-Path -LiteralPath $ffmpeg) -or -not (Test-Path -LiteralPath $ffprobe)) {
    throw "容器未生成完整候选文件。"
}

$captures = @(
    @{ File = "ffmpeg-version.txt"; Command = $ffmpeg; Args = @("-version") },
    @{ File = "ffmpeg-buildconf.txt"; Command = $ffmpeg; Args = @("-buildconf") },
    @{ File = "ffmpeg-formats.txt"; Command = $ffmpeg; Args = @("-formats") },
    @{ File = "ffmpeg-codecs.txt"; Command = $ffmpeg; Args = @("-codecs") },
    @{ File = "ffmpeg-encoders.txt"; Command = $ffmpeg; Args = @("-encoders") },
    @{ File = "ffmpeg-decoders.txt"; Command = $ffmpeg; Args = @("-decoders") },
    @{ File = "ffmpeg-filters.txt"; Command = $ffmpeg; Args = @("-filters") },
    @{ File = "ffmpeg-protocols.txt"; Command = $ffmpeg; Args = @("-protocols") },
    @{ File = "ffmpeg-bsfs.txt"; Command = $ffmpeg; Args = @("-bsfs") },
    @{ File = "ffprobe-version.txt"; Command = $ffprobe; Args = @("-version") }
)
foreach ($capture in $captures) {
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        # Windows PowerShell 5.1 can promote a native program's stderr to a
        # terminating NativeCommandError under Stop. FFmpeg writes its banner
        # there even on success, so capture it while checking the real exit code.
        $ErrorActionPreference = "Continue"
        & $capture.Command @($capture.Args) 2>&1 |
            Out-File -LiteralPath (Join-Path $candidate $capture.File) -Encoding utf8
        $captureExitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    if ($captureExitCode -ne 0) { throw "Windows 候选验证失败：$($capture.File)" }
}

& python (Join-Path $PSScriptRoot "scripts\compare_capabilities.py") `
    --ffmpeg $ffmpeg `
    --ffprobe $ffprobe `
    --output (Join-Path $candidate "capabilities.json") `
    --compare-required
if ($LASTEXITCODE -ne 0) { throw "候选能力采集失败。" }
