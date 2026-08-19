# SUSESI Hotel Wi-Fi Helper

A lightweight, internal network microservice designed to provide a deterministic connection and captive portal recovery workflow for hotel guests connecting to the open `SUSESI` Wi-Fi network.

---

## The Problem & Solution

### The Problem
On the open `SUSESI` Wi-Fi network, the MikroTik HotSpot captive portal and ProSpot authentication flow work correctly. However, certain mobile operating systems and browsers (due to aggressive Captive Network Assistant heuristics, private MAC addresses, or background app switching) fail to automatically trigger the captive portal login popup upon association.

Guests assume the Wi-Fi is broken and contact Reception or IT.

### The Solution: Deterministic Two-QR Code Workflow
Room TVs display two clear QR codes:

1. **QR #1 — Wi-Fi Network Setup**:
   ```text
   WIFI:T:nopass;S:SUSESI;;
   ```
   *Action:* Automatically associates the guest's device with the `SUSESI` open SSID and acquires a DHCP IP (subnet `10.1.0.0/16`).

2. **QR #2 — Internet Login Trigger**:
   ```text
   http://<HELPER_IP_OR_HOST>:8080/wifi?room=342
   # or with HTTPS: https://wifi.susesihotel.com/wifi?room=342
   ```
   *Action:* Opens the browser to the Wi-Fi Helper. The Helper verifies that the MikroTik HotSpot login gateway is healthy, and serves a branded connect page with a prominent **"İnternete Bağlan"** button linking directly to `http://10.1.3.1/login`.

---

## Experimental Hypothesis: Android Chrome HTTP Warning

### The Observed Behavior
During physical Android testing, manually navigating or redirecting to `http://10.1.3.1/login` caused Chrome to display a security warning (*"The site ahead is not secure"* / *"Connection is not private"*) because the captive portal gateway endpoint is plain HTTP. The guest had to tap *"Continue to site"* to reach ProSpot.

### The Experimental Test Flow
To test whether a user-initiated navigation provides a lower-friction guest experience than an automated 302 redirect:
1. QR #2 directs the guest to the Wi-Fi Helper.
2. The Helper serves a clean, branded landing page (`connect.html`).
3. The guest explicitly taps the primary button: **"İnternete Bağlan"** (`<a href="http://10.1.3.1/login">`).
4. **Important:** This is treated as an **experimental hypothesis** and must be validated on physical Android hardware. We do not assume this will completely bypass browser security prompts. If the warning persists, the page includes clear micro-guidance in 4 languages (*"If your browser shows a security prompt, tap 'Continue' to open the login page"*), keeping the prompt as a known platform limitation.

---

## Core Architecture & Network Flow

```text
+-----------------------+
|  Room TV (QR Codes)   |
+-----------------------+
   | (QR #1: Connect)
   v
+-----------------------+
|  SUSESI Open Wi-Fi    |  ---> Guest receives DHCP IP (e.g., 10.1.29.47)
+-----------------------+
   | (QR #2: Scan Login URL)
   v
+-----------------------+
|  Wi-Fi Helper Server  |  ---> 1. Extracts client IP (socket connection)
|  (Hotel LAN / Docker) |       2. Sanitizes room parameter
+-----------------------+       3. Server-side async probe to http://10.1.3.1/login
   |                                 |
   | [If MikroTik Healthy]           | [If MikroTik Unreachable / Error]
   v                                 v
+--------------------------------+   +---------------------------------------------+
| Branded Connect Page           |   | Self-contained Multilingual Error Page      |
| [ İnternete Bağlan ] Button    |   | + Structured JSON Failure Log (stdout)      |
| -> http://10.1.3.1/login       |   +---------------------------------------------+
+--------------------------------+
   | (Guest taps button)
   v
+-----------------------+
| MikroTik HotSpot      |  ---> Redirects guest to ProSpot portal
| (10.1.3.1/login)      |
+-----------------------+
   |
   v
+-----------------------+
| ProSpot Login System  |  ---> Guest enters password & authenticates
| (login.prospot.online)|
+-----------------------+
   |
   v
+-----------------------+
| Internet Access       |
+-----------------------+
```

---

## Diagnostic Boundaries & Capabilities

### What Reaching the Helper Proves:
- The guest device has associated with the Wi-Fi network.
- The device received a valid, routable IP address from DHCP (`10.1.0.0/16`).
- The pre-authentication path from the guest subnet to the Helper server is functional (Walled Garden routing).

### What It Does NOT Prove:
- It does **not** guarantee that the guest device can directly reach `http://10.1.3.1/login` (the Helper's probe is a separate server-side test of gateway reachability).
- It does **not** inspect physical RF conditions (RSSI, SNR, 2.4 vs 5 GHz).
- It does **not** inspect device internal adapter state or physical MAC address (due to mobile MAC randomization and L3 routing).

---

## Failure-Only Logging Principle

- **Successful Connections:** Fast HTTP 302 redirect. **No alerts or failure logs are generated.**
- **Failures (MikroTik Down / Timeout / 5xx):** A structured JSON event is written to `stdout` for ingestion by centralized logging tools.

### Example Structured Failure Log:
```json
{
  "timestamp": "2026-08-18T13:45:00.123456+00:00",
  "level": "ERROR",
  "event": "mikrotik_probe_failed",
  "client_ip": "10.1.29.47",
  "room": "342",
  "error_type": "timeout",
  "error_message": "Probe timed out after 1.5s: Request timed out",
  "status_code": null,
  "probe_duration_ms": 1502.4,
  "target_url": "http://10.1.3.1/login",
  "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"
}
```

---

## Quick Start & Local Development

### 1. Requirements
- Docker & Docker Compose **or** Python 3.12+

### 2. Running with Docker Compose (Recommended)
```bash
# Clone the repository
git clone https://github.com/i1k3r/wifi-helper.git
cd wifi-helper

# Build and start the container
docker compose up -d --build

# View container logs
docker compose logs -f
```

The service will be accessible on `http://localhost:8080/wifi`.

### 3. Running Locally with Python
```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start development server
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

---

## Container Image / GHCR

The application is automatically built and published to GitHub Container Registry on every push to `main`:

```text
ghcr.io/i1k3r/wifi-helper:latest
```

### TrueNAS SCALE Custom App Deployment
This pre-built GHCR image can be used directly when deploying a **Custom App** in TrueNAS SCALE:
- **Image repository:** `ghcr.io/i1k3r/wifi-helper`
- **Image tag:** `latest` (or a specific commit SHA tag)
- **Port mapping:** Host port `8080` (bound to `10.1.11.126`) -> Container port `8080`
- **Environment variables:** Configured as needed matching the `.env.example` schema.

---

## Running Automated Tests

Run the complete test suite using `pytest`:

```bash
# Inside virtual environment
pytest -v

# Or using Docker
docker run --rm -v $(pwd):/app -w /app python:3.12-slim bash -c "pip install -r requirements.txt && pytest -v"
```

---

## Configuration Reference

Configuration is managed via environment variables or a `.env` file:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `HOST` | `0.0.0.0` | Bind IP address |
| `PORT` | `8080` | Bind port |
| `MIKROTIK_LOGIN_URL` | `http://10.1.3.1/login` | Destination HotSpot URL for HTTP 302 redirect |
| `MIKROTIK_PROBE_URL` | `http://10.1.3.1/login` | Endpoint tested by the async HTTP GET probe |
| `PROBE_TIMEOUT_SECONDS` | `1.5` | Probe timeout threshold |
| `TRUST_PROXY_HEADERS` | `false` | When `false`, client IP is taken from direct socket |
| `LOG_LEVEL` | `INFO` | Logging level |

---

## Documentation

- [System Architecture](docs/ARCHITECTURE.md) — Detailed design, component breakdown, and probe mechanics.
- [Network Flow](docs/NETWORK_FLOW.md) — Step-by-step packet flow, IP addressing, and client transitions.
- [MikroTik Walled Garden Setup](docs/WALLED_GARDEN.md) — Configuration guide for RouterOS Walled Garden entries.
