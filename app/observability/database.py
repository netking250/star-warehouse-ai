"""Low-cardinality SQLAlchemy database metrics without statement or parameter logging."""

from __future__ import annotations

import logging
import re
import time
from functools import partial
from typing import cast

from sqlalchemy import event
from sqlalchemy.engine import Connection, Engine

from app.observability.metrics import (
    adjust_database_connections_in_use,
    record_database_connection_error,
    record_database_query_duration,
)

logger = logging.getLogger(__name__)

_QUERY_STACK_KEY = "t17_database_query_stack"
_INSTRUMENTED_ENGINES: set[int] = set()
_STATEMENT_OPERATION_PATTERN = re.compile(r"^([A-Za-z]+)")
_KNOWN_OPERATIONS = frozenset({"SELECT", "INSERT", "UPDATE", "DELETE", "COMMIT"})


def _engine_role(engine: Engine) -> str:
    """Return a bounded role label for an async or sync SQLAlchemy engine."""
    return "async" if bool(getattr(engine.dialect, "is_async", False)) else "sync"


def _statement_operation(statement: object) -> str:
    """Extract only a bounded SQL verb; never retain statement text."""
    if not isinstance(statement, str):
        return "OTHER"
    match = _STATEMENT_OPERATION_PATTERN.match(statement.lstrip())
    operation = match.group(1).upper() if match is not None else "OTHER"
    return operation if operation in _KNOWN_OPERATIONS else "OTHER"


def _query_stack(connection: Connection) -> list[tuple[float, str]]:
    """Return the per-connection nested query timing stack."""
    value = connection.info.get(_QUERY_STACK_KEY)
    if isinstance(value, list):
        return cast(list[tuple[float, str]], value)
    stack: list[tuple[float, str]] = []
    connection.info[_QUERY_STACK_KEY] = stack
    return stack


def _record_query_duration(connection: Connection) -> None:
    """Pop and record one query duration while isolating telemetry failures."""
    stack = _query_stack(connection)
    if not stack:
        return
    started, operation = stack.pop()
    try:
        record_database_query_duration(
            engine=_engine_role(connection.engine),
            operation=operation,
            duration_seconds=time.perf_counter() - started,
        )
    except Exception as telemetry_error:
        logger.debug(
            "Database query metric unavailable: %s",
            type(telemetry_error).__name__,
        )


def _before_cursor_execute(
    connection: Connection,
    cursor: object,
    statement: str,
    parameters: object,
    context: object,
    executemany: bool,
) -> None:
    """Start a bounded timer without logging SQL or bind values."""
    del cursor, parameters, context, executemany
    _query_stack(connection).append((time.perf_counter(), _statement_operation(statement)))


def _after_cursor_execute(
    connection: Connection,
    cursor: object,
    statement: str,
    parameters: object,
    context: object,
    executemany: bool,
) -> None:
    """Finish one successful statement timer."""
    del cursor, statement, parameters, context, executemany
    _record_query_duration(connection)


def _handle_error(exception_context: object) -> None:
    """Record a bounded database error and close any active statement timer."""
    connection = getattr(exception_context, "connection", None)
    if isinstance(connection, Connection):
        _record_query_duration(connection)
    original_exception = getattr(exception_context, "original_exception", None)
    is_disconnect = bool(getattr(exception_context, "is_disconnect", False))
    error_name = type(original_exception).__name__.lower()
    category = "connection" if is_disconnect else "query"
    if "timeout" in error_name or "deadline" in error_name:
        category = "timeout"
    try:
        engine = (
            _engine_role(connection.engine) if isinstance(connection, Connection) else "unknown"
        )
        record_database_connection_error(engine=engine, category=category)
    except Exception as telemetry_error:
        logger.debug(
            "Database error metric unavailable: %s",
            type(telemetry_error).__name__,
        )


def _on_pool_checkout(
    dbapi_connection: object,
    connection_record: object,
    connection_proxy: object,
    *,
    engine: str,
) -> None:
    """Record one checked-out pooled connection."""
    del dbapi_connection, connection_record, connection_proxy
    try:
        adjust_database_connections_in_use(engine=engine, delta=1)
    except Exception as telemetry_error:
        logger.debug(
            "Database pool metric unavailable: %s",
            type(telemetry_error).__name__,
        )


def _on_pool_checkin(
    dbapi_connection: object,
    connection_record: object,
    *,
    engine: str,
) -> None:
    """Record one returned pooled connection."""
    del dbapi_connection, connection_record
    try:
        adjust_database_connections_in_use(engine=engine, delta=-1)
    except Exception as telemetry_error:
        logger.debug(
            "Database pool metric unavailable: %s",
            type(telemetry_error).__name__,
        )


def _on_pool_invalidate(
    dbapi_connection: object,
    connection_record: object,
    exception: BaseException | None,
    *,
    engine: str,
) -> None:
    """Record a pool invalidation as a bounded connection failure."""
    del dbapi_connection, connection_record, exception
    try:
        record_database_connection_error(engine=engine, category="connection")
    except Exception as telemetry_error:
        logger.debug(
            "Database connection metric unavailable: %s",
            type(telemetry_error).__name__,
        )


def setup_database_observability(*engines: Engine) -> None:
    """Install aggregate SQL and pool metrics on the supplied application engines once."""
    for engine in engines:
        engine_id = id(engine)
        if engine_id in _INSTRUMENTED_ENGINES:
            continue
        role = _engine_role(engine)
        event.listen(engine, "before_cursor_execute", _before_cursor_execute)
        event.listen(engine, "after_cursor_execute", _after_cursor_execute)
        event.listen(engine, "handle_error", _handle_error)
        event.listen(
            engine.pool,
            "checkout",
            partial(_on_pool_checkout, engine=role),
        )
        event.listen(
            engine.pool,
            "checkin",
            partial(_on_pool_checkin, engine=role),
        )
        event.listen(
            engine.pool,
            "invalidate",
            partial(_on_pool_invalidate, engine=role),
        )
        _INSTRUMENTED_ENGINES.add(engine_id)
