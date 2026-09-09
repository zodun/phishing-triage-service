from __future__ import annotations

import logging
import sys

import structlog
from prometheus_client import Counter, Histogram

REQUESTS = Counter("answer_requests_total", "Answer requests by outcome", ["outcome"])
LATENCY = Histogram(
    "answer_latency_seconds",
    "End-to-end /v1/answer latency",
    buckets=(0.1, 0.25, 0.5, 1, 2, 4, 8, 16),
)
GUARD_TRIPS = Counter("guardrail_trips_total", "Guardrail trips", ["stage", "code"])
TOKENS = Counter("model_tokens_total", "Model tokens consumed", ["model", "kind"])


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level.upper())
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level.upper())),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "app") -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
