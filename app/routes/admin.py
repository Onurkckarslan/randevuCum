from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from ..models import Business, Appointment, Service, Staff
from ..templates_config import templates
from datetime import datetime, timedelta
from typing import Optional

router = APIRouter(prefix="/admin")

# ── Basit admin şifresi (ileride .env'e taşı) ────────────────────────────────
ADMIN_PASSWORD = "randevucum2026"
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
        base = biz.plan_expires_at if (biz.plan_expires_at and biz.plan_expires_at > datetime.utcnow()) else datetime.utcnow()
        biz.plan_expires_at = base + timedelta(days=30 * months)
    else:
        biz.plan_expires_at = None
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
