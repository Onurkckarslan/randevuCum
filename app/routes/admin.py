from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from ..models import Business, Appointment, Service, Staff
from ..templates_config import templates
from datetime import datetime, timedelta
from typing import Optional
import asyncio
from ..whatsapp import purchase_twilio_number

router = APIRouter(prefix="/admin")

# ── Basit admin şifresi (ileride .env'e taşı) ────────────────────────────────
ADMIN_PASSWORD = "Askay6464*"
ADMIN_COOKIE   = "rc_admin_session"

def is_admin(request: Request) -> bool:
    return request.cookies.get(ADMIN_COOKIE) == ADMIN_PASSWORD

def require_admin(request: Request):
    if not is_admin(request):
        raise HTTPException(status_code=302, headers={"Location": "/admin/login"})

# ── LOGIN ─────────────────────────────────────────────────────────────────────
@router.get("/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    return templates.TemplateResponse("admin/login.html", {"request": request, "error": None})

@router.post("/login")
async def admin_login(request: Request, password: str = Form(...)):
    if password == ADMIN_PASSWORD:
        response = RedirectResponse("/admin", status_code=302)
        response.set_cookie(ADMIN_COOKIE, ADMIN_PASSWORD, httponly=True, max_age=86400*7)
        return response
    return templates.TemplateResponse("admin/login.html", {"request": request, "error": "Şifre hatalı!"})

@router.get("/logout")
async def admin_logout():
    response = RedirectResponse("/admin/login", status_code=302)
    response.delete_cookie(ADMIN_COOKIE)
    return response

# ── DASHBOARD ─────────────────────────────────────────────────────────────────
@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    require_admin(request)
    businesses  = db.query(Business).order_by(Business.created_at.desc()).all()
    total_biz   = len(businesses)
    total_appt  = db.query(Appointment).count()
    premium_cnt = sum(1 for b in businesses if b.plan == "premium")
    temel_cnt   = total_biz - premium_cnt
    active_cnt  = sum(1 for b in businesses if b.is_active)
    # Bu ayki randevular
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0)
    month_appt  = db.query(Appointment).filter(Appointment.created_at >= month_start).count()
    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request,
        "businesses": businesses,
        "total_biz": total_biz,
        "total_appt": total_appt,
        "premium_cnt": premium_cnt,
        "temel_cnt": temel_cnt,
        "active_cnt": active_cnt,
        "month_appt": month_appt,
        "now": now,
    })

# ── İŞLETME DETAY ─────────────────────────────────────────────────────────────
@router.get("/business/{biz_id}", response_class=HTMLResponse)
async def admin_business_detail(biz_id: int, request: Request, db: Session = Depends(get_db)):
    require_admin(request)
    biz = db.query(Business).filter(Business.id == biz_id).first()
    if not biz:
        raise HTTPException(404)
    appointments = db.query(Appointment).filter(
        Appointment.business_id == biz_id
    ).order_by(Appointment.created_at.desc()).limit(50).all()
    return templates.TemplateResponse("admin/business_detail.html", {
        "request": request, "biz": biz, "appointments": appointments
    })

# ── PLAN DEĞİŞTİR ─────────────────────────────────────────────────────────────
@router.post("/business/{biz_id}/plan")
async def admin_set_plan(
    biz_id: int, request: Request,
    plan: str = Form(...),
    months: int = Form(1),
    db: Session = Depends(get_db)
):
    require_admin(request)
    biz = db.query(Business).filter(Business.id == biz_id).first()
    if not biz:
        raise HTTPException(404)

    biz.plan = plan

    if plan == "premium":
        # Premium'a yükselt, WhatsApp numarası al
        base = biz.plan_expires_at if (biz.plan_expires_at and biz.plan_expires_at > datetime.utcnow()) else datetime.utcnow()
        biz.plan_expires_at = base + timedelta(days=30 * months)
        biz.whatsapp_enabled = True

        # Eğer WhatsApp numarası yoksa, Twilio'dan satın al veya boş numaralardan birini ata
        if not biz.whatsapp_phone:
            print(f"[Admin] Setting Twilio number for business {biz_id}...")

            # Önce boş (kimseye atanmamış) numaralardan birini bul
            existing_assigned = db.query(Business).filter(
                Business.whatsapp_phone != None,
                Business.whatsapp_phone != ""
            ).all()
            assigned_numbers = {b.whatsapp_phone for b in existing_assigned}

            # Mevcut Twilio numaraları (config'ten)
            available_twilio_numbers = [
                "+1 415 691 2998",
                "+1 510 871 8367",
                "+14155238886"
            ]

            # Boş numaraları bul
            free_numbers = [n for n in available_twilio_numbers if n not in assigned_numbers]

            if free_numbers:
                # Numarayı normalize et (boşluğu kaldır)
                normalized = free_numbers[0].replace(" ", "")
                biz.whatsapp_phone = normalized
                print(f"[Admin] Twilio number assigned: {normalized}")
            else:
                # Tüm numaralar atanmışsa, yeni satın al
                print(f"[Admin] All Twilio numbers assigned, buying new one...")
                phone_number = await purchase_twilio_number()
                if phone_number:
                    # Yeni numarayı da normalize et
                    normalized = phone_number.replace(" ", "")
                    biz.whatsapp_phone = normalized
                    print(f"[Admin] New number purchased: {normalized}")
                else:
                    print(f"[Admin] Failed to purchase number (may be in sandbox mode)")
    else:
        # Temel plana düşür
        biz.plan_expires_at = None
        biz.whatsapp_enabled = False

    db.commit()
    return RedirectResponse(f"/admin/business/{biz_id}", status_code=302)

# ── AKTİF/PASİF TOG ─────────────────────────────────────────────────────────
@router.post("/business/{biz_id}/toggle")
async def admin_toggle_business(biz_id: int, request: Request, db: Session = Depends(get_db)):
    require_admin(request)
    biz = db.query(Business).filter(Business.id == biz_id).first()
    if not biz:
        raise HTTPException(404)
    biz.is_active = not biz.is_active
    db.commit()
    return RedirectResponse(f"/admin/business/{biz_id}", status_code=302)

# ── İŞLETME SİL ─────────────────────────────────────────────────────────────
@router.post("/business/{biz_id}/delete")
async def admin_delete_business(biz_id: int, request: Request, db: Session = Depends(get_db)):
    require_admin(request)
    biz = db.query(Business).filter(Business.id == biz_id).first()
    if not biz:
        raise HTTPException(404)
    db.delete(biz)
    db.commit()
    return RedirectResponse("/admin", status_code=302)

# ── RANDEVU DURUM DEĞİŞTİR ───────────────────────────────────────────────────
@router.post("/appointment/{appt_id}/status")
async def admin_set_appt_status(
    appt_id: int, request: Request,
    status: str = Form(...),
    db: Session = Depends(get_db)
):
    require_admin(request)
    appt = db.query(Appointment).filter(Appointment.id == appt_id).first()
    if not appt:
        raise HTTPException(404)
    appt.status = status
    db.commit()
    return RedirectResponse(f"/admin/business/{appt.business_id}", status_code=302)

# ── WHATSAPP NUMARALARINI NORMALIZE ET ────────────────────────────────────
@router.post("/normalize-numbers")
async def admin_normalize_numbers(request: Request, db: Session = Depends(get_db)):
    require_admin(request)

    businesses = db.query(Business).all()
    updated_count = 0

    for biz in businesses:
        if biz.whatsapp_phone:
            original = biz.whatsapp_phone
            normalized = original.replace(" ", "")

            if original != normalized:
                biz.whatsapp_phone = normalized
                updated_count += 1

    db.commit()
    print(f"[Admin] {updated_count} WhatsApp numbers normalized")

    return RedirectResponse("/admin", status_code=302)
