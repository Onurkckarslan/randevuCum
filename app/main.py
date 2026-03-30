from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import asyncio
from .database import engine, SessionLocal, get_db
from . import models
from .routes import auth, panel, booking, categories, staff_portal, admin, whatsapp
from .scheduler import scheduler_loop
from .auth import get_current_business_id
from .models import Business
from pathlib import Path
from sqlalchemy.orm import Session

_BASE = Path(__file__).parent.parent

@asynccontextmanager
async def lifespan(app: FastAPI):
    models.Base.metadata.create_all(bind=engine)

    # Database migrations
    from sqlalchemy import text, inspect
    db = SessionLocal()
    try:
        # Helper to check if column exists
        inspector = inspect(engine)

        # ── Add s3_url to business_photos ──
        if "business_photos" in inspector.get_table_names():
            cols = [col["name"] for col in inspector.get_columns("business_photos")]
            if "s3_url" not in cols:
                db.execute(text("ALTER TABLE business_photos ADD COLUMN s3_url VARCHAR(500)"))

        # ── Add staff_login_id and role to staff ──
        if "staff" in inspector.get_table_names():
            cols = [col["name"] for col in inspector.get_columns("staff")]
            if "staff_login_id" not in cols:
                db.execute(text("ALTER TABLE staff ADD COLUMN staff_login_id VARCHAR(50)"))
            if "role" not in cols:
                db.execute(text("ALTER TABLE staff ADD COLUMN role VARCHAR(20) DEFAULT 'personel'"))

        # ── Add is_paid to appointments ──
        if "appointments" in inspector.get_table_names():
            cols = [col["name"] for col in inspector.get_columns("appointments")]
            if "is_paid" not in cols:
                db.execute(text("ALTER TABLE appointments ADD COLUMN is_paid BOOLEAN DEFAULT FALSE"))

        # ── Add whatsapp_enabled and whatsapp_phone to businesses ──
        if "businesses" in inspector.get_table_names():
            cols = [col["name"] for col in inspector.get_columns("businesses")]
            if "whatsapp_enabled" not in cols:
                db.execute(text("ALTER TABLE businesses ADD COLUMN whatsapp_enabled BOOLEAN DEFAULT FALSE"))
            if "whatsapp_phone" not in cols:
                db.execute(text("ALTER TABLE businesses ADD COLUMN whatsapp_phone VARCHAR(20)"))

        # ── Create customer_profiles if not exists ──
        if "customer_profiles" not in inspector.get_table_names():
            db.execute(text("""
                CREATE TABLE customer_profiles (
                    id SERIAL PRIMARY KEY,
                    business_id INTEGER NOT NULL,
                    name VARCHAR(100),
                    phone VARCHAR(20) NOT NULL,
                    notes TEXT,
                    preferences TEXT,
                    allergies TEXT,
                    vip_status BOOLEAN DEFAULT FALSE,
                    total_visits INTEGER DEFAULT 0,
                    last_visit TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))

        # ── Create expenses if not exists ──
        if "expenses" not in inspector.get_table_names():
            db.execute(text("""
                CREATE TABLE expenses (
                    id SERIAL PRIMARY KEY,
                    business_id INTEGER NOT NULL,
                    amount INTEGER NOT NULL,
                    category VARCHAR(50) DEFAULT 'Diğer',
                    description TEXT,
                    date VARCHAR(10) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))

        # ── Create whatsapp_conversations if not exists ──
        if "whatsapp_conversations" not in inspector.get_table_names():
            db.execute(text("""
                CREATE TABLE whatsapp_conversations (
                    id SERIAL PRIMARY KEY,
                    business_id INTEGER NOT NULL,
                    customer_phone VARCHAR(20) NOT NULL,
                    status VARCHAR(50) DEFAULT 'waiting_service',
                    selected_service_id INTEGER,
                    selected_staff_id INTEGER,
                    selected_date VARCHAR(10),
                    selected_time VARCHAR(5),
                    customer_name VARCHAR(100),
                    message_count INTEGER DEFAULT 0,
                    last_message_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))

        # ── Add selected_staff_id to whatsapp_conversations if it doesn't exist ──
        if "whatsapp_conversations" in inspector.get_table_names():
            cols = [col["name"] for col in inspector.get_columns("whatsapp_conversations")]
            if "selected_staff_id" not in cols:
                db.execute(text("ALTER TABLE whatsapp_conversations ADD COLUMN selected_staff_id INTEGER"))

        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Migration warning: {e}")
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

from fastapi.exceptions import RequestValidationError

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    print(f"[VALIDATION ERROR] {request.method} {request.url.path}")
    print(f"[VALIDATION ERROR] Details: {exc.errors()}")
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=422,
        content={"detail": str(exc)},
    )

app.include_router(auth.router)         # EN ÖNCE — /giris, /kayit vb.
app.include_router(admin.router)        # Sonra admin
app.include_router(panel.router)
app.include_router(categories.router)
app.include_router(whatsapp.router)     # WhatsApp webhook
app.include_router(booking.router)      # SON — catch-all /{slug}
app.include_router(staff_portal.router)
