# Безопасность и DevSecOps (ARKANA PULSE)

## Секреты

- **Не коммитьте `.env`** — он в `.gitignore`. Используйте `.env.example` как шаблон.
- **Production:** храните секреты вне репозитория:
  - **Docker secrets:** создайте файлы (например, `.secrets/bot_token.txt`, `.secrets/api_key.txt`), добавьте `.secrets/` в `.gitignore`. В `docker-compose` задайте секреты и в сервисе `api` передайте переменные:
    - `BOT_TOKEN_FILE=/run/secrets/bot_token`
    - `API_KEY_FILE=/run/secrets/api_key`
  - Либо используйте переменные окружения оркестратора (Kubernetes Secrets, Docker Swarm secrets и т.д.) и те же переменные `*_FILE` на путях к смонтированным файлам.
- Приложение поддерживает чтение секретов из файлов: если задана переменная `BOT_TOKEN_FILE` (или `API_KEY_FILE`, `BINANCE_API_SECRET_FILE`) и по этому пути лежит файл, значение подставляется из файла.

## HTTPS

- По умолчанию nginx слушает только HTTP (порт 80). Для HTTPS:
  1. Разместите сертификат и ключ в `nginx/ssl/` (например, `fullchain.pem`, `privkey.pem`).
  2. Скопируйте `nginx/conf.d/arkana-ssl.conf.example` в `nginx/conf.d/arkana-ssl.conf` и при необходимости поправьте пути к сертификатам.
  3. Перезапустите nginx: `docker compose restart nginx`.
- Для локальной разработки можно сгенерировать самоподписанный сертификат: `./scripts/generate-dev-cert.sh` (затем включите конфиг HTTPS по инструкции выше).
- В production используйте сертификаты от Let's Encrypt (certbot) или от вашего CA.

## Метрики Prometheus

- Эндпоинт `/metrics` отдаёт метрики приложения (число запросов, латентность) без проверки API-ключа.
- В production ограничьте доступ к `/metrics` (например, в nginx по IP или через отдельный location с allow/deny, либо не проксируйте его наружу).
- /metrics по-прежнему не через Nginx; доступ только из внутренней сети + при необходимости firewall для портов 3000/9090 на хосте.

## Сети Docker

- **back** — внутренняя сеть (`internal: true`): `api`, `redis`, `prometheus`, `grafana`. Redis недоступен с хоста; метрики API скрейпит только Prometheus по `api:8000`.
- **front** — сеть для nginx и api; пользовательский трафик с хоста идёт в nginx (порты 80/443).

## Grafana и Prometheus

- После `docker compose up`: Grafana — `http://localhost:3000`, Prometheus — `http://localhost:9090` (см. `monitoring/README.md`).
- Учётные данные Grafana задаются через `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD` в `.env`.

## Обновления и уязвимости

- **Dependabot** (см. `.github/dependabot.yml`) создаёт PR с обновлениями зависимостей и GitHub Actions.
- **Trivy:** в CI — скан **файловой системы** репозитория (`trivy-fs`) и **Docker-образа** API (`build`). Локально образ: `./scripts/trivy-scan.sh arkana_pulse-api`. Учитывается `.trivyignore`.
- **Semgrep:** SAST в CI (`semgrep` job); каталог `static/` перечислен в `.semgrepignore`.

## Сообщение об уязвимости

Если вы обнаружили уязвимость, опишите её по возможности без публичного раскрытия (например, через Issues с меткой security или по контакту, указанному в репозитории) 
