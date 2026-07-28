FROM docker.io/library/debian@sha256:7b140f374b289a7c2befc338f42ebe6441b7ea838a042bbd5acbfca6ec875818

ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC LANG=C.UTF-8 LC_ALL=C.UTF-8 SOURCE_DATE_EPOCH=1777848300

RUN rm -f /etc/apt/sources.list.d/debian.sources \
 && printf '%s\n' \
    'deb [check-valid-until=no] http://snapshot.debian.org/archive/debian/20260713T000000Z bookworm main' \
    'deb [check-valid-until=no] http://snapshot.debian.org/archive/debian-security/20260713T000000Z bookworm-security main' \
    > /etc/apt/sources.list \
 && apt-get -o Acquire::Check-Valid-Until=false update \
 && apt-get install -y --no-install-recommends \
    autoconf=2.71-3 \
    automake=1:1.16.5-1.3 \
    binutils-mingw-w64-x86-64=2.40-2+10.4 \
    ca-certificates=20230311+deb12u1 \
    cmake=3.25.1-1 \
    file=1:5.44-3 \
    g++-mingw-w64-x86-64-win32=12.2.0-14+deb12u1+25.2+b1 \
    gcc-mingw-w64-x86-64-win32=12.2.0-14+deb12u1+25.2+b1 \
    git=1:2.39.5-0+deb12u3 \
    libtool=2.4.7-7~deb12u1 \
    make=4.3-4.1 \
    meson=1.0.1-5 \
    mingw-w64=10.0.0-3 \
    mingw-w64-tools=10.0.0-3 \
    nasm=2.16.01-1 \
    ninja-build=1.11.1-2~deb12u1 \
    patch=2.7.6-7 \
    pkg-config=1.8.1-1 \
    python3=3.11.2-1+b1 \
    xz-utils=5.4.1-1+deb12u1 \
    yasm=1.3.0-4 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /repo
ENV QONIC_BUILD_CONTAINER=1
ENTRYPOINT ["/bin/bash", "third_party/ffmpeg-build/build.sh"]
