from ..templates_config import templates
from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from ..models import Staff, Appointment, Service
from jose import JWTError, jwt
from datetime import datetime, timedelta, date
import os

router = APIRouter(prefix="/personel")

SECRET_KEY   = os.getenv("SECRET_KEY", "RandevuCum-secret-change-in-prod")
ALGORITHM    = "HS256"
COOKIE_NAME  = "staff_token"
EXPIRE_DAYS  = 30
IS_PRODUCTION = os.getenv("ENVIRONMENT") == "production"


def create_staff_token(staff_id: int) -> str:
    expire = datetime.utcnow() + timedelta(days=EXPIRE_DAYS)
    return jwt.encode({"staff_id": str(staff_id), "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def get_current_staff_id(request: Request) -> int | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return int(payload.get("staff_id"))
    except JWTError:
        return None


def get_current_staff(request: Request, db: Session) -> Staff | None:
    staff_id = get_current_staff_id(request)
    if not staff_id:
        return None
    return db.query(Staff).filter(Staff.id == staff_id, Staff.is_active == True).first()


# ── GİRİŞ SAYFASI ──────────────────────────────────────────────────────────
@router.get("/giris", response_class=HTMLResponse)
async def staff_login_page(request: Request, db: Session = Depends(get_db)):
    if get_current_staff(request, db):
        return RedirectResponse("/personel/defterim", status_code=302)
    return templates.TemplateResponse("personel/giris.html", {"request": request, "error": None})


@router.post("/giris")
async def staff_login(
    request: Request,
    email: str = Form(...),
    pin: str   = Form(...),
    db: Session = Depends(get_db)
):
    email = email.strip().lower()
    pin   = pin.strip()
    staff = db.query(Staff).filter(
        Staff.email == email,
        Staff.pin   == pin,
        Staff.is_active == True
    ).first()

    if not staff:
        return templates.TemplateResponse("personel/giris.html", {
            "request": request,
            "error": "E-posta veya PIN hatalı."
        }, status_code=401)

    token = create_staff_token(staff.id)
    resp  = RedirectResponse("/personel/defterim", status_code=302)
    resp.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        secure=IS_PRODUCTION,  # HTTPS only in production
        samesite="strict",      # Stricter CSRF protection
        max_age=60*60*24*EXPIRE_DAYS
    )
    return resp


# ── ÇIKIŞ ──────────────────────────────────────────────────────────────────
@router.get("/cikis")
async def staff_logout():
    resp = RedirectResponse("/personel/giris", status_code=302)
    resp.delete_cookie(COOKIE_NAME)
    return resp


# ── İSTATİSTİK/DASHBOARD ──────────────────────────────────────────────
@router.get("/istatistik", response_class=HTMLResponse)
async def staff_statistics(request: Request, db: Session = Depends(get_db)):
    staff = get_current_staff(request, db)
    if not staff:
        return RedirectResponse("/personel/giris", status_code=302)

    today = date.today().isoformat()
    month_start = date(today.split("-")[0], today.split("-")[1], 1)

    # Bugünün randevuları
    today_appts = db.query(Appointment).filter(
        Appointment.staff_id == staff.id,
        Appointment.date == today,
        Appointment.status != "iptal"
    ).all()

    # Bu ay randevuları
    month_appts = db.query(Appointment).filter(
        Appointment.staff_id == staff.id,
        Appointment.date >= month_start.isoformat(),
        Appointment.status != "iptal"
    ).all()

    # Bugünün geliri
    today_income = sum(appt.service.price for appt in today_appts if appt.service)

    # Bu ayın geliri
    month_income = sum(appt.service.price for appt in month_appts if appt.service)

    # Tüm zamanın geliri
    all_appts = db.query(Appointment).filter(
        Appointment.staff_id == staff.id,
        Appointment.status != "iptal"
    ).all()
    total_income = sum(appt.service.price for appt in all_appts if appt.service)

    # Hizmet bazlı gelir
    service_income = {}
    for appt in all_appts:
        if appt.service:
            svc_name = appt.service.name
            service_income[svc_name] = service_income.get(svc_name, 0) + appt.service.price

    return templates.TemplateResponse("personel/istatistik.html", {
        "request": request,
        "staff": staff,
        "biz": staff.business,
        "today_appts": today_appts,
        "today_income": today_income,
        "month_income": month_income,
        "total_income": total_income,
        "month_appts_count": len(month_appts),
        "service_income": service_income,
    })


# ── PERSONEL PANELİ ──────────────────────────────────────────────────
@router.get("/panel", response_class=HTMLResponse)
@router.get("/defterim", response_class=HTMLResponse)
async def staff_panel(request: Request, d: str = None, db: Session = Depends(get_db)):
    staff = get_current_staff(request, db)
    if not staff:
        return RedirectResponse("/personel/giris", status_code=302)

    sel_date = d or date.today().isoformat()
    appointments = db.query(Appointment).filter(
        Appointment.staff_id == staff.id,
        Appointment.date     == sel_date,
        Appointment.status   != "iptal"
    ).order_by(Appointment.time).all()

    slot_map = {a.time: a for a in appointments}

    slots = []
    h, m = 9, 0
    while h < 21:
        slots.append(f"{h:02d}:{m:02d}")
        m += 30
        if m >= 60:
            m = 0; h += 1

    return templates.TemplateResponse("personel/panel.html", {
        "request": request,
        "staff": staff,
        "biz": staff.business,
        "appointments": appointments,
        "slot_map": slot_map,
        "slots": slots,
        "sel_date": sel_date,
    })
