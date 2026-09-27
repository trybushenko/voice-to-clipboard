# Build on the oldest supported glibc with matching GI/Python ABI.
FROM ubuntu:22.04 AS builder
ENV DEBIAN_FRONTEND=noninteractive PYTHONNOUSERSITE=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential python3-venv python3-dev python3-tk python3-gi gir1.2-gtk-3.0 \
    gir1.2-atspi-2.0 gir1.2-ayatanaappindicator3-0.1 libportaudio2 \
    libegl1 libgl1 libxcb-cursor0 libxkbcommon-x11-0 dpkg-dev git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv --system-site-packages /build-venv
ENV PATH=/build-venv/bin:$PATH
RUN --mount=type=cache,target=/root/.cache/pip python -m pip install --upgrade pip setuptools wheel
WORKDIR /build
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY packaging ./packaging
RUN --mount=type=cache,target=/root/.cache/pip python -m pip install -r packaging/requirements.txt '.[whisper,hotkeys,desktop]'
COPY . .
RUN bash packaging/linux/build.sh
