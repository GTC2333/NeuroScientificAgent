#!/bin/bash
# download_deps.sh — MAS 离线构建依赖下载脚本
#
# 参考 /srv/openhands-offline-build/download_dependencies.sh 的离线构建技巧
# 一次性下载所有构建依赖到本地，后续 docker build 可完全离线
#
# Usage:
#   ./docker/download_deps.sh              # 下载全部
#   ./docker/download_deps.sh pip          # 只下载 pip wheels
#   ./docker/download_deps.sh apt          # 只下载 apt packages
#   ./docker/download_deps.sh npm          # 只下载 npm cache

set -euo pipefail

log() { echo "[$(date '+%F %T')] $*"; }
die() { log "ERROR: $*"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# 支持环境变量覆盖路径
OFFLINE_DEPS_PATH="${OFFLINE_DEPS_PATH:-/opt/offline-deps}"
if [[ -d "$OFFLINE_DEPS_PATH" ]]; then
    # 使用 /opt/offline-deps/ 结构
    OFFLINE_DIR="$OFFLINE_DEPS_PATH"
    log "Using shared offline deps: $OFFLINE_DIR"
else
    # 回退到 docker/offline-deps/
    OFFLINE_DIR="${SCRIPT_DIR}/offline-deps"
    log "Using local offline deps: $OFFLINE_DIR"
fi

# Proxy config (inherits env or defaults)
PROXY_URL="${HTTP_PROXY:-${http_proxy:-}}"
PROXY_ARG=""
if [[ -n "$PROXY_URL" ]]; then
    PROXY_ARG="--proxy $PROXY_URL"
    log "Using proxy: $PROXY_URL"
fi

# Docker network mode for download containers
DOCKER_NET="${DOCKER_NET:---network host}"

# Target: all / pip / apt / npm
TARGET="${1:-all}"

# Force official PyPI (override pip.conf)
PIP_INDEX_URL="https://pypi.org/simple"
PIP_TRUSTED_HOST="pypi.org"
# Use --no-cache-dir to ignore user/system pip.conf
PIP_EXTRA_ARGS="--no-cache-dir --index-url=${PIP_INDEX_URL} --trusted-host=${PIP_TRUSTED_HOST}"

# Python version for wheel downloads (pip format: 12 for cp312)
PYTHON_VERSION_MAJOR="3.12"
PYTHON_VERSION_PIP="12"

############################################
# 1. Download pip wheels
############################################
download_pip_wheels() {
    log "=== Downloading pip wheels ==="

    local PIP_DIR="${OFFLINE_DIR}/python/cp312/any"
    mkdir -p "$PIP_DIR"

    # Check existing wheels (if > 50, assume already downloaded)
    local EXISTING_COUNT
    EXISTING_COUNT=$(ls "${PIP_DIR}"/*.whl 2>/dev/null | wc -l)
    log "[pip] Existing wheels: $EXISTING_COUNT"

    if [[ "$EXISTING_COUNT" -gt 50 ]]; then
        log "[pip] Already have $EXISTING_COUNT wheels, skipping download"
        return
    fi

    # Main container wheels
    log "[pip] Downloading main container wheels..."
    pip download \
        -r "${SCRIPT_DIR}/requirements.txt" \
        -d "${PIP_DIR}" \
        --platform manylinux2014_x86_64 \
        --platform manylinux_2_17_x86_64 \
        --python-version ${PYTHON_VERSION_PIP} \
        --only-binary=:all: \
        ${PIP_EXTRA_ARGS} \
        2>&1 || {
        # Fallback: download without platform constraint (gets source dists too)
        log "[pip] Binary-only download incomplete, trying with source packages..."
        pip download \
            -r "${SCRIPT_DIR}/requirements.txt" \
            -d "${PIP_DIR}" \
            ${PIP_EXTRA_ARGS} \
            2>&1
    }
    log "[pip] Main wheels: $(ls "${PIP_DIR}" | wc -l) files"

    # Sandbox container wheels (use same cp312/any for simplicity)
    log "[pip] Downloading sandbox container wheels..."
    pip download \
        -r "${SCRIPT_DIR}/sandbox-requirements.txt" \
        -d "${PIP_DIR}" \
        --platform manylinux2014_x86_64 \
        --platform manylinux_2_17_x86_64 \
        --python-version ${PYTHON_VERSION_PIP} \
        --only-binary=:all: \
        ${PIP_EXTRA_ARGS} \
        2>&1 || {
        log "[pip] Binary-only download incomplete, trying with source packages..."
        pip download \
            -r "${SCRIPT_DIR}/sandbox-requirements.txt" \
            -d "${PIP_DIR}" \
            ${PIP_EXTRA_ARGS} \
            2>&1
    }
    log "[pip] Sandbox wheels: $(ls "${PIP_DIR}" | wc -l) files"

    log "=== pip wheels download complete ==="
}

############################################
# 2. Download apt .deb packages
############################################
download_apt_packages() {
    log "=== Downloading apt packages ==="

    local DEB_DIR="${OFFLINE_DIR}/apt/pool/main"
    mkdir -p "$DEB_DIR"

    # Main container apt deps: nginx, curl, docker.io
    MAIN_PACKAGES="nginx curl docker.io"
    # Sandbox container apt deps: curl, git, ripgrep
    SANDBOX_PACKAGES="curl git ripgrep"
    # Build-stage deps: gcc
    BUILD_PACKAGES="gcc"

    ALL_PACKAGES="$MAIN_PACKAGES $SANDBOX_PACKAGES $BUILD_PACKAGES"
    # Deduplicate
    ALL_PACKAGES=$(echo "$ALL_PACKAGES" | tr ' ' '\n' | sort -u | tr '\n' ' ')

    # Check existing packages
    local EXISTING_COUNT=$(ls "${DEB_DIR}"/*.deb 2>/dev/null | wc -l || echo "0")
    log "[apt] Existing packages: $EXISTING_COUNT"

    if [[ $EXISTING_COUNT -gt 300 ]]; then
        log "[apt] Already have $EXISTING_COUNT packages, skipping download"
    else
        log "[apt] Downloading packages: $ALL_PACKAGES"

        docker run --rm ${DOCKER_NET} \
            -e http_proxy="${PROXY_URL}" \
            -e https_proxy="${PROXY_URL}" \
            -e HTTP_PROXY="${PROXY_URL}" \
            -e HTTPS_PROXY="${PROXY_URL}" \
            -v "${DEB_DIR}:/output" \
            python:3.12-slim \
            bash -c "
                export DEBIAN_FRONTEND=noninteractive && \
                apt-get update && \
                apt-get install -y --download-only --no-install-recommends ${ALL_PACKAGES} && \
                cp /var/cache/apt/archives/*.deb /output/ 2>/dev/null || true && \
                echo 'Downloaded APT packages'
            "
    fi

    # Generate Packages index for local APT repo (always regenerate)
    log "[apt] Generating APT repo index..."
    cd "${OFFLINE_DIR}/apt"
    if command -v dpkg-scanpackages &>/dev/null; then
        dpkg-scanpackages pool/main /dev/null > Packages 2>/dev/null
        gzip -k -f Packages
    else
        # Use Docker container to generate index
        docker run --rm \
            -v "${OFFLINE_DIR}/apt:/repo" \
            python:3.12-slim \
            bash -c "
                apt-get update && apt-get install -y dpkg-dev && \
                cd /repo && \
                dpkg-scanpackages pool/main /dev/null > Packages && \
                gzip -k -f Packages
            "
    fi
    cd "$PROJECT_DIR"

    log "[apt] APT repo: $(ls "${DEB_DIR}"/*.deb 2>/dev/null | wc -l) .deb files"
    log "=== apt packages download complete ==="
}

############################################
# 3. Download npm cache
############################################
download_npm_cache() {
    log "=== Downloading npm packages ==="

    local NPM_CACHE_DIR="${OFFLINE_DIR}/node/v20"
    local FRONTEND_DIR="${PROJECT_DIR}/frontend/claudecodeui"

    if [[ ! -f "${FRONTEND_DIR}/package.json" ]]; then
        log "[npm] WARN: frontend/claudecodeui/package.json not found, skipping"
        return
    fi

    # Check existing npm cache
    if [[ -f "${NPM_CACHE_DIR}/node_modules.tar.gz" ]]; then
        local EXISTING_SIZE=$(du -sh "${NPM_CACHE_DIR}/node_modules.tar.gz" 2>/dev/null | cut -f1)
        log "[npm] Already have cache (${EXISTING_SIZE}), skipping download"
        return
    fi

    # Use a node container to npm ci and then tar the node_modules
    log "[npm] Installing and caching node_modules..."
    docker run --rm ${DOCKER_NET} \
        -e http_proxy="${PROXY_URL}" \
        -e https_proxy="${PROXY_URL}" \
        -e HTTP_PROXY="${PROXY_URL}" \
        -e HTTPS_PROXY="${PROXY_URL}" \
        -v "${FRONTEND_DIR}:/src:ro" \
        -v "${NPM_CACHE_DIR}:/output" \
        node:20-slim \
        bash -c "
            cd /tmp && \
            cp /src/package.json /src/package-lock.json . 2>/dev/null || cp /src/package.json . && \
            npm ci --ignore-scripts 2>&1 && \
            tar czf /output/node_modules.tar.gz node_modules && \
            echo 'npm cache created'
        "

    log "[npm] Cache size: $(du -sh "${NPM_CACHE_DIR}/node_modules.tar.gz" 2>/dev/null | cut -f1)"
    log "=== npm packages download complete ==="
}

############################################
# Main
############################################

log "=========================================="
log "MAS 离线构建依赖下载"
log "=========================================="
log "Target: ${TARGET}"
log "Offline dir: ${OFFLINE_DIR}"
log "Proxy: ${PROXY_URL:-none}"
log "=========================================="

case "$TARGET" in
    pip)
        download_pip_wheels
        ;;
    apt)
        download_apt_packages
        ;;
    npm)
        download_npm_cache
        ;;
    all)
        # 并行执行3个下载任务
        log "Starting parallel downloads..."
        (
            download_pip_wheels
        ) &
        PIP_PID=$!

        (
            download_apt_packages
        ) &
        APT_PID=$!

        (
            download_npm_cache
        ) &
        NPM_PID=$!

        # 等待所有任务完成
        wait $PIP_PID || true
        wait $APT_PID || true
        wait $NPM_PID || true

        log "All parallel downloads completed"
        ;;
    *)
        echo "Usage: $0 [all|pip|apt|npm]"
        exit 1
        ;;
esac

echo ""
log "=========================================="
log "Download complete!"
log "=========================================="
log "Directory structure:"
log "  ${OFFLINE_DIR}/"
log "    ├── python/cp312/any/      # Python wheels"
log "    ├── apt/pool/main/        # APT packages"
log "    └── node/v20/             # Node modules"
log ""
log "Or use legacy structure:"
log "    ├── pip-wheels/main/       # Main container Python deps (legacy)"
log "    ├── pip-wheels/sandbox/    # Sandbox container Python deps (legacy)"
log "    └── npm-cache/             # Frontend node_modules (legacy)"
log ""
log "Next: run ./build_images.sh to build with offline deps"
log "=========================================="
