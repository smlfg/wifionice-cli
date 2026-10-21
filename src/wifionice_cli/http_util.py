"""Minimal stdlib HTTP client that maps transport failures to CliError."""

from __future__ import annotations

import http.cookiejar
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from wifionice_cli import exit_codes as ec
from wifionice_cli.errors import CliError
from wifionice_cli.json_util import parse_json_object


@dataclass
class HttpResult:
    status: int
    url: str
    body: str
    headers: dict[str, str]


class HttpClient:
    """Follows redirects and keeps cookies; raises CliError(3) on transport failure."""

    def __init__(self, timeout: float = 5.0, *, retries: int = 2) -> None:
        self.timeout = timeout
        self.retries = max(1, retries)
        self.cookies = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookies),
        )

    def request(
        self,
        method: str,
        url: str,
        *,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
        accept_status: tuple[int, ...] = (200,),
    ) -> HttpResult:
        last: CliError | None = None
        for attempt in range(self.retries):
            try:
                return self._request_once(
                    method,
                    url,
                    data=data,
                    headers=headers,
                    accept_status=accept_status,
                )
            except CliError as e:
                if e.code != ec.NETWORK or attempt + 1 >= self.retries:
                    raise
                last = e
        raise last  # pragma: no cover

    def _request_once(
        self,
        method: str,
        url: str,
        *,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
        accept_status: tuple[int, ...] = (200,),
    ) -> HttpResult:
        req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
        try:
            with self._opener.open(req, timeout=self.timeout) as resp:
                result = HttpResult(
                    status=resp.status,
                    url=resp.geturl(),
                    body=resp.read().decode("utf-8", errors="replace"),
                    headers={k.lower(): v for k, v in resp.headers.items()},
                )
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")
            except OSError:
                pass
            result = HttpResult(
                status=e.code,
                url=url,
                body=body,
                headers={k.lower(): v for k, v in (e.headers or {}).items()},
            )
        except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as e:
            raise CliError(
                f"cannot reach {url}",
                code=ec.NETWORK,
                details={"reason": str(e)},
            ) from e

        if result.status in accept_status:
            return result
        if result.status in (401, 403):
            raise CliError(
                f"portal denied the request (HTTP {result.status})",
                code=ec.AUTH,
                details={"url": url, "status": result.status},
            )
        raise CliError(
            f"unexpected HTTP {result.status} from {url}",
            code=ec.NETWORK,
            details={"url": url, "status": result.status},
        )

    def json_request(
        self,
        method: str,
        url: str,
        *,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
        not_found_ok: bool = False,
    ) -> dict[str, Any] | None:
        accept = (200, 404) if not_found_ok else (200,)
        result = self.request(method, url, data=data, headers=headers, accept_status=accept)
        if result.status == 404:
            return None
        return parse_json_object(result.body, name=f"response from {url}")

    def get_html(self, url: str) -> HttpResult:
        return self.request("GET", url, headers={"Accept": "text/html"})


def form_encode(fields: dict[str, str]) -> bytes:
    return urllib.parse.urlencode(fields).encode("ascii")
