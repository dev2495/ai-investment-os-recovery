# Docker External SSD Storage Runbook

## Current State

Docker Desktop is installed and running.

Observed on 2026-07-01:

```text
Docker Desktop 4.80.0
Context: desktop-linux
Images: 0
Docker.raw: /Users/devarshthakkar/Library/Containers/com.docker.docker/Data/vms/0/data/Docker.raw
```

The current Docker Desktop image store is still on internal storage.

The project Compose stack uses Docker-managed named volumes for database/vector/queue data.

Because Docker Desktop's disk image location is on the external SSD, named volumes live inside the external Docker disk image and avoid macOS bind-mount/FUSE issues for services such as Qdrant and Postgres.

## Required Before Pulling Images

Move Docker Desktop disk image location to the external SSD.

Recommended target folder:

```text
/Volumes/Devarsh SSD/Docker Desktop Data
```

Safe UI path:

1. Open Docker Desktop.
2. Go to Settings.
3. Go to Resources.
4. Go to Advanced.
5. Change Disk image location to `/Volumes/Devarsh SSD/Docker Desktop Data`.
6. Let Docker Desktop move or create the disk image.
7. Restart Docker Desktop if prompted.
8. Re-run `docker info` and confirm Docker is healthy.

Why this matters:

- Compose bind mounts control service data.
- Docker Desktop disk image location controls image layers and Docker-managed storage.
- Pulling images before this step can grow internal storage.

## Start Runtime After Storage Move

```bash
cd "/Volumes/Devarsh SSD/Obsidian memory /_ai_os_runtime"
cp .env.example .env
docker compose config
docker compose up -d
docker compose ps
```

## Health Checks

Postgres:

```bash
docker exec ai_os_postgres pg_isready -U ai_os -d ai_os
```

Qdrant:

```bash
curl -s http://127.0.0.1:6333/readyz
```

Redis:

```bash
docker exec ai_os_redis redis-cli ping
```

## Safety

Do not use internal Docker Desktop disk image storage for this project.

Do not start containers that pull large images until the disk image location is external.
