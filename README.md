# ARKANA PULSE

[Русский](#ru) · [English](#en)

---

## RU

**ARKANA PULSE** — крипто-дашборд/бот с API на FastAPI и веб-интерфейсом, упакованный в Docker Compose и дополненный базовыми DevSecOps-практиками (CI SAST/SCA/scan, мониторинг, hardening контейнера).

### Возможности

- **Веб-интерфейс** через Nginx (единая точка входа).
- **API** на FastAPI.
- **Redis** для кэша/ограничений (внутренняя сеть).
- **Мониторинг**: Prometheus + Grafana (готовый datasource + dashboard provisioning).
- **CI security**: Ruff (lint), Semgrep (SAST), Trivy (fs + image).

### Стек

- **Backend**: Python, FastAPI
- **Infra**: Docker, Docker Compose, Nginx, Redis
- **Observability**: Prometheus, Grafana
- **DevSecOps / CI**: GitHub Actions, Ruff, Semgrep, Trivy, Dependabot

### Быстрый старт (Docker Compose)

1) Создайте `.env` на базе примера:

```bash
cp .env.example .env
```

2) Запустите стек:

```bash
docker compose up -d --build
```

### Доступы по умолчанию

- **Приложение (через Nginx)**: `http://localhost` (порт 80)
- **Grafana**: `http://localhost:3000` (логин/пароль из `.env`)
- **Prometheus**: `http://localhost:9090`

Подробности про мониторинг: `monitoring/README.md`.

### HTTPS (опционально)

- Локальный dev-сертификат: `./scripts/generate-dev-cert.sh`
- Инструкция по включению TLS: см. `SECURITY.md` и `nginx/README.md`

### DevSecOps заметки (что уже есть)

- **CI**: `.github/workflows/ci.yml`
  - Ruff lint
  - Semgrep SAST (`semgrep scan --config auto`)
  - Trivy: скан репозитория (fs) и Docker-образа API (image)
- **Secrets hygiene**: не коммитьте `.env` (используйте `.env.example`)
- **Метрики**: API отдаёт `/metrics`, Prometheus скрейпит `api:8000/metrics` (см. `monitoring/prometheus/prometheus.yml`)
- **Сети Compose**:
  - `back` — `internal: true` (Redis недоступен снаружи)
  - `front` — трафик клиента приходит в Nginx

Подробнее по безопасности: `SECURITY.md`.

---

## EN

**ARKANA PULSE** is a crypto dashboard/bot with a FastAPI backend and a web UI, packaged with Docker Compose and augmented with practical DevSecOps basics (CI SAST/SCA/scanning, monitoring, container hardening).

### Features

- **Web UI** behind Nginx (single ingress point).
- **FastAPI** backend.
- **Redis** for cache/rate limiting (internal network).
- **Monitoring**: Prometheus + Grafana (provisioned datasource + dashboard).
- **CI security**: Ruff (lint), Semgrep (SAST), Trivy (fs + image).

### Tech stack

- **Backend**: Python, FastAPI
- **Infra**: Docker, Docker Compose, Nginx, Redis
- **Observability**: Prometheus, Grafana
- **DevSecOps / CI**: GitHub Actions, Ruff, Semgrep, Trivy, Dependabot

### Quick start (Docker Compose)

1) Create `.env` from the template:

```bash
cp .env.example .env
```

2) Start the stack:

```bash
docker compose up -d --build
```

### Default endpoints

- **App (via Nginx)**: `http://localhost` (port 80)
- **Grafana**: `http://localhost:3000` (credentials from `.env`)
- **Prometheus**: `http://localhost:9090`

Monitoring details: `monitoring/README.md`.

### HTTPS (optional)

- Generate a local dev certificate: `./scripts/generate-dev-cert.sh`
- How to enable TLS: see `SECURITY.md` and `nginx/README.md`

### DevSecOps notes (what’s already included)

- **CI**: `.github/workflows/ci.yml`
  - Ruff lint
  - Semgrep SAST (`semgrep scan --config auto`)
  - Trivy: filesystem scan + API image scan
- **Secrets hygiene**: do not commit `.env` (use `.env.example`)
- **Metrics**: API exposes `/metrics`, Prometheus scrapes `api:8000/metrics` (see `monitoring/prometheus/prometheus.yml`)
- **Compose networks**:
  - `back` — `internal: true` (Redis not exposed to the host)
  - `front` — client traffic goes to Nginx

For more: `SECURITY.md`.

