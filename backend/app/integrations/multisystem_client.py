"""Small async client for the external multiSystem calculation service."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from app.config import settings


class MultiSystemClientError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        self.status_code = status_code
        super().__init__(message)


class MultiSystemClient:
    def __init__(self) -> None:
        self.base_url = settings.multisystem_base_url.rstrip("/") + "/"
        self.timeout = float(settings.multisystem_timeout_seconds)

    async def start_energy(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await asyncio.to_thread(self._request, "POST", "/simulation/energy/start", payload)

    async def progress(self, simulation_id: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._request, "GET", f"/simulation/energy/progress/{simulation_id}", None)

    async def simple_result(self, simulation_id: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._request, "GET", f"/simulation/energy/result/{simulation_id}", None)

    async def cancel(self, simulation_id: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._request, "POST", f"/simulation/energy/cancel/{simulation_id}", None)

    async def health(self) -> dict[str, Any]:
        return await asyncio.to_thread(self._request, "GET", "/health", None, False)

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None,
        unwrap: bool = True,
    ) -> dict[str, Any]:
        url = urljoin(self.base_url, path.lstrip("/"))
        body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json; charset=utf-8"
        if settings.multisystem_api_key:
            headers["X-API-Key"] = settings.multisystem_api_key
        request = Request(url=url, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
                status_code = response.status
        except HTTPError as exc:
            raw = exc.read()
            detail = self._decode_error(raw, str(exc.reason))
            raise MultiSystemClientError(detail, exc.code) from exc
        except URLError as exc:
            raise MultiSystemClientError(f"multiSystem 服务不可用：{exc.reason}") from exc
        except TimeoutError as exc:
            raise MultiSystemClientError("multiSystem 请求超时") from exc

        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MultiSystemClientError(f"multiSystem 返回了无效 JSON（HTTP {status_code}）", status_code) from exc
        if not isinstance(decoded, dict):
            raise MultiSystemClientError("multiSystem 响应必须是 JSON 对象", status_code)
        if not unwrap or "code" not in decoded:
            return decoded
        code = int(decoded.get("code") or status_code)
        if code != 200:
            raise MultiSystemClientError(str(decoded.get("message") or "multiSystem 请求失败"), code)
        data = decoded.get("data")
        if data is None:
            return {}
        if not isinstance(data, dict):
            raise MultiSystemClientError("multiSystem 响应 data 必须是对象", status_code)
        return data

    @staticmethod
    def _decode_error(raw: bytes, fallback: str) -> str:
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return f"multiSystem 请求失败：{fallback}"
        if isinstance(decoded, dict):
            return str(decoded.get("message") or decoded.get("detail") or fallback)
        return fallback


multisystem_client = MultiSystemClient()