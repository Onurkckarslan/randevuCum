from fastapi.templating import Jinja2Templates
from jinja2 import FileSystemLoader, Environment
from pathlib import Path
import os

_BASE = Path(__file__).parent.parent   # → RandevuCum/
_TMPL = str(_BASE / "app" / "templates")

# auto_reload=True + cache_size=0 → her request'te dosyayı diskten okur
_env = Environment(
    loader=FileSystemLoader(_TMPL),
    auto_reload=True,
    cache_size=0,          # template cache'i tamamen kapat
    bytecode_cache=None,
)
_env.globals["enumerate"] = enumerate

templates = Jinja2Templates(env=_env)
