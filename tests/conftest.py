import importlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
STUBS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stubs")

# Haqiqiy aiogram o'rnatilmagan muhitda (masalan, sandbox) soddalashtirilgan nusxa ishlatiladi.
# Haqiqiy aiogram bo'lsa, faqat unga bog'liq bo'lmagan servis testlari ishga tushadi.
try:
    importlib.import_module("aiogram")
    collect_ignore_glob = ["test_sim_*.py"]
except ImportError:
    sys.path.append(STUBS)
