# Third-Party Components

This directory accompanies Qonic Audio distributions. Qonic Audio's own source
is licensed under `GPL-3.0-or-later`; the complete text is at the package root
in `LICENSE`.

## Runtime components

- **Qt / PySide6 / Shiboken6 6.11.1** — distributed through shared libraries
  on the LGPL-3.0 route. The package includes LGPLv3, Qt attribution and exact
  source-availability records under `Qt/`, `PySide6/` and `Shiboken6/`.
- **FFmpeg Audio Runtime 8.1.1** — GPL-3.0-or-later. See
  `FFmpeg-NOTICE.md`; the complete corresponding source must accompany the
  package under `Corresponding_Source/`.
- **ncmdump 1.5.1** — MIT. See `ncmdump-MIT.txt` and `ncmdump-NOTICE.md`.
- **watchdog** — Apache-2.0; see `watchdog-Apache-2.0.txt`.
- **mutagen** — GPL-2.0-or-later; see `mutagen-GPL-2.0.txt`.
- **PyInstaller bootloader** — GPL-2.0-or-later with its bootloader exception;
  see `PyInstaller-GPL-2.0-with-Bootloader-Exception.txt`.
- **Microsoft VC Runtime** — only reviewed permitted redistributables are
  included. The project-owner confirmation and audit evidence are maintained
  in the release compliance records; no debug runtime or build tool is shipped.

## Installer build component

- **Inno Setup 6.7.3** — used to create the Windows installer wrapper. See
  `Inno-Setup-License.txt`. The vendored Simplified Chinese message source and
  its pinned upstream provenance are recorded under `installer/languages/`.

## Publication-candidate material

The release-assembly process copies the complete component notice index and
all collected licence bodies into this directory, adds the corresponding source
archive, and generates a recipient-facing source-availability document. A
candidate must not be published when those generated materials, its SHA-256
manifest, or its archive integrity test are absent.
