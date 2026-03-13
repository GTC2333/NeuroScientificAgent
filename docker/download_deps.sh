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
OFFLINE_DIR="${SCRIPT_DIR}/offline-deps"

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

############################################
# 1. Download pip wheels
############################################
download_pip_wheels() {
    log "=== Downloading pip wheels ==="

    # Main container wheels
    log "[pip] Downloading main container wheels..."
    pip download \
        -r "${SCRIPT_DIR}/requirements.txt" \
        -d "${OFFLINE_DIR}/pip-wheels/main" \
        --platform manylinux2014_x86_64 \
        --platform linux_x86_64 \
        --python-version 3.11 \
        --only-binary=:all: \
        2>&1 || {
        # Fallback: download without platform constraint (gets source dists too)
        log "[pip] Binary-only download incomplete, trying with source packages..."
        pip download \
            -r "${SCRIPT_DIR}/requirements.txt" \
            -d "${OFFLINE_DIR}/pip-wheels/main" \
            2>&1
    }
    log "[pip] Main wheels: $(ls "${OFFLINE_DIR}/pip-wheels/main/" | wc -l) files"

    # Sandbox container wheels
    log "[pip] Downloading sandbox container wheels..."
    pip download \
        -r "${SCRIPT_DIR}/sandbox-requirements.txt" \
        -d "${OFFLINE_DIR}/pip-wheels/sandbox" \
        --platform manylinux2014_x86_64 \
        --platform linux_x86_64 \
        --python-version 3.11 \
        --only-binary=:all: \
        2>&1 || {
        log "[pip] Binary-only download incomplete, trying with source packages..."
        pip download \
            -r "${SCRIPT_DIR}/sandbox-requirements.txt" \
            -d "${OFFLINE_DIR}/pip-wheels/sandbox" \
            2>&1
    }
    log "[pip] Sandbox wheels: $(ls "${OFFLINE_DIR}/pip-wheels/sandbox/" | wc -l) files"

    log "=== pip wheels download complete ==="
}

############################################
# 2. Download apt .deb packages
############################################
download_apt_packages() {
    log "=== Downloading apt packages ==="

    local DEB_DIR="${OFFLINE_DIR}/apt-repo/pool/main"
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

    log "[apt] Downloading packages: $ALL_PACKAGES"

    docker run --rm ${DOCKER_NET} \
        -e http_proxy="${PROXY_URL}" \
        -e https_proxy="${PROXY_URL}" \
        -e HTTP_PROXY="${PROXY_URL}" \
        -e HTTPS_PROXY="${PROXY_URL}" \
        -v "${DEB_DIR}:/output" \
        python:3.11-slim \
        bash -c "
            export DEBIAN_FRONTEND=noninteractive && \
            apt-get update && \
            apt-get install -y --download-only --no-install-recommends ${ALL_PACKAGES} && \
            cp /var/cache/apt/archives/*.deb /output/ 2>/dev/null || true && \
            echo 'Downloaded APT packages'
        "

    # Generate Packages index for local APT repo
    log "[apt] Generating APT repo index..."
    cd "${OFFLINE_DIR}/apt-repo"
    if command -v dpkg-scanpackages &>/dev/null; then
        dpkg-scanpackages pool/main /dev/null > Packages 2>/dev/null
        gzip -k -f Packages
    else
        # Use Docker container to generate index
        docker run --rm \
            -v "${OFFLINE_DIR}/apt-repo:/repo" \
            python:3.11-slim \
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

    local NPM_CACHE_DIR="${OFFLINE_DIR}/npm-cache"
    local FRONTEND_DIR="${PROJECT_DIR}/frontend/claudecodeui"

    if [[ ! -f "${FRONTEND_DIR}/package.json" ]]; then
        log "[npm] WARN: frontend/claudecodeui/package.json not found, skipping"
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
        download_pip_wheels
        download_apt_packages
        download_npm_cache
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
log "    ├── pip-wheels/main/       # Main container Python deps"
log "    ├── pip-wheels/sandbox/    # Sandbox container Python deps"
log "    ├── apt-repo/              # Local APT repository"
log "    └── npm-cache/             # Frontend node_modules tarball"
log ""
log "Next: run ./build_images.sh to build with offline deps"
log "=========================================="
