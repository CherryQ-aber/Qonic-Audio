# Qonic Audio FFmpeg format support matrix

This matrix is derived from the runtime command sites, not from the much broader
capability set of the current Gyan build.

| Format | Read | Write | Required implementation | Metadata / cover expectation |
|---|---:|---:|---|---|
| MP3 | yes | yes | FFmpeg MP3 decoder + libmp3lame | ID3 metadata; attached cover copied when present |
| FLAC | yes | yes | native FLAC decoder/encoder | Vorbis comments and picture blocks preserved by export flow |
| WAV | yes | yes | PCM codecs + WAV mux/demux | basic metadata only; no cover promise |
| AAC | yes | yes | native AAC decoder/encoder + ADTS | audio metadata is best effort |
| M4A | yes | yes | MOV/MP4 demux + ipod mux + AAC/ALAC | atoms, chapters and attached cover copied where supported |
| OGG | yes | yes | libogg + libvorbis | Vorbis comments |
| Opus | yes | yes | Ogg/Opus demux + libopus | Opus comments |
| APE | yes | no | native Monkey's Audio decoder | input compatibility only |
| AIFF/AIF | yes | no | AIFF demux + PCM/ALAC decode | input compatibility only |
| ALAC | yes | no | MOV/MP4 demux + ALAC decoder | input compatibility only |
| WMA | yes | no | ASF demux + WMA family decoders | input compatibility only |

Cross-cutting requirements: `rubberband`, `asetrate`, `aresample`, `atempo`,
raw `s16le`, `lavfi/sine` for deterministic tests, file/pipe protocols,
metadata/chapter mapping, and optional stream copy for cover data.

Network access, video encoding, hardware acceleration, subtitle rendering,
optical-media input and nonfree codecs are outside the Qonic release scope.
