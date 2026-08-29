import random
import uuid
from typing import Optional
from urllib.parse import urlparse
import httpcloak
import httpx
from config import PROXY

_PROXY_HOST_SUFFIXES = (".ip.tv",)

def should_use_proxy(url: str) -> bool:
    """Return True only if the request is destined to TMS hosts that block standard IPs."""
    if not PROXY:
        return False
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host in ("localhost", "127.0.0.1", "::1", "0.0.0.0") or host.endswith(".gov.br") or host.endswith(".googleapis.com"):
        return False
    return any(host.endswith(sfx) for sfx in _PROXY_HOST_SUFFIXES)

def _get_browser_context() -> dict:
    """Generate realistic Chrome browser fingerprint headers."""
    chrome_versions = ["124.0.0.0", "125.0.0.0", "126.0.0.0", "127.0.0.0", "128.0.0.0", "129.0.0.0", "130.0.0.0"]
    safari_ver = "537.36"
    platforms = [
        ("Windows NT 10.0; Win64; x64", "Windows", "?0"),
        ("Macintosh; Intel Mac OS X 10_15_7", "macOS", "?0"),
        ("X11; Linux x86_64", "Linux", "?0"),
    ]
    plat, platform_name, mobile = random.choice(platforms)
    chrome_ver = random.choice(chrome_versions)
    major = chrome_ver.split(".")[0]
    ua = f"Mozilla/5.0 ({plat}) AppleWebKit/{safari_ver} (KHTML, like Gecko) Chrome/{chrome_ver} Safari/{safari_ver}"
    sec_ch_ua = f'"Chromium";v="{major}", "Google Chrome";v="{major}", "Not/A)Brand";v="99"'
    return {
        "user-agent": ua,
        "sec-ch-ua": sec_ch_ua,
        "sec-ch-ua-mobile": mobile,
        "sec-ch-ua-platform": f'"{platform_name}"',
    }

def _generate_traceparent() -> tuple[str, str]:
    """Generate W3C App Insights traceparent and request-id."""
    trace_id = uuid.uuid4().hex
    span_id = uuid.uuid4().hex[:16]
    traceparent = f"00-{trace_id}-{span_id}-01"
    request_id = f"|{trace_id}.{span_id}"
    return traceparent, request_id

class HttpCloakClient:
    """Async wrapper for httpcloak session with per-request proxy routing."""

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout
        self.session = httpcloak.Session(preset="chrome-latest", timeout=timeout)
        if PROXY:
            self.proxy_session = httpcloak.Session(
                preset="chrome-latest", timeout=timeout, proxy=PROXY
            )
        else:
            self.proxy_session = None

    def _session_for(self, url: str):
        if self.proxy_session is not None and should_use_proxy(url):
            return self.proxy_session
        return self.session

    def set_default_headers(self, headers: dict):
        """Apply default headers to both sessions."""
        self.session.headers.update(headers)
        if self.proxy_session is not None:
            self.proxy_session.headers.update(headers)

    def set_cookie(self, name: str, value: str, domain: str = ""):
        """Set cookie on both direct and proxy sessions."""
        if not domain:
            self.session.set_cookie(name, value)
            if self.proxy_session is not None:
                self.proxy_session.set_cookie(name, value)
            return
        self.session.set_cookie(name, value, domain=domain)
        if self.proxy_session is not None:
            self.proxy_session.set_cookie(name, value, domain=domain)

    @staticmethod
    def _cookie_value(session, name: str) -> Optional[str]:
        try:
            for c in session.get_cookies():
                if getattr(c, "name", None) == name:
                    return getattr(c, "value", str(c))
        except Exception:
            pass
        return None

    def get_cookie(self, name: str) -> Optional[str]:
        if self.proxy_session is not None:
            val = self._cookie_value(self.proxy_session, name)
            if val:
                return val
        return self._cookie_value(self.session, name)

    def close(self):
        try:
            self.session.close()
        except Exception:
            pass
        if self.proxy_session is not None:
            try:
                self.proxy_session.close()
            except Exception:
                pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.close()

    async def get(self, url: str, headers: Optional[dict] = None, params: Optional[dict] = None):
        return await self._session_for(url).get_async(url, headers=headers, params=params)

    async def post(self, url: str, json: Optional[dict] = None, data: Optional[dict] = None, headers: Optional[dict] = None, params: Optional[dict] = None):
        if data is not None:
            return await self._session_for(url).post_async(url, data=data, headers=headers, params=params)
        return await self._session_for(url).post_async(url, json_data=json, headers=headers, params=params)

    async def put(self, url: str, json: Optional[dict] = None, headers: Optional[dict] = None, params: Optional[dict] = None):
        return await self._session_for(url).put_async(url, json_data=json, headers=headers, params=params)

    async def patch(self, url: str, json: Optional[dict] = None, headers: Optional[dict] = None, params: Optional[dict] = None):
        return await self._session_for(url).request_async("PATCH", url, json_data=json, headers=headers, params=params)

class RoutingAsyncClient(httpx.AsyncClient):
    """Async HTTP client for external APIs like Google Firebase / Firestore."""
    def __init__(self, timeout: float = 30.0, **kwargs):
        super().__init__(timeout=timeout, follow_redirects=True, **kwargs)

