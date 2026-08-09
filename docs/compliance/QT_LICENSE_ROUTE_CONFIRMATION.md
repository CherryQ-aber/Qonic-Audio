# Qt / PySide6 LGPL Route Confirmation

Status: **PENDING OWNER CONFIRMATION**

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

## Owner confirmation required

This document deliberately does not contain a signature or an automatic legal
acceptance.  It can become CLOSED only after the project owner confirms that
the future public package will use the tested LGPL candidate, retain the
required notices and source-availability material, and complete the specified
native Windows acceptance checks.
