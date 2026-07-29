# Berber Randevu Sistemi

Web tabanlı berber randevu sistemi. Müşteriler siteden hizmet, tarih ve saat seçerek randevu alır; berber ise admin panelinden randevuları yönetir.

**Canlı:** https://berber-randevu-bk4y.onrender.com

## Özellikler

- Müşteri tarafı: hizmet + tarih seçimi, o gün için müsait saatlerin otomatik hesaplanması, randevu onayı
- Admin paneli (`/admin`):
  - Günlük/haftalık özet, bekleyen randevular, 30 saniyede bir canlı yenilenen bildirimler
  - Takvim ve liste görünümleri, randevu durumu güncelleme (onayla / tamamla / iptal et)
  - Hizmet fiyatlarını panelden düzenleme
  - Admin şifresini panelden değiştirme

## Teknoloji

- Backend: Python + Flask (`app.py`)
- Veritabanı: production'da PostgreSQL (Supabase), lokalde SQLite (`berber.db`)
- Deployment: Render.com

## Lokalde çalıştırma

```bash
pip install -r requirements.txt
python app.py
```

Varsayılan olarak `http://localhost:5000` üzerinde SQLite ile çalışır (`DATABASE_URL` ortam değişkeni tanımlı değilse).

## Ortam Değişkenleri

| Değişken | Açıklama |
|---|---|
| `SECRET_KEY` | Flask session anahtarı |
| `ADMIN_PASSWORD` | Admin paneli için yedek/master şifre (panelden değiştirilen şifreyi unutursan bu her zaman çalışır) |
| `DATABASE_URL` | PostgreSQL connection string (Supabase) — tanımlı değilse SQLite kullanılır |

## Hizmetler ve Çalışma Saatleri

Hizmet listesi ve fiyatları veritabanında tutulur, admin panelinden (`/admin/hizmetler`) düzenlenebilir. Çalışma saatleri (`app.py` içindeki `WORKING_HOURS`) Pzt–Cmt 09:00–19:00, 30 dakikalık slotlar şeklinde sabittir.
