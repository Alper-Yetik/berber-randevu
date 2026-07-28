# Berber Randevu Sistemi

Web tabanlı berber randevu sistemi. Müşteriler siteden randevu alıyor, manuel defter tutmaya gerek kalmıyor.

## Yayın / Deployment
- GitHub: https://github.com/Alper-Yetik/berber-randevu
- Canlı: https://berber-randevu-bk4y.onrender.com (Render.com)
- Render deploy config: `render.yaml` (buildCommand: `pip install -r requirements.txt`, startCommand: `python app.py`)

## Teknoloji
- Backend: Python + Flask (`app.py` — tek dosyalık monolith)
- Veritabanı: production'da Supabase (PostgreSQL, `DATABASE_URL` env var varsa `USE_PG=True` olur); lokalde SQLite (`berber.db`)
- `psycopg2-binary` ile Postgres bağlantısı; sorgu placeholder'ı PG'de `%s`, SQLite'da `?` (`PH` değişkeni)
- Supabase bağlantısı Session pooler üzerinden (`aws-0-eu-west-1.pooler.supabase.com:5432`) — Transaction pooler ücretsiz planda IPv4 add-on gerektirdiği için Session pooler tercih edildi

## Ortam Değişkenleri (Render'da ayarlanır)
- `SECRET_KEY` — Flask session anahtarı (Render'da otomatik üretiliyor)
- `ADMIN_PASSWORD` — `/admin` paneli şifresi (yoksa varsayılan `admin123`, production'da mutlaka set edilmeli)
- `DATABASE_URL` — Supabase Postgres connection string (Session pooler, port 5432)

## İş Mantığı
- Hizmetler (`SERVICES` listesi, app.py:23): Saç Kesimi 30dk/150₺, Sakal Düzeltme 20dk/100₺, Saç+Sakal 45dk/230₺, Fön 20dk/80₺, Çocuk Kesimi 25dk/100₺
- Çalışma saatleri (`WORKING_HOURS`, app.py:31): Pzt–Cmt 09:00–19:00, 30dk slotlar, Pazar kapalı
- Admin paneli: `/admin`, şifre `ADMIN_PASSWORD` ile korunuyor
