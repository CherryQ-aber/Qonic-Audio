# Corresponding source delivery

For every distributed Qonic FFmpeg candidate or accepted release, publish the
generated complete-corresponding-source archive alongside the binaries. The
archive contains:

- every exact source archive used by the build;
- source and dependency lockfiles;
- build-environment and FFmpeg configure locks;
- Dockerfile, cross file and all build scripts;
- all applied patch directories, including empty directories when no patch was
  applied;
- build and licensing documentation;
- the verified license texts and license inventory copied from every exact
  source tree, including the Rubber Band and bundled KissFFT notices.

Generate it only after source verification:

```powershell
python .\third_party\ffmpeg-build\scripts\generate_source_bundle.py
```

Retain the archive and its SHA-256 sidecar for at least as long as the
corresponding binaries are offered. If a candidate is accepted, copy these
materials into the release compliance bundle; do not rely on a moving branch
or an upstream “latest” link.
