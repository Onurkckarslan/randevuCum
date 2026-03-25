from fastapi.templating import Jinja2Templates
from jinja2 import FileSystemLoader, Environment
from pathlib import Path
from datetime import datetime
import os

_BASE = Path(__file__).parent.parent   # → RandevuCum/
_TMPL = str(_BASE / "app" / "templates")

# Türkçe tarih formatı
def format_date_tr(date_obj):
    """Tarihi 'DD Ay YYYY' formatında Türkçe olarak formatla"""
    if isinstance(date_obj, str):
        # YYYY-MM-DD formatından parse et
        try:
            date_obj = datetime.strptime(date_obj, "%Y-%m-%d")
        except:
            return date_obj

    if not isinstance(date_obj, datetime):
        return date_obj

    months_tr = {
        1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan",
        5: "Mayıs", 6: "Haziran", 7: "Temmuz", 8: "Ağustos",
        9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık"
    }

    return f"{date_obj.day} {months_tr.get(date_obj.month, '')} {date_obj.year}"

# auto_reload=True + cache_size=0 → her request'te dosyayı diskten okur
_env = Environment(
    loader=FileSystemLoader(_TMPL),
    auto_reload=True,
    cache_size=0,          # template cache'i tamamen kapat
    bytecode_cache=None,
)
_env.globals["enumerate"] = enumerate
_env.filters["date_tr"] = format_date_tr

templates = Jinja2Templates(env=_env)
