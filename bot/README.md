# 🎌 Anime Telegram Bot

Python + aiogram 3 + Jikan API (MyAnimeList) + PostgreSQL (ixtiyoriy). Interfeys — o'zbek tilida.

## Imkoniyatlar
- 🔍 Nom bo'yicha qidirish (oddiy matn yozish yetarli)
- 🖼 Rasm va batafsil ma'lumot (reyting, qism, holat, janr, studiya, mazmun)
- 🎭 Janrlar, 🔥 mashhur, 🏆 top reyting (sahifalash bilan)
- 🎲 Tavsiyalar: tasodifiy, o'xshash, sevimlilarga asoslangan
- ⭐ Sevimlilar (PostgreSQL yoki JSON fayl)
- 🛠 Professional Admin panel (pastda)

## Tuzilma
```
main.py            kirish nuqtasi
config.py          sozlamalar
bot/callbacks.py   callback ma'lumotlari
bot/keyboards.py   klaviaturalar
bot/handlers/      start, browse, anime, favorites, featured, search, errors
bot/handlers/admin/ panel, setup, stats, users, broadcast, anime, featured, admins, logs
bot/middlewares.py foydalanuvchilarni kuzatish + bloklash
bot/services/      jikan.py (API klient), storage.py (sevimlilar), catalog_client.py,
                   database.py + repo/ (admin jadvallari), access.py (huquqlar), broadcaster.py, stats.py
bot/utils/         text.py, messages.py, timefmt.py
tests/             servis testlari + oflayn simulyator (tests/stubs)
```

## 1. Lokal ishga tushirish
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # BOT_TOKEN ni yozing
python main.py
```
`DATABASE_URL` bo'sh bo'lsa, sevimlilar `data/favorites.json` da saqlanadi.

## 2. Render
1. Kodni GitHub'ga yuklang (`.env` yuklanmaydi).
2. Render → New → Blueprint (yoki Web Service) → repo'ni tanlang. `render.yaml` ishlatiladi.
3. Environment: `BOT_TOKEN` ni kiriting.
4. Sevimlilar doimiy saqlansin desangiz: Render PostgreSQL yarating va **Internal Database URL** ni `DATABASE_URL` ga qo'ying.
5. Eslatma: bepul Web Service 15 daqiqa so'rovsiz uxlaydi. Bot uxlamasligi uchun UptimeRobot orqali `https://<app>.onrender.com/` manzilini 5 daqiqada ping qiling, yoki pullik Background Worker oling.

## 3. Railway
1. New Project → Deploy from GitHub repo.
2. Variables: `BOT_TOKEN`.
3. + New → Database → PostgreSQL, so'ng botga `DATABASE_URL` = `${{Postgres.DATABASE_URL}}` qo'shing.
4. `Procfile` start buyrug'ini beradi. Deploy tugagach bot ishlaydi.

## Xavfsizlik
Tokenni hech qachon kodga yoki GitHub'ga yozmang. Token oshkor bo'lsa, @BotFather → `/revoke` orqali yangilang.

## Eslatmalar
- Jikan limiti: sekundiga 3 ta so'rov. Bot kesh va navbat bilan buni avtomatik boshqaradi.
- Mazmun (synopsis) MyAnimeList'dan inglizcha keladi; qolgan interfeys o'zbekcha.
- 18+ kontent (Hentai/Erotica/Rx) filtrlanadi.

---

# 🛠 Admin panel

Bot ichida ishlaydi: `/admin` buyrug'i yoki adminlarga ko'rinadigan «🛠 Admin panel» tugmasi. Interfeys to'liq o'zbekcha, barcha menyularda «Orqaga» va «🏠 Admin panel» tugmalari, xavfli amallar tasdiqlash oynasi bilan.

## Bo'limlar
| Bo'lim | Imkoniyatlar |
|---|---|
| 📊 Statistika | Umumiy · Foydalanuvchilar (7 kunlik grafik) · Qidiruvlar (bugun/7/30 kun, eng ko'p qidirilganlar) · Top animelar · Bot holati |
| 👥 Foydalanuvchilar | Ro'yxat (sahifalash), ID/@username bo'yicha qidirish, bloklash/blokdan chiqarish, faollik tarixi |
| 📣 Xabar yuborish | Matn yoki rasm+izoh, ixtiyoriy havola-tugma (reklama/e'lon), ko'rib chiqish, jonli jarayon (yuborildi / bloklagan / xatolik), to'xtatish, tarix |
| 🎬 Anime boshqaruvi | Anime qo'shish/tahrirlash/o'chirish, ⭐ tavsiya etilganlar, 🔥 mashhur ro'yxati (qo'shish, tartib, olib tashlash) |
| ⚙️ Adminlar | Admin qo'shish, huquqlarni yoqish/o'chirish, olib tashlash |
| 📜 Harakatlar tarixi | Kim, qachon, nima qilgani (hammasi yoki faqat o'zingiznikilar) |

Admin qo'shgan animelar foydalanuvchilar qidiruvida MyAnimeList natijalari bilan birga chiqadi. «Mashhur» ro'yxati foydalanuvchining «🔥 Mashhur» bo'limida tepada, «Tavsiya» ro'yxati «🎲 Tavsiya → ⭐ Admin tavsiyalari» da ko'rinadi. MyAnimeList animelarining ma'lumotini tahrirlab bo'lmaydi (ular tashqi manbadan keladi) — tahrirlash admin qo'shgan animelar uchun.

## Xavfsizlik
- Admin faqat **Telegram ID** orqali aniqlanadi. Har bir admin tugmasi/xabari bajarilishidan oldin ID va huquq tekshiriladi; xavfli amallar (bloklash, o'chirish, adminni olib tashlash) tasdiqlashda qayta tekshiriladi.
- Admin amallari faqat shaxsiy chatda ishlaydi. Oddiy foydalanuvchi admin tugmalarini soxtalashtirsa ham «⛔ ruxsat yo'q» oladi.
- Huquqlar: `stats`, `users`, `broadcast`, `anime`, `admins`. Oddiy admin faqat o'zida bor huquqni bera oladi, `admins` huquqini va Super Adminni faqat Super Admin boshqaradi; o'z huquqini o'zgartira olmaydi; `admins` huquqli adminlar bir-birini o'zgartira olmaydi.
- **Super Admin** (@jumaboyev101): barcha huquqlar, hech kim uning huquqlarini o'zgartira/olib tashlay olmaydi, adminlarni bloklab bo'lmaydi.

## Super Admin ID sini xavfsiz bog'lash (`/claim`)
Username o'zgarishi yoki boshqaga o'tishi mumkin, shuning uchun u faqat **birinchi bog'lash** uchun ishlatiladi, undan keyin tekshiruv Telegram ID bo'yicha.
1. Bot birinchi marta ishga tushganda (Super Admin bog'lanmagan bo'lsa) hosting **loglariga** bir martalik kod yozadi:
   `SUPER ADMIN hali bog'lanmagan. @jumaboyev101 akkauntidan botga yuboring:  /claim XXXX-XXXX-XXXX`
   (yoki o'zingiz `SUPER_ADMIN_SETUP_CODE` o'zgaruvchisiga kod yozasiz — kamida 8 belgi).
2. **@jumaboyev101** akkauntidan botga shaxsiy chatda `/claim KOD` yuboring. Kod **ham**, username **ham** mos kelishi shart; kod xabari chatdan o'chiriladi.
3. Muvaffaqiyatli bo'lsa ID bazaga yoziladi, kod bekor bo'ladi, `/claim` boshqalar uchun jim turadi. Noto'g'ri urinishlar cheklangan (5 ta / 15 daqiqa, umumiy 30 ta / soat).
4. Telegram ID ni bilsangiz (`/id` buyrug'i ko'rsatadi), `SUPER_ADMIN_IDS=<id>` bersangiz `/claim` umuman o'chadi.
5. Akkauntni almashtirish kerak bo'lsa: `RESET_SUPER_ADMIN_BINDING=1` bilan qayta ishga tushiring, yangi kod logda chiqadi, bog'lagach o'zgaruvchini **o'chiring**.

## Ma'lumotlar bazasi
Admin paneli yangi jadvallar yaratadi (`users`, `search_logs`, `anime_stats`, `counters`, `custom_anime`, `featured`, `admins`, `admin_logs`, `broadcasts`) va avtomatik `CREATE TABLE IF NOT EXISTS` bilan ishga tushadi. `DATABASE_URL` bo'lsa sevimlilar jadvali bilan **bir xil PostgreSQL**, bo'lmasa lokal `data/bot.db` (SQLite). Mavjud `favorites` jadvali o'zgarmaydi. Qidiruv jurnali 90 kundan keyin tozalanadi.

> ⚠️ Render/Railway bepul rejalarida disk vaqtinchalik: SQLite/JSON fayllar qayta deploydan keyin yo'qoladi (jumladan Super Admin bog'lanishi, bloklanganlar, qo'shilgan animelar). Admin panel uchun **PostgreSQL (`DATABASE_URL`) ulashni qat'iy tavsiya qilamiz**. Bot bitta nusxada (single instance) ishlashi kerak.

## Sinovlar
```bash
pip install pytest
python -m pytest tests -q
```
`tests/stubs` — aiogram o'rnatilmagan muhit uchun soddalashtirilgan nusxa (haqiqiy aiogram bor bo'lsa ishlatilmaydi va simulyator testlari o'tkazib yuboriladi).
