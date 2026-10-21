"""WIFIonICE captive-portal client (documented endpoints, no invented APIs).

Verified flows (see README, section "Endpunkte"):

* CNA API (current portal): ``POST {base}/cna/logon`` with JSON ``{}`` and the
  literal header ``X-Csrf-Token: csrf``; logoff via ``POST {base}/cna/logoff``;
  status via ``GET {base}/cna/wifi/user_info``.
* Legacy portal (fallback on HTTP 404): ``GET {base}/de/`` stores a ``csrf``
  cookie, then ``POST {base}/de/`` with ``login=true&CSRFToken=<token>``.
* Onboard ICE portal (only reachable on the train): ``GET {iceportal}/api1/rs/status``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from wifionice_cli import exit_codes as ec
from wifionice_cli.errors import CliError
from wifionice_cli.http_util import HttpClient, form_encode
from wifionice_cli.json_util import parse_json_object
from wifionice_cli.url_util import join_preserve_base_path

_CNA_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "X-Csrf-Token": "csrf",
}
_ACCEPT_MARKER = re.compile(r"""id\s*=\s*["']accept["']""", re.IGNORECASE)
_CSRF_INPUT = re.compile(
    r"""name\s*=\s*["']CSRFToken["'][^>]*value\s*=\s*["']([^"']+)["']""",
    re.IGNORECASE,
)
_SENSITIVE_KEY_PARTS = ("password", "passwd", "secret", "token", "csrf", "credential")


@dataclass
class PortalStatus:
    authenticated: bool
    method: str
    session: dict[str, Any]


def _is_authenticated_flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value == 1
    return str(value).strip().lower() in ("1", "true", "yes", "authenticated")


def _public_session_fields(result: Any) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {}
    public: dict[str, Any] = {}
    for key, value in result.items():
        lowered = str(key).lower()
        if any(part in lowered for part in _SENSITIVE_KEY_PARTS):
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            public[str(key)] = value
    return public


class PortalClient:
    def __init__(
        self,
        base_url: str,
        *,
        iceportal_url: str = "https://iceportal.de",
        timeout: float = 5.0,
        retries: int = 2,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.iceportal_url = iceportal_url.rstrip("/")
        self.http = HttpClient(timeout=timeout, retries=retries)

    def _url(self, *parts: str) -> str:
        return join_preserve_base_path(self.base_url, *parts)

    def cna_status(self) -> PortalStatus | None:
        url = self._url("cna/wifi/user_info")
        payload = self.http.json_request("GET", url, not_found_ok=True)
        if payload is None:
            return None
        result = payload.get("result")
        if not isinstance(result, dict):
            raise CliError(
                f"unexpected user_info payload from {url}",
                code=ec.PARSE,
                details={"keys": sorted(payload.keys())},
            )
        return PortalStatus(
            authenticated=_is_authenticated_flag(result.get("authenticated")),
            method="cna",
            session=_public_session_fields(result),
        )

    def legacy_status(self) -> PortalStatus:
        result = self.http.get_html(self._url("de") + "/")
        return PortalStatus(
            authenticated=_ACCEPT_MARKER.search(result.body) is None,
            method="legacy",
            session={},
        )

    def status(self) -> PortalStatus:
        cna = self.cna_status()
        if cna is not None:
            return cna
        return self.legacy_status()

    def cna_logon(self) -> dict[str, Any] | None:
        url = self._url("cna/logon")
        headers = dict(_CNA_HEADERS, Referer=self._url("cna/"))
        payload = self.http.json_request("POST", url, data=b"{}", headers=headers, not_found_ok=True)
        if payload is None:
            return None
        result = payload.get("result")
        if str(result).strip().lower() != "success":
            raise CliError(
                "portal rejected the checkin (agreement or session not accepted)",
                code=ec.AUTH,
                details={"result": result},
            )
        return payload

    def cna_logoff(self) -> tuple[bool, str | None]:
        """Best-effort CNA logoff. Returns (success, optional warning message)."""
        url = self._url("cna/logoff")
        headers = dict(_CNA_HEADERS, Referer=self._url("cna/"))
        try:
            payload = self.http.json_request(
                "POST", url, data=b"{}", headers=headers, not_found_ok=True
            )
        except CliError as e:
            return False, str(e)
        if payload is None:
            return False, None
        if str(payload.get("result")).strip().lower() == "success":
            return True, None
        return False, "portal rejected the logoff"

    def legacy_login(self) -> dict[str, Any]:
        url = self._url("de") + "/"
        page = self.http.get_html(url)
        csrf = None
        for cookie in self.http.cookies:
            if cookie.name == "csrf":
                csrf = cookie.value
                break
        if not csrf:
            match = _CSRF_INPUT.search(page.body)
            csrf = match.group(1) if match else None
        if not csrf:
            raise CliError(
                f"could not find the portal CSRF token on {url}",
                code=ec.PARSE,
            )
        result = self.http.request(
            "POST",
            url,
            data=form_encode({"login": "true", "CSRFToken": csrf}),
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": url,
            },
        )
        if _ACCEPT_MARKER.search(result.body) is not None:
            raise CliError(
                "portal rejected the checkin (agreement not accepted)",
                code=ec.AUTH,
            )
        return {"result": "success", "method": "legacy"}

    def checkin(self) -> dict[str, Any]:
        cna = self.cna_logon()
        if cna is not None:
            return {"result": cna.get("result"), "method": "cna"}
        return self.legacy_login()

    def iceportal_status(self) -> dict[str, Any]:
        url = join_preserve_base_path(self.iceportal_url, "api1/rs/status")
        result = self.http.request("GET", url, headers={"Accept": "application/json"})
        if not result.body.strip():
            raise CliError(
                "onboard ICE portal returned an empty body (train speed is only available on board)",
                code=ec.PARSE,
                details={"url": url},
            )
        return parse_json_object(result.body, name=f"response from {url}")
