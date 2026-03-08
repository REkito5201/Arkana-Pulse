#!/usr/bin/env bash
# Генерация самоподписанного сертификата для локальной разработки (HTTPS).
# Не использовать в production — только для тестов в браузере по https://localhost.
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SSL_DIR="$PROJECT_ROOT/nginx/ssl"
mkdir -p "$SSL_DIR"
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout "$SSL_DIR/privkey.pem" \
  -out "$SSL_DIR/fullchain.pem" \
  -subj "/CN=localhost/O=Arkana Pulse Dev"
echo "Сертификаты созданы: $SSL_DIR/privkey.pem, $SSL_DIR/fullchain.pem"
echo "Для использования HTTPS: скопируйте nginx/conf.d/arkana-ssl.conf.example в arkana-ssl.conf и перезапустите nginx."
