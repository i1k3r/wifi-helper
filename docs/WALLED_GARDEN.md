# MikroTik HotSpot Walled Garden Configuration Guide

> **IMPORTANT NOTICE:**  
> **DO NOT modify the production MikroTik configuration during current development/testing.**  
> This documentation outlines the exact RouterOS commands required **before** production deployment so unauthenticated guest devices can reach the Wi-Fi Helper server.

---

## Why Walled Garden is Required

When a guest connects to the open `SUSESI` SSID:
1. MikroTik assigns the device an IP address in `10.1.0.0/16`.
2. By default, MikroTik HotSpot blocks all external TCP traffic from unauthenticated devices and intercepts port 80 HTTP requests to redirect them to `http://10.1.3.1/login`.
3. When the guest scans **QR #2** pointing to `http://<HELPER_IP>:8080/wifi`, the request will be dropped or prematurely intercepted by MikroTik *unless* the Helper's IP and port are whitelisted in MikroTik's **Walled Garden IP List**.

---

## Required RouterOS Configuration (For Future Deployment)

With the Wi-Fi Helper published on the TrueNAS guest interface `eno4np3` at IP address `10.1.11.126` listening on port `8080`:

### Option A: IP Walled Garden Rule (Recommended for IP-based QR #2)
Add an IP Walled Garden rule to permit direct TCP communication from unauthenticated guest clients to the Helper server:

```routeros
/ip hotspot walled-garden ip
add action=accept comment="Allow unauthenticated guests to reach Wi-Fi Helper" \
    dst-address=10.1.11.126 dst-port=8080 protocol=tcp
```

### Option B: Hostname Walled Garden Rule (If using a domain name for QR #2)
If QR #2 uses a hostname such as `http://wifi.susesi.local:8080/wifi`:

```routeros
/ip hotspot walled-garden
add action=allow comment="Allow unauthenticated access to Wi-Fi Helper hostname" \
    dst-host=wifi.susesi.local dst-port=8080
```

> **Note on DNS:** If using a hostname, ensure MikroTik HotSpot DNS server resolves `wifi.susesi.local` to the Helper IP for unauthenticated clients.

---

## Pre-Deployment Verification Checklist

1. [ ] Deploy Wi-Fi Helper Docker container on the hotel LAN server.
2. [ ] Add the Walled Garden IP entry on the MikroTik router.
3. [ ] Connect a test smartphone to `SUSESI` (unauthenticated).
4. [ ] Open `http://<HELPER_IP>:8080/wifi?room=TEST` in the smartphone browser.
5. [ ] Verify the phone reaches the Helper and is immediately redirected (`302`) to `http://10.1.3.1/login`.
6. [ ] Verify that the ProSpot login screen opens smoothly.
