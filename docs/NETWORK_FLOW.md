# SUSESI Network Flow Specification

## Network Environment Parameters

| Parameter | Value | Description |
| :--- | :--- | :--- |
| **Guest SSID** | `SUSESI` | Open hotel guest Wi-Fi network (No WPA/WEP password) |
| **Guest Subnet** | `10.1.0.0/16` | Dynamic DHCP pool for guest devices (e.g. `10.1.29.47/16`) |
| **Gateway / DNS** | `10.1.3.1` | MikroTik HotSpot router IP |
| **HotSpot Interface**| `ether2` | Physical router port servicing HotSpot |
| **HotSpot DHCP Pool**| `Hotspot_Dhcp`| DHCP server definition on MikroTik |
| **HotSpot Login URL**| `http://10.1.3.1/login` | Local HotSpot entrypoint |
| **ProSpot Portal** | `http://login.prospot.online/...` | Upstream cloud guest authentication service |
| **TrueNAS Guest Interface** | `eno4np3` (`10.1.11.126/16`) | Wi-Fi Helper published IP for guest network |
| **TrueNAS Mgmt Interface**  | `eno1np0` (`10.10.1.155/16`) | VLAN 2 Management network (Wi-Fi Helper NOT exposed here) |

---

## Step-by-Step Guest Journey

```text
+------+             +---------+          +---------------+          +------------+          +---------+
| Guest|             | Room TV |          | Wi-Fi Helper  |          |  MikroTik  |          | ProSpot |
+------+             +---------+          +---------------+          +------------+          +---------+
   |                      |                       |                         |                     |
   |--- 1. Scan QR #1 --->|                       |                         |                     |
   |   (WIFI:T:nopass;    |                       |                         |                     |
   |    S:SUSESI;;)       |                       |                         |                     |
   |                      |                       |                         |                     |
   |--- 2. DHCP Request & Association ------------+------------------------>|                     |
   |<-- 3. DHCP Offer (IP: 10.1.29.47, GW: 10.1.3.1) -----------------------|                     |
   |                      |                       |                         |                     |
   |--- 4. Scan QR #2 --->|                       |                         |                     |
   |   (http://<HELPER_IP>:8080/wifi?room=342)    |                         |                     |
   |                      |                       |                         |                     |
   |--- 5. HTTP GET /wifi?room=342 -------------->|                         |                     |
   |                      |                       |--- 6. GET 10.1.3.1/login|                     |
   |                      |                       |<-- 7. 200/302 OK -------|                     |
   |<-- 8. HTTP 302 -> http://10.1.3.1/login -----|                         |                     |
   |                      |                       |                         |                     |
   |--- 9. HTTP GET http://10.1.3.1/login --------------------------------->|                     |
   |<-- 10. HTTP 302 -> http://login.prospot.online/?location=... ----------|                     |
   |                      |                       |                         |                     |
   |--- 11. Navigate to ProSpot Portal ---------------------------------------------------------->|
   |--- 12. Submit credentials (room/password) -------------------------------------------------->|
   |<-- 13. Radius Authentication Success ----------------------------------+---------------------|
   |                      |                       |                         |                     |
   |=== 14. Full Internet Access Enabled ==================================>|====================>|
```

---

## State Transition Table

| Phase | Guest State | Network Access Allowed | Destination |
| :--- | :--- | :--- | :--- |
| **1. Associated** | Unauthenticated | Helper IP (Walled Garden) + Local Gateway `10.1.3.1` | Wi-Fi Helper |
| **2. Redirected** | Unauthenticated | `10.1.3.1` + `login.prospot.online` (Walled Garden) | MikroTik HotSpot / ProSpot |
| **3. Authenticated**| Authenticated | Full Internet | Any |
