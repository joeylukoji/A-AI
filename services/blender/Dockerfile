FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    BLENDER_VERSION=4.2.5 \
    AI_STUB=0 \
    BLENDER_BIN=/usr/local/bin/blender \
    LANG=C.UTF-8

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl xz-utils python3 python3-pip \
    libx11-6 libxi6 libxxf86vm1 libxfixes3 libxrender1 \
    libgl1 libxkbcommon0 libsm6 libice6 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN for base in \
      "https://mirror.clarkson.edu/blender" \
      "https://mirrors.ocf.berkeley.edu/blender" \
      "https://ftp.halifax.rwth-aachen.de/blender" \
      "https://download.blender.org"; do \
      curl -fsSL --retry 2 \
        "$base/release/Blender4.2/blender-${BLENDER_VERSION}-linux-x64.tar.xz" \
        -o /tmp/blender.tar.xz && break; \
    done \
 && test -s /tmp/blender.tar.xz \
 && mkdir -p /opt/blender \
 && tar -xJf /tmp/blender.tar.xz -C /opt/blender --strip-components=1 \
 && rm /tmp/blender.tar.xz \
 && ln -sf /opt/blender/blender /usr/local/bin/blender \
 && blender --version

WORKDIR /app
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt
COPY worker.py s3util.py openings.py ./
COPY scripts ./scripts
COPY catalog ./catalog

CMD ["python3", "-u", "worker.py"]
