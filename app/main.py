from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import asyncio
import time
from collections import defaultdict
from .database import engine, SessionLocal, get_db
from . import models
from .routes import auth, panel, booking, categories, staff_portal, admin, whatsapp, leads, subscription
from .scheduler import scheduler_loop
from .auth import get_current_business_id
from .models import Business
from pathlib import Path
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

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

        # ── PRIORITY 1: Add subscription fields to businesses (BEFORE any queries!) ──
        if "businesses" in inspector.get_table_names():
            cols = [col["name"] for col in inspector.get_columns("businesses")]

            subscription_cols = {
                "subscription_status": "VARCHAR(20) DEFAULT 'trial'",
                "paytr_card_token": "VARCHAR(255)",
                "card_last4": "VARCHAR(4)",
                "card_brand": "VARCHAR(20)",
                "next_billing_date": "TIMESTAMP",
                "payment_failed_count": "INTEGER DEFAULT 0"
            }

            for col_name, col_type in subscription_cols.items():
                if col_name not in cols:
                    try:
                        query = f"ALTER TABLE businesses ADD COLUMN {col_name} {col_type}"
                        db.execute(text(query))
                        db.commit()  # Commit immediately for safety
                        print(f"[Migration] ✅ Column added: {col_name}")
                    except Exception as col_err:
                        db.rollback()
                        print(f"[Migration] Column {col_name} may already exist: {str(col_err)}")

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

        # ── Add is_paid and end_date to appointments ──
        if "appointments" in inspector.get_table_names():
            cols = [col["name"] for col in inspector.get_columns("appointments")]
            if "is_paid" not in cols:
                db.execute(text("ALTER TABLE appointments ADD COLUMN is_paid BOOLEAN DEFAULT FALSE"))
            if "end_date" not in cols:
                db.execute(text("ALTER TABLE appointments ADD COLUMN end_date VARCHAR(10)"))

        # ── Add whatsapp_enabled and whatsapp_phone to businesses ──
        if "businesses" in inspector.get_table_names():
            cols = [col["name"] for col in inspector.get_columns("businesses")]
            if "whatsapp_enabled" not in cols:
                db.execute(text("ALTER TABLE businesses ADD COLUMN whatsapp_enabled BOOLEAN DEFAULT FALSE"))
            if "whatsapp_phone" not in cols:
                db.execute(text("ALTER TABLE businesses ADD COLUMN whatsapp_phone VARCHAR(20)"))
            if "business_code" not in cols:
                db.execute(text("ALTER TABLE businesses ADD COLUMN business_code VARCHAR(6) UNIQUE"))
            if "logo_url" not in cols:
                db.execute(text("ALTER TABLE businesses ADD COLUMN logo_url VARCHAR(500)"))
            if "plan_type" not in cols:
                db.execute(text("ALTER TABLE businesses ADD COLUMN plan_type VARCHAR(20) DEFAULT 'temel'"))
            if "subscription_end_date" not in cols:
                db.execute(text("ALTER TABLE businesses ADD COLUMN subscription_end_date TIMESTAMP"))

            # ── Auto-assign business_code to NULL entries ──
            import random, string
            def generate_unique_code():
                while True:
                    code = ''.join(random.choices(string.digits, k=6))
                    if not db.query(Business).filter(Business.business_code == code).first():
                        return code

            null_businesses = db.query(Business).filter(Business.business_code == None).all()
            for biz in null_businesses:
                biz.business_code = generate_unique_code()

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

        # ── Create payments table if not exists ──
        if "payments" not in inspector.get_table_names():
            try:
                db.execute(text("""
                    CREATE TABLE payments (
                        id SERIAL PRIMARY KEY,
                        business_id INTEGER NOT NULL,
                        amount INTEGER NOT NULL,
                        plan_type VARCHAR(20),
                        status VARCHAR(20) DEFAULT 'pending',
                        paytr_ref_no VARCHAR(100),
                        error_msg VARCHAR(255),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        paid_at TIMESTAMP
                    )
                """))
                print("[Migration] ✅ Payments table created")
            except Exception as tbl_err:
                print(f"[Migration] Payments table creation error: {str(tbl_err)}")

        db.commit()
        print("[Migration] ✅ Tüm migration'lar başarıyla tamamlandı")
    except Exception as e:
        db.rollback()
        print(f"[Migration] ❌ HATA: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

    asyncio.create_task(scheduler_loop())
    yield

app = FastAPI(title="RandevuCum", lifespan=lifespan)

# ── Rate Limiting (In-Memory) ──
_rate_limit_store = defaultdict(list)  # IP → [timestamps]
RATE_LIMIT_REQUESTS = 100  # requests per minute
RATE_LIMIT_WINDOW = 60  # seconds

class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Get client IP
        client_ip = request.client.host if request.client else "unknown"

        # Limit only auth endpoints to prevent brute force
        if request.url.path in ["/giris", "/kayit", "/personel/giris"]:
            now = time.time()
            # Clean old timestamps
            _rate_limit_store[client_ip] = [ts for ts in _rate_limit_store[client_ip] if now - ts < RATE_LIMIT_WINDOW]

            # Check rate limit
            if len(_rate_limit_store[client_ip]) >= RATE_LIMIT_REQUESTS:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Çok fazla giriş denemesi. Lütfen 1 dakika sonra tekrar deneyin."}
                )

            # Add current timestamp
            _rate_limit_store[client_ip].append(now)

        response = await call_next(request)
        return response

# ── Security Headers Middleware ──
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=()"
        return response

app.add_middleware(RateLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.mount("/static", StaticFiles(directory=str(_BASE / "app" / "static")), name="static")

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    print(f"[VALIDATION ERROR] {request.method} {request.url.path}")
    for error in exc.errors():
        print(f"  {error['loc']}: {error['msg']}")
    return JSONResponse(status_code=422, content={"detail": exc.errors()})

from .templates_config import templates
from datetime import datetime

templates.env.globals["enumerate"] = enumerate
templates.env.globals["now"] = lambda: datetime.utcnow()

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
app.include_router(leads.router)        # Lead API endpoint
app.include_router(subscription.router) # Abonelik & Ödeme
app.include_router(panel.router)
app.include_router(categories.router)
app.include_router(whatsapp.router)     # WhatsApp webhook
app.include_router(booking.router)      # SON — catch-all /{slug}
app.include_router(staff_portal.router)
