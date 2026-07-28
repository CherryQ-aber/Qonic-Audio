# Qonic Audio Compliance Tools

本目录是 `Qonic Audio` / `Qonic Audio Converter & Editor` 的第三方依赖证据采集工具。它只使用 Python 标准库，默认离线，不下载、不替换、不删除任何运行依赖。

## 当前边界

- 默认入口只做本地扫描、版本查询、SHA-256 和报告生成；任何下载脚本都要求显式网络开关。
- 不修改 `converter.py`、`watcher.py`、QML、requirements、PyInstaller spec 或二进制。
- 当前唯一审计基线是 `Release/External_Test/2026-07-24_b4edd4d/` 下的冻结归档及对应展开目录。
- FFmpeg、ffprobe 与 ncmdump 未获授权时不得替换；Qt 模块最小化不属于本轮。
- 报告中的候选许可证和风险分类不是法律意见。
- 输出会脱敏项目根目录和 Windows 用户目录。

## 统一入口

对已有展开发行目录运行：

由于项目已经存在用于运行时二进制的 `Tools/` 目录，Windows 无法再并存一个仅大小写不同的 `tools/`；因此本仓库把合规工具放在 `Tools/compliance/`。Windows 上旧提示词中的小写命令仍可解析，跨平台命令应使用下列真实大小写。

```powershell
python Tools/compliance/collect_all.py `
  --project-root . `
  --dist-path "Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test" `
  --dist-archive "Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test.7z" `
  --output "compliance/report"
```

若需要重新展开最终 `.7z`，使用可信的本机 7-Zip，并确保展开目录与冻结归档一一对应：

```powershell
python Tools/compliance/collect_all.py `
  --project-root . `
  --dist-path "Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test" `
  --dist-archive "Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test.7z" `
  --output "compliance/report"
```

退出码：

- `0`：通过
- `1`：存在普通警告
- `2`：存在阻断问题
- `3`：工具执行失败

严格验证：

```powershell
python Tools/compliance/validate_compliance.py `
  --manifest "compliance/report/THIRD_PARTY_MANIFEST.json" `
  --strict
```

## ncmdump 官方资产比对

项目所有者提供官方 CLI Windows amd64 ZIP 后，按权威发行展开目录运行：

```powershell
python Tools/compliance/verify_ncmdump_asset.py `
  --local-file "Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test/_internal/Tools/ncmdump/ncmdump.exe" `
  --asset-file "ncmdump-1.5.1-windows-amd64.zip" `
  --output "compliance/report/ncmdump"
```

脚本会拒绝 ZIP 路径穿越、绝对路径、驱动器路径和符号链接，并只在 SHA-256 与大小完全一致时写入 `byte_identical_to_upstream: true`。

本轮核验结果为 `BYTE_IDENTICAL`：官方 ZIP SHA-256 为 `BB849221C06B8FDBFF42AEFB86BAEA9C07256568658D80F4BE72A39A2A1632DC`，其中唯一的 `ncmdump.exe` 与权威发行文件逐字节一致。现有 EXE 保留，未解压覆盖或替换。

## 显式官方材料下载

以下命令默认关闭网络，只有显式开关才会访问证据 JSON 中记录的官方 URL：

```powershell
python Tools/compliance/verify_qt_wheels.py `
  --dist-path "Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test" `
  --metadata "Tools/compliance/evidence/qt-6.11.1-upstream.json" `
  --output "compliance/report/qt" `
  --wheel-cache "third_party/upstream-assets/qt" `
  --allow-download

python Tools/compliance/fetch_qt_sources.py `
  --evidence "Tools/compliance/evidence/qt-6.11.1-upstream.json" `
  --output "third_party/source-archives/qt" `
  --allow-network
```

FFmpeg 官方 Gyan 资产比对使用 `verify_ffmpeg_asset.py`，以流式读取 7z 成员完成，不会把官方 EXE 覆盖到发行目录。

## 测试

```powershell
python -m unittest discover -s Tools/compliance/tests -p "test_*.py" -v
```

## 合规包

`build_compliance_bundle.py` 在存在 BLOCKER 时默认拒绝生成。不得使用 `--allow-blockers` 制作对外发布材料；该开关只用于内部审查快照。
