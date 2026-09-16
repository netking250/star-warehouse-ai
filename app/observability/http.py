"""HTTP request observability helpers with bounded route labels."""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import Request
from starlette.responses import Response

from app.observability.metrics import (
    HTTP_REQUESTS_IN_FLIGHT,
    record_http_request,
)

logger = logging.getLogger(__name__)

RequestHandler = Callable[[Request], Awaitable[Response]]

_EXCLUDED_EXACT_PATHS = frozenset(
    {
        "/metrics",
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/favicon.svg",
        "/icons.svg",
        "/index.html",
        "/admin.html",
    }
)
_EXCLUDED_PREFIXES = ("/assets/", "/customer/", "/shared/")


def should_instrument_http_path(path: str) -> bool:
    """Return whether a request path represents application traffic."""
    return path not in _EXCLUDED_EXACT_PATHS and not path.startswith(_EXCLUDED_PREFIXES)


def _route_template(request: Request) -> object | None:
    """Return the Starlette route object, never the raw request path."""
    return request.scope.get("route")


async def observe_http_request(request: Request, call_next: RequestHandler) -> Response:
    """Measure one request without allowing telemetry errors to affect its response."""
    if not should_instrument_http_path(request.url.path):
        return await call_next(request)

    started = time.perf_counter()
    in_flight_recorded = False
    try:
        HTTP_REQUESTS_IN_FLIGHT.inc()
        in_flight_recorded = True
    except Exception as telemetry_error:
        logger.debug("HTTP in-flight metric unavailable: %s", type(telemetry_error).__name__)
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    except Exception as request_error:
        logger.error(
            "HTTP request failed",
            extra={
                "event": "http_request_failed",
                "method": request.method,
                "route": str(getattr(_route_template(request), "path", "unmatched")),
                "status_code": status_code,
                "error_category": "server_error",
                "error_type": type(request_error).__name__,
            },
        )
        raise
    finally:
        duration_seconds = time.perf_counter() - started
        try:
            record_http_request(
                route=_route_template(request),
                method=request.method,
                status_code=status_code,
                duration_seconds=duration_seconds,
            )
        except Exception as telemetry_error:
            # Metrics are diagnostic only; a registry/exporter failure must not mask the
            # application response or an application exception.
            logger.debug("HTTP metric recording unavailable: %s", type(telemetry_error).__name__)
        if in_flight_recorded:
            try:
                HTTP_REQUESTS_IN_FLIGHT.dec()
            except Exception as telemetry_error:
                logger.debug(
                    "HTTP in-flight metric unavailable: %s", type(telemetry_error).__name__
                )
