# UniFi Network Voucher Manager

A single-file Flask application that issues UniFi guest WiFi vouchers. Users request a code from a self-service portal while administrators configure options through a PIN-protected page. The application aims to be easy to deploy on a small server or appliance.

![Screenshot_2](https://github.com/user-attachments/assets/5f8a78a9-1694-40dd-9939-b0f20fa984b3)

![Screenshot_11](https://github.com/user-attachments/assets/9e2ca1b0-257e-4b25-9cae-62926a80f84c)

---

## Key Features

### Voucher Delivery
- Display the voucher on the web page for a configurable number of seconds.
- Optionally send the code via SMTP. The email text can be customised.

  ![Screenshot_11](https://github.com/user-attachments/assets/4fee1b4d-f2dc-4fa3-a1fd-139f55a70417)

  ![Screenshot_12](https://github.com/user-attachments/assets/57fd73ee-1f98-4def-bf04-f7df3cd8ca0d)

### Admin Interface
- Access protected by a PIN **and** IP whitelist.

![Screenshot_13](https://github.com/user-attachments/assets/74a44ae4-bba7-4ee5-8864-60d692837975)

- Modify site texts in English and French, choose colours, upload a logo and favicon.

![Screenshot_3](https://github.com/user-attachments/assets/9c88874e-fa90-4dda-9fed-f024940cfa95)

- Configure default voucher duration, data limits, bandwidth and guest count.
- Enable/disable form fields (first/last name, email, phone, reservation ID).
- Import or export reservation data from CSV.
- Fetch the UniFi site ID and test API or SMTP connectivity directly from the UI.

![Screenshot_1](https://github.com/user-attachments/assets/766dd09a-21c1-431c-9414-925f97b32e9f)

![Screenshot_4](https://github.com/user-attachments/assets/076b608e-b63b-4e45-bb96-a3eecfcb77d5)

![Screenshot_5](https://github.com/user-attachments/assets/239181bd-b9d7-4cc3-bbbd-587c3941547e)

![Screenshot_3](https://github.com/user-attachments/assets/99f303ad-2982-4618-bcc2-825668b3a944)

  
- View currently active vouchers and revoke them if needed.


![Screenshot_6](https://github.com/user-attachments/assets/974f3f09-6382-474c-9779-96a53c57a9db)

![Screenshot_8](https://github.com/user-attachments/assets/45975f77-e394-413c-90b2-a6933a03b0df)



### Reservations
- Time‑bound reservations are stored in `reservations.csv`.
- A reservation can override voucher parameters such as minutes or bandwidth.
- Expired reservations are hidden from the table and any issued vouchers are removed from UniFi.

![image](https://github.com/user-attachments/assets/c73f4575-2e92-466d-b43b-d44e3cc59a26)

### Logging
- `voucher_log.csv` records every voucher attempt with IP, MAC (if available), success flag and user details.
- `app.log` keeps application events and rotates automatically when the file grows beyond 10,000 lines.

![image](https://github.com/user-attachments/assets/7c1ee38c-2b0a-46fb-92a9-e2c6fc1be9e8)

![image](https://github.com/user-attachments/assets/dc335ca4-bb60-42e6-a219-8e05eadf8c05)

### Localization
- Public portal and terms page available in English and French. Text for both languages is editable.

![Screenshot_6](https://github.com/user-attachments/assets/91f36e49-2da2-4018-a524-5a5885268143)


![screencapture-127-0-0-1-8080-terms-2025-07-02-10_54_29](https://github.com/user-attachments/assets/c81a9e0b-8d0a-4a0a-a756-6b8d85a9ed72)

Note that all user input fields intended for text or titles in the settings can be written in raw HTML to allow for more customization, such as adding images, formatting text, and so on.
See the following example in the ToU:

![Screenshot_8](https://github.com/user-attachments/assets/b8af15eb-a0e2-485a-8e82-50958dc10ddd)

![Screenshot_7](https://github.com/user-attachments/assets/cfd20a98-13e4-43ec-97eb-1286b0271333)


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
4. Have an API key from your local Unifi Console :

![Screenshot_10](https://github.com/user-attachments/assets/b618048e-928e-4878-8a29-df0d01d1b4eb)

5. Make sure the software is in a network / vlan able to ping the console.
6. Ensure that on the Unifi console, you have an open Wi-Fi network setup to use only vouchers :

![Screenshot_7](https://github.com/user-attachments/assets/d18bc2aa-1f9a-4ae1-bce7-cc5536978a95)

7. Setup config.ini for your needs.
8. In the web interface, go into the settings, connect and test API link to your console in there and customize the fields for your company :

![screencapture-127--10_09_40](https://github.com/user-attachments/assets/e972ec7d-e59d-41e1-b75b-87c2847e6354)

9. Done !

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





