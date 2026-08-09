# Final Third-Party Compliance Review

Scope: the sole owner-authoritative Qonic Audio v5.0 Internal Test onedir archive and its corresponding expanded directory.

- Archive SHA-256: `BB0967E85AF2857C23587F3CEF37C37D14ED4E4106B7261F21E2F247B47F42F4`
- Native third-party files without an inventory owner: `0`

## A. CLOSED

- **CPython Runtime 3.12.1** — Evidence chain recorded in inventory.
- **OpenSSL 3.0.11** — Evidence chain recorded in inventory.
- **NumPy 2.4.6** — Evidence chain recorded in inventory.
- **Pillow 12.2.0** — No separately shipped Pillow codec DLL was found; the exact wheel licence material is staged.
- **charset-normalizer 3.4.7** — Evidence chain recorded in inventory.
- **Mutagen 1.47.0** — Evidence chain recorded in inventory.
- **watchdog 6.0.0** — Evidence chain recorded in inventory.
- **Qt Multimedia FFmpeg 7.1.3** — Evidence chain recorded in inventory.
- **FFmpeg Audio Runtime 8.1.1** — Binary hashes, configuration and corresponding-source bundle match the closed B5 evidence.
- **ncmdump 1.5.1** — Evidence chain recorded in inventory.
- **Microsoft VC Runtime 14.x (11 reviewed files)** — Evidence chain recorded in inventory.

## B. WARNING

- **libffi ABI 8 (source version not embedded)** — The ABI is identified as 8, but the exact libffi source-release version is not embedded in the frozen DLL.
- **PyInstaller bootloader not embedded in frozen artifact** — The frozen executable's CArchive identifies the PyInstaller bootloader. The current build executable differs, so its version is not used as frozen-artifact proof; the exact build-time PyInstaller version is not embedded.

## C. BLOCKER

None.

## D. OWNER ACTION

- **PySide6 6.11.1** — LGPL route technical staging has passed; owner confirmation remains pending.
- **shiboken6 6.11.1** — LGPL route technical staging has passed; owner confirmation remains pending.
- **Qt Runtime 6.11.1** — The GPL-only groups pass isolated staging removal. Owner confirmation and native Windows acceptance remain pending.

- Required owner action `QT_LICENSE_ROUTE`: The selected public-distribution route is LGPL-3.0. The owner must confirm the pending LGPL route record after the integration candidate retains the staged notices, source-availability information and native Windows acceptance evidence. This does not reopen the CLOSED Microsoft VC Runtime item.

## E. NOT APPLICABLE

None.

## Release boundary

The frozen `.7z` was not rebuilt or changed. Licence staging is an accompanying publication-material set; a future public distribution assembly must include the required staged notices/licence texts without changing the frozen application payload.
