"""Polite, cached, retrying client for the public Overpass API.

Design goals: never re-download what is already on disk, never hammer the shared server
(minimum interval between requests, exponential backoff on 429/5xx, honour Retry-After),
and never treat a runtime-error response as data.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

import httpx

from pipelines.geo import BBox
from pipelines.osm_config import Selector

logger = logging.getLogger(__name__)

DEFAULT_URL = "https://overpass-api.de/api/interpreter"
DEFAULT_USER_AGENT = "SiteScout-MVP/0.1 (personal hackathon project; low volume; cached)"
RETRYABLE_STATUS = frozenset({429, 502, 503, 504})


class OverpassError(RuntimeError):
    """Raised when Overpass cannot return usable data after all retries."""


def build_query(
    selectors: Iterable[Selector],
    bbox: BBox,
    *,
    timeout_s: int = 180,
    geometry: bool = False,
) -> str:
    """Build an Overpass QL query for nodes, ways and relations matching any selector.

    Args:
        selectors: tag filters; an element matching any of them is returned.
        bbox: the search box.
        timeout_s: server-side timeout in seconds.
        geometry: if True return full geometry (``out geom``), else centres (``out center``).
    """
    lines = [f"nwr{s.overpass()}({bbox.overpass()});" for s in selectors]
    if not lines:
        raise ValueError("at least one selector is required")
    out = "out geom tags;" if geometry else "out center tags;"
    return f"[out:json][timeout:{timeout_s}];\n(\n  " + "\n  ".join(lines) + f"\n);\n{out}"


def cache_name(label: str, query: str) -> str:
    """File name for a cached response: readable label plus a hash of the exact query."""
    digest = hashlib.sha1(query.encode("utf-8"), usedforsecurity=False).hexdigest()[:10]
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in label)
    return f"{safe}-{digest}.json"


class OverpassClient:
    """Fetch Overpass JSON with on-disk caching, pacing and bounded retries."""

    def __init__(
        self,
        cache_dir: Path,
        *,
        url: str = DEFAULT_URL,
        min_interval_s: float = 8.0,
        request_timeout_s: float = 300.0,
        max_attempts: int = 6,
        backoff_base_s: float = 20.0,
        user_agent: str = DEFAULT_USER_AGENT,
        http_client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._cache_dir = cache_dir
        self._url = url
        self._min_interval_s = min_interval_s
        self._max_attempts = max_attempts
        self._backoff_base_s = backoff_base_s
        self._client = http_client or httpx.Client(
            timeout=request_timeout_s, headers={"User-Agent": user_agent}
        )
        self._sleep = sleep
        self._clock = clock
        self._last_request_at: float | None = None

    def fetch(self, label: str, query: str) -> dict[str, Any]:
        """Return the parsed JSON for ``query``, from cache when available.

        Raises:
            OverpassError: after ``max_attempts`` failed attempts or on a runtime-error remark.
        """
        path = self._cache_dir / cache_name(label, query)
        if path.exists():
            logger.info("overpass cache hit: %s", path.name)
            return _read_json(path)

        payload = self._request_with_retries(label, query)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        tmp.replace(path)  # atomic: a crash never leaves a half-written cache file
        return payload

    def _pace(self) -> None:
        if self._last_request_at is not None:
            wait = self._min_interval_s - (self._clock() - self._last_request_at)
            if wait > 0:
                self._sleep(wait)
        self._last_request_at = self._clock()

    def _request_with_retries(self, label: str, query: str) -> dict[str, Any]:
        last_error = "no attempt made"
        for attempt in range(1, self._max_attempts + 1):
            self._pace()
            try:
                response = self._client.post(self._url, data={"data": query})
            except httpx.HTTPError as exc:
                last_error = f"{type(exc).__name__}: {exc}"
            else:
                if response.status_code == 200:
                    payload = _parse_payload(response)
                    remark = str(payload.get("remark", ""))
                    if "runtime error" in remark or "timed out" in remark:
                        last_error = f"server remark: {remark}"
                    else:
                        return payload
                elif response.status_code in RETRYABLE_STATUS:
                    last_error = f"HTTP {response.status_code}"
                    retry_after = _retry_after_s(response)
                    if retry_after is not None:
                        self._sleep(retry_after)
                else:
                    raise OverpassError(
                        f"{label}: HTTP {response.status_code}: {response.text[:200]}"
                    )
            if attempt < self._max_attempts:
                backoff = self._backoff_base_s * 2 ** (attempt - 1)
                logger.warning(
                    "overpass %s attempt %d failed (%s); waiting %.0fs",
                    label,
                    attempt,
                    last_error,
                    backoff,
                )
                self._sleep(backoff)
        raise OverpassError(f"{label}: gave up after {self._max_attempts} attempts ({last_error})")


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise OverpassError(f"cache file {path} does not contain a JSON object")
    return data


def _parse_payload(response: httpx.Response) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError as exc:
        raise OverpassError(f"response was not JSON: {response.text[:200]}") from exc
    if not isinstance(data, dict):
        raise OverpassError("response JSON was not an object")
    return data


def _retry_after_s(response: httpx.Response) -> float | None:
    value = response.headers.get("Retry-After")
    if value is None:
        return None
    try:
        return max(0.0, min(float(value), 300.0))
    except ValueError:
        return None
