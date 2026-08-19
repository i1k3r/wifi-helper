"""MikroTik HotSpot health check probe service."""

import time
from dataclasses import dataclass
from typing import Optional
import httpx


@dataclass
class ProbeResult:
    """Result data structure for MikroTik gateway health probe."""
    is_healthy: bool
    status_code: Optional[int] = None
    duration_ms: float = 0.0
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    target_url: str = ""


async def check_mikrotik_health(
    client: httpx.AsyncClient,
    probe_url: str,
    timeout_seconds: float = 1.5,
) -> ProbeResult:
    """
    Perform a server-side health check against the MikroTik HotSpot login servlet.
    
    IMPORTANT:
    1. This probe must use HTTP GET, NOT HEAD. (MikroTik HotSpot returns 503 on HEAD).
    2. A successful response confirms the Helper can reach the MikroTik gateway HTTP service.
       It does NOT guarantee the guest's local Wi-Fi link or DHCP lease, but ensures the
       authentication infrastructure is responsive before redirecting.
    3. Status codes 2xx, 3xx, 401 are considered healthy (HotSpot daemon active & responding).
       Status codes 5xx, timeouts, connection refused, or network drops are marked unhealthy.
    """
    start_time = time.monotonic()
    
    try:
        # Standard browser headers to ensure transparent response from MikroTik servlet
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        
        # We do not follow redirects because a 302/307 from MikroTik (e.g. to ProSpot or /login)
        # already proves that the HotSpot servlet is up and responding.
        response = await client.get(
            probe_url,
            timeout=timeout_seconds,
            headers=headers,
            follow_redirects=False,
        )
        
        duration_ms = round((time.monotonic() - start_time) * 1000, 2)
        status_code = response.status_code

        # 2xx, 3xx, 401 are healthy responses from HotSpot gateway
        if 200 <= status_code < 400 or status_code == 401:
            return ProbeResult(
                is_healthy=True,
                status_code=status_code,
                duration_ms=duration_ms,
                target_url=probe_url,
            )
        elif status_code >= 500:
            return ProbeResult(
                is_healthy=False,
                status_code=status_code,
                duration_ms=duration_ms,
                error_type="http_5xx",
                error_message=f"MikroTik returned server error status HTTP {status_code}",
                target_url=probe_url,
            )
        else:
            # Other 4xx status codes (e.g. 404 Not Found if path is misconfigured)
            return ProbeResult(
                is_healthy=False,
                status_code=status_code,
                duration_ms=duration_ms,
                error_type=f"http_{status_code}",
                error_message=f"MikroTik returned unexpected status HTTP {status_code}",
                target_url=probe_url,
            )

    except httpx.TimeoutException as exc:
        duration_ms = round((time.monotonic() - start_time) * 1000, 2)
        return ProbeResult(
            is_healthy=False,
            status_code=None,
            duration_ms=duration_ms,
            error_type="timeout",
            error_message=f"Probe timed out after {timeout_seconds}s: {str(exc) or 'Request timed out'}",
            target_url=probe_url,
        )

    except httpx.ConnectError as exc:
        duration_ms = round((time.monotonic() - start_time) * 1000, 2)
        return ProbeResult(
            is_healthy=False,
            status_code=None,
            duration_ms=duration_ms,
            error_type="connection_error",
            error_message=f"Failed to connect to MikroTik gateway: {str(exc) or 'Connection refused'}",
            target_url=probe_url,
        )

    except httpx.NetworkError as exc:
        duration_ms = round((time.monotonic() - start_time) * 1000, 2)
        return ProbeResult(
            is_healthy=False,
            status_code=None,
            duration_ms=duration_ms,
            error_type="network_error",
            error_message=f"Network error during probe: {str(exc)}",
            target_url=probe_url,
        )

    except Exception as exc:
        duration_ms = round((time.monotonic() - start_time) * 1000, 2)
        return ProbeResult(
            is_healthy=False,
            status_code=None,
            duration_ms=duration_ms,
            error_type="unknown_error",
            error_message=f"Unexpected probe error: {str(exc)}",
            target_url=probe_url,
        )
