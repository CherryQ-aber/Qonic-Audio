# Qt Module Minimization Review

This is an evidence-only staging review of the owner-frozen onedir package. No Qt file was removed.

| Classification | Count | Meaning |
| --- | ---: | --- |
| REQUIRED | 19 | Directly imported or mandatory platform/multimedia runtime. |
| TRANSITIVE_REQUIRED | 0 | Verified dependency of a required module. |
| POSSIBLY_REMOVABLE | 126 | No direct import evidence; isolate and test before deletion. |
| UNUSED | 0 | Proven unused by isolated packaged regression. |
| NEEDS_TESTING | 112 | Static analysis is insufficient to remove safely. |

## Actual modules

| Module | Files | Bytes | Classification | Qt source module(s) |
| --- | ---: | ---: | --- | --- |
| `PySide6` | 164 | 49554475 | POSSIBLY_REMOVABLE | not mapped |
| `PySide6.QtCore` | 1 | 3330360 | POSSIBLY_REMOVABLE | pyside-setup/qtbase-bindings |
| `PySide6.QtGui` | 1 | 3896632 | POSSIBLY_REMOVABLE | pyside-setup/qtbase-bindings |
| `PySide6.QtMultimedia` | 1 | 571704 | POSSIBLY_REMOVABLE | pyside-setup/qtmultimedia-bindings |
| `PySide6.QtMultimediaWidgets` | 1 | 141624 | POSSIBLY_REMOVABLE | pyside-setup/qtmultimedia-bindings |
| `PySide6.QtNetwork` | 1 | 1007416 | POSSIBLY_REMOVABLE | pyside-setup/qtbase-bindings |
| `PySide6.QtOpenGL` | 1 | 8713016 | POSSIBLY_REMOVABLE | not mapped |
| `PySide6.QtQml` | 1 | 474936 | POSSIBLY_REMOVABLE | pyside-setup/qtdeclarative-bindings |
| `PySide6.QtQuick` | 1 | 774456 | POSSIBLY_REMOVABLE | pyside-setup/qtdeclarative-bindings |
| `PySide6.QtQuickControls2` | 1 | 92472 | POSSIBLY_REMOVABLE | pyside-setup/qtdeclarative-bindings |
| `PySide6.QtWidgets` | 1 | 4856120 | POSSIBLY_REMOVABLE | pyside-setup/qtbase-bindings |
| `Qt63DAnimation` | 1 | 522552 | POSSIBLY_REMOVABLE | qt3d |
| `Qt63DCore` | 1 | 549176 | POSSIBLY_REMOVABLE | qt3d |
| `Qt63DExtras` | 1 | 764728 | POSSIBLY_REMOVABLE | qt3d |
| `Qt63DInput` | 1 | 408888 | POSSIBLY_REMOVABLE | qt3d |
| `Qt63DLogic` | 1 | 73016 | POSSIBLY_REMOVABLE | qt3d |
| `Qt63DQuick` | 1 | 325432 | POSSIBLY_REMOVABLE | qt3d |
| `Qt63DQuickAnimation` | 1 | 145208 | POSSIBLY_REMOVABLE | qt3d |
| `Qt63DQuickExtras` | 1 | 248632 | POSSIBLY_REMOVABLE | qt3d |
| `Qt63DQuickInput` | 1 | 66872 | POSSIBLY_REMOVABLE | qt3d |
| `Qt63DQuickLogic` | 1 | 31032 | POSSIBLY_REMOVABLE | qt3d |
| `Qt63DQuickRender` | 1 | 553272 | POSSIBLY_REMOVABLE | qt3d |
| `Qt63DQuickScene2D` | 1 | 115000 | POSSIBLY_REMOVABLE | qt3d |
| `Qt63DQuickScene3D` | 1 | 102712 | POSSIBLY_REMOVABLE | qt3d |
| `Qt63DRender` | 1 | 2599736 | POSSIBLY_REMOVABLE | qt3d |
| `Qt6Charts` | 1 | 1758520 | POSSIBLY_REMOVABLE | qtcharts |
| `Qt6ChartsQml` | 1 | 579896 | POSSIBLY_REMOVABLE | qtcharts |
| `Qt6Concurrent` | 1 | 35128 | POSSIBLY_REMOVABLE | qtbase |
| `Qt6Core` | 1 | 10480440 | REQUIRED | qtbase |
| `Qt6DataVisualization` | 1 | 1217848 | POSSIBLY_REMOVABLE | qtdatavis3d |
| `Qt6DataVisualizationQml` | 1 | 442680 | POSSIBLY_REMOVABLE | qtdatavis3d |
| `Qt6Graphs` | 1 | 2559800 | POSSIBLY_REMOVABLE | qtgraphs |
| `Qt6Gui` | 1 | 9589560 | REQUIRED | qtbase |
| `Qt6LabsAnimation` | 1 | 55096 | POSSIBLY_REMOVABLE | qtdeclarative |
| `Qt6LabsFolderListModel` | 1 | 122168 | POSSIBLY_REMOVABLE | qtdeclarative |
| `Qt6LabsPlatform` | 1 | 284472 | POSSIBLY_REMOVABLE | qtdeclarative |
| `Qt6LabsQmlModels` | 1 | 197432 | POSSIBLY_REMOVABLE | qtdeclarative |
| `Qt6LabsSettings` | 1 | 61752 | POSSIBLY_REMOVABLE | qtdeclarative |
| `Qt6LabsSharedImage` | 1 | 56632 | POSSIBLY_REMOVABLE | qtdeclarative |
| `Qt6LabsStyleKit` | 1 | 1464632 | POSSIBLY_REMOVABLE | qtdeclarative |
| `Qt6LabsStyleKitImpl` | 1 | 280376 | POSSIBLY_REMOVABLE | qtdeclarative |
| `Qt6LabsSynchronizer` | 1 | 68408 | POSSIBLY_REMOVABLE | qtdeclarative |
| `Qt6LabsWavefrontMesh` | 1 | 60728 | POSSIBLY_REMOVABLE | qtdeclarative |
| `Qt6Location` | 1 | 1690424 | POSSIBLY_REMOVABLE | qtlocation |
| `Qt6Multimedia` | 1 | 1283896 | REQUIRED | qtmultimedia |
| `Qt6MultimediaQuick` | 1 | 293688 | NEEDS_TESTING | qtmultimedia |
| `Qt6MultimediaWidgets` | 1 | 62264 | NEEDS_TESTING | qtmultimedia |
| `Qt6Network` | 1 | 1771320 | REQUIRED | qtbase |
| `Qt6OpenGL` | 1 | 1977656 | NEEDS_TESTING | qtbase |
| `Qt6OpenGLWidgets` | 1 | 64824 | NEEDS_TESTING | qtbase |
| `Qt6Pdf` | 1 | 4611384 | POSSIBLY_REMOVABLE | qtwebengine |
| `Qt6PdfQuick` | 1 | 575800 | POSSIBLY_REMOVABLE | qtwebengine |
| `Qt6Positioning` | 1 | 523064 | POSSIBLY_REMOVABLE | qtpositioning |
| `Qt6PositioningQuick` | 1 | 345912 | POSSIBLY_REMOVABLE | qtpositioning |
| `Qt6Qml` | 1 | 5380920 | REQUIRED | qtdeclarative |
| `Qt6QmlCore` | 1 | 134456 | NEEDS_TESTING | qtdeclarative |
| `Qt6QmlLocalStorage` | 1 | 62264 | NEEDS_TESTING | qtdeclarative |
| `Qt6QmlMeta` | 1 | 160056 | NEEDS_TESTING | qtdeclarative |
| `Qt6QmlModels` | 1 | 997176 | NEEDS_TESTING | qtdeclarative |
| `Qt6QmlNetwork` | 1 | 128312 | NEEDS_TESTING | qtdeclarative |
| `Qt6QmlWorkerScript` | 1 | 80696 | NEEDS_TESTING | qtdeclarative |
| `Qt6QmlXmlListModel` | 1 | 133432 | NEEDS_TESTING | qtdeclarative |
| `Qt6Quick` | 1 | 6593336 | REQUIRED | qtdeclarative |
| `Qt6Quick3D` | 1 | 1470776 | NEEDS_TESTING | qtquick3d |
| `Qt6Quick3DAssetImport` | 1 | 70456 | NEEDS_TESTING | qtquick3d |
| `Qt6Quick3DAssetUtils` | 1 | 317240 | NEEDS_TESTING | qtquick3d |
| `Qt6Quick3DEffects` | 1 | 419128 | NEEDS_TESTING | qtquick3d |
| `Qt6Quick3DHelpers` | 1 | 717112 | NEEDS_TESTING | qtquick3d |
| `Qt6Quick3DHelpersImpl` | 1 | 536888 | NEEDS_TESTING | qtquick3d |
| `Qt6Quick3DParticleEffects` | 1 | 24376 | NEEDS_TESTING | qtquick3d |
| `Qt6Quick3DParticles` | 1 | 2082104 | NEEDS_TESTING | qtquick3d |
| `Qt6Quick3DRuntimeRender` | 1 | 4415288 | NEEDS_TESTING | qtquick3d |
| `Qt6Quick3DSpatialAudio` | 1 | 85816 | NEEDS_TESTING | qtquick3d |
| `Qt6Quick3DUtils` | 1 | 482104 | NEEDS_TESTING | qtquick3d |
| `Qt6Quick3DXr` | 1 | 914232 | NEEDS_TESTING | qtquick3d |
| `Qt6QuickControls2` | 1 | 103224 | REQUIRED | qtdeclarative |
| `Qt6QuickControls2Basic` | 1 | 1848632 | NEEDS_TESTING | qtdeclarative |
| `Qt6QuickControls2BasicStyleImpl` | 1 | 90936 | NEEDS_TESTING | qtdeclarative |
| `Qt6QuickControls2FluentWinUI3StyleImpl` | 1 | 221496 | NEEDS_TESTING | qtdeclarative |
| `Qt6QuickControls2Fusion` | 1 | 1511736 | NEEDS_TESTING | qtdeclarative |
| `Qt6QuickControls2FusionStyleImpl` | 1 | 185656 | NEEDS_TESTING | qtdeclarative |
| `Qt6QuickControls2Imagine` | 1 | 3088184 | NEEDS_TESTING | qtdeclarative |
| `Qt6QuickControls2ImagineStyleImpl` | 1 | 70456 | NEEDS_TESTING | qtdeclarative |
| `Qt6QuickControls2Impl` | 1 | 331064 | NEEDS_TESTING | qtdeclarative |
| `Qt6QuickControls2Material` | 1 | 1922360 | NEEDS_TESTING | qtdeclarative |
| `Qt6QuickControls2MaterialStyleImpl` | 1 | 312120 | NEEDS_TESTING | qtdeclarative |
| `Qt6QuickControls2Universal` | 1 | 1592632 | NEEDS_TESTING | qtdeclarative |
| `Qt6QuickControls2UniversalStyleImpl` | 1 | 142136 | NEEDS_TESTING | qtdeclarative |
| `Qt6QuickControls2WindowsStyleImpl` | 1 | 66872 | NEEDS_TESTING | qtdeclarative |
| `Qt6QuickDialogs2` | 1 | 159544 | NEEDS_TESTING | qtdeclarative |
| `Qt6QuickDialogs2QuickImpl` | 1 | 2857272 | NEEDS_TESTING | qtdeclarative |
| `Qt6QuickDialogs2Utils` | 1 | 47416 | NEEDS_TESTING | qtdeclarative |
| `Qt6QuickEffects` | 1 | 433976 | NEEDS_TESTING | qtdeclarative |
| `Qt6QuickLayouts` | 1 | 308536 | NEEDS_TESTING | qtdeclarative |
| `Qt6QuickParticles` | 1 | 641336 | NEEDS_TESTING | qtdeclarative |
| `Qt6QuickShapes` | 1 | 348472 | NEEDS_TESTING | qtdeclarative |
| `Qt6QuickTemplates2` | 1 | 2061112 | NEEDS_TESTING | qtdeclarative |
| `Qt6QuickTest` | 1 | 314168 | NEEDS_TESTING | qtdeclarative |
| `Qt6QuickTimeline` | 1 | 98104 | NEEDS_TESTING | qtquicktimeline |
| `Qt6QuickTimelineBlendTrees` | 1 | 82744 | NEEDS_TESTING | qtquicktimeline |
| `Qt6QuickVectorImage` | 1 | 70968 | NEEDS_TESTING | qtdeclarative |
| `Qt6QuickVectorImageGenerator` | 1 | 287032 | NEEDS_TESTING | qtdeclarative |
| `Qt6QuickVectorImageHelpers` | 1 | 191800 | NEEDS_TESTING | qtdeclarative |
| `Qt6RemoteObjects` | 1 | 872760 | POSSIBLY_REMOVABLE | qtremoteobjects |
| `Qt6RemoteObjectsQml` | 1 | 67896 | POSSIBLY_REMOVABLE | qtremoteobjects |
| `Qt6Scxml` | 1 | 539448 | POSSIBLY_REMOVABLE | qtscxml |
| `Qt6ScxmlQml` | 1 | 121656 | POSSIBLY_REMOVABLE | qtscxml |
| `Qt6Sensors` | 1 | 225080 | POSSIBLY_REMOVABLE | qtsensors |
| `Qt6SensorsQuick` | 1 | 277304 | POSSIBLY_REMOVABLE | qtsensors |
| `Qt6ShaderTools` | 1 | 4336952 | POSSIBLY_REMOVABLE | qtshadertools |
| `Qt6SpatialAudio` | 1 | 740152 | POSSIBLY_REMOVABLE | qtmultimedia |
| `Qt6Sql` | 1 | 311608 | POSSIBLY_REMOVABLE | qtbase |
| `Qt6StateMachine` | 1 | 341816 | POSSIBLY_REMOVABLE | qtscxml |
| `Qt6StateMachineQml` | 1 | 117048 | POSSIBLY_REMOVABLE | qtscxml |
| `Qt6Svg` | 1 | 642360 | POSSIBLY_REMOVABLE | qtsvg |
| `Qt6Test` | 1 | 382776 | POSSIBLY_REMOVABLE | qtbase |
| `Qt6TextToSpeech` | 1 | 133432 | POSSIBLY_REMOVABLE | qtspeech |
| `Qt6VirtualKeyboard` | 1 | 443192 | POSSIBLY_REMOVABLE | qtvirtualkeyboard |
| `Qt6VirtualKeyboardQml` | 1 | 101176 | POSSIBLY_REMOVABLE | qtvirtualkeyboard |
| `Qt6VirtualKeyboardSettings` | 1 | 72504 | POSSIBLY_REMOVABLE | qtvirtualkeyboard |
| `Qt6WebChannel` | 1 | 255800 | POSSIBLY_REMOVABLE | qtwebchannel |
| `Qt6WebChannelQuick` | 1 | 63288 | POSSIBLY_REMOVABLE | qtwebchannel |
| `Qt6WebEngineCore` | 1 | 204828984 | POSSIBLY_REMOVABLE | qtwebengine |
| `Qt6WebEngineQuick` | 1 | 693560 | POSSIBLY_REMOVABLE | qtwebengine |
| `Qt6WebEngineQuickDelegatesQml` | 1 | 165688 | POSSIBLY_REMOVABLE | qtwebengine |
| `Qt6WebSockets` | 1 | 219960 | POSSIBLY_REMOVABLE | qtwebsockets |
| `Qt6WebView` | 1 | 60216 | POSSIBLY_REMOVABLE | qtwebview |
| `Qt6WebViewQuick` | 1 | 84280 | POSSIBLY_REMOVABLE | qtwebview |
| `Qt6Widgets` | 1 | 6594360 | REQUIRED | qtbase |
| `plugin:Hangul` | 3 | 63328 | POSSIBLY_REMOVABLE | not mapped |
| `plugin:OpenWNN` | 3 | 1577328 | POSSIBLY_REMOVABLE | not mapped |
| `plugin:Pinyin` | 3 | 1194336 | POSSIBLY_REMOVABLE | not mapped |
| `plugin:TCIme` | 3 | 313968 | POSSIBLY_REMOVABLE | not mapped |
| `plugin:Thai` | 3 | 45382 | POSSIBLY_REMOVABLE | not mapped |
| `plugin:generic` | 1 | 101176 | POSSIBLY_REMOVABLE | not mapped |
| `plugin:iconengines` | 1 | 72504 | POSSIBLY_REMOVABLE | not mapped |
| `plugin:imageformats` | 10 | 1887792 | NEEDS_TESTING | not mapped |
| `plugin:multimedia` | 2 | 942704 | REQUIRED | not mapped |
| `plugin:networkinformation` | 1 | 70968 | NEEDS_TESTING | not mapped |
| `plugin:platforminputcontexts` | 1 | 33592 | NEEDS_TESTING | not mapped |
| `plugin:platforms` | 4 | 2271456 | REQUIRED | not mapped |
| `plugin:qmldir` | 1 | 525 | POSSIBLY_REMOVABLE | not mapped |
| `plugin:qmltooling` | 13 | 1106904 | POSSIBLY_REMOVABLE | not mapped |
| `plugin:qtvkbpluginsplugin.dll` | 1 | 32056 | POSSIBLY_REMOVABLE | not mapped |
| `plugin:qtvkbpluginsplugin.qmltypes` | 1 | 215 | POSSIBLY_REMOVABLE | not mapped |
| `plugin:styles` | 1 | 230712 | NEEDS_TESTING | not mapped |
| `plugin:tls` | 3 | 687016 | NEEDS_TESTING | not mapped |
| `qml:Qt.labs.StyleKit` | 42 | 241700 | POSSIBLY_REMOVABLE | not mapped |
| `qml:Qt.labs.animation` | 3 | 35393 | POSSIBLY_REMOVABLE | not mapped |
| `qml:Qt.labs.assetdownloader` | 10 | 2935708 | POSSIBLY_REMOVABLE | not mapped |
| `qml:Qt.labs.folderlistmodel` | 3 | 39247 | POSSIBLY_REMOVABLE | not mapped |
| `qml:Qt.labs.platform` | 3 | 76012 | POSSIBLY_REMOVABLE | not mapped |
| `qml:Qt.labs.qmlmodels` | 3 | 46006 | POSSIBLY_REMOVABLE | not mapped |
| `qml:Qt.labs.settings` | 3 | 32571 | POSSIBLY_REMOVABLE | not mapped |
| `qml:Qt.labs.sharedimage` | 3 | 34234 | POSSIBLY_REMOVABLE | not mapped |
| `qml:Qt.labs.synchronizer` | 3 | 33223 | POSSIBLY_REMOVABLE | not mapped |
| `qml:Qt.labs.wavefrontmesh` | 3 | 33437 | POSSIBLY_REMOVABLE | not mapped |
| `qml:Qt3D.Animation` | 3 | 74805 | POSSIBLY_REMOVABLE | not mapped |
| `qml:Qt3D.Core` | 3 | 112286 | POSSIBLY_REMOVABLE | not mapped |
| `qml:Qt3D.Extras` | 3 | 171957 | POSSIBLY_REMOVABLE | not mapped |
| `qml:Qt3D.Input` | 3 | 153433 | POSSIBLY_REMOVABLE | not mapped |
| `qml:Qt3D.Logic` | 3 | 34345 | POSSIBLY_REMOVABLE | not mapped |
| `qml:Qt3D.Render` | 3 | 254378 | POSSIBLY_REMOVABLE | not mapped |
| `qml:Qt5Compat.GraphicalEffects` | 28 | 1029317 | POSSIBLY_REMOVABLE | not mapped |
| `qml:Qt5Compat.GraphicalEffects.private` | 10 | 493673 | POSSIBLY_REMOVABLE | not mapped |
| `qml:QtCharts` | 3 | 237824 | POSSIBLY_REMOVABLE | not mapped |
| `qml:QtCharts.designer` | 2 | 10532 | POSSIBLY_REMOVABLE | not mapped |
| `qml:QtCharts.designer.default` | 16 | 8107 | POSSIBLY_REMOVABLE | not mapped |
| `qml:QtCharts.designer.images` | 32 | 40888 | POSSIBLY_REMOVABLE | not mapped |
| `qml:QtCore` | 3 | 48406 | REQUIRED | not mapped |
| `qml:QtDataVisualization` | 3 | 204405 | POSSIBLY_REMOVABLE | not mapped |
| `qml:QtDataVisualization.designer` | 4 | 35468 | POSSIBLY_REMOVABLE | not mapped |
| `qml:QtDataVisualization.designer.default` | 3 | 1954 | POSSIBLY_REMOVABLE | not mapped |
| `qml:QtDataVisualization.designer.images` | 6 | 7645 | POSSIBLY_REMOVABLE | not mapped |
| `qml:QtGraphs` | 3 | 349615 | POSSIBLY_REMOVABLE | not mapped |
| `qml:QtGraphs.designer` | 8 | 36002 | POSSIBLY_REMOVABLE | not mapped |
| `qml:QtGraphs.designer.default` | 9 | 4349 | POSSIBLY_REMOVABLE | not mapped |
| `qml:QtGraphs.designer.images` | 18 | 23081 | POSSIBLY_REMOVABLE | not mapped |
| `qml:QtLocation` | 4 | 151429 | POSSIBLY_REMOVABLE | not mapped |
| `qml:QtMultimedia` | 4 | 127067 | REQUIRED | not mapped |
| `qml:QtNetwork` | 3 | 50758 | POSSIBLY_REMOVABLE | not mapped |
| `qml:QtPositioning` | 3 | 111784 | POSSIBLY_REMOVABLE | not mapped |
| `qml:QtQml` | 3 | 38553 | REQUIRED | not mapped |
| `qml:QtQml.Models` | 3 | 111290 | REQUIRED | not mapped |
| `qml:QtQml.StateMachine` | 3 | 45245 | NEEDS_TESTING | not mapped |
| `qml:QtQml.WorkerScript` | 3 | 32282 | REQUIRED | not mapped |
| `qml:QtQml.XmlListModel` | 3 | 35560 | NEEDS_TESTING | not mapped |
| `qml:QtQuick` | 3 | 693763 | REQUIRED | not mapped |
| `qml:QtQuick.Controls` | 3 | 42066 | REQUIRED | not mapped |
| `qml:QtQuick.Controls.Basic` | 76 | 196193 | NEEDS_TESTING | not mapped |
| `qml:QtQuick.Controls.FluentWinUI3` | 854 | 5390967 | NEEDS_TESTING | not mapped |
| `qml:QtQuick.Controls.Fusion` | 76 | 200003 | NEEDS_TESTING | not mapped |
| `qml:QtQuick.Controls.Imagine` | 62 | 213037 | NEEDS_TESTING | not mapped |
| `qml:QtQuick.Controls.Material` | 73 | 262874 | NEEDS_TESTING | not mapped |
| `qml:QtQuick.Controls.Universal` | 72 | 196624 | NEEDS_TESTING | not mapped |
| `qml:QtQuick.Controls.Windows` | 58 | 803298 | NEEDS_TESTING | not mapped |
| `qml:QtQuick.Controls.designer` | 136 | 105305 | NEEDS_TESTING | not mapped |
| `qml:QtQuick.Controls.impl` | 10 | 86205 | NEEDS_TESTING | not mapped |
| `qml:QtQuick.Dialogs` | 3 | 48378 | NEEDS_TESTING | not mapped |
| `qml:QtQuick.Dialogs.quickimpl` | 60 | 333515 | NEEDS_TESTING | not mapped |
| `qml:QtQuick.Effects` | 3 | 45275 | NEEDS_TESTING | not mapped |
| `qml:QtQuick.Layouts` | 3 | 59024 | REQUIRED | not mapped |
| `qml:QtQuick.LocalStorage` | 3 | 31472 | NEEDS_TESTING | not mapped |
| `qml:QtQuick.NativeStyle` | 3 | 988954 | NEEDS_TESTING | not mapped |
| `qml:QtQuick.NativeStyle.controls` | 20 | 42422 | NEEDS_TESTING | not mapped |
| `qml:QtQuick.NativeStyle.util` | 2 | 1696 | NEEDS_TESTING | not mapped |
| `qml:QtQuick.Particles` | 3 | 117911 | NEEDS_TESTING | not mapped |
| `qml:QtQuick.Pdf` | 8 | 126360 | NEEDS_TESTING | not mapped |
| `qml:QtQuick.Pdf.+Material` | 1 | 695 | NEEDS_TESTING | not mapped |
| `qml:QtQuick.Pdf.+Universal` | 1 | 688 | NEEDS_TESTING | not mapped |
| `qml:QtQuick.Scene2D` | 3 | 34379 | NEEDS_TESTING | not mapped |
| `qml:QtQuick.Scene3D` | 3 | 35362 | NEEDS_TESTING | not mapped |
| `qml:QtQuick.Shapes` | 3 | 52022 | NEEDS_TESTING | not mapped |
| `qml:QtQuick.Templates` | 3 | 335140 | NEEDS_TESTING | not mapped |
| `qml:QtQuick.Timeline` | 3 | 36858 | NEEDS_TESTING | not mapped |
| `qml:QtQuick.Timeline.BlendTrees` | 3 | 34642 | NEEDS_TESTING | not mapped |
| `qml:QtQuick.VectorImage` | 3 | 35167 | NEEDS_TESTING | not mapped |
| `qml:QtQuick.VectorImage.Helpers` | 3 | 34598 | NEEDS_TESTING | not mapped |
| `qml:QtQuick.VirtualKeyboard` | 6 | 42174 | NEEDS_TESTING | not mapped |
| `qml:QtQuick.VirtualKeyboard.Components` | 34 | 865612 | NEEDS_TESTING | not mapped |
| `qml:QtQuick.VirtualKeyboard.Core` | 3 | 92995 | NEEDS_TESTING | not mapped |
| `qml:QtQuick.VirtualKeyboard.Layouts` | 3 | 84753 | NEEDS_TESTING | not mapped |
| `qml:QtQuick.VirtualKeyboard.Settings` | 3 | 41147 | NEEDS_TESTING | not mapped |
| `qml:QtQuick.VirtualKeyboard.Styles` | 13 | 525234 | NEEDS_TESTING | not mapped |
| `qml:QtQuick.Window` | 3 | 31972 | REQUIRED | not mapped |
| `qml:QtQuick.tooling` | 11 | 74607 | NEEDS_TESTING | not mapped |
| `qml:QtQuick3D` | 4 | 348253 | NEEDS_TESTING | not mapped |
| `qml:QtQuick3D.AssetUtils` | 3 | 33714 | NEEDS_TESTING | not mapped |
| `qml:QtQuick3D.AssetUtils.designer` | 10 | 18484 | NEEDS_TESTING | not mapped |
| `qml:QtQuick3D.Effects` | 24 | 55080 | NEEDS_TESTING | not mapped |
| `qml:QtQuick3D.Effects.designer` | 46 | 65042 | NEEDS_TESTING | not mapped |
| `qml:QtQuick3D.Helpers` | 9 | 141878 | NEEDS_TESTING | not mapped |
| `qml:QtQuick3D.Helpers.designer` | 71 | 182760 | NEEDS_TESTING | not mapped |
| `qml:QtQuick3D.Helpers.impl` | 7 | 66444 | NEEDS_TESTING | not mapped |
| `qml:QtQuick3D.Helpers.meshes` | 1 | 128684 | NEEDS_TESTING | not mapped |
| `qml:QtQuick3D.MaterialEditor` | 13 | 98696 | NEEDS_TESTING | not mapped |
| `qml:QtQuick3D.ParticleEffects` | 3 | 31107 | NEEDS_TESTING | not mapped |
| `qml:QtQuick3D.ParticleEffects.designer` | 26 | 271067 | NEEDS_TESTING | not mapped |
| `qml:QtQuick3D.Particles3D` | 3 | 109450 | NEEDS_TESTING | not mapped |
| `qml:QtQuick3D.Particles3D.designer` | 121 | 215506 | NEEDS_TESTING | not mapped |
| `qml:QtQuick3D.SpatialAudio` | 3 | 43596 | NEEDS_TESTING | not mapped |
| `qml:QtQuick3D.Xr` | 4 | 73137 | NEEDS_TESTING | not mapped |
| `qml:QtQuick3D.designer` | 81 | 333032 | NEEDS_TESTING | not mapped |
| `qml:QtQuick3D.designer.images` | 103 | 69360 | NEEDS_TESTING | not mapped |
| `qml:QtQuick3D.designer.source` | 4 | 1359 | NEEDS_TESTING | not mapped |
| `qml:QtQuick3D.lightmapviewer` | 8 | 48772 | NEEDS_TESTING | not mapped |
| `qml:QtRemoteObjects` | 3 | 36755 | POSSIBLY_REMOVABLE | not mapped |
| `qml:QtScxml` | 3 | 45085 | POSSIBLY_REMOVABLE | not mapped |
| `qml:QtSensors` | 3 | 68251 | POSSIBLY_REMOVABLE | not mapped |
| `qml:QtTest` | 7 | 145154 | POSSIBLY_REMOVABLE | not mapped |
| `qml:QtTextToSpeech` | 3 | 106890 | POSSIBLY_REMOVABLE | not mapped |
| `qml:QtWebChannel` | 3 | 34799 | POSSIBLY_REMOVABLE | not mapped |
| `qml:QtWebEngine` | 3 | 174607 | POSSIBLY_REMOVABLE | not mapped |
| `qml:QtWebEngine.ControlsDelegates` | 17 | 47545 | POSSIBLY_REMOVABLE | not mapped |
| `qml:QtWebSockets` | 3 | 87381 | POSSIBLY_REMOVABLE | not mapped |
| `qml:QtWebView` | 3 | 40364 | POSSIBLY_REMOVABLE | not mapped |
| `shiboken6` | 5 | 1124376 | POSSIBLY_REMOVABLE | not mapped |

## Staging recommendation

Create a separate removal candidate from this list only. It must compare installer size and pass complete packaged regression before any module can be reclassified as `UNUSED`.
