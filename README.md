# UniFi Network Voucher Manager

A single-file Flask application that issues UniFi guest WiFi vouchers. Users request a code from a self-service portal while administrators configure options through a PIN-protected page. The application aims to be easy to deploy on a small server or appliance.

---

## Key Features

### Voucher Delivery
- Display the voucher on the web page for a configurable number of seconds.
- Optionally send the code via SMTP. The email text can be customised.

### Admin Interface
- Access protected by a PIN **and** IP whitelist.
- Modify site texts in English and French, choose colours, upload a logo and favicon.
- Configure default voucher duration, data limits, bandwidth and guest count.
- Enable/disable form fields (first/last name, email, phone, reservation ID).
- Import or export reservation data from CSV.
- Fetch the UniFi site ID and test API or SMTP connectivity directly from the UI.
- View currently active vouchers and revoke them if needed.

### Reservations
- Time‑bound reservations are stored in `reservations.csv`.
- A reservation can override voucher parameters such as minutes or bandwidth.
- Expired reservations are hidden from the table and any issued vouchers are removed from UniFi.

### Logging
- `voucher_log.csv` records every voucher attempt with IP, MAC (if available), success flag and user details.
- `app.log` keeps application events and rotates automatically when the file grows beyond 10,000 lines.

### Localization
- Public portal and terms page available in English and French. Text for both languages is editable.

### Security and Abuse Protection
- Rate limiting is enforced per IP. Both the limit per minute and the time window are configurable.
- A separate cooldown can block repeated voucher requests from the same IP for a set period.
- The admin area requires both a valid PIN and a request originating from a whitelisted IP address.
- Expired vouchers are periodically cleaned up from the UniFi controller to avoid lingering access.
- Basic validation ensures mandatory fields are provided and that email addresses look valid.

---

## Getting Started

1. **Install Python 3.8+** on the host running the application.
2. Clone this repository and run `python app.py` to start. Missing dependencies are installed automatically on the first launch.
3. Browse to `http://<server>:8080` for the public portal. Use `/admin/pin` from a whitelisted IP to access the settings page.

---

## Configuration

Most options are stored in `settings.json` and can be modified from the admin interface. A few core settings are kept in `config.ini`:

```ini
[General]
favicon = Aha-Soft-Free-Global-Security-Global-Network.ico
site_title = UniFi Guest Portal
pin_code = 1234
whitelisted_ips = 127.0.0.1, ::1
```

- **pin_code** – numeric PIN required to reach the admin settings.
- **whitelisted_ips** – comma separated list of IPv4/IPv6 addresses allowed to visit `/admin/pin`. Only those IPs can authenticate as administrators.

After adjusting the file, restart the application for changes to take effect.

The admin page exposes all other settings:
- UniFi API URL, key and optional site ID.
- SMTP server details if you wish to email vouchers.
- Portal appearance (texts, colours, logo, favicon).
- Which form fields are shown and whether they are mandatory.
- Default voucher minutes, data usage, bandwidth limits and allowed guests.
- Reservations table management.
- Cooldown and rate‑limit values.

All edits are saved to disk immediately.

---

## Logs

- `voucher_log.csv` – history of voucher generation attempts.
- `app.log` – rotating application log. Old logs are archived automatically when the file exceeds ~10k lines.

MAC addresses are looked up from UniFi if not supplied in the request headers.

---

## License

This project is released under the MIT License. Use at your own risk.

