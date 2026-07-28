# ncmdump Notice

当前项目发行包会随包携带：

- `Tools/ncmdump/ncmdump.exe`

本仓库当前仅在 `Tools/ncmdump/` 保存运行所需二进制文件；上游 MIT 许可证原文已补充为 `LICENSES/ncmdump-MIT.txt`。

当前候选二进制的可核验信息：

- 自报版本：`ncmdump 1.5.1`
- SHA-256：`A1F6F6CE87500B7B1F2A89DBF85B13E81D327EEA4641DAF8AFE0AB840F2C518C`
- 上游仓库：`https://github.com/taurusxin/ncmdump`
- 上游版本：`1.5.1`
- 正确 CLI 官方资产：`ncmdump-1.5.1-windows-amd64.zip`
- 正确 CLI 官方资产 SHA-256：`BB849221C06B8FDBFF42AEFB86BAEA9C07256568658D80F4BE72A39A2A1632DC`
- 已核验资产：`ncmdump-1.5.1-windows-amd64.zip`
- 已核验资产 SHA-256：`BB849221C06B8FDBFF42AEFB86BAEA9C07256568658D80F4BE72A39A2A1632DC`
- 精确源码 commit：`76a55d862f767ee20ae417ecd128fde442eea77f`
- 精确源码 SHA-256：`70D1C692130B0C0C53276417FD6246C02C4C39D057005F0435FF4942C7CFF11E`
- Windows 构建：GitHub Actions `windows-latest`、CMake Release、`x64-windows-static`
- vcpkg baseline：`a62ce77d56ee07513b4b67de1ec2daeaebfae51a`
- 静态依赖：TagLib `2.0.2`、zlib `1.3.1`、utfcpp `4.0.6`
- 上游许可证：MIT License

审核结论：

- 当前 v5.0 内部测试候选已明确标记 ncmdump 为随包外部工具，并附带上游 MIT 许可证文本。
- 官方 CLI ZIP 内唯一的 `ncmdump.exe` 与权威发行目录文件大小和 SHA-256 完全一致，`byte_identical_to_upstream = true`。
- 按所有者决定保留当前 EXE；未执行解压覆盖或替换。
- 精确 commit 源码、vcpkg 构建元数据以及三项静态依赖源码归档均已保存并通过哈希校验。
- 上游 `1.5.1` 的 `LICENSE.txt` 版权行仍是 `[year] [fullname]` 占位符；本项目按上游原文保留，没有自行猜测或改写权利人。

建议至少核对：

- 官方 GitHub Actions 使用的具体 `windows-latest` runner 镜像版本与编译器补丁版本未在 Release 元数据中固定
