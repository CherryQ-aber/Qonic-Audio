# Qt Plugin Analysis

- 事实：插件目录来自实际发行目录扫描。
- 推断：platforms/imageformats/multimedia/styles/tls/networkinformation/platforminputcontexts 与当前桌面、多媒体和网络栈相关。
- 风险：仅凭文件存在不能证明运行时实际加载；第一阶段不删除任何插件。

- `plugin:Hangul`: 3 files, `POSSIBLY_UNUSED`
- `plugin:OpenWNN`: 3 files, `POSSIBLY_UNUSED`
- `plugin:Pinyin`: 3 files, `POSSIBLY_UNUSED`
- `plugin:TCIme`: 3 files, `POSSIBLY_UNUSED`
- `plugin:Thai`: 3 files, `POSSIBLY_UNUSED`
- `plugin:generic`: 1 files, `POSSIBLY_UNUSED`
- `plugin:iconengines`: 1 files, `POSSIBLY_UNUSED`
- `plugin:imageformats`: 10 files, `LIKELY_REQUIRED`
- `plugin:multimedia`: 2 files, `LIKELY_REQUIRED`
- `plugin:networkinformation`: 1 files, `LIKELY_REQUIRED`
- `plugin:platforminputcontexts`: 1 files, `LIKELY_REQUIRED`
- `plugin:platforms`: 4 files, `LIKELY_REQUIRED`
- `plugin:qmldir`: 1 files, `POSSIBLY_UNUSED`
- `plugin:qmltooling`: 13 files, `POSSIBLY_UNUSED`
- `plugin:qtvkbpluginsplugin.dll`: 1 files, `POSSIBLY_UNUSED`
- `plugin:qtvkbpluginsplugin.qmltypes`: 1 files, `POSSIBLY_UNUSED`
- `plugin:styles`: 1 files, `LIKELY_REQUIRED`
- `plugin:tls`: 3 files, `LIKELY_REQUIRED`
