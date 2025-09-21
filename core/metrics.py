from __future__ import annotations

import logging
import time

logger = logging.getLogger("metrics")

_COUNTERS: dict[str, int] = {}
_HIST: dict[str, list[float]] = {}


def inc(name: str, amount: int = 1, **labels) -> None:
    key = _key(name, labels)
    _COUNTERS[key] = _COUNTERS.get(key, 0) + int(amount)
    try:
        logger.info(
            "metric.counter", extra={"metric": name, "value": _COUNTERS[key], "labels": labels}
        )
    except Exception:
        pass


def observe(name: str, value: float, **labels) -> None:
    key = _key(name, labels)
    _HIST.setdefault(key, []).append(float(value))
    try:
        logger.info("metric.histogram", extra={"metric": name, "value": value, "labels": labels})
    except Exception:
        pass


class timer:
    def __init__(self, name: str, **labels) -> None:
        self.name = name
        self.labels = labels
        self._t0: float | None = None

    def __enter__(self):
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._t0 is None:
            return False
        dt = time.perf_counter() - self._t0
        observe(self.name, dt, **self.labels)
        return False


def _key(name: str, labels: dict[str, object]) -> str:
    if not labels:
        return name
    try:
        parts = [name] + [f"{k}={labels[k]}" for k in sorted(labels.keys())]
        return ":".join(parts)
    except Exception:
        return name
