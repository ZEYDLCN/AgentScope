"""structlog kurulumu — JSON log, trace_id korelasyonu.

Asla loglanmaz: ham prompt içeriği, API anahtarı, tam kullanıcı girdisi
(§21 Güvenlik). Yalnızca redakte önizlemeler loglanabilir.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import MutableMapping
from contextvars import ContextVar
from typing import Any

import structlog

_trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)
_request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def bind_trace_id(trace_id: str | None) -> None:
    _trace_id_var.set(trace_id)


def bind_request_id(request_id: str | None) -> None:
    _request_id_var.set(request_id)


def _add_correlation_ids(
    _logger: object, _method_name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    if (trace_id := _trace_id_var.get()) is not None:
        event_dict.setdefault("trace_id", trace_id)
    if (request_id := _request_id_var.get()) is not None:
        event_dict.setdefault("request_id", request_id)
    return event_dict


def configure_logging(log_level: str = "INFO") -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            _add_correlation_ids,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(component: str) -> structlog.stdlib.BoundLogger:
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(component=component)
    return logger
