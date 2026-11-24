# Yangilangan botni hostingga qayta joylash

Yangi kutubxona kerak emas (`requirements.txt` o'zgarmagan; SQLite — Python ichida). Mavjud `.env` va hosting o'zgaruvchilaringiz o'z holicha qoladi.

## 0. Tayyorgarlik (1 marta)
1. **PostgreSQL ulang** (tavsiya): Render → New → PostgreSQL → *Internal Database URL* ni botning `DATABASE_URL` ga qo'ying. Bo'lmasa admin ma'lumotlari qayta deploydan keyin yo'qoladi.
2. (Ixtiyoriy) `SUPER_ADMIN_SETUP_CODE` ga o'zingiz kod yozing (kamida 8 belgi), shunda logdan qidirish shart emas.
3. Boshqa yangi o'zgaruvchilar ixtiyoriy: `SUPER_ADMIN_USERNAME` (standart `jumaboyev101`), `SUPER_ADMIN_IDS`, `ADMIN_IDS`, `TIMEZONE_OFFSET` (standart 5).

## 1. Render
1. ZIP ni oching, fayllarni GitHub repoga **ustiga yozib** yuklang (`.env` yuklamang, u ZIP da yo'q).
2. Render avtomatik qayta deploy qiladi (yoki *Manual Deploy → Deploy latest commit*).
3. **Logs** ni oching: `SUPER ADMIN hali bog'lanmagan ... /claim XXXX-XXXX-XXXX` qatori chiqadi.

## 2. Railway
1. Kodni GitHub'ga push qiling — Railway o'zi qayta deploy qiladi.
2. Variables'ga `DATABASE_URL = ${{Postgres.DATABASE_URL}}` (agar hali yo'q bo'lsa).
3. Deploy Logs'dan `/claim` kodini oling.

## 3. VPS / lokal
```bash
unzip anime-bot-admin.zip && cd anime-bot
cp /eski/joy/.env .env        # tokeningiz saqlanadi
pip install -r requirements.txt
python main.py                # loglarda /claim kodi chiqadi
```
(systemd ishlatsangiz: `sudo systemctl restart anime-bot`.)

## 4. Super Admin ni bog'lash
1. **@jumaboyev101** akkauntidan botga shaxsiy chatda yuboring: `/claim XXXX-XXXX-XXXX`
2. «Siz Super Admin sifatida bog'landingiz» xabari kelsa — tayyor. `/admin` bilan panelni oching.
3. Telegram ID ni bilmoqchi bo'lsangiz: `/id`.

## 5. Tekshirib chiqing
- Oddiy hisobdan `/admin` yozing → «faqat adminlar uchun» deyishi kerak.
- `/start`, qidiruv, sevimlilar avvalgidek ishlashi kerak.
- Adminlar → Admin qo'shish orqali yordamchi admin qo'shing va huquqlarini sozlang.

## Muammolar
| Belgi | Yechim |
|---|---|
| Logda `/claim` kodi yo'q | Super Admin allaqachon bog'langan (yoki `SUPER_ADMIN_IDS` berilgan). Qayta bog'lash: `RESET_SUPER_ADMIN_BINDING=1` → qayta ishga tushirish → bog'lang → o'zgaruvchini o'chiring |
| Qayta deploydan keyin admin/bloklash/anime yo'qoldi | `DATABASE_URL` (PostgreSQL) ulanmagan — 0-qadam |
| «Juda ko'p urinish» | 15 daqiqa kuting yoki botni qayta ishga tushiring |
| Bot ikki nusxada ishlayapti | Bitta nusxa qoldiring (polling conflict) |
