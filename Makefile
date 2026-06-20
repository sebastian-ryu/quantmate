.PHONY: backend-dev frontend-dev db-up db-down db-logs install-backend install-frontend

install-backend:
	python3 -m pip install -e "backend[dev]"

install-frontend:
	npm --prefix frontend install

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
