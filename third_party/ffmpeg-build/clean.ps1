[CmdletBinding(SupportsShouldProcess)]
param()

$ErrorActionPreference = "Stop"
$buildRoot = (Resolve-Path -LiteralPath $PSScriptRoot).Path
$targets = @(
    (Join-Path $buildRoot "work"),
    (Join-Path $buildRoot "output")
)

foreach ($target in $targets) {
    $resolvedParent = (Resolve-Path -LiteralPath (Split-Path -Parent $target)).Path
    if ($resolvedParent -ne $buildRoot) {
        throw "拒绝清理工作区之外的路径：$target"
    }
    if (Test-Path -LiteralPath $target) {
        if ($PSCmdlet.ShouldProcess($target, "清理 FFmpeg 自构建临时产物")) {
            Remove-Item -LiteralPath $target -Recurse -Force
            New-Item -ItemType Directory -Path $target | Out-Null
            New-Item -ItemType File -Path (Join-Path $target ".gitkeep") | Out-Null
        }
    }
}
