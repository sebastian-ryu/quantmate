# Local Setup

## Docker

The project uses Docker Compose for local MySQL.

Check Docker:

```bash
docker --version
docker compose version
```

If Docker is not installed, install Docker Desktop for Mac:

https://docs.docker.com/desktop/setup/install/mac-install/

After installation, open Docker Desktop once and wait until it is running.

## Environment File

Create a local environment file:

```bash
cp .env.example .env
```

Then edit `.env` and change local passwords before real use.

Do not commit `.env`.

## MySQL

Start MySQL:

```bash
docker compose up -d mysql
```

Check status:

```bash
docker compose ps
docker compose logs -f mysql
```

Connect with the MySQL CLI inside the container:

```bash
docker compose exec mysql mysql -uquantmate -p quantmate
```

Stop MySQL:

```bash
docker compose down
```

Delete the local MySQL data volume:

```bash
docker compose down -v
```

Use `down -v` only when you intentionally want to remove local database data.

