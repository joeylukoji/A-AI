# LibreCAD (GPLv2) — sidecar du compose par défaut.
# Le DXF Go (AC1015) s’ouvre aussi dans QCAD Community.
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    QT_QPA_PLATFORM=offscreen \
    QCAD_BIN=/usr/bin/librecad \
    QCAD_SCRIPT=/app/normalize_dxf.js \
    QCAD_PORT=9090

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        librecad \
        xvfb \
        python3 \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && test -x /usr/bin/librecad

WORKDIR /app
COPY services/qcad/server.py /app/server.py
COPY internal/export/qcad_normalize.js /app/normalize_dxf.js

RUN useradd --create-home --shell /usr/sbin/nologin aai \
    && chown -R aai:aai /app
USER aai
ENV HOME=/home/aai

EXPOSE 9090
HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9090/healthz')"

CMD ["python3", "-u", "/app/server.py"]
