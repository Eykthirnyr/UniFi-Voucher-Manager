#!/usr/bin/env python3
"""
UniFi Voucher Portal – single-file Flask application
2025-05-25 – universal cloud/on-prem API + admin UI
"""
APP_VERSION = "1.0.5"

import os, sys, json, csv, re, subprocess, configparser, logging, ipaddress
from datetime import datetime, timedelta
from functools import wraps
from logging.handlers import RotatingFileHandler
import smtplib, ssl
from email.message import EmailMessage

# ───────────────────────── Dependencies ──────────────────────────────
def _ensure(pkgs):
    import importlib, pkg_resources
    missing = [p for p in pkgs
               if p.lower() not in {x.key for x in pkg_resources.working_set}]
    if missing:
        subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])
_ensure(['Flask', 'requests', 'Flask-Limiter', 'waitress'])

from flask import (Flask, render_template, request, redirect, url_for, flash,
                   session, send_from_directory, make_response, abort)
import requests
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_limiter.extension import LimitGroup
from waitress import serve

# ───────────────────────── Paths / defaults ──────────────────────────
APP = os.path.abspath(os.path.dirname(__file__))
CFG = os.path.join(APP, 'config.ini')
STG = os.path.join(APP, 'settings.json')
LOG = os.path.join(APP, 'app.log')
CSV = os.path.join(APP, 'reservations.csv')
VLOG = os.path.join(APP, 'voucher_log.csv')

RUNNING_DOCKER = os.path.exists('/.dockerenv') or os.environ.get('RUN_IN_DOCKER')
DOCKER_INIT_FLAG = os.path.join(APP, '.docker_initialized')

TPL = os.path.join(APP, 'templates')
STA = os.path.join(APP, 'static')
LOGOS = os.path.join(STA, 'logos')
FAV   = os.path.join(STA, 'favicons')

ALLOWED_ICON = {'.ico'}
ALLOWED_LOGO = {'.png', '.jpg', '.jpeg', '.svg'}

DEFAULT_CFG = {
    'General': {
        'favicon': 'default_favicon.ico',
        'site_title': 'UniFi Guest Portal',
        'pin_code': '1234',
        'whitelisted_ips': '127.0.0.1, ::1'
    }
}

DEFAULT_STG = {
    "site_name": "Welcome to Our Guest WiFi",
    "site_name_en": "Welcome to Our Guest WiFi",
    "site_name_fr": "Bienvenue sur notre WiFi invité",
    "site_description": "Please fill out the form below to get access.",
    "site_description_en": "Please fill out the form below to get access.",
    "site_description_fr": "Veuillez remplir le formulaire ci-dessous pour obtenir l'accès.",
    "logo_path": "default_logo.svg",
    "logo_scale": 100,
    "default_language": "en",
    "terms_text_en": "These are the default terms of use...",
    "terms_text_fr": "Voici les conditions d'utilisation par d\u00e9faut...",
    "screen_display_seconds": 8,
    "primary_color": "#3498db",
    "secondary_color": "#2c3e50",
    "fields": {
        "first_name":     {"display": True,  "mandatory": True},
        "last_name":      {"display": True,  "mandatory": True},
        "email":          {"display": True,  "mandatory": True},
        "phone":          {"display": True,  "mandatory": False},
        "reservation_id": {"display": False, "mandatory": False}
    },
    "delivery_method": "Direct Display",           # or 'SMTP'
    "smtp": {
        "server": "", "port": 587, "user": "", "password": "", "use_tls": True
    },
    "email_subject": "Your WiFi Voucher Code",
    "email_body_pre": "Here is your code:",
    "email_body_post": "Enjoy your stay!",
    "default_voucher_minutes": 1440,
    "default_data_usage_mb": 0,
    "default_rx_kbps": 0,
    "default_tx_kbps": 0,
    "default_authorized_guests": 1,
    "cooldown": {"enabled": False, "seconds": 300},
    "rate_limit_per_minute": 5,
    "rate_limit_scope_minutes": 1,
    "api_key": "ABCDEF1234567890",
    "api_url": "https://192.168.10.1/proxy/network/integration",
    "site_id": "default"
}

LANGS = {
    "en": "English",
    "fr": "Français"
}

I18N = {
    "en": {
        "First Name": "First Name",
        "Last Name": "Last Name",
        "Email": "Email",
        "Phone Number": "Phone Number",
        "Reservation ID": "Reservation ID",
        "I accept the Terms of Use": "I accept the Terms of Use",
        "Get WiFi Access": "Get WiFi Access",
        "Terms of Use": "Terms of Use",
        "Required": "Required",
        "Invalid email": "Invalid email",
        "Accept terms": "Accept terms",
        "Reservation ID not found": "Reservation ID not found",
        "Reservation not yet active": "Reservation not yet active",
        "Reservation expired": "Reservation expired",
        "Voucher sent by email": "Voucher sent by email",
        "Your Voucher Code: {code}": "Your Voucher Code: {code}",
        "Voucher error: {err}": "Voucher error: {err}",
        "SMTP error: {err}": "SMTP error: {err}",
        "Not authorised": "Not authorised",
        "Wrong PIN": "Wrong PIN",
        "Logged out.": "Logged out.",
        "Back to Portal": "Back to Portal"
    },
    "fr": {
        "First Name": "Prénom",
        "Last Name": "Nom",
        "Email": "E-mail",
        "Phone Number": "Téléphone",
        "Reservation ID": "ID de réservation",
        "I accept the Terms of Use": "J'accepte les Conditions d'utilisation",
        "Get WiFi Access": "Obtenir l'accès Wi-Fi",
        "Terms of Use": "Conditions d'utilisation",
        "Required": "Obligatoire",
        "Invalid email": "E-mail invalide",
        "Accept terms": "Accepter les conditions",
        "Reservation ID not found": "ID de réservation introuvable",
        "Reservation not yet active": "La réservation n'est pas encore active",
        "Reservation expired": "La réservation est expirée",
        "Voucher sent by email": "Bon envoyé par e-mail",
        "Your Voucher Code: {code}": "Votre code Wi-Fi : {code}",
        "Voucher error: {err}": "Erreur de bon : {err}",
        "SMTP error: {err}": "Erreur SMTP : {err}",
        "Not authorised": "Non autorisé",
        "Wrong PIN": "Code PIN incorrect",
        "Logged out.": "Déconnexion effectuée.",
        "Back to Portal": "Retour au portail"
    }
}

def tr(key, lang=None, **fmt):
    if not lang:
        lang = session.get('lang', load_stg().get('default_language', 'en'))
    msg = I18N.get(lang, I18N['en']).get(key, key)
    if fmt:
        try:
            msg = msg.format(**fmt)
        except Exception:
            pass
    return msg

# ───────────────────────── File helpers ──────────────────────────────
def _archive_log():
    if os.path.exists(LOG):
        try:
            with open(LOG, 'r', errors='ignore') as f:
                lines = sum(1 for _ in f)
            if lines > 10000:
                ts = datetime.now().strftime('%Y%m%d-%H%M%S')
                os.rename(LOG, f"app_{ts}.log")
        except Exception:
            pass


def _init_files():
    for d in (TPL, STA, LOGOS, FAV):
        os.makedirs(d, exist_ok=True)
    if not os.path.exists(CFG):
        cp = configparser.ConfigParser(); cp.read_dict(DEFAULT_CFG)
        with open(CFG, 'w') as f:
            cp.write(f)
    if not os.path.exists(STG):
        json.dump(DEFAULT_STG, open(STG, 'w'), indent=4)
    if not os.path.exists(CSV):
        csv.writer(open(CSV, 'w', newline='')).writerow(
            ['ReservationID', 'StartDate', 'EndDate',
             'Minutes', 'DataMB', 'RxKbps', 'TxKbps', 'GuestLimit'])
        csv.writer(open(CSV, 'a', newline='')).writerow(
            ['BK123', '01/06/2025', '05/06/2025', '1440', '0', '0', '0', '1'])
    if not os.path.exists(VLOG):
        csv.writer(open(VLOG, 'w', newline='')).writerow([
            'Timestamp', 'Success', 'Code', 'Delivery', 'Email', 'IP', 'MAC',
            'FirstName', 'LastName', 'Phone', 'Minutes', 'ReservationID',
            'Deleted'])
    _archive_log()
_init_files()

def load_cfg():
    cp=configparser.ConfigParser(); cp.read(CFG); return cp
def save_cfg(cp): cp.write(open(CFG,'w'))

def load_stg():
    return json.load(open(STG,encoding='utf-8'))
def save_stg(d):
    json.dump(d, open(STG,'w',encoding='utf-8'), indent=4)

def parse_date(value):
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError("invalid date")

def load_reservations(include_past=False):
    rows=[]
    if not os.path.exists(CSV):
        return rows
    with open(CSV,newline='') as f:
        for row in csv.DictReader(f):
            try:
                sd=parse_date(row['StartDate'])
                ed=parse_date(row['EndDate'])
            except Exception:
                continue
            row['StartDate_obj']=sd
            row['EndDate_obj']=ed
            rows.append(row)
    if not include_past:
        cutoff=datetime.now().date()-timedelta(days=1)
        rows=[r for r in rows if r['EndDate_obj']>=cutoff]
    return rows

# ───────────────────────── Logging ───────────────────────────────────
hand = RotatingFileHandler(LOG, maxBytes=200_000, backupCount=3)
hand.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))

app = Flask(__name__, template_folder=TPL, static_folder=STA)
app.config['SECRET_KEY'] = os.urandom(24)
app.logger.addHandler(hand); app.logger.setLevel(logging.INFO)

@app.context_processor
def inject_globals():
    lang = session.get('lang', load_stg().get('default_language', 'en'))
    return {
        "app_version": APP_VERSION,
        "lang": lang,
        "t": lambda k, **f: tr(k, lang, **f),
        "LANGS": LANGS
    }

# ───────────────────────── Rate limiter ──────────────────────────────
def _mk_limiter(stg):
    lim = Limiter(get_remote_address, app=app,
        default_limits=[f"{stg['rate_limit_per_minute']} per {stg['rate_limit_scope_minutes']} minute"],
        storage_uri="memory://")
    return lim

limiter = _mk_limiter(load_stg())

LAST_CLEANUP = datetime.min

def periodic_cleanup():
    global LAST_CLEANUP
    if datetime.now() - LAST_CLEANUP > timedelta(hours=6):
        cleanup_expired_vouchers()
        LAST_CLEANUP = datetime.now()

def update_rate_limits(stg):
    per = max(int(stg.get('rate_limit_per_minute', 1)), 1)
    mins = max(int(stg.get('rate_limit_scope_minutes', 1)), 1)
    rule = f"{per} per {mins} minute"
    limiter.limit_manager.set_default_limits([
        LimitGroup(rule, get_remote_address)
    ])

# ───────────────────────── Utils ─────────────────────────────────────
ip = lambda: request.headers.get('X-Forwarded-For', request.remote_addr)

def mac_from_unifi():
    """Look up the client's MAC address from UniFi using its IP."""
    addr = ip()
    if not addr:
        return ''
    params = {'limit': '1', 'filter': f'ipAddress.eq({addr})'}
    js, err = call_unifi_api('clients', params=params)
    if not err:
        try:
            return js['data'][0].get('macAddress', '')
        except (KeyError, IndexError, TypeError):
            pass
    return ''

def mac_addr():
    for h in ('X-UniFi-MAC-Addr', 'X-MAC-Address', 'X-Device-Mac'):
        val = request.headers.get(h)
        if val:
            return val
    return mac_from_unifi()
whitelisted = lambda: ip() in [x.strip() for x in load_cfg().get('General','whitelisted_ips').split(',')]
limiter.request_filter(whitelisted)

@app.after_request
def _log(resp):
    app.logger.info("%s %s %s %s", ip(), request.method, request.path, resp.status_code)
    return resp

def _save_upload(file, folder, allowed):
    if not file or file.filename == '': return None
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed: return None
    fname = "upload"+ext
    file.save(os.path.join(folder, fname))
    return fname

def log_voucher(success, code='', method='', email='', first='', last='', phone='', minutes=0,
                reservation_id='', mac=''):
    with open(VLOG, 'a', newline='') as f:
        csv.writer(f).writerow([
            datetime.now().isoformat(timespec='seconds'),
            '1' if success else '0',
            code,
            method,
            email or '',
            ip(),
            mac,
            first,
            last,
            phone,
            minutes,
            reservation_id,
            ''
        ])

# ───────────────────────── Docker first-run redirect ─────────────---
@app.before_request
def docker_setup_redirect():
    if RUNNING_DOCKER and not os.path.exists(DOCKER_INIT_FLAG):
        allowed = {'docker_setup', 'static', 'favicon', 'logo'}
        if request.endpoint not in allowed:
            return redirect(url_for('docker_setup'))

# ───────────────────────── SMTP helper ─────────────────────────────--
def send_email(to_addr, subject, body):
    stg = load_stg()
    smtp = stg.get('smtp', {})
    server = smtp.get('server')
    user   = smtp.get('user')
    if not (server and user and to_addr):
        return "SMTP not configured"
    conn = None
    try:
        port = int(smtp.get('port', 587))
        conn = smtplib.SMTP(server, port, timeout=30)
        conn.ehlo()
        if smtp.get('use_tls', True):
            context = ssl._create_unverified_context()
            conn.starttls(context=context)
            conn.ehlo()
        pwd = smtp.get('password')
        if pwd:
            conn.login(user, pwd)

        msg = EmailMessage()
        msg['From'] = user
        msg['To'] = to_addr
        msg['Subject'] = subject
        msg.set_content(body)

        conn.send_message(msg)
        return None
    except Exception as e:
        return str(e)
    finally:
        if conn:
            try:
                conn.quit()
            except Exception:
                pass

def cleanup_expired_vouchers():
    if not os.path.exists(VLOG):
        return
    rows = []
    changed = False
    now = datetime.now()
    res_map = {}
    if os.path.exists(CSV):
        with open(CSV, newline='') as f:
            for r in csv.DictReader(f):
                try:
                    res_map[r['ReservationID']] = parse_date(r['EndDate'])
                except Exception:
                    pass
    with open(VLOG, newline='') as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        for extra in ['ReservationID','Deleted','Success','MAC','FirstName','LastName','Phone']:
            if extra not in fields:
                fields.append(extra)
        for row in reader:
            try:
                ts = datetime.fromisoformat(row['Timestamp'])
                mins = int(row.get('Minutes', 0))
                expired = mins and now > ts + timedelta(minutes=mins)
            except Exception:
                expired = False
            res_id = row.get('ReservationID')
            if res_id:
                endd = res_map.get(res_id)
                if not endd or datetime.now().date() > endd:
                    expired = True
            if expired and not row.get('Deleted'):
                params = {'filter': f"code.eq('{row['Code']}')"}
                _, err = call_unifi_api('hotspot/vouchers', 'DELETE', params=params)
                if not err:
                    row['Deleted'] = '1'
                    changed = True
            rows.append(row)
    if changed:
        with open(VLOG, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

def delete_all_vouchers():
    js, err = call_unifi_api('hotspot/vouchers', params={'limit': '1000'})
    if err:
        return err
    for v in js.get('data', []):
        vid = v.get('id')
        if vid:
            _, _ = call_unifi_api(f'hotspot/vouchers/{vid}', 'DELETE')
    return None

def delete_vouchers_for_res(res_id):
    if not os.path.exists(VLOG):
        return
    rows = []
    changed = False
    with open(VLOG, newline='') as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        for extra in ['ReservationID','Deleted','Success','MAC','FirstName','LastName','Phone']:
            if extra not in fields:
                fields.append(extra)
        for row in reader:
            if row.get('ReservationID') == res_id and not row.get('Deleted'):
                params = {'filter': f"code.eq('{row['Code']}')"}
                _, err = call_unifi_api('hotspot/vouchers', 'DELETE', params=params)
                if not err:
                    row['Deleted'] = '1'
                    changed = True
            rows.append(row)
    if changed:
        with open(VLOG, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader(); writer.writerows(rows)

def delete_voucher_code(code):
    """Delete a specific voucher from UniFi and mark it deleted in the log."""
    params = {'filter': f"code.eq('{code}')"}
    _, err = call_unifi_api('hotspot/vouchers', 'DELETE', params=params)
    if err:
        return err
    if not os.path.exists(VLOG):
        return None
    rows = []
    changed = False
    with open(VLOG, newline='') as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        for row in reader:
            if row.get('Code') == code and row.get('Deleted') != '1':
                row['Deleted'] = '1'
                changed = True
            rows.append(row)
    if changed:
        with open(VLOG, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader(); writer.writerows(rows)
    return None

def active_vouchers():
    """Return list of non-expired, non-deleted vouchers from the log."""
    res_map = {}
    if os.path.exists(CSV):
        with open(CSV, newline='') as f:
            for r in csv.DictReader(f):
                try:
                    res_map[r['ReservationID']] = parse_date(r['EndDate'])
                except Exception:
                    pass
    rows = []
    now = datetime.now()
    if os.path.exists(VLOG):
        with open(VLOG, newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('Success') != '1' or row.get('Deleted') == '1':
                    continue
                try:
                    ts = datetime.fromisoformat(row['Timestamp'])
                    mins = int(row.get('Minutes', 0))
                    if mins and now > ts + timedelta(minutes=mins):
                        continue
                except Exception:
                    pass
                rid = row.get('ReservationID')
                if rid:
                    endd = res_map.get(rid)
                    if endd and datetime.now().date() > endd:
                        continue
                rows.append(row)
    return rows

# ───────────────────────── UniFi API helper ──────────────────────────
def call_unifi_api(endpoint, method='GET', data=None, params=None, site_specific=True):
    stg = load_stg()
    base = stg.get('api_url', '').rstrip('/')
    key = stg.get('api_key', '')
    site = stg.get('site_id', 'default')

    if not (base and key): return None, "API not configured"

    if base.startswith('https://api.ui.com'):
        hdr = {
            'Authorization': f'Bearer {key}',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
    else:
        hdr = {
            'X-API-KEY': key,
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }

    if site_specific:
        if site:
            if base.endswith('/v1/sites'):
                url = f"{base}/{site}/{endpoint.lstrip('/')}"
            elif base.endswith('/v1'):
                url = f"{base}/sites/{site}/{endpoint.lstrip('/')}"
            else:
                url = f"{base}/v1/sites/{site}/{endpoint.lstrip('/')}"
        else:
            if base.endswith('/v1/sites'):
                base = base[:-len('/sites')]
            if not base.endswith('/v1'):
                base = f"{base}/v1"
            url = f"{base}/{endpoint.lstrip('/')}"
    else:
        if base.endswith('/v1/sites'):
            base = base[:-len('/sites')]
        if not base.endswith('/v1'):
            base = f"{base}/v1"
        url = f"{base}/{endpoint.lstrip('/')}"

    try:
        kwargs = dict(headers=hdr, verify=False, timeout=15)
        if data is not None:
            kwargs['json'] = data
        if params:
            kwargs['params'] = params
        r = requests.request(method, url, **kwargs)
        r.raise_for_status()
        if r.text:
            return r.json(), None
        return {}, None
    except requests.exceptions.JSONDecodeError:
        return None, "Non-JSON response (check URL)"
    except requests.exceptions.RequestException as e:
        return None, str(e)


def generate_voucher(name, minutes, data_mb=None, rx=None, tx=None, guest_limit=None):
    body = {"count": 1, "name": name, "timeLimitMinutes": int(minutes)}
    if guest_limit:
        body["authorizedGuestLimit"] = int(guest_limit)
    if data_mb:
        body["dataUsageLimitMBytes"] = int(data_mb)
    if rx:
        body["rxRateLimitKbps"] = int(rx)
    if tx:
        body["txRateLimitKbps"] = int(tx)
    js, err = call_unifi_api('hotspot/vouchers', 'POST', body)
    if err: return None, err
    try:    return js['vouchers'][0]['code'], None
    except (KeyError,IndexError): return None, "No voucher code"

# ───────────────────────── Decorators ────────────────────────────────
def admin_only(fn):
    @wraps(fn)
    def wrap(*a,**k):
        if not (whitelisted() and session.get('admin_authed')):
            flash(tr('Not authorised'),"danger"); return redirect(url_for('index'))
        return fn(*a,**k)
    return wrap

# ───────────────────────── Static files ──────────────────────────────
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(FAV, load_cfg().get('General','favicon',
                                   fallback='default_favicon.ico'),
                               mimetype='image/x-icon')

@app.route('/logo')
def logo():
    return send_from_directory(LOGOS, load_stg()['logo_path'])

@app.route('/lang/<lang>')
def set_lang(lang):
    if lang in LANGS:
        session['lang'] = lang
    return redirect(request.referrer or url_for('index'))

# ───────────────────────── Public Terms page ─────────────────────────
@app.route('/terms')
def terms():
    stg = load_stg()
    lang = session.get('lang', stg.get('default_language', 'en'))
    return render_template('terms.html',
                           settings=stg, config=load_cfg(), lang=lang)

# ───────────────────────── Docker first boot setup ───────────────────
@app.route('/docker_setup', methods=['GET','POST'])
def docker_setup():
    if not RUNNING_DOCKER:
        abort(404)
    if os.path.exists(DOCKER_INIT_FLAG):
        return redirect(url_for('index'))
    ips = ''
    pin = ''
    force = request.form.get('force')
    if request.method == 'POST':
        ips = request.form.get('whitelisted_ips', '').strip()
        pin = request.form.get('pin', '').strip()
        invalid = []
        if ips:
            for item in [i.strip() for i in ips.split(',') if i.strip()]:
                try:
                    ipaddress.ip_address(item)
                except ValueError:
                    invalid.append(item)
        if not ips:
            flash('Please enter at least one IP', 'danger')
        elif not re.fullmatch(r"\d{4}", pin):
            flash('PIN must be 4 digits', 'danger')
        elif invalid and not force:
            flash('Some IPs seem invalid: ' + ', '.join(invalid) + '. Submit again to confirm anyway.', 'warning')
            force = '1'
        else:
            cfg = load_cfg()
            cfg['General']['whitelisted_ips'] = ips
            cfg['General']['pin_code'] = pin
            save_cfg(cfg)
            open(DOCKER_INIT_FLAG, 'w').write('done')
            flash('Configuration saved', 'success')
            return redirect(url_for('index'))
    countdown = 45 if not force else 0
    return render_template('docker_setup.html', settings=load_stg(), config=load_cfg(),
                           ips=ips, pin=pin, force=force, countdown=countdown)

# ───────────────────────── Guest index page ──────────────────────────
@app.route('/', methods=['GET','POST'])
@limiter.limit("2 per second", exempt_when=whitelisted)
def index():
    periodic_cleanup()
    stg, cfg = load_stg(), load_cfg()
    cd_enabled = stg['cooldown']['enabled'] and not whitelisted()
    if cd_enabled:
        key=f"cd_{ip()}"; last=session.get(key)
        if last:
            wait = stg['cooldown']['seconds']
            elapsed = (datetime.now() - datetime.fromisoformat(last)).total_seconds()
            if elapsed < wait:
                remain = int(wait - elapsed)
                return render_template('cooldown.html',
                                        remaining=remain,
                                        settings=stg, config=cfg)

    form = request.form.to_dict() if request.method=='POST' else {}
    if request.method=='POST':
        errs={}
        for f,meta in stg['fields'].items():
            if not meta['display']: continue
            v = form.get(f,'').strip()
            if meta['mandatory'] and not v: errs[f]="Required"
            if f=='email' and v and not re.match(r"[^@]+@[^@]+\.[^@]+",v):
                errs[f]="Invalid email"

        if not form.get('terms'): errs['terms']="Accept terms"

        if errs:
            for k,v in errs.items():
                field = tr(k.replace('_',' ').title())
                flash(f"{field}: {tr(v)}", "warning")
            log_voucher(False, method=stg['delivery_method'], email=form.get('email',''),
                        first=form.get('first_name',''), last=form.get('last_name',''),
                        phone=form.get('phone',''), reservation_id=form.get('reservation_id',''),
                        mac=mac_addr())
        else:
            first = form.get('first_name','')
            last = form.get('last_name','')
            name = (first+" "+last).strip() or ip()
            minutes = stg['default_voucher_minutes']
            data_mb = stg.get('default_data_usage_mb')
            rx = stg.get('default_rx_kbps')
            tx = stg.get('default_tx_kbps')
            guest_limit = stg.get('default_authorized_guests')

            res_id = form.get('reservation_id','').strip()
            if stg['fields'].get('reservation_id', {}).get('display') and res_id:
                reservations = load_reservations(True)
                res = next((r for r in reservations if r['ReservationID']==res_id), None)
                if not res:
                    flash(tr('Reservation ID not found'),'danger')
                    log_voucher(False, method=stg['delivery_method'], email=form.get('email',''),
                                first=first, last=last, phone=form.get('phone',''),
                                reservation_id=res_id, mac=mac_addr())
                    return redirect(url_for('index'))
                today = datetime.now().date()
                if today < res['StartDate_obj']:
                    flash(tr('Reservation not yet active'),'danger')
                    log_voucher(False, method=stg['delivery_method'], email=form.get('email',''),
                                first=first, last=last, phone=form.get('phone',''),
                                reservation_id=res_id, mac=mac_addr())
                    return redirect(url_for('index'))
                if today > res['EndDate_obj']:
                    flash(tr('Reservation expired'),'danger')
                    log_voucher(False, method=stg['delivery_method'], email=form.get('email',''),
                                first=first, last=last, phone=form.get('phone',''),
                                reservation_id=res_id, mac=mac_addr())
                    return redirect(url_for('index'))
                minutes = int(res.get('Minutes') or minutes)
                data_mb = int(res.get('DataMB') or data_mb or 0)
                rx = int(res.get('RxKbps') or rx or 0)
                tx = int(res.get('TxKbps') or tx or 0)
                guest_limit = int(res.get('GuestLimit') or guest_limit or 1)

            code, err = generate_voucher(
                name,
                minutes,
                data_mb,
                rx,
                tx,
                guest_limit
            )
            if err:
                flash(tr('Voucher error: {err}', err=err),"danger")
                log_voucher(False, method=stg['delivery_method'], email=form.get('email',''),
                            first=first, last=last, phone=form.get('phone',''),
                            reservation_id=res_id, mac=mac_addr())
            else:
                delivery = 'SMTP' if stg['delivery_method']=='SMTP' else 'screen'
                to_addr = form.get('email') if delivery=='SMTP' else ''
                if delivery=='SMTP':
                    body = f"{stg['email_body_pre']}\n{code}\n{stg['email_body_post']}"
                    err = send_email(to_addr, stg['email_subject'], body)
                    if err:
                        flash(tr('SMTP error: {err}', err=err), "danger")
                    else:
                        flash(tr('Voucher sent by email'), "success")
                else:
                    flash(tr('Your Voucher Code: {code}', code=code),"voucher")
                log_voucher(True, code, delivery, to_addr, first, last,
                            form.get('phone',''), minutes, res_id, mac_addr())
                if cd_enabled:
                    session[key]=datetime.now().isoformat()
                return redirect(url_for('index'))

    return render_template('index.html',
                           settings=stg, config=cfg,
                           whitelisted=whitelisted(), form=form)

# ───────────────────────── Admin PIN login ───────────────────────────
@app.route('/admin/pin', methods=['GET','POST'])
def pin_entry():
    if not whitelisted(): abort(403)
    if request.method=='POST':
        if request.form.get('pin') == load_cfg().get('General','pin_code'):
            session['admin_authed']=True
            return redirect(url_for('settings_page'))
        flash(tr('Wrong PIN'),"danger")
    return render_template('pin.html',
                           settings=load_stg(), config=load_cfg())

# ───────────────────────── Settings page ─────────────────────────────
def _flash_api_test():
    js, err = call_unifi_api('info', site_specific=False)
    if err: flash("API error: "+err,"danger")
    else:   flash(f"✔︎ Connection OK (UniFi {js.get('applicationVersion','?')})","success")

def fetch_site_id():
    js, err = call_unifi_api('sites', site_specific=False)
    if err:
        return None, err
    try:
        return js['data'][0]['id'], None
    except (KeyError, IndexError):
        return None, 'No site ID found'

@app.route('/admin/settings', methods=['GET','POST'])
@admin_only
def settings_page():
    periodic_cleanup()
    stg, cfg = load_stg(), load_cfg()
    reservations = load_reservations()

    if request.method=='POST':

        new = json.loads(json.dumps(stg))     # deep-copy
        simple = ['site_name_en','site_name_fr',
                  'site_description_en','site_description_fr',
                  'primary_color','secondary_color',
                  'terms_text_en','terms_text_fr','default_language',
                  'api_url','site_id','delivery_method',
                  'email_subject','email_body_pre','email_body_post']
        for k in simple:
            if k in request.form: new[k] = request.form[k]

        if 'screen_display_seconds' in request.form:
            new['screen_display_seconds'] = int(request.form['screen_display_seconds'] or 0)

        if request.form.get('api_key'): new['api_key'] = request.form['api_key'].strip()
        new['default_voucher_minutes'] = int(request.form.get('default_voucher_minutes',
                                                              stg['default_voucher_minutes']))
        new['default_data_usage_mb'] = int(request.form.get('default_data_usage_mb',
                                                          stg.get('default_data_usage_mb',0) or 0))
        new['default_rx_kbps'] = int(request.form.get('default_rx_kbps',
                                                    stg.get('default_rx_kbps',0) or 0))
        new['default_tx_kbps'] = int(request.form.get('default_tx_kbps',
                                                    stg.get('default_tx_kbps',0) or 0))
        new['default_authorized_guests'] = int(request.form.get('default_authorized_guests',
                                                            stg.get('default_authorized_guests',1) or 1))
        # SMTP
        new['smtp']['server'] = request.form.get('smtp_server','')
        new['smtp']['port']   = int(request.form.get('smtp_port',587))
        new['smtp']['user']   = request.form.get('smtp_user','')
        pwd_field = request.form.get('smtp_password','')
        if pwd_field and pwd_field != '********':
            new['smtp']['password'] = pwd_field
        new['smtp']['use_tls'] = 'smtp_tls' in request.form

        # cooldown / rate-limit
        new['cooldown']['enabled'] = 'cooldown_enabled' in request.form
        new['cooldown']['seconds'] = int(request.form.get('cooldown_seconds',300))
        new['rate_limit_per_minute']    = int(request.form.get('rate_limit_per_minute',5))
        new['rate_limit_scope_minutes'] = int(request.form.get('rate_limit_scope_minutes',1))

        # form fields
        for f in new['fields']:
            new['fields'][f]['display']   = f'field_{f}_display' in request.form
            new['fields'][f]['mandatory'] = (f'field_{f}_mandatory' in request.form and
                                             new['fields'][f]['display'])

        # uploads
        if (ico := _save_upload(request.files.get('favicon_upload'), FAV, ALLOWED_ICON)):
            cfg.set('General','favicon',ico); save_cfg(cfg)
        if (logo := _save_upload(request.files.get('logo_upload'), LOGOS, ALLOWED_LOGO)):
            new['logo_path'] = logo

        if 'logo_scale' in request.form:
            try:
                val = int(request.form['logo_scale'])
                if 50 <= val <= 150:
                    new['logo_scale'] = val
            except ValueError:
                pass

        save_stg(new)
        update_rate_limits(new)

        if 'add_reservation' in request.form:
            rid = request.form.get('res_id','').strip()
            sd  = request.form.get('start_date','').strip()
            ed  = request.form.get('end_date','').strip()
            mins = request.form.get('res_minutes','').strip()
            data = request.form.get('res_data_mb','').strip()
            rx   = request.form.get('res_rx','').strip()
            tx   = request.form.get('res_tx','').strip()
            guests = request.form.get('res_guests','').strip()
            errs=[]
            if not rid:
                errs.append('ID required')
            try:
                sd_dt=parse_date(sd)
                ed_dt=parse_date(ed)
                if ed_dt < sd_dt:
                    errs.append('End before start')
            except Exception:
                errs.append('Invalid dates')
            existing=[r['ReservationID'] for r in load_reservations(True)]
            if rid in existing:
                errs.append('ID already exists')
            if errs:
                for e in errs:
                    flash(e,'danger')
            else:
                with open(CSV,'a',newline='') as f:
                    csv.writer(f).writerow([
                        rid,sd,ed,mins,data,rx,tx,guests
                    ])
                flash('Reservation added','success')
            return redirect(url_for('settings_page'))

        if 'fetch_site_id' in request.form:
            sid, err = fetch_site_id()
            if err:
                flash('Fetch error: ' + err, 'danger')
            else:
                new['site_id'] = sid
                save_stg(new)
                flash('Site ID fetched: ' + sid, 'success')
        elif request.form.get('del_reservation'):
            rid = request.form.get('del_reservation')
            with open(CSV, newline='') as f:
                orig = list(csv.DictReader(f))
            rows = [r for r in orig if r['ReservationID'] != rid]
            with open(CSV, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=orig[0].keys() if orig else
                                       ['ReservationID','StartDate','EndDate','Minutes','DataMB','RxKbps','TxKbps','GuestLimit'])
                writer.writeheader(); writer.writerows(rows)
            if len(rows) < len(orig):
                delete_vouchers_for_res(rid)
                flash('Reservation removed', 'success')
            else:
                flash('Reservation not found', 'warning')
        elif request.form.get('import_csv'):
            file = request.files.get('csv_file')
            if file and file.filename:
                try:
                    text = file.read().decode('utf-8-sig')
                    rows = list(csv.DictReader(text.splitlines()))
                    required = {'ReservationID','StartDate','EndDate'}
                    if not rows or not required.issubset(rows[0].keys()):
                        raise ValueError('Missing columns')
                    with open(CSV, 'w', newline='') as f:
                        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                        writer.writeheader()
                        writer.writerows(rows)
                    csv.writer(open(VLOG,'w',newline='')).writerow([
                        'Timestamp','Success','Code','Delivery','Email','IP','MAC',
                        'FirstName','LastName','Phone','Minutes','ReservationID','Deleted'])
                    delete_all_vouchers()
                    flash('CSV imported and table updated.', 'success')
                except Exception as e:
                    flash('Import error: ' + str(e), 'danger')
            else:
                flash('No file selected', 'warning')
        elif request.form.get('refresh_reservations'):
            delete_all_vouchers()
            flash('Table refreshed', 'info')
        elif 'api_test' in request.form:
            _flash_api_test()
        elif 'smtp_test' in request.form:
            to_addr = request.form.get('smtp_test_addr') or new['smtp']['user']
            body = "This is a test email from UniFi Voucher Portal."
            err = send_email(to_addr, "SMTP Test", body)
            if err:
                flash("SMTP error: " + err, "danger")
            else:
                flash("Settings saved. Test email sent", "success")
        else:
            flash("Settings saved","success")

        return redirect(url_for('settings_page'))

    return render_template('settings.html', settings=stg, config=cfg,
                           reservations=reservations)

# ───────────────────────── Active Vouchers ───────────────────────────
@app.route('/admin/vouchers', methods=['GET', 'POST'])
@admin_only
def manage_vouchers():
    periodic_cleanup()
    if request.method == 'POST' and request.form.get('revoke'):
        code = request.form.get('revoke')
        err = delete_voucher_code(code)
        if err:
            flash('Revoke error: ' + err, 'danger')
        else:
            flash('Voucher revoked', 'success')
        return redirect(url_for('manage_vouchers'))

    vouchers = active_vouchers()
    return render_template('vouchers.html', vouchers=vouchers,
                           settings=load_stg(), config=load_cfg())

# ───────────────────────── Logout ────────────────────────────────────
@app.route('/admin/logout')
def logout():
    session.clear(); flash(tr('Logged out.'),"info")
    return redirect(url_for('index'))

# ───────────────────────── CSV sample ────────────────────────────────
@app.route('/download_csv_example')
@admin_only
def download_csv_example():
    sample = (
        "ReservationID,StartDate,EndDate,Minutes,DataMB,RxKbps,TxKbps,GuestLimit\n"
        "BK123,01/06/2025,05/06/2025,1440,0,0,0,1\n"
    )
    res = make_response(sample)
    res.headers['Content-Type']        = 'text/csv'
    res.headers['Content-Disposition'] = 'attachment; filename=reservations_example.csv'
    return res

# ───────────────────────── Main ──────────────────────────────────────
if __name__ == '__main__':
    print("UniFi Voucher Portal → http://0.0.0.0:8080")
    serve(app, host='0.0.0.0', port=8080)
