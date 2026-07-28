# FFmpeg self-build route evaluation

| Route | Traceability | Repeatability | Current host readiness | Decision |
|---|---|---|---|---|
| Native MSYS2 | medium; package repository state needs an additional snapshot lock | medium | unavailable | not selected |
| WSL cross-build | high when distro and packages are pinned | high | WSL is not installed | viable fallback |
| Pinned container + MinGW-w64 | high; image digest, Debian snapshot and package versions are explicit | high | Docker Desktop `linux/amd64` verified and B3 completed | selected and validated |

The selected route minimizes dependence on developer-machine state. The
container image is addressed by immutable digest, APT uses a dated Debian
snapshot, direct packages use exact versions, all source archives have SHA-256
locks, and the final manifest captures the complete installed package list and
compiler output.

Docker Desktop 4.83.0 / Engine 29.6.2 was found in the current user's local
installation and verified with a Linux/amd64 server. B3 completed on
2026-07-26. The final image digest is
`sha256:2f0011b5e4618c8da63b2ddde3a6a25138cc014d294da5937a65dfc3314679a2`;
candidate and corresponding-source identities are recorded in
`candidate-build-attempt.json`. Formal binaries remain untouched while B4 and
B5 are pending.
