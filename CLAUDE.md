Proje tanıtımı, özellikler ve kurulum için `README.md`'ye bak. Bu dosya yalnızca Claude Code'a özel altyapı detayları ve kod içinden kolayca anlaşılmayan mimari kararları içerir.

## Altyapı
- Render service: `berber-randevu` (srv-d9hie47lk1mc73e1uub0)
- Supabase project: `berber-randevu` (ref: `usbdjyycpwfkscologii`, org: Alper-Yetik's Org)
- Supabase bağlantısı Session pooler üzerinden (`aws-0-eu-west-1.pooler.supabase.com:5432`) — Transaction pooler ücretsiz planda IPv4 add-on gerektirdiği için tercih edilmedi

## Mimari kararlar (kod okurken şaşırtabilecek noktalar)
- Admin şifresi `settings` tablosunda hash'li tutulur (`/admin/sifre-degistir` ile değiştirilebilir). Ayrıca Render'daki `ADMIN_PASSWORD` env variable'ı HER ZAMAN yedek/master şifre olarak da geçerlidir (bkz. `admin_login`, `admin_change_password`) — panelden değiştirilen şifre unutulursa kilitlenmeyi önlemek için.
- Hizmet fiyatları `services` tablosunda tutulur, koddaki `DEFAULT_SERVICES` sadece ilk kurulumda tabloyu doldurmak için kullanılır. Fiyatlar `/admin/hizmetler` üzerinden düzenlenir; kodda sabit değildir.
- `appointments` tablosunda `(appointment_date, appointment_time)` üzerinde `status != 'cancelled'` koşullu unique index var (`ux_appt_slot`) — aynı saate çift randevu oluşmasını (double-submit / race condition) DB seviyesinde engeller. `randevu_al` içindeki insert bu yüzden `SlotTakenError`'ı yakalayıp zarif hata gösteriyor.
