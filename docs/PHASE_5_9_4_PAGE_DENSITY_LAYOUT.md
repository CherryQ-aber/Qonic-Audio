# Phase 5.9.4 页面密度与卡片布局整理

## 结论

Phase 5.9.4 已完成工程实现。此次只重新分配 QML 页面空间、合并重复卡片并明确滚动承载，没有修改 Python 业务行为、TaskQueueModel / EditorSession 语义、转换与导出服务、播放器后端、主题、勾选图标或一级导航。

自动转码队列现在是页面主区域；文件信息页按宽度使用封面、Metadata、技术信息的 1～3 列布局；歌词页保留原文和草稿各自独立的滚动条；Pitch 参数、试听和导出形成响应式工作区；设置页在中宽和宽屏使用两列分组。

## 页面结构变化

### 自动转码

修改前：

```text
入口/状态卡片
任务队列
多组转换操作卡片
扫描摘要卡片
```

修改后：

```text
紧凑入口与全局输出摘要
任务队列（填充剩余高度）
内联扫描摘要
紧凑转换与队列操作
```

- 页面不再使用外层 Flickable；队列 ListView 是该页唯一主要纵向滚动容器。
- 队列最小高度为 190 px，并随窗口剩余空间扩展。
- 三档几何测试均要求队列高度不少于页面可用高度的 38%，且高于顶部入口和底部操作区。
- 添加文件、扫描目录、watcher、目标格式、默认输出目录、右键菜单、多选和任务级策略仍调用原有入口。
- 扫描摘要只显示已扫描、新增、重复、不支持和当前状态，不恢复第二套候选列表。

### 文件信息

修改前：

```text
安全说明
读取状态
封面
Metadata
技术信息
编辑操作
```

修改后：

```text
安全说明 + 读取/草稿状态
封面 | Metadata | 技术信息（响应式）
紧凑编辑操作
```

- 页面可用宽度不小于 880 px：三列。
- 页面可用宽度为 660～879 px：封面与 Metadata 同行，技术信息跨两列置于下方。
- 页面可用宽度小于 660 px：单列。
- Metadata 获得最大首选宽度；封面保持约 20%～30% 的合理宽度。
- 封面编辑器只显示一张“当前有效封面”，替换、移除、恢复、dirty 和统一导出入口不变。
- 页面只保留一个外层纵向 Flickable。

### 歌词

修改前：

```text
安全说明卡
来源/状态卡
歌词行预览
原始歌词
当前草稿
草稿操作
```

修改后：

```text
当前文件 + 来源 + dirty + 常用操作
歌词行预览 | 歌词草稿工作区
```

- 页面可用宽度不小于 720 px 时，歌词行预览与草稿编辑区按约 36% / 64% 并排；更窄时回退单列。
- 原始歌词与当前草稿在编辑器宽度不小于 660 px 时并排，否则纵向排列。
- `originalLyricsVerticalScrollBar` 和 `draftLyricsVerticalScrollBar` 继续分别绑定各自 ScrollView，并锚定在各自窗格内部。
- 页面外层滚动条只负责窄窗口的页面回退，不与两个歌词正文滚动条重合。
- 长歌词不会撑高页面，歌词草稿、读取、解析、编辑和导出逻辑未改。
- 歌词页没有重新加入任何封面 UI。

### 音频内容处理 / Pitch

修改前：

```text
参数
试听状态
试听操作
导出状态
导出操作
```

修改后：

```text
Pitch 参数 | 试听状态与控制 | 导出结果
```

- Pitch 卡宽度不小于 900 px 时使用三列；不足时按参数、试听、导出单列回退。
- 三个区域仍在同一 Pitch 卡片内，只增加轻量内部工作窗格，没有拆分状态或服务。
- 半音范围、步进、缓存键、试听、取消、返回原音频、no-clobber 导出、打开位置和显式载入结果均未改。
- 最近导出路径使用单行省略和 tooltip，不自动载入结果。

### 音频编辑首页

- 当前文件名、路径、播放源、dirty 和导出入口合并进紧凑当前文件摘要。
- 当前文件摘要在可用宽度不小于 720 px 时两列，窄窗口单列。
- 删除重复的歌词草稿摘要卡和重复安全说明；当前文件栏、播放器、文件浏览、波形占位和页面切换均保留。
- 页面继续使用一个外层 Flickable；没有把播放器改为全局播放器。

### 设置

- 页面标题、草稿状态和草稿操作合并为一个紧凑头部。
- 设置分组可用宽度不小于 900 px 时两列，否则单列。
- 设置页继续只有一个外层 Flickable；设置字段、保存语义、确认逻辑、设备和 ASIO 占位状态均未改。

## 滚动体系

- 自动转码：页面不滚动，任务队列独立滚动。
- 文件信息：一个页面 Flickable。
- 歌词：一个页面回退 Flickable；歌词行预览、原始歌词和当前草稿按内容区域独立滚动。两个正文滚动条位于各自窗格内，与页面滚动条不重合。
- 音频编辑 / Pitch：音频编辑页的单一 Flickable 承载窄窗口回退，Pitch 内部没有新增 ScrollView。
- 设置：一个页面 Flickable。
- 日志列表的既有独立滚动未改。

没有新增“页面 ScrollView → 卡片 ScrollView → TextArea ScrollView”层级；歌词编辑器保留的是修复前已经存在且业务必要的两个正文 ScrollView。

## 响应式验证

AppShell 扣除侧栏、检查器和外壳后，自动化测试使用以下真实页面视口：

| 外层窗口 | 页面视口 | 自动转码 | 文件信息 | 歌词 | Pitch | 设置 |
| --- | --- | --- | --- | --- | --- | --- |
| 1280×720 | 754×612 | 队列 ≥ 38%，主操作可见 | 2 列，技术信息下置 | 主区 2 列，编辑器内部单列 | 单列回退 | 单列 |
| 1440×900 | 914×792 | 队列 ≥ 38%，填充剩余高度 | 3 列 | 主区 2 列，编辑器内部单列 | 3 列 | 2 列 |
| 1920×1080 | 1392×972 | 队列 ≥ 38%，横向填充 | 3 列 | 主区 2 列，编辑器内部 2 列 | 3 列 | 2 列 |

三档测试同时检查组件不发生水平溢出、底部操作可访问、歌词正文实际可滚动、两个正文滚动条位于各自 ScrollView 内且不与页面滚动条相交。

## 验证结果

```powershell
python -m compileall -q .
python -B main_qml.py --qml-smoke-test
python -B main_qml.py --qml-smoke-test --qml-open-module=autoConvert
python -B main_qml.py --qml-smoke-test --qml-open-module=metadata
python -B main_qml.py --qml-smoke-test --qml-open-module=lyricsCover
python -B main_qml.py --qml-smoke-test --qml-open-module=audioEditor
python -B main_qml.py --qml-smoke-test --qml-open-module=settings
python -m pytest -q -p no:cacheprovider
python -B -c "import gui"
python -B -c "from ui.main_window import MainWindow"
```

- Phase 5.9.4 三档布局、页面几何和既有布局专项：`17 passed, 15 subtests passed`。
- 相关图标、浅色主题、运行模式、统一导出和 Phase 5.9.4 复核：`26 passed, 15 subtests passed`。
- 完整回归：初始布局结项为 `457 passed, 2 warnings, 20 subtests passed`；后续修复 QML 列表参数桥接并新增 3 项真实 QML 调用测试后为 `460 passed, 2 warnings, 20 subtests passed`。
- 两条 warning 均为既有 `QMouseEvent` 构造弃用提示；没有新增 QML undefined、binding loop、anchor conflict 或布局警告。
- 默认用户模式可见结构检查覆盖自动转码、文件信息、歌词、Pitch 和设置页；检查后正常关闭，无残留 QML 窗口。

## 安全与边界

- 未修改 Python 业务文件。
- 未改变 TaskQueueModel、watcher 任务策略、ConvertThread 或队列调度语义。
- 未改变 FileSession、EditorSession、Metadata/Lyrics/Cover 草稿和统一导出语义。
- 未改变播放器、Pitch 后端、缓存键、FFmpeg、NCM、no-clobber 或源文件保护。
- 未改变左侧导航、自动转码与音频编辑大分区、主题、图标系统或勾选 UI 图标。
- Preview / smoke 不执行真实入队、扫描、播放、转换、导出或配置保存。
- Legacy Widgets 布局未改，imports 和 Safe Start 保持通过。

## 后续桥接修复

- 实际使用发现任务右键“本轮转换到……”在 `TaskQueueView.qml` 调用 Python 时报告 JavaScript Array 无法转换为 `PyObject`，导致方法体和文件夹对话框均未执行。
- `AutoConvertViewModel` 中 11 个 QML 列表入口现明确注册为 `QVariantList`；队列方法体、输出目录策略、统一调度器、转换后端和 no-clobber 均未改。
- 新增 `tests/test_qml_auto_convert_list_bridge.py`，验证所有元对象签名、JavaScript Array 实参、右键目录入口和底部“转换到……”的单次调度。
- 旧 `add_scan_candidates(object, str, int)` 仍保留 `PyObject`，因为它只用于已停产扫描预览的 Python Signal 兼容路径，不是生产 QML 数组入口。

## 已知问题

- P0：无。
- P1：无。
- P2：真实媒体的完整鼠标级验收仍建议由用户按本阶段场景执行；本轮已完成安全模式可见结构检查和自动化交互/状态回归，但没有为了布局验收主动转换或写出用户媒体。
- P2：1280×720 下文件信息技术摘要、Pitch 三个区域和设置分组会按设计下置，需要页面滚动访问，不存在永久截断或不可访问操作。

工程条件已满足进入 Phase 5.9.5 的“方案确认”，但本阶段不会实现或预改大工作区分区。
