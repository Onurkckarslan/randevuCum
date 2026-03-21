from ..templates_config import templates
from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Business, Service, Staff, WorkHour, Appointment, BusinessPhoto
from sqlalchemy.orm import joinedload
from ..sms import send_appointment_confirm
from datetime import date, datetime, timedelta
from typing import Optional
import asyncio

router = APIRouter()

SLOT_INTERVAL = 60  # Dakika


def generate_slots(open_time: str, close_time: str, duration: int, booked: list[str]) -> list[dict]:
    """Tüm slotları dolu/boş bilgisiyle döndür."""
    slots = []
    start = datetime.strptime(open_time, "%H:%M")
    end   = datetime.strptime(close_time, "%H:%M")
    current = start
    while current + timedelta(minutes=duration) <= end:
        slot = current.strftime("%H:%M")
        slots.append({"time": slot, "available": slot not in booked})
        current += timedelta(minutes=SLOT_INTERVAL)
    return slots


@router.get("/", response_class=HTMLResponse)
async def homepage(request: Request, db: Session = Depends(get_db)):
    businesses = db.query(Business).filter(Business.is_active == True).all()
    return templates.TemplateResponse("index.html", {
        "request": request, "businesses": businesses
    })


@router.get("/isletmeler-icin", response_class=HTMLResponse)
async def for_businesses(request: Request):
    return templates.TemplateResponse("isletmeler.html", {"request": request})


@router.get("/{slug}", response_class=HTMLResponse)
async def business_page(slug: str, request: Request, db: Session = Depends(get_db)):
    biz = db.query(Business).filter(Business.slug == slug, Business.is_active == True).first()
    if not biz:
        raise HTTPException(status_code=404, detail="İşletme bulunamadı")

    services    = db.query(Service).filter(Service.business_id == biz.id, Service.is_active == True).all()
    staff       = db.query(Staff).filter(Staff.business_id == biz.id, Staff.is_active == True).all()
    work_hours  = db.query(WorkHour).filter(WorkHour.business_id == biz.id).order_by(WorkHour.day_of_week).all()
    photos      = db.query(BusinessPhoto).filter(BusinessPhoto.business_id == biz.id).all()

    return templates.TemplateResponse("customer/business.html", {
        "request": request, "biz": biz, "services": services,
        "staff": staff, "work_hours": work_hours, "photos": photos,
    })


@router.get("/{slug}/musait-saatler")
async def available_slots(
    slug: str,
    service_id: int,
    selected_date: str,
    request: Request,
    staff_id: int = None,
    db: Session = Depends(get_db)
):
    """AJAX: Seçilen tarih için uygun saatleri döndür."""
    biz = db.query(Business).filter(Business.slug == slug).first()
    if not biz:
        return {"slots": []}

    svc = db.query(Service).filter(Service.id == service_id, Service.business_id == biz.id).first()
    if not svc:
        return {"slots": []}

    try:
        selected = datetime.strptime(selected_date, "%Y-%m-%d")
    except ValueError:
        return {"slots": []}

    day_of_week = selected.weekday()
    wh = db.query(WorkHour).filter(
        WorkHour.business_id == biz.id,
        WorkHour.day_of_week == day_of_week
    ).first()

    if wh and wh.is_closed:
        return {"slots": [], "closed": True}

    # Work hours yoksa varsayılan 09:00-19:00
    if not wh:
        from datetime import time as dtime
        class _WH: open_time="09:00"; close_time="19:00"; is_closed=False
        wh = _WH()

    booked_q = db.query(Appointment).filter(
        Appointment.business_id == biz.id,
        Appointment.date == selected_date,
        Appointment.status != "iptal"
    )
    # Personel seçiliyse sadece o personelin dolu saatlerini göster
    if staff_id:
        booked_q = booked_q.filter(Appointment.staff_id == staff_id)
    booked = [a.time for a in booked_q.all()]

    slots = generate_slots(wh.open_time, wh.close_time, svc.duration, booked)
    return {"slots": slots, "closed": False}


@router.post("/{slug}/randevu-al", response_class=HTMLResponse)
async def book_appointment(
    slug: str,
    request: Request,
    service_id: int = Form(...),
    staff_id: Optional[str] = Form(None),
    selected_date: str = Form(...),
    selected_time: str = Form(...),
    customer_name: str = Form(...),
    customer_phone: str = Form(...),
    notes: str = Form(""),
    db: Session = Depends(get_db)
):
    try:
        biz = db.query(Business).filter(Business.slug == slug).first()
        if not biz:
            raise HTTPException(status_code=404)

        svc = db.query(Service).filter(Service.id == service_id, Service.business_id == biz.id).first()
        if not svc:
            raise HTTPException(status_code=400, detail="Hizmet bulunamadı")

        # Çakışma kontrolü
        conflict = db.query(Appointment).filter(
            Appointment.business_id == biz.id,
            Appointment.date == selected_date,
            Appointment.time == selected_time,
            Appointment.status != "iptal"
        ).first()
        if conflict:
            raise HTTPException(status_code=400, detail="Bu saat dolu, lütfen başka bir saat seçin.")

        staff_id_int = int(staff_id) if staff_id and staff_id.strip() else None

        apt = Appointment(
            business_id=biz.id,
            service_id=service_id,
            staff_id=staff_id_int,
            customer_name=customer_name,
            customer_phone=customer_phone,
            date=selected_date,
            time=selected_time,
            notes=notes,
            status="bekliyor"
        )
        db.add(apt)
        db.commit()
        db.refresh(apt)

        # SMS gönder (async, hata olsa da devam et)
        asyncio.create_task(send_appointment_confirm(
            customer_name, customer_phone,
            biz.name, svc.name,
            selected_date, selected_time
        ))

        return templates.TemplateResponse("customer/booking_success.html", {
            "request": request,
            "biz": biz,
            "apt": apt,
            "service": svc,
        })
    except HTTPException:
        raise
    except Exception as e:
        print(f"[BOOKING ERROR] {slug}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Booking error: {str(e)}")

