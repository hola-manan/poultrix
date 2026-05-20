.PHONY: up down build logs clean

up:
	docker compose -f infra/docker-compose.example.yml up --build -d

down:
	docker compose -f infra/docker-compose.example.yml down -v

build:
	docker compose -f infra/docker-compose.example.yml build

logs:
	docker compose -f infra/docker-compose.example.yml logs -f

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .coverage htmlcov
	rm -rf data/*.json data/*.tif data/*.csv
