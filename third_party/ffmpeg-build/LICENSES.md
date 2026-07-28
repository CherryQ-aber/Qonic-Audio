# Build dependency licensing

The candidate is intended for distribution only under Qonic Audio's
GPL-3.0-or-later release terms.

| Component | Locked version | License treatment |
|---|---|---|
| FFmpeg | 8.1.1 / exact commit | GPL build (`--enable-gpl --enable-version3`) |
| zlib | 1.3.1 | zlib license |
| LAME | 3.100 | LGPL-2.0-or-later library build |
| libogg | 1.3.6 | BSD-3-Clause |
| libvorbis | 1.3.7 | BSD-3-Clause |
| Opus | 1.6.1 | BSD-3-Clause |
| Rubber Band | 4.0.0 / exact commit | GPL-2.0-or-later |

Rubber Band uses its bundled FFT and resampler implementations. Optional FFTW,
Intel IPP, SLEEF, libsamplerate and Speex integrations are disabled. The
license collector copies the exact license files from each verified source
tree into the candidate evidence directory.

`--enable-nonfree` is forbidden by both the configure lock and tests.
