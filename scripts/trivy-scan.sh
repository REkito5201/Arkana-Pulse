#!/usr/bin/env bash
# Сканирование Docker-образов на уязвимости (Trivy).
# Использование: ./scripts/trivy-scan.sh [имя_образа]
# Пример: ./scripts/trivy-scan.sh arkana_pulse-api
set -e
IMAGE="${1:-arkana_pulse-api}"
if ! command -v trivy &>/dev/null; then
  echo "Установите Trivy: https://github.com/aquasecurity/trivy#installation"
  exit 1
fi
echo "Сканирование образа: $IMAGE"
trivy image --exit-code 1 --severity HIGH,CRITICAL "$IMAGE"
