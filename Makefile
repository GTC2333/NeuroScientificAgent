.PHONY: build up down logs clean rebuild restart

# Build images
build:
	docker-compose build

# Start containers
up:
	docker-compose up -d

# Stop containers
down:
	docker-compose down

# View all logs
logs:
	docker-compose logs -f

# View sandbox logs
logs-sandbox:
	docker-compose logs -f sandbox

# View main logs
logs-main:
	docker-compose logs -f main

# Clean up
clean:
	docker-compose down -v
	docker system prune -f

# Rebuild and start
rebuild: down build up

# Quick restart
restart: down up
