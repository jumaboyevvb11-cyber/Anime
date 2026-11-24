# O'zgargan va yangi fayllar

## Mavjud fayllarga kiritilgan o'zgarishlar (kichik, xulq-atvor saqlangan)
- `main.py` — repo/access/middleware ulandi; `build_dispatcher()` ajratildi. **Tuzatish:** `Dispatcher(storage=...)` aiogram FSM saqlagichi uchun band, shu sabab sevimlilar saqlagichi `workflow_data["storage"]` orqali beriladi (handlerlar o'zgarmadi).
- `config.py` — yangi sozlamalar (super admin, admin ID lar, SQLite yo'li, vaqt mintaqasi).
- `bot/handlers/__init__.py` — admin routerlari birinchi, qidiruv eng oxirida.
- `bot/handlers/start.py` — adminlarga «🛠 Admin panel» tugmasi.
- `bot/handlers/search.py`, `anime.py` — qidiruv va ko'rishlarni statistikaga yozish (orqa fonda); tavsiya menyusida admin tavsiyalari.
- `bot/keyboards.py`, `bot/callbacks.py` — `main_menu(is_admin)`, `recommend_menu(has_featured)`, `CB_FEATURED`.
- `bot/services/storage.py` — `total()`, `purge()` qo'shildi.
- `bot/utils/text.py` — admin qo'shgan anime tavsifida «(inglizcha)» belgisi chiqmaydi.
- `.env.example`, `render.yaml`, `README.md`, `.gitignore`.

## Yangi fayllar
- `bot/services/`: `database.py`, `repo/` (users, searches, catalog, admins, broadcasts), `access.py`, `catalog_client.py`, `broadcaster.py`, `stats.py`
- `bot/handlers/admin/`: `panel, setup, stats, users, broadcast, anime, featured, admins, logs, common`
- `bot/handlers/featured.py`, `bot/middlewares.py`, `bot/keyboards_admin.py`, `bot/callbacks_admin.py`, `bot/states.py`, `bot/utils/timefmt.py`
- `tests/` — servis testlari va oflayn simulyator
- `HOSTING_YANGILASH.md` — hostingga qayta joylash yo'riqnomasi
