# UniFi Network Voucher Manager

A lightweight Flask application for issuing UniFi guest WiFi vouchers. Users can obtain a voucher on screen or via email, while administrators manage settings through a PIN-protected interface.

---

## Features

- **Voucher Delivery**
  - On‑screen display with configurable timeout
  - Email sending via SMTP
- **Admin Interface**
  - PIN protected and IP whitelisted
  - Change portal texts (per language), colors, logo and favicon
  - Adjust default voucher parameters (duration, data limit, rate limits, guest count)
  - Manage input fields (first/last name, email, phone, reservation ID)
  - Import/export reservations from CSV
  - Fetch UniFi site ID and test API connectivity
  - Test SMTP settings directly from the UI
- **Reservations**
  - Supports time‑bound reservations stored in `reservations.csv`
  - Reservation entries can override voucher defaults
  - Expired reservations are hidden from the table and their vouchers are revoked
- **Logging**
  - `voucher_log.csv` records every attempt with MAC address, IP, success flag and user details
  - Application log rotates when exceeding 10k lines
- **Localization**
  - Public portal available in English and French
  - Separate site texts and terms of use for each language
  - View and revoke active vouchers from the admin area
- **Security**
  - Configurable rate limiting and cooldowns with whitelist bypass
  - Automatic cleanup of expired vouchers from UniFi

---

## Requirements

- Python 3.8+
- `Flask`, `Flask-Limiter`, `requests`, `waitress`

Install dependencies automatically by running the app; missing packages will be installed on first launch.

---

## Running

```bash
python app.py
```

The portal will start on `http://0.0.0.0:8080`. Access `/admin/pin` from a whitelisted IP to configure settings.

---

## Configuration Highlights

Settings are stored in `settings.json` and editable via the admin UI:

- **UniFi API** – URL, API key and optional site ID
- **SMTP** – host, port, credentials and TLS option
- **Appearance** – logo, favicon, colors and site texts
- **Form Fields** – toggle display/mandatory state for each input
- **Voucher Defaults** – minutes, data usage, bandwidth limits and allowed guests
- **Reservations** – upload a CSV or add entries manually; outdated entries are cleaned up automatically

All changes are applied immediately and persisted to disk.

---

## Logs

- `voucher_log.csv` – history of voucher generation attempts
- `app.log` – application events (archived when exceeding 10,000 lines)

Entries include MAC address if available. The application attempts to query UniFi for the client MAC when headers do not provide it.

---

## License

Released under the MIT License. Use at your own risk.

