"""HTTP client for Bilibili public web APIs."""

from __future__ import annotations

import time
from typing import Any

import httpx

from bili_analyzer.services.crawler.rate_limiter import RateLimiter

BASE_URL = "https://api.bilibili.com"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


class BiliClientError(RuntimeError):
    """Base error for Bilibili client failures."""


class BiliApiError(BiliClientError):
    def __init__(self, code: int, message: str, url: str) -> None:
        self.code = code
        self.message = message
        self.url = url
        super().__init__(f"Bilibili API error code={code}: {message} ({url})")


class BiliClient:
    def __init__(
        self,
        cookie: str | None = None,
        timeout: float = 10.0,
        retry_times: int = 3,
        rate_limit_interval: float = 0.5,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        headers = {
            "User-Agent": user_agent,
            "Referer": "https://www.bilibili.com/",
            "Accept": "application/json, text/plain, */*",
        }
        if cookie:
            headers["Cookie"] = cookie

        self.retry_times = retry_times
        self.rate_limiter = RateLimiter(rate_limit_interval)
        self._client = httpx.Client(
            base_url=BASE_URL,
            headers=headers,
            timeout=timeout,
            follow_redirects=True,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "BiliClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def get_json(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(self.retry_times + 1):
            self.rate_limiter.wait()
            try:
                response = self._client.get(path, params=params)
                response.raise_for_status()
                payload = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                self._sleep_with_backoff(attempt)
                continue

            code = payload.get("code")
            if code is None or code != 0:
                raise BiliApiError(
                    code if isinstance(code, int) else -1,
                    str(payload.get("message", "unknown error")),
                    str(response.url),
                )
            data = payload.get("data")
            if data is None:
                return {}
            if not isinstance(data, dict):
                return {}
            return data

        raise BiliClientError(
            f"Request failed after {self.retry_times + 1} attempts: {path}"
        ) from last_error

    @staticmethod
    def _sleep_with_backoff(attempt: int) -> None:
        time.sleep(min(2.0**attempt * 0.5, 8.0))

