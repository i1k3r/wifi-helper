# Physical Android Device Testing Guide

## Purpose
This document specifies the exact protocol for testing the **HTTPS Helper → User-Click → HTTP MikroTik** experimental hypothesis on physical Android devices connected to the SUSESI hotel network.

---

## Known Real-World Baseline
On a physical Android smartphone connected to `SUSESI` Wi-Fi:
- Scanning or navigating directly to `http://10.1.3.1/login` triggers an **Android Chrome Security Warning** (*"The site ahead is not secure"* / *"Connection is not private"*).
- Tapping **"Advanced" → "Continue to site"** successfully opens the ProSpot login portal and allows normal guest authentication.

---

## Experimental Hypothesis to Validate
**Hypothesis:** Does navigating from an HTTPS Helper landing page via an explicit user click on a large **"İnternete Bağlan"** button alter or reduce the security warning compared to direct HTTP navigation or automatic 302 redirection?

---

## Test Setup & Requirements

1. **Physical Devices Required:**
   - 1x Android device running a modern Chrome version (Android 12, 13, or 14).
   - (Optional) 1x iOS device running Safari for comparison.
2. **Network Connection:**
   - Connected to open `SUSESI` SSID (unauthenticated).
   - Obtains IP in `10.1.0.0/16`.
3. **Wi-Fi Helper Server:**
   - Running with `AUTO_REDIRECT=false` (Default).
   - Reachable via Walled Garden.

---

## Step-by-Step Test Procedure

### Test 1: Experimental User-Initiated Flow (`AUTO_REDIRECT=false`)

1. Connect the Android phone to `SUSESI` Wi-Fi.
2. Open the camera / QR scanner and scan **QR #2** pointing to the Helper (`https://<HELPER_HOST>/wifi?room=342` or `http://<HELPER_IP>:8080/wifi?room=342`).
3. **Observation 1:** Verify the Helper landing page opens with:
   - "SUSESI LUXURY RESORT" branding
   - Room badge (e.g. `342`)
   - Prominent **"İnternete Bağlan"** button
4. Tap the **"İnternete Bağlan"** button.
5. **Observation 2 (Critical):** Record what Chrome does immediately upon tapping:
   - **Case A:** Opens `http://10.1.3.1/login` directly without any security warning.
   - **Case B:** Displays the Chrome warning (*"The site ahead is not secure"*). Verify if tapping *"Continue to site"* opens ProSpot.
   - **Case C:** Displays an omnibox warning badge ("Not secure") without a full-page blocking interstitial.

### Test 2: Comparative Automatic 302 Flow (`AUTO_REDIRECT=true`)

1. Set `AUTO_REDIRECT=true` in `.env` and restart the container (`docker compose up -d`).
2. Scan **QR #2** again.
3. **Observation 3:** Record Chrome's behavior when experiencing the immediate 302 redirect.

---

## Result Interpretation & Next Steps

| Outcome | Meaning | Action Plan |
| :--- | :--- | :--- |
| **Case A (No Warning)** | User-gesture link navigation successfully mitigated the full-page interstitial on Android Chrome. | Adopt `connect.html` as the standard production UX. |
| **Case B (Warning Persists)** | Chrome enforces the insecure HTTP warning regardless of user click gesture. | 1. Treat the warning as an unavoidable platform constraint of plain HTTP captive portals.<br>2. Do NOT attempt to weaken or bypass browser security.<br>3. Keep the in-page multilingual micro-guidance (*"Tap 'Advanced' → 'Continue' to complete login"*) so guests know exactly what to do. |
| **Case C (Omnibox badge only)** | Interstitial avoided; address bar chip visible. | Acceptable production experience. |
