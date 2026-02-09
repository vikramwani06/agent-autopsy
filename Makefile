# =============================================================================
# Agent Autopsy Docker Makefile
# =============================================================================

.PHONY: help build run stop logs clean test deploy

# Default target
help:
	@echo "Agent Autopsy Docker Commands:"
	@echo ""
	@echo "  build     - Build Docker image"
	@echo "  run       - Run Docker container"
	@echo "  stop      - Stop Docker container"
	@echo "  logs      - View container logs"
	@echo "  clean     - Remove Docker images and containers"
	@echo "  test      - Run tests in container"
	@echo "  deploy    - Deploy to production"
	@echo ""

# Build Docker image
build:
	@echo "Building Agent Autopsy Docker image..."
	docker build -t agent-autopsy:latest .
	@echo "Build complete!"

# Run with Docker Compose
run:
	@echo "Starting Agent Autopsy with Docker Compose..."
	docker-compose up -d
	@echo "Application started!"
	@echo "API: http://localhost:8000"
	@echo "UI:  http://localhost:8501"

# Stop application
stop:
	@echo "Stopping Agent Autopsy..."
	docker-compose down
	@echo "Application stopped!"

# View logs
logs:
	docker-compose logs -f

# Clean up Docker resources
clean:
	@echo "Cleaning up Docker resources..."
	docker-compose down -v
	docker system prune -f
	@echo "Cleanup complete!"

# Run tests
test:
	@echo "Running tests in Docker..."
	docker-compose run --rm agent-autopsy python -m pytest tests/

# Deploy to production
deploy:
	@echo "Deploying to production..."
	docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
	@echo "Deployment complete!"

# Development setup
dev:
	@echo "Setting up development environment..."
	cp .env.example .env
	@echo "Please edit .env file with your credentials"
	@echo "Then run: make run"

# Production build
build-prod:
	@echo "Building production image..."
	docker build -t agent-autopsy:$(shell git describe --tags --always) .
	docker tag agent-autopsy:$(shell git describe --tags --always) agent-autopsy:latest
	@echo "Production build complete!"

# Backup data
backup:
	@echo "Backing up reports..."
	mkdir -p backup
	docker run --rm -v $(PWD)/reports:/data -v $(PWD)/backup:/backup alpine tar czf /backup/reports-$(shell date +%Y%m%d).tar.gz -C /data .
	@echo "Backup complete!"

# Restore data
restore:
	@echo "Restoring reports..."
	@if [ -z "$(FILE)" ]; then echo "Usage: make restore FILE=backup-file.tar.gz"; exit 1; fi
	docker run --rm -v $(PWD)/reports:/data -v $(PWD)/backup:/backup alpine tar xzf /backup/$(FILE) -C /data .
	@echo "Restore complete!"
