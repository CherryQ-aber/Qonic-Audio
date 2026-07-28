# Proposed Qonic-maintained FFmpeg scope

## Decision

Build FFmpeg 8.1.1 from commit
`239f2c733de417201d7ad3b3b8b0d9b63285b2b1` as static Windows x86-64
`ffmpeg.exe` and `ffprobe.exe` executables. Use a pinned Debian container and a
pinned MinGW-w64 win32-thread cross compiler. Keep the candidate isolated under
`third_party/ffmpeg-build/output/candidate/`.

## Required external libraries

- zlib 1.3.1 for PNG/deflate support.
- LAME 3.100 for MP3 output.
- libogg 1.3.6 and libvorbis 1.3.7 for Ogg/Vorbis output.
- Opus 1.6.1 for Opus output.
- Rubber Band 4.0.0 with its bundled FFT and resampler implementations for the
  QML duration-preserving pitch path.

Rubber Band 4.0.0 is source/API compatible but is not assumed to be output
identical to the former 1.8.1 library. B4 must therefore compare pitch,
duration, channel count, output readability and representative quality before
any replacement proposal.

## Explicit exclusions

The configure lock disables network access, autodetection and all unlisted
components. It does not enable OpenSSL, GnuTLS, libx264, libx265, libvpx,
hardware acceleration, subtitle renderers, optical-media libraries or any
`--enable-nonfree` component.

## Release boundary

The scripts never write to `Tools/ffmpeg/bin`. A future owner-approved
replacement must copy the two accepted candidate files in a separate,
reviewable operation and then rebuild the authoritative onedir package.
