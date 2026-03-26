"""
Метрики Prometheus для мониторинга API (запросы, длительность).
Эндпоинт /metrics не защищён API-ключом — в production ограничьте доступ (nginx/firewall).
"""
from __future__ import annotations

import time
from collections.abc import Callable

from fastapi import Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware

REQUEST_COUNT = Counter(
    "arkana_http_requests_total",
    "Total HTTP requests",
    ["method", "path_template", "status"],
)
REQUEST_LATENCY = Histogram(
    "arkana_http_request_duration_seconds",
    "Request latency in seconds",
    ["method", "path_template"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)


def _path_template(path: str) -> str:
    """Сводит путь к шаблону (например, /api/v1/candles/BTCUSDT -> /api/v1/candles/{symbol})."""
    if path.startswith("/api/v1/candles/"):
        return "/api/v1/candles/{symbol}"
    if path.startswith("/api/v1/signal/"):
        return "/api/v1/signal/{symbol}"
    return path.split("?")[0] or "/"


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Считает запросы и латентность для Prometheus."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        method = request.method
        path_tpl = _path_template(request.url.path)
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start
        status = response.status_code
        REQUEST_COUNT.labels(method=method, path_template=path_tpl, status=status).inc()
        REQUEST_LATENCY.labels(method=method, path_template=path_tpl).observe(duration)
        return response


def metrics_content() -> bytes:
    """Возвращает тело ответа для /metrics."""
    return generate_latest()


def metrics_content_type() -> str:
    return CONTENT_TYPE_LATEST
