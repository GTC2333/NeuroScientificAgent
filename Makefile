.PHONY: build build-sandbox build-main up down down-all logs clean rebuild restart

SCRIPT_DIR := $(shell cd .. && pwd)
TAG ?= latest

# Build images (delegates to build_images.sh)
build: build-sandbox build-main

build-sandbox:
	$(SCRIPT_DIR)/build_images.sh sandbox $(TAG)

build-main:
	$(SCRIPT_DIR)/build_images.sh main $(TAG)

# Start main container (delegates to run_main.sh)
up:
	$(SCRIPT_DIR)/run_main.sh $(TAG)

# Stop main container
down:
	docker compose down

# Stop all (main + sandbox containers)
down-all:
	docker compose down
	docker ps --filter "name=mas-sandbox-" -q | xargs -r docker rm -f 2>/dev/null || true

# View logs
logs:
	docker compose logs -f

# Clean up everything
clean:
	docker compose down -v
	docker ps --filter "name=mas-sandbox-" -q | xargs -r docker rm -f 2>/dev/null || true
	docker system prune -f

# Rebuild and start
rebuild: down build up

# Quick restart
restart: down up
