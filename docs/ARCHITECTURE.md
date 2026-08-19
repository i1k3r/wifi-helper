# System Architecture

## Overview
The **SUSESI Hotel Wi-Fi Helper** acts as an intermediary bridge between a guest scanning QR #2 on their room TV and the hotel's existing MikroTik HotSpot login gateway (`http://10.1.3.1/login`).

The helper does **not** replace MikroTik HotSpot or ProSpot authentication, does **not** proxy guest credentials, and does **not** perform RouterOS configuration changes. Its purpose is deterministic reachability, failure observability, and providing a controlled user experience.

---

## Component Diagram

```text
  +-------------------------------------------------------------------------+
  |                           GUEST ROOM TV                                 |
  |  [ QR #1: WIFI:T:nopass;S:SUSESI;; ]   [ QR #2: https://<HOST>/wifi ]   |
  +-------------------------------------------------------------------------+
                                 |
                                 | (QR #2 scanned by guest phone)
                                 v
  +-------------------------------------------------------------------------+
  |                   WI-FI HELPER MICROSERVICE (HTTPS)                     |
  |                                                                         |
  |  +---------------------+   +---------------------+   +---------------+  |
  |  |  Socket IP Extractor|   | Room Sanitizer      |   | /health       |  |
  |  |  (Direct TCP Host)  |   | (^[a-zA-Z0-9_-]+$)  |   | (Lightweight) |  |
  |  +---------------------+   +---------------------+   +---------------+  |
  |                                |                                        |
  |                                v                                        |
  |  +-------------------------------------------------------------------+  |
  |  |                      Async HTTP GET Probe                         |  |
  |  |  Target: http://10.1.3.1/login                                    |  |
  |  |  Timeout: 1.5s | User-Agent: Browser | Follow Redirects: False    |  |
  |  +-------------------------------------------------------------------+  |
  |            |                                            |               |
  |            | (Healthy: 2xx, 3xx, 401)                   | (Unhealthy)   |
  |            v                                            v               |
  |  +-----------------------------------+  +----------------------------+  |
  |  | Experimental Connect Page (200 OK)|  | 1. Log Structured JSON     |  |
  |  | User Button: [İnternete Bağlan]   |  | 2. Render Offline Error UI |  |
  |  | Target: http://10.1.3.1/login     |  |    (EN, TR, RU, DE)        |  |
  |  | (No auto/JS redirect, no proxy)   |  +----------------------------+  |
  |  +-----------------------------------+                                  |
  +-------------------------------------------------------------------------+
               | (User taps "İnternete Bağlan" button)
               v
  +-------------------------------------------------------------------------+
  |                        MIKROTIK HOTSPOT GATEWAY                         |
  |                        (IP: 10.1.3.1, Interface: ether2)                |
  +-------------------------------------------------------------------------+
               |
               v
  +-------------------------------------------------------------------------+
  |                        PROSPOT CLOUD LOGIN PORTAL                       |
  |                        (http://login.prospot.online/...)                |
  +-------------------------------------------------------------------------+
```

---

## Experimental Hypothesis: Android Chrome HTTP Warning

### 1. Real-World Observed Behavior
In validated testing on a physical Android device, opening `http://10.1.3.1/login` directly causes Android Chrome to display an HTTP security warning:
> *"The site ahead is not secure"* / *"Connection is not private"*

The user must tap **"Advanced" → "Continue to site"** to reach the ProSpot login screen.

### 2. Experimental Test: User-Initiated Navigation
The Helper implements a minimal, controlled test for this behavior:
1. **HTTPS Helper Page:** Guest scans QR #2 to land on a secure HTTPS Helper page.
2. **User-Initiated Button:** The page displays a large button: **"İnternete Bağlan"** (with multilingual options).
3. **Button Target:** Direct standard HTML link `<a href="http://10.1.3.1/login" class="connect-btn">`.
4. **No Automated Redirect:** No HTTP 302/307 redirect, no JavaScript `location.href` or `window.open` trigger.
5. **No Proxying / No URL Fabrication:** The Helper does not proxy the page or fabricate ProSpot session URLs.

### 3. Hypothesis & Evaluation Protocol
- **Hypothesis:** Does initiating the navigation via an explicit user click on a top-level link reduce or alter the Chrome security warning compared to an automated 302 redirect?
- **Testing Requirement:** This **must be tested on a physical Android device** connected to the real SUSESI network.
- **Handling Persistent Warnings:** If Android Chrome still presents the security interstitial on click:
  - We do **not** attempt to bypass browser security.
  - The warning is documented as a known platform constraint of plain HTTP captive portals.
  - The in-page micro-guidance (*"Tap 'Advanced' → 'Continue to site' to complete hotel login"*) provides reassuring instructions to minimize guest confusion.

---

## Detailed Probe Mechanics

### 1. HTTP Method: `GET` (Not `HEAD`)
- Production testing confirmed that `curl -I http://10.1.3.1/login` (HTTP `HEAD`) returns `503 Service Unavailable` on MikroTik's embedded HotSpot servlet.
- The Helper strictly executes an asynchronous **HTTP `GET`** request with standard browser headers (`Accept: text/html...`, `User-Agent: Mozilla...`).

### 2. Status Code Interpretation
- **`200 OK`**: The HotSpot login HTML page is actively served. Marked **Healthy**.
- **`302 Found` / `307 Temporary Redirect`**: The HotSpot servlet is immediately issuing a redirect (e.g. to the ProSpot cloud URL). Marked **Healthy**.
- **`401 Unauthorized`**: The HotSpot servlet is acknowledging authentication requirements. Marked **Healthy**.
- **`5xx Server Error`**: HotSpot daemon or upstream handler is crashing or out of resources. Marked **Unhealthy** (`error_type: http_5xx`).
- **Connection Refused / Network Unreachable**: Marked **Unhealthy** (`error_type: connection_error`).
- **Timeout (>1.5s)**: Marked **Unhealthy** (`error_type: timeout`).

---

## Caching Strategy
To ensure that mobile browsers never cache the helper responses and always perform fresh checks:
- All dynamic responses attach anti-caching headers:
  ```http
  Cache-Control: no-store, no-cache, must-revalidate, max-age=0
  Pragma: no-cache
  Expires: 0
  ```

---

## Client IP & Privacy Handling
- Client IP is obtained directly from the TCP socket (`request.client.host`).
- Headers like `X-Forwarded-For` are ignored by default (`TRUST_PROXY_HEADERS=false`) to avoid spoofing.
- No guest credentials, MAC addresses, or personal browsing history are logged or inspected.
