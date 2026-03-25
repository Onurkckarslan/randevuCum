from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import asyncio
from .database import engine, SessionLocal, get_db
from . import models
from .routes import auth, panel, booking, categories, staff_portal, admin
from .scheduler import scheduler_loop
from .auth import get_current_business_id
from .models import Business
from pathlib import Path
from sqlalchemy.orm import Session

_BASE = Path(__file__).parent.parent

@asynccontextmanager
async def lifespan(app: FastAPI):
    models.Base.metadata.create_all(bind=engine)

    # S3 column migration
    # Staff authorization migration
    from sqlalchemy import text
    db = SessionLocal()
    try:
        db.execute(text("""
            ALTER TABLE business_photos
            ADD COLUMN IF NOT EXISTS s3_url VARCHAR(500)
        """))
        db.execute(text("""
            ALTER TABLE staff
            ADD COLUMN IF NOT EXISTS staff_login_id VARCHAR(50)
        """))
        db.execute(text("""
            ALTER TABLE staff
            ADD COLUMN IF NOT EXISTS role VARCHAR(20) DEFAULT 'personel'
        """))
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS customer_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_id INTEGER NOT NULL,
                name VARCHAR(100),
                phone VARCHAR(20) NOT NULL,
                notes TEXT,
                preferences TEXT,
                allergies TEXT,
                vip_status BOOLEAN DEFAULT 0,
                total_visits INTEGER DEFAULT 0,
                last_visit DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))
        db.commit()
    except Exception as e:
        db.rollback()
    finally:
        db.close()

    asyncio.create_task(scheduler_loop())
    yield

app = FastAPI(title="RandevuCum", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(_BASE / "app" / "static")), name="static")

from .templates_config import templates

templates.env.globals["enumerate"] = enumerate

# current_business'i global Jinja2 context processor olarak ekle
_orig_response = templates.TemplateResponse.__func__ if hasattr(templates.TemplateResponse, '__func__') else None

import functools
_orig = templates.TemplateResponse

@functools.wraps(_orig)
def _patched_response(name, context, *args, **kwargs):
    request = context.get("request")
    if request and "current_business" not in context:
        biz_id = get_current_business_id(request)
        if biz_id:
            db = SessionLocal()
            try:
                context["current_business"] = db.query(Business).filter(Business.id == biz_id).first()
            finally:
                db.close()
        else:
            context["current_business"] = None
    return _orig(name, context, *args, **kwargs)

templates.TemplateResponse = _patched_response

app.include_router(auth.router)         # EN ÖNCE — /giris, /kayit vb.
app.include_router(admin.router)        # Sonra admin
app.include_router(panel.router)
app.include_router(categories.router)
app.include_router(booking.router)      # SON — catch-all /{slug}
app.include_router(staff_portal.router)
