.PHONY: build build-sandbox build-all up down down-all logs logs-main clean rebuild restart

# Build main container
build:
	docker-compose build

# Build sandbox image
build-sandbox:
	docker build -t mas-sandbox:latest -f docker/sandbox.Dockerfile .

# Build everything
build-all: build-sandbox build

# Start main container
up:
	docker-compose up -d

# Stop main container
down:
	docker-compose down

# Stop all (main + sandbox containers)
down-all:
	docker-compose down
	docker ps --filter "name=mas-sandbox-" -q | xargs -r docker rm -f 2>/dev/null || true

# View all logs
logs:
	docker-compose logs -f

# View main logs
logs-main:
	docker-compose logs -f main

# Clean up everything (containers, volumes, orphan sandboxes)
clean:
	docker-compose down -v
	docker ps --filter "name=mas-sandbox-" -q | xargs -r docker rm -f 2>/dev/null || true
	docker volume ls --filter "name=mas-workspace-" -q | xargs -r docker volume rm 2>/dev/null || true
	docker system prune -f

# Rebuild and start
rebuild: down build-all up

# Quick restart
restart: down up
