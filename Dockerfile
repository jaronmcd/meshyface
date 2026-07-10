FROM python:3.11-slim

ARG MESH_DASH_VERSION=
ARG MESH_DASH_GIT_COMMIT=nogit
ARG MESH_DASH_PR_NUMBER=

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MESH_DASH_VERSION=${MESH_DASH_VERSION} \
    MESH_DASH_GIT_COMMIT=${MESH_DASH_GIT_COMMIT} \
    MESH_DASH_PR_NUMBER=${MESH_DASH_PR_NUMBER} \
    MESH_DASH_HISTORY_DB=/data/mesh_dashboard_history.sqlite3 \
    MESH_DASH_THEME_SETTINGS_FILE=/data/mesh_dashboard_theme_settings.json \
    MESH_DASHBOARD_MAP_PACKS_DIR=/data/map_packs

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY mesh_dashboard.py mesh_connection.py ./
COPY meshdash ./meshdash
COPY scripts/build_map_pack.py scripts/build_offline_atlas.py scripts/install_map_pack.py ./scripts/
COPY LICENSE README.md THIRD_PARTY_NOTICES.md THIRD_PARTY_PYTHON_DEPENDENCIES.md ./
COPY third_party ./third_party

RUN mkdir -p /data

VOLUME ["/data"]
EXPOSE 8877
STOPSIGNAL SIGINT

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8877/', timeout=3).read(1)"

ENTRYPOINT ["python", "mesh_dashboard.py"]
