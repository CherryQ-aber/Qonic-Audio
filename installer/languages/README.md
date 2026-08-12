# Installer language resources

`ChineseSimplified.isl` is pinned from the Inno Setup `is-6_7_3` source tag:

```text
https://raw.githubusercontent.com/jrsoftware/issrc/refs/tags/is-6_7_3/Files/Languages/Unofficial/ChineseSimplified.isl
```

Upstream raw file SHA-256:

```text
7D544B9BB1D142CFA11F2E5D3CC8ABE2E55F8E066C5124E3772675AA236E1278
```

Vendored UTF-8/LF copy SHA-256 (one upstream trailing space normalized):

```text
75EC648A9C1B547B1C35113B06BC85CEDE51C1C1D7D089AF8FD974331F930570
```

The file declares compatibility with Inno Setup 6.5.0 and later. It is kept
inside the project so installer builds do not depend on language files present
on a particular development machine.

The vendored copy normalizes one trailing space and is therefore marked as a
project-pinned copy rather than an unmodified upstream byte stream. Inno Setup's
licence terms are preserved at `../../LICENSES/Inno-Setup-License.txt`.
