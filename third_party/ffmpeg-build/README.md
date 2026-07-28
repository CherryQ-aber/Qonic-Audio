# Qonic-maintained FFmpeg build

This directory defines the reproducible Windows x86-64 FFmpeg build used by
Qonic Audio. It is a candidate-production system only: no script in this
directory writes to `Tools/ffmpeg/bin`.

The build is pinned at four layers:

1. immutable Debian OCI image digest;
2. dated Debian snapshot plus exact direct package versions;
3. exact source versions/commits and SHA-256 values;
4. an allowlisted FFmpeg configure command.

The only permitted candidate destination is `output/candidate/`. A project
owner must separately approve replacement of the formal onedir runtime.

See `BUILDING.md` for execution and `SOURCE_OFFER.md` for corresponding-source
delivery.
