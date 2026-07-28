from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, timedelta
import calendar
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'berber_gizli_anahtar_2024')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

# Veritabanı: Render'da PostgreSQL, lokalde SQLite
DATABASE_URL = os.environ.get('DATABASE_URL', '')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
USE_PG = bool(DATABASE_URL)

if USE_PG:
    import psycopg2, psycopg2.extras, psycopg2.errors
    PH = '%s'
    SlotTakenError = psycopg2.errors.UniqueViolation
else:
    import sqlite3
    PH = '?'
    SlotTakenError = sqlite3.IntegrityError

SERVICES = [
    {'name': 'Saç Kesimi',    'duration': 30, 'price': 150},
    {'name': 'Sakal Düzeltme','duration': 20, 'price': 100},
    {'name': 'Saç + Sakal',   'duration': 45, 'price': 230},
    {'name': 'Fön',           'duration': 20, 'price': 80},
    {'name': 'Çocuk Kesimi',  'duration': 25, 'price': 100},
]

WORKING_HOURS = {
    'start': '09:00',
    'end': '19:00',
    'slot_duration': 30,
    'working_days': [0, 1, 2, 3, 4, 5],
}

DAYS_TR   = ['Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt', 'Paz']
MONTHS_TR = ['', 'Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran',
             'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık']


# ─── Veritabanı yardımcıları ────────────────────────────────────────────────

def get_conn():
    if USE_PG:
        return psycopg2.connect(DATABASE_URL)
    conn = sqlite3.connect('berber.db')
    conn.row_factory = sqlite3.Row
    return conn

def qfetchall(conn, sql, params=()):
    if USE_PG:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as c:
            c.execute(sql, params)
            return [dict(r) for r in c.fetchall()]
    return [dict(r) for r in conn.execute(sql, params).fetchall()]

def qfetchone(conn, sql, params=()):
    if USE_PG:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as c:
            c.execute(sql, params)
            r = c.fetchone()
            return dict(r) if r else None
    r = conn.execute(sql, params).fetchone()
    return dict(r) if r else None

def qscalar(conn, sql, params=()):
    if USE_PG:
        with conn.cursor() as c:
            c.execute(sql, params)
            r = c.fetchone()
            return int(r[0]) if r and r[0] is not None else 0
    r = conn.execute(sql, params).fetchone()
    return int(r[0]) if r and r[0] is not None else 0

def qinsert(conn, sql, params=()):
    if USE_PG:
        with conn.cursor() as c:
            c.execute(sql + ' RETURNING id', params)
            rid = c.fetchone()[0]
        conn.commit()
        return rid
    cur = conn.execute(sql, params)
    conn.commit()
    return cur.lastrowid

def qexecute(conn, sql, params=()):
    if USE_PG:
        with conn.cursor() as c:
            c.execute(sql, params)
        conn.commit()
    else:
        conn.execute(sql, params)
        conn.commit()

def init_db():
    conn = get_conn()
    if USE_PG:
        sql = """
            CREATE TABLE IF NOT EXISTS appointments (
                id            SERIAL PRIMARY KEY,
                customer_name TEXT NOT NULL,
                phone         TEXT NOT NULL,
                service       TEXT NOT NULL,
                duration      INTEGER NOT NULL,
                price         INTEGER NOT NULL,
                appointment_date TEXT NOT NULL,
                appointment_time TEXT NOT NULL,
                status        TEXT DEFAULT 'pending',
                notes         TEXT,
                created_at    TIMESTAMP DEFAULT NOW()
            )
        """
    else:
        sql = """
            CREATE TABLE IF NOT EXISTS appointments (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT NOT NULL,
                phone         TEXT NOT NULL,
                service       TEXT NOT NULL,
                duration      INTEGER NOT NULL,
                price         INTEGER NOT NULL,
                appointment_date TEXT NOT NULL,
                appointment_time TEXT NOT NULL,
                status        TEXT DEFAULT 'pending',
                notes         TEXT,
                created_at    TEXT DEFAULT (datetime('now','localtime'))
            )
        """
    qexecute(conn, sql)
    qexecute(conn, """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_appt_slot
        ON appointments (appointment_date, appointment_time)
        WHERE status != 'cancelled'
    """)
    qexecute(conn, "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")

    if qfetchone(conn, f"SELECT 1 FROM settings WHERE key = {PH}", ('admin_password_hash',)) is None:
        qexecute(conn,
            f"INSERT INTO settings (key, value) VALUES ({PH}, {PH})",
            ('admin_password_hash', generate_password_hash(ADMIN_PASSWORD)))
    conn.close()

def get_admin_password_hash():
    conn = get_conn()
    row = qfetchone(conn, f"SELECT value FROM settings WHERE key = {PH}", ('admin_password_hash',))
    conn.close()
    return row['value'] if row else generate_password_hash(ADMIN_PASSWORD)

def set_admin_password_hash(new_hash):
    conn = get_conn()
    sql = f"UPDATE settings SET value = {PH} WHERE key = {PH}"
    qexecute(conn, sql, (new_hash, 'admin_password_hash'))
    conn.close()


# ─── İş mantığı ─────────────────────────────────────────────────────────────

def get_all_slots():
    slots = []
    start = datetime.strptime(WORKING_HOURS['start'], '%H:%M')
    end   = datetime.strptime(WORKING_HOURS['end'],   '%H:%M')
    cur = start
    while cur < end:
        slots.append(cur.strftime('%H:%M'))
        cur += timedelta(minutes=WORKING_HOURS['slot_duration'])
    return slots

def get_blocked_slots(date_str):
    conn  = get_conn()
    booked = qfetchall(conn,
        f"SELECT appointment_time, duration FROM appointments "
        f"WHERE appointment_date = {PH} AND status NOT IN ('cancelled')",
        (date_str,))
    conn.close()

    blocked  = set()
    slot_dur = WORKING_HOURS['slot_duration']
    for b in booked:
        t = datetime.strptime(b['appointment_time'], '%H:%M')
        n = (b['duration'] + slot_dur - 1) // slot_dur
        for i in range(n):
            blocked.add((t + timedelta(minutes=i * slot_dur)).strftime('%H:%M'))
    return blocked


# ─── Müşteri sayfaları ───────────────────────────────────────────────────────

@app.route('/')
def index():
    today    = date.today().isoformat()
    max_date = (date.today() + timedelta(days=60)).isoformat()
    return render_template('index.html', services=SERVICES,
                           min_date=today, max_date=max_date)

@app.route('/musait-saatler')
def musait_saatler():
    date_str     = request.args.get('tarih', '')
    service_name = request.args.get('hizmet', '')
    if not date_str or not service_name:
        return jsonify([])
    try:
        selected = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify([])
    if selected < date.today():
        return jsonify([])
    if datetime.strptime(date_str, '%Y-%m-%d').weekday() not in WORKING_HOURS['working_days']:
        return jsonify({'kapali': True})
    service = next((s for s in SERVICES if s['name'] == service_name), None)
    if not service:
        return jsonify([])

    all_slots = get_all_slots()
    blocked   = get_blocked_slots(date_str)
    slot_dur  = WORKING_HOURS['slot_duration']
    n_needed  = (service['duration'] + slot_dur - 1) // slot_dur
    available = []
    for i, slot in enumerate(all_slots):
        slot_dt = datetime.strptime(slot, '%H:%M')
        if selected == date.today() and slot_dt.time() <= datetime.now().time():
            continue
        ok = True
        for j in range(n_needed):
            check = (slot_dt + timedelta(minutes=j * slot_dur)).strftime('%H:%M')
            if check in blocked or check not in all_slots:
                ok = False; break
        if ok:
            available.append(slot)
    return jsonify(available)

@app.route('/randevu-al', methods=['POST'])
def randevu_al():
    name     = request.form.get('customer_name', '').strip()
    phone    = request.form.get('phone', '').strip()
    svc_name = request.form.get('service', '').strip()
    date_str = request.form.get('date', '').strip()
    time_str = request.form.get('time', '').strip()

    if not all([name, phone, svc_name, date_str, time_str]):
        flash('Lütfen tüm alanları doldurun.', 'error')
        return redirect(url_for('index'))
    service = next((s for s in SERVICES if s['name'] == svc_name), None)
    if not service:
        flash('Geçersiz hizmet seçimi.', 'error')
        return redirect(url_for('index'))
    slot_dur = WORKING_HOURS['slot_duration']
    n_needed = (service['duration'] + slot_dur - 1) // slot_dur
    slot_dt  = datetime.strptime(time_str, '%H:%M')
    needed_slots = {(slot_dt + timedelta(minutes=i * slot_dur)).strftime('%H:%M') for i in range(n_needed)}
    if needed_slots & get_blocked_slots(date_str):
        flash('Bu saat doldu. Lütfen başka bir saat seçin.', 'error')
        return redirect(url_for('index'))

    conn = get_conn()
    try:
        appt_id = qinsert(conn,
            f"INSERT INTO appointments (customer_name, phone, service, duration, price, appointment_date, appointment_time) "
            f"VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH})",
            (name, phone, svc_name, service['duration'], service['price'], date_str, time_str))
    except SlotTakenError:
        conn.rollback()
        conn.close()
        flash('Bu saat doldu. Lütfen başka bir saat seçin.', 'error')
        return redirect(url_for('index'))
    conn.close()

    d = datetime.strptime(date_str, '%Y-%m-%d')
    date_display = f"{d.day} {MONTHS_TR[d.month]} {d.year} {DAYS_TR[d.weekday()]}"
    return render_template('confirmation.html',
        appt_id=appt_id, customer_name=name, service=svc_name,
        date_display=date_display, time=time_str,
        price=service['price'], duration=service['duration'])


# ─── Admin ───────────────────────────────────────────────────────────────────

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated

@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if session.get('admin'):
        return redirect(url_for('admin_dashboard'))
    if request.method == 'POST':
        if check_password_hash(get_admin_password_hash(), request.form.get('password', '')):
            session['admin'] = True
            return redirect(url_for('admin_dashboard'))
        flash('Yanlış şifre!', 'error')
    return render_template('admin_login.html')

@app.route('/admin/cikis')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('admin_login'))

@app.route('/admin/sifre-degistir', methods=['GET', 'POST'])
@admin_required
def admin_change_password():
    if request.method == 'POST':
        current  = request.form.get('current_password', '')
        new_pw   = request.form.get('new_password', '')
        new_pw2  = request.form.get('new_password2', '')

        if not check_password_hash(get_admin_password_hash(), current):
            flash('Mevcut şifre yanlış.', 'error')
        elif len(new_pw) < 6:
            flash('Yeni şifre en az 6 karakter olmalı.', 'error')
        elif new_pw != new_pw2:
            flash('Yeni şifreler eşleşmiyor.', 'error')
        else:
            set_admin_password_hash(generate_password_hash(new_pw))
            flash('Şifre başarıyla değiştirildi.', 'success')
            return redirect(url_for('admin_dashboard'))
    return render_template('admin_change_password.html')

@app.route('/admin/panel')
@admin_required
def admin_dashboard():
    today = date.today().isoformat()
    conn  = get_conn()

    today_appts = qfetchall(conn,
        f"SELECT * FROM appointments WHERE appointment_date = {PH} AND status != 'cancelled' ORDER BY appointment_time",
        (today,))

    week_start = (date.today() - timedelta(days=date.today().weekday())).isoformat()
    week_end   = (date.today() + timedelta(days=6 - date.today().weekday())).isoformat()

    stats = {
        'today':         len(today_appts),
        'weekly':        qscalar(conn,
            f"SELECT COUNT(*) FROM appointments WHERE appointment_date BETWEEN {PH} AND {PH} AND status != 'cancelled'",
            (week_start, week_end)),
        'total':         qscalar(conn,
            "SELECT COUNT(*) FROM appointments WHERE status != 'cancelled'"),
        'pending':       qscalar(conn,
            "SELECT COUNT(*) FROM appointments WHERE status = 'pending'"),
        'revenue_today': qscalar(conn,
            f"SELECT COALESCE(SUM(price),0) FROM appointments WHERE appointment_date = {PH} AND status = 'completed'",
            (today,)),
        'revenue_week':  qscalar(conn,
            f"SELECT COALESCE(SUM(price),0) FROM appointments WHERE appointment_date BETWEEN {PH} AND {PH} AND status = 'completed'",
            (week_start, week_end)),
    }

    service_stats = qfetchall(conn,
        "SELECT service, COUNT(*) as cnt FROM appointments WHERE status != 'cancelled' GROUP BY service ORDER BY cnt DESC")
    conn.close()

    d = datetime.strptime(today, '%Y-%m-%d')
    today_str = f"{d.day} {MONTHS_TR[d.month]} {d.year}"
    return render_template('admin_dashboard.html',
        today_appts=today_appts, stats=stats,
        service_stats=service_stats, today=today, today_str=today_str)

@app.route('/admin/canli-randevular')
@admin_required
def canli_randevular():
    today = date.today().isoformat()
    conn  = get_conn()
    rows  = qfetchall(conn,
        f"SELECT id, customer_name, phone, service, appointment_time, status "
        f"FROM appointments WHERE appointment_date = {PH} AND status != 'cancelled' ORDER BY appointment_time",
        (today,))
    conn.close()
    return jsonify(rows)


@app.route('/admin/randevular')
@admin_required
def admin_appointments():
    filter_date   = request.args.get('tarih', '')
    filter_status = request.args.get('durum', '')
    conn  = get_conn()
    query  = "SELECT * FROM appointments WHERE 1=1"
    params = []
    if filter_date:
        query += f" AND appointment_date = {PH}"; params.append(filter_date)
    if filter_status:
        query += f" AND status = {PH}"; params.append(filter_status)
    query += " ORDER BY appointment_date DESC, appointment_time ASC"
    rows = qfetchall(conn, query, params)
    conn.close()

    appointments = []
    for a in rows:
        d = datetime.strptime(a['appointment_date'], '%Y-%m-%d')
        a['date_display'] = f"{d.day} {MONTHS_TR[d.month]} {DAYS_TR[d.weekday()]}"
        appointments.append(a)
    return render_template('admin_appointments.html',
        appointments=appointments, filter_date=filter_date, filter_status=filter_status)

@app.route('/admin/durum-guncelle', methods=['POST'])
@admin_required
def update_status():
    data       = request.json
    appt_id    = data.get('id')
    new_status = data.get('status')
    if new_status not in ('pending', 'confirmed', 'completed', 'cancelled'):
        return jsonify({'error': 'Geçersiz durum'}), 400
    conn = get_conn()
    qexecute(conn, f"UPDATE appointments SET status = {PH} WHERE id = {PH}", (new_status, appt_id))
    conn.close()
    return jsonify({'ok': True})

@app.route('/admin/takvim')
@admin_required
def admin_calendar():
    year  = request.args.get('yil',  date.today().year,  type=int)
    month = request.args.get('ay',   date.today().month, type=int)
    if month < 1:  month = 12; year -= 1
    if month > 12: month = 1;  year += 1

    month_start = f"{year}-{month:02d}-01"
    month_end   = f"{year+1}-01-01" if month == 12 else f"{year}-{month+1:02d}-01"

    conn = get_conn()
    rows = qfetchall(conn,
        f"SELECT appointment_date, COUNT(*) as cnt FROM appointments "
        f"WHERE appointment_date >= {PH} AND appointment_date < {PH} AND status != 'cancelled' "
        f"GROUP BY appointment_date",
        (month_start, month_end))
    conn.close()

    appt_map = {r['appointment_date']: r['cnt'] for r in rows}
    cal = calendar.monthcalendar(year, month)
    return render_template('admin_calendar.html',
        year=year, month=month, month_name=MONTHS_TR[month], cal=cal,
        appt_map=appt_map, today=date.today().isoformat(),
        prev_year=year if month > 1 else year-1, prev_month=month-1 if month > 1 else 12,
        next_year=year if month < 12 else year+1, next_month=month+1 if month < 12 else 1,
        days_tr=DAYS_TR, working_days=WORKING_HOURS['working_days'])

@app.route('/admin/gun-detay')
@admin_required
def admin_day_detail():
    day  = request.args.get('tarih', date.today().isoformat())
    conn = get_conn()
    appts = qfetchall(conn,
        f"SELECT * FROM appointments WHERE appointment_date = {PH} ORDER BY appointment_time",
        (day,))
    conn.close()
    d = datetime.strptime(day, '%Y-%m-%d')
    day_display = f"{d.day} {MONTHS_TR[d.month]} {d.year} {DAYS_TR[d.weekday()]}"
    return render_template('admin_day_detail.html',
        appts=appts, day=day, day_display=day_display)


try:
    init_db()
except Exception as e:
    print(f"DB init uyarı: {e}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = not USE_PG
    print("=" * 50)
    print(" Berber Randevu Sistemi Başladı")
    print(f" Veritabanı: {'PostgreSQL' if USE_PG else 'SQLite (lokal)'}")
    print(f" http://localhost:{port}")
    print("=" * 50)
    app.run(host='0.0.0.0', port=port, debug=debug)
