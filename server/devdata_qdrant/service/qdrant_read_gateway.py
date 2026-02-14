"""HTTP gateway for read-only Qdrant requests."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import httpx

from server.settings import get_settings

DEFAULT_TIMEOUT_SECONDS = 60.0


class QdrantGatewayError(Exception):
    """Typed gateway error used by service layer mapping."""

    def __init__(
        self,
        message: str,
        *,
        upstream_status: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.upstream_status = upstream_status
        self.details = details or {}


def _qdrant_base_url() -> str:
    return get_settings().qdrant_url.rstrip("/")


def _qdrant_url(path: str) -> str:
    normalized = path if path.startswith("/") else f"/{path}"
    return f"{_qdrant_base_url()}{normalized}"


def _truncate(value: str, max_len: int = 1500) -> str:
    if len(value) <= max_len:
        return value
    return f"{value[:max_len]}..."


async def _request_json(
    method: str,
    path: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    payload: Optional[Dict[str, Any]] = None,
    timeout_seconds: Optional[float] = None,
) -> Dict[str, Any]:
    timeout = timeout_seconds or DEFAULT_TIMEOUT_SECONDS
    url = _qdrant_url(path)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(method=method, url=url, params=params, json=payload)
    except httpx.TimeoutException as exc:
        raise QdrantGatewayError(
            "Qdrant upstream request timed out",
            details={"timeout_seconds": timeout},
        ) from exc
    except httpx.RequestError as exc:
        raise QdrantGatewayError(
            "Qdrant upstream is unavailable",
            details={"reason": str(exc)},
        ) from exc

    if response.status_code >= 400:
        upstream_body = _truncate(response.text or "")
        raise QdrantGatewayError(
            "Qdrant upstream returned an error response",
            upstream_status=response.status_code,
            details={
                "upstream_status": response.status_code,
                "upstream_body": upstream_body,
                "upstream_url": url,
            },
        )

    try:
        payload_json = response.json()
    except ValueError as exc:
        raise QdrantGatewayError(
            "Qdrant upstream returned invalid JSON",
            upstream_status=response.status_code,
            details={"upstream_url": url},
        ) from exc

    if not isinstance(payload_json, dict):
        raise QdrantGatewayError(
            "Qdrant upstream returned an unexpected payload shape",
            upstream_status=response.status_code,
            details={"payload_type": type(payload_json).__name__},
        )

    return payload_json


async def get_json(
    path: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    timeout_seconds: Optional[float] = None,
) -> Dict[str, Any]:
    return await _request_json("GET", path, params=params, timeout_seconds=timeout_seconds)


async def post_json(
    path: str,
    payload: Dict[str, Any],
    *,
    params: Optional[Dict[str, Any]] = None,
    timeout_seconds: Optional[float] = None,
) -> Dict[str, Any]:
    return await _request_json("POST", path, params=params, payload=payload, timeout_seconds=timeout_seconds)


async def stream_get(
    path: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    timeout_seconds: Optional[float] = None,
) -> Tuple[httpx.Response, httpx.AsyncClient]:
    """Start an upstream stream request and return response + live client."""
    timeout = timeout_seconds or DEFAULT_TIMEOUT_SECONDS
    url = _qdrant_url(path)
    client = httpx.AsyncClient(timeout=timeout)

    try:
        request = client.build_request(method="GET", url=url, params=params)
        response = await client.send(request, stream=True)
    except httpx.TimeoutException as exc:
        await client.aclose()
        raise QdrantGatewayError(
            "Qdrant upstream request timed out",
            details={"timeout_seconds": timeout},
        ) from exc
    except httpx.RequestError as exc:
        await client.aclose()
        raise QdrantGatewayError(
            "Qdrant upstream is unavailable",
            details={"reason": str(exc)},
        ) from exc

    if response.status_code >= 400:
        raw_bytes = await response.aread()
        await response.aclose()
        await client.aclose()

        body_text = _truncate(raw_bytes.decode("utf-8", errors="replace"))
        raise QdrantGatewayError(
            "Qdrant upstream returned an error response",
            upstream_status=response.status_code,
            details={
                "upstream_status": response.status_code,
                "upstream_body": body_text,
                "upstream_url": url,
            },
        )

    return response, client

