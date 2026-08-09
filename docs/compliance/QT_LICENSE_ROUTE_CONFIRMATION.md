# Qt / PySide6 LGPL Route Confirmation

Status: **OWNER CONFIRMATION RECORDED — HUMAN WINDOWS ACCEPTANCE PENDING**

| Field | Value |
| --- | --- |
| Selected route | GNU Lesser General Public License version 3 (LGPL-3.0) |
| Qt | 6.11.1 |
| PySide6 | 6.11.1 |
| shiboken6 | 6.11.1 |
| Reason | The Qonic Audio distribution uses the Qt for Python Community Edition and intends to comply with the LGPLv3 distribution conditions. |

## Technical evidence status

- The public PySide6, PySide6_Essentials, PySide6_Addons and shiboken6 6.11.1
  wheels used for the frozen package declare `LGPL-3.0-only OR GPL-2.0-only OR
  GPL-3.0-only` in their actual wheel metadata. This is technical package
  evidence, not a statement of an owner's licence entitlement.
- The frozen package contains four GPL-only Qt module groups. The isolated
  staging candidate removed all four groups and passed the packaged QML smoke
  matrix; see [route verification](QT_LGPL_ROUTE_VERIFICATION.md).
- The shipped PySide6 binding `.pyd` files import Qt6 shared DLLs through their
  PE import tables. A staging `Qt6Core.dll` replacement-loader smoke passed;
  there is no observed Qonic hash or signature gate for the DLL.
- Exact source availability is documented in
  [QT_SOURCE_AVAILABILITY.md](QT_SOURCE_AVAILABILITY.md).
- The applicable LGPLv3 text and Qt/PySide/Shiboken notices are staged under
  `docs/compliance/staging/licenses/`.
- The identified r2 integration candidate removed all four verified GPL-only
  groups and carries recipient-facing LGPLv3, attribution and exact
  source-availability material. Its automatic `QT_QPA_PLATFORM=windows` smoke
  and runtime-plugin checks passed; see
  [QT_WINDOWS_NATIVE_ACCEPTANCE.md](QT_WINDOWS_NATIVE_ACCEPTANCE.md).

## Owner confirmation record

On 2026-08-09 (Asia/Shanghai), the project owner provided the following
confirmation in the Qonic Audio project task:

> 我确认 Qonic Audio 后续公开发行采用 LGPL-3.0 路线，使用经验证的
> Qt/PySide6/shiboken6 6.11.1 动态链接 integration candidate，持续移除已验证的
> GPL-only Qt 模块组，并随发行提供 LGPLv3、Qt 归属及精确源码可得性材料；同时完成
> Windows 原生验收。

This record captures the owner's project-direction statement. It is not an
agent-issued legal opinion or an automatic release acceptance.

## Remaining release-close gate

The LGPL-3.0 public-release route is not yet CLOSED. The r2 integration
candidate has been created, identified and automatically checked, but the
visible native Windows interaction acceptance listed in
`QT_WINDOWS_NATIVE_ACCEPTANCE.md` remains to be recorded. The frozen
authoritative package remains unchanged and is not this future integration
candidate.
