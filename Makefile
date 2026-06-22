.PHONY: dev dev-up dev-stop dev-down dev-logs backend-dev frontend-dev db-up db-down db-logs db-migrate db-revision db-seed install-backend install-frontend prod-build prod-up prod-down prod-logs

install-backend:
	python3 -m pip install -e "backend[dev]"

install-frontend:
	npm --prefix frontend install

dev: dev-up

dev-up:
	bash scripts/dev-up.sh

dev-stop:
	bash scripts/dev-stop.sh

dev-down: dev-stop

dev-logs:
	tail -f logs/backend.log logs/frontend.log

backend-dev:
	python3 -m uvicorn quantmate_api.main:app --app-dir backend/src --reload --host 127.0.0.1 --port 8000

frontend-dev:
	npm --prefix frontend run dev -- --host 127.0.0.1

db-up:
	docker compose up -d mysql

db-down:
	docker compose down

db-logs:
	docker compose logs -f mysql

db-migrate:
	python3 -m alembic -c backend/alembic.ini upgrade head

db-revision:
	python3 -m alembic -c backend/alembic.ini revision --autogenerate

db-seed:
	python3 -m quantmate_api.seed

prod-build:
	docker compose -f docker-compose.prod.yml build

prod-up:
	docker compose -f docker-compose.prod.yml up -d

prod-down:
	docker compose -f docker-compose.prod.yml down

prod-logs:
	docker compose -f docker-compose.prod.yml logs -f
