# Мониторинг (Prometheus + Grafana)

Стек поднимается вместе с приложением: `docker compose up -d`.

| Сервис      | URL по умолчанию | Назначение                          |
|------------|------------------|-------------------------------------|
| Prometheus | http://localhost:9090 | Targets, PromQL, метаданные скрейпа |
| Grafana    | http://localhost:3000 | Дашборды (логин из `.env`)          |

## Как это связано

- **API** отдаёт метрики на `http://api:8000/metrics` (внутри сети Docker `back`).
- **Prometheus** скрейпит `api:8000` по конфигу `prometheus/prometheus.yml`.
- **Grafana** использует Prometheus как datasource (provisioning в `grafana/provisioning/`).
- Дашборд **Arkana Pulse API** подхватывается из `grafana/dashboards/arkana-pulse.json`.

Эндпоинт `/metrics` **не** проксируется через Nginx — доступ только из внутренней сети или с хоста через Prometheus.

## Переменные окружения

См. `.env.example`: `GRAFANA_ADMIN_USER`, `GRAFANA_ADMIN_PASSWORD`.
