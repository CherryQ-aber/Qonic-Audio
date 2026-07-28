[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$python = (Get-Command python).Source
& $python (Join-Path $PSScriptRoot "scripts\download_sources.py") --offline
if ($LASTEXITCODE -ne 0) { throw "源码缓存校验失败。" }
& $python (Join-Path $PSScriptRoot "scripts\verify_sources.py")
if ($LASTEXITCODE -ne 0) { throw "源码 SHA-256 校验失败。" }
& $python -m pytest (Join-Path $PSScriptRoot "tests") -q
if ($LASTEXITCODE -ne 0) { throw "FFmpeg 自构建静态测试失败。" }
