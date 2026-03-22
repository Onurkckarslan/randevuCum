from ..templates_config import templates
from fastapi import APIRouter, Request, Form, Depends, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Business, Service, Staff, WorkHour, Appointment, BusinessPhoto
import shutil, os, uuid
from pathlib import Path
from ..s3_upload import upload_photo_to_s3, delete_photo_from_s3

UPLOAD_DIR = Path(__file__).parent.parent / "static" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
from ..auth import get_current_business_id
from datetime import date, datetime

router = APIRouter()

DAYS = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]


def get_biz(request: Request, db: Session) -> Business:
    biz_id = get_current_business_id(request)
    if not biz_id:
        raise HTTPException(status_code=303, headers={"Location": "/giris"})
    biz = db.query(Business).filter(Business.id == biz_id).first()
    if not biz:
        raise HTTPException(status_code=303, headers={"Location": "/giris"})
    return biz


@router.get("/panel/randevu-defteri", response_class=HTMLResponse)
async def ledger(request: Request, d: str = None, db: Session = Depends(get_db)):
    biz = get_biz(request, db)
    sel_date = d or date.today().isoformat()
    appointments = db.query(Appointment).filter(
        Appointment.business_id == biz.id,
        Appointment.date == sel_date,
        Appointment.status != "iptal"
    ).all()
    staff_list = db.query(Staff).filter(Staff.business_id == biz.id).all()
    services   = db.query(Service).filter(Service.business_id == biz.id).all()

    # Slot map: {time: {staff_id_or_0: appointment}}
    from collections import defaultdict
    slot_map = defaultdict(dict)
    for a in appointments:
        sid = a.staff_id or 0
        slot_map[a.time][sid] = a

    # 09:00 – 21:00, 60 dk aralıklar
    slots = []
    for h in range(9, 21):
        slots.append(f"{h:02d}:00")

    return templates.TemplateResponse("business/ledger.html", {
        "request": request, "biz": biz,
        "staff_list": staff_list, "services": services,
        "slot_map": slot_map, "slots": slots,
        "sel_date": sel_date,
    })

@router.get("/panel", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    biz = get_biz(request, db)
    today_str = date.today().isoformat()
    today_appointments = db.query(Appointment).filter(
        Appointment.business_id == biz.id,
        Appointment.date == today_str
    ).order_by(Appointment.time).all()

    upcoming = db.query(Appointment).filter(
        Appointment.business_id == biz.id,
        Appointment.date >= today_str,
        Appointment.status != "iptal"
    ).order_by(Appointment.date, Appointment.time).limit(10).all()

    # ── İstatistikler ──
    from sqlalchemy import func
    total_appointments = db.query(func.count(Appointment.id)).filter(
        Appointment.business_id == biz.id, Appointment.status != "iptal"
    ).scalar() or 0

    today_count = len([a for a in today_appointments if a.status != "iptal"])

    # Bu ayki randevular
    month_start = date.today().replace(day=1).isoformat()
    month_appointments = db.query(Appointment).filter(
        Appointment.business_id == biz.id,
        Appointment.date >= month_start,
        Appointment.status != "iptal"
    ).all()
    month_count = len(month_appointments)

    # Bu ayki tahmini gelir
    month_revenue = 0
    for a in month_appointments:
        if a.service and a.service.price:
            month_revenue += a.service.price

    # Bekleyen randevular
    pending_count = db.query(func.count(Appointment.id)).filter(
        Appointment.business_id == biz.id,
        Appointment.date >= today_str,
        Appointment.status == "bekliyor"
    ).scalar() or 0

    # Personel sayısı
    staff_count = db.query(func.count(Staff.id)).filter(
        Staff.business_id == biz.id, Staff.is_active == True
    ).scalar() or 0

    # Hizmet sayısı
    service_count = db.query(func.count(Service.id)).filter(
        Service.business_id == biz.id, Service.is_active == True
    ).scalar() or 0

    return templates.TemplateResponse("business/dashboard.html", {
        "request": request,
        "biz": biz,
        "today_appointments": today_appointments,
        "upcoming": upcoming,
        "today": today_str,
        "total_appointments": total_appointments,
        "today_count": today_count,
        "month_count": month_count,
        "month_revenue": month_revenue,
        "pending_count": pending_count,
        "staff_count": staff_count,
        "service_count": service_count,
    })


@router.get("/panel/today-appointments", response_class=HTMLResponse)
async def today_appointments_detail(request: Request, db: Session = Depends(get_db)):
    print("=== BUGUN RANDEVULAR ROUTE CALLED ===")
    biz = get_biz(request, db)
    today_str = date.today().isoformat()
    appointments = db.query(Appointment).filter(
        Appointment.business_id == biz.id,
        Appointment.date == today_str
    ).order_by(Appointment.time).all()

    return templates.TemplateResponse("business/appointments_today.html", {
        "request": request,
        "biz": biz,
        "appointments": appointments,
        "today": today_str,
    })


@router.get("/panel/month-appointments", response_class=HTMLResponse)
async def month_appointments_detail(request: Request, db: Session = Depends(get_db)):
    biz = get_biz(request, db)
    month_start = date.today().replace(day=1).isoformat()
    appointments = db.query(Appointment).filter(
        Appointment.business_id == biz.id,
        Appointment.date >= month_start,
        Appointment.status != "iptal"
    ).order_by(Appointment.date, Appointment.time).all()

    month_name = date.today().strftime("%B %Y")
    return templates.TemplateResponse("business/appointments_month.html", {
        "request": request,
        "biz": biz,
        "appointments": appointments,
        "month_name": month_name,
    })


@router.get("/panel/gelir-takibi", response_class=HTMLResponse)
async def revenue_tracking(request: Request, ay: str = None, db: Session = Depends(get_db)):
    biz = get_biz(request, db)
    from sqlalchemy import func
    from datetime import timedelta
    import calendar

    today_date = date.today()
    if ay:
        try:
            parts = ay.split("-")
            sel_year, sel_month = int(parts[0]), int(parts[1])
        except Exception:
            sel_year, sel_month = today_date.year, today_date.month
    else:
        sel_year, sel_month = today_date.year, today_date.month

    month_start = date(sel_year, sel_month, 1).isoformat()
    last_day = calendar.monthrange(sel_year, sel_month)[1]
    month_end = date(sel_year, sel_month, last_day).isoformat()

    appointments = db.query(Appointment).filter(
        Appointment.business_id == biz.id,
        Appointment.date >= month_start,
        Appointment.date <= month_end,
        Appointment.status != "iptal"
    ).order_by(Appointment.date, Appointment.time).all()

    staff_list = db.query(Staff).filter(Staff.business_id == biz.id, Staff.is_active == True).all()

    # Günlük gelir
    daily_revenue = {}
    staff_revenue = {}
    total_revenue = 0
    total_count = 0

    for a in appointments:
        price = a.service.price if a.service and a.service.price else 0
        day_key = a.date
        daily_revenue[day_key] = daily_revenue.get(day_key, 0) + price
        total_revenue += price
        total_count += 1

        s_name = a.staff.name if a.staff else "Genel"
        if s_name not in staff_revenue:
            staff_revenue[s_name] = {"count": 0, "revenue": 0}
        staff_revenue[s_name]["count"] += 1
        staff_revenue[s_name]["revenue"] += price

    # Önceki ay karşılaştırma
    if sel_month == 1:
        prev_year, prev_month = sel_year - 1, 12
    else:
        prev_year, prev_month = sel_year, sel_month - 1
    prev_start = date(prev_year, prev_month, 1).isoformat()
    prev_last = calendar.monthrange(prev_year, prev_month)[1]
    prev_end = date(prev_year, prev_month, prev_last).isoformat()

    prev_appointments = db.query(Appointment).filter(
        Appointment.business_id == biz.id,
        Appointment.date >= prev_start,
        Appointment.date <= prev_end,
        Appointment.status != "iptal"
    ).all()
    prev_revenue = sum(a.service.price for a in prev_appointments if a.service and a.service.price)
    prev_count = len(prev_appointments)

    ay_isimleri = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
                   "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]

    return templates.TemplateResponse("business/revenue.html", {
        "request": request, "biz": biz,
        "sel_year": sel_year, "sel_month": sel_month,
        "ay_isim": ay_isimleri[sel_month],
        "appointments": appointments,
        "daily_revenue": daily_revenue,
        "staff_revenue": staff_revenue,
        "total_revenue": total_revenue,
        "total_count": total_count,
        "prev_revenue": prev_revenue,
        "prev_count": prev_count,
        "staff_list": staff_list,
    })


@router.get("/panel/hizmetler", response_class=HTMLResponse)
async def services_page(request: Request, db: Session = Depends(get_db)):
    biz = get_biz(request, db)
    services = db.query(Service).filter(Service.business_id == biz.id).all()
    return templates.TemplateResponse("business/services.html", {
        "request": request, "biz": biz, "services": services
    })


@router.post("/panel/hizmet-ekle")
async def add_service(
    request: Request,
    name: str = Form(...),
    duration: int = Form(30),
    price: int = Form(0),
    db: Session = Depends(get_db)
):
    biz = get_biz(request, db)
    db.add(Service(business_id=biz.id, name=name, duration=duration, price=price))
    db.commit()
    return RedirectResponse("/panel/hizmetler", status_code=302)


@router.post("/panel/hizmet-sil/{service_id}")
async def delete_service(service_id: int, request: Request, db: Session = Depends(get_db)):
    biz = get_biz(request, db)
    svc = db.query(Service).filter(Service.id == service_id, Service.business_id == biz.id).first()
    if svc:
        db.delete(svc)
        db.commit()
    return RedirectResponse("/panel/hizmetler", status_code=302)


@router.get("/panel/personel", response_class=HTMLResponse)
async def staff_page(request: Request, db: Session = Depends(get_db)):
    biz = get_biz(request, db)
    staff = db.query(Staff).filter(Staff.business_id == biz.id).all()
    return templates.TemplateResponse("business/staff.html", {
        "request": request, "biz": biz, "staff": staff
    })


@router.post("/panel/personel-ekle")
async def add_staff(
    request: Request,
    name: str = Form(...),
    email: str = Form(""),
    pin: str = Form(""),
    db: Session = Depends(get_db)
):
    biz = get_biz(request, db)

    # Email zaten var mı kontrol et (sadece doldurulduysa)
    if email and db.query(Staff).filter(Staff.email == email).first():
        # Hata: Email zaten kullanılıyor (şimdi sadece ekleme yapıyoruz, error handling eklememiyor)
        pass

    staff = Staff(
        business_id=biz.id,
        name=name,
        email=email if email else None,
        pin=pin if pin else None
    )
    db.add(staff)
    db.commit()
    return RedirectResponse("/panel/personel", status_code=302)


@router.post("/panel/personel-sil/{staff_id}")
async def delete_staff(staff_id: int, request: Request, db: Session = Depends(get_db)):
    biz = get_biz(request, db)
    s = db.query(Staff).filter(Staff.id == staff_id, Staff.business_id == biz.id).first()
    if s:
        db.delete(s)
        db.commit()
    return RedirectResponse("/panel/personel", status_code=302)


@router.get("/panel/personel-duzenle/{staff_id}", response_class=HTMLResponse)
async def edit_staff_page(staff_id: int, request: Request, db: Session = Depends(get_db)):
    biz = get_biz(request, db)
    staff = db.query(Staff).filter(Staff.id == staff_id, Staff.business_id == biz.id).first()
    if not staff:
        return RedirectResponse("/panel/personel", status_code=302)
    return templates.TemplateResponse("business/staff_edit.html", {
        "request": request, "biz": biz, "staff": staff
    })


@router.post("/panel/personel-duzenle/{staff_id}")
async def update_staff(
    staff_id: int,
    request: Request,
    name: str = Form(...),
    email: str = Form(""),
    pin: str = Form(""),
    db: Session = Depends(get_db)
):
    biz = get_biz(request, db)
    staff = db.query(Staff).filter(Staff.id == staff_id, Staff.business_id == biz.id).first()
    if not staff:
        return RedirectResponse("/panel/personel", status_code=302)

    # Email zaten başkası tarafından kullanılıyor mı kontrol et
    if email and email != staff.email:
        existing = db.query(Staff).filter(Staff.email == email, Staff.id != staff_id).first()
        if existing:
            # Email already used, but continue anyway for now
            pass

    staff.name = name
    staff.email = email if email else None
    staff.pin = pin if pin else None
    db.commit()
    return RedirectResponse("/panel/personel", status_code=302)


@router.get("/panel/randevular", response_class=HTMLResponse)
async def appointments_page(request: Request, filter: str = "upcoming", db: Session = Depends(get_db)):
    biz = get_biz(request, db)
    today = date.today().isoformat()
    q = db.query(Appointment).filter(Appointment.business_id == biz.id)
    if filter == "upcoming":
        q = q.filter(Appointment.date >= today)
    elif filter == "past":
        q = q.filter(Appointment.date < today)
    # filter == "all" → hepsi
    appointments = q.order_by(Appointment.date.desc(), Appointment.time).all()
    return templates.TemplateResponse("business/appointments.html", {
        "request": request, "biz": biz, "appointments": appointments, "filter": filter
    })


@router.post("/panel/randevu-iptal/{apt_id}")
async def cancel_appointment(apt_id: int, request: Request, db: Session = Depends(get_db)):
    biz = get_biz(request, db)
    apt = db.query(Appointment).filter(Appointment.id == apt_id, Appointment.business_id == biz.id).first()
    if apt:
        apt.status = "iptal"
        db.commit()
    return RedirectResponse("/panel/randevular", status_code=302)


@router.get("/panel/calisma-saatleri", response_class=HTMLResponse)
async def work_hours_page(request: Request, db: Session = Depends(get_db)):
    biz = get_biz(request, db)
    hours = {wh.day_of_week: wh for wh in db.query(WorkHour).filter(WorkHour.business_id == biz.id).all()}
    return templates.TemplateResponse("business/work_hours.html", {
        "request": request, "biz": biz, "hours": hours, "days": DAYS
    })


@router.get("/panel/profil", response_class=HTMLResponse)
async def profile_edit_page(request: Request, db: Session = Depends(get_db)):
    biz = get_biz(request, db)
    return templates.TemplateResponse("business/profile_edit.html", {
        "request": request, "biz": biz, "success": False
    })


@router.post("/panel/profil-guncelle", response_class=HTMLResponse)
async def update_profile(
    request: Request,
    name: str = Form(...),
    category: str = Form(...),
    phone: str = Form(""),
    district: str = Form(""),
    address: str = Form(""),
    description: str = Form(""),
    db: Session = Depends(get_db)
):
    biz = get_biz(request, db)
    biz.name = name
    biz.category = category
    biz.phone = phone
    biz.district = district
    biz.address = address
    biz.description = description
    db.commit()
    db.refresh(biz)
    return templates.TemplateResponse("business/profile_edit.html", {
        "request": request, "biz": biz, "success": True
    })


@router.post("/panel/calisma-saatleri-kaydet")
async def save_work_hours(request: Request, db: Session = Depends(get_db)):
    biz = get_biz(request, db)
    form = await request.form()

    for day in range(7):
        existing = db.query(WorkHour).filter(
            WorkHour.business_id == biz.id, WorkHour.day_of_week == day
        ).first()

        is_closed = form.get(f"closed_{day}") == "on"
        open_time  = form.get(f"open_{day}", "09:00")
        close_time = form.get(f"close_{day}", "19:00")

        if existing:
            existing.is_closed  = is_closed
            existing.open_time  = open_time
            existing.close_time = close_time
        else:
            db.add(WorkHour(
                business_id=biz.id, day_of_week=day,
                open_time=open_time, close_time=close_time, is_closed=is_closed
            ))
    db.commit()
    return RedirectResponse("/panel/calisma-saatleri", status_code=302)


# ── FOTOĞRAFLAR ──────────────────────────────────────────────
@router.get("/panel/fotolar", response_class=HTMLResponse)
async def photos_page(request: Request, db: Session = Depends(get_db)):
    biz = get_biz(request, db)
    photos = db.query(BusinessPhoto).filter(BusinessPhoto.business_id == biz.id).order_by(BusinessPhoto.is_cover.desc(), BusinessPhoto.created_at.desc()).all()
    return templates.TemplateResponse("business/photos.html", {"request": request, "biz": biz, "photos": photos})


@router.post("/panel/fotograf-yukle")
async def upload_photo(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    biz = get_biz(request, db)
    ext = Path(file.filename).suffix.lower()
    if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
        raise HTTPException(status_code=400, detail="Sadece JPG, PNG, WEBP desteklenir.")

    # S3'e yükle
    fname = f"{uuid.uuid4().hex}{ext}"
    file_content = await file.read()
    s3_url = upload_photo_to_s3(file_content, fname)

    if not s3_url:
        raise HTTPException(status_code=500, detail="Fotoğraf yüklenemedi")

    # DB'ye S3 URL'sini kaydet
    is_cover = not db.query(BusinessPhoto).filter(BusinessPhoto.business_id == biz.id).first()
    db.add(BusinessPhoto(business_id=biz.id, filename=fname, s3_url=s3_url, is_cover=is_cover))
    db.commit()
    return RedirectResponse("/panel/fotolar", status_code=302)


@router.post("/panel/fotograf-sil/{photo_id}")
async def delete_photo(photo_id: int, request: Request, db: Session = Depends(get_db)):
    biz = get_biz(request, db)
    photo = db.query(BusinessPhoto).filter(BusinessPhoto.id == photo_id, BusinessPhoto.business_id == biz.id).first()
    if photo:
        # S3'den sil
        delete_photo_from_s3(photo.filename)
        db.delete(photo)
        db.commit()
        # Eğer kapak fotoğrafıysa bir sonrakini kapak yap
        if photo.is_cover:
            next_photo = db.query(BusinessPhoto).filter(BusinessPhoto.business_id == biz.id).first()
            if next_photo:
                next_photo.is_cover = True
                db.commit()
    return RedirectResponse("/panel/fotolar", status_code=302)


@router.post("/panel/fotograf-kapak/{photo_id}")
async def set_cover(photo_id: int, request: Request, db: Session = Depends(get_db)):
    biz = get_biz(request, db)
    db.query(BusinessPhoto).filter(BusinessPhoto.business_id == biz.id).update({"is_cover": False})
    photo = db.query(BusinessPhoto).filter(BusinessPhoto.id == photo_id, BusinessPhoto.business_id == biz.id).first()
    if photo:
        photo.is_cover = True
        db.commit()
    return RedirectResponse("/panel/fotolar", status_code=302)

