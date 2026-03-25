from ..templates_config import templates
from fastapi import APIRouter, Request, Form, Depends, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from ..database import get_db
from ..models import Business, Service, Staff, WorkHour, Appointment, BusinessPhoto, Product, CustomerProfile, Expense
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
    # Business owner check
    biz_id = get_current_business_id(request)
    if biz_id:
        biz = db.query(Business).filter(Business.id == biz_id).first()
        if biz:
            return biz

    # Admin staff check
    from .staff_portal import get_current_staff_id
    staff_id = get_current_staff_id(request)
    if staff_id:
        staff = db.query(Staff).filter(Staff.id == staff_id, Staff.role == "admin", Staff.is_active == True).first()
        if staff:
            biz = db.query(Business).filter(Business.id == staff.business_id).first()
            if biz:
                return biz

    raise HTTPException(status_code=303, headers={"Location": "/giris"})


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

    # Calculate visit counts for all customers
    all_appointments = db.query(Appointment).filter(
        Appointment.business_id == biz.id,
        Appointment.status != "iptal"
    ).all()
    customer_visits = {}
    for a in all_appointments:
        customer_visits[a.customer_phone] = customer_visits.get(a.customer_phone, 0) + 1

    return templates.TemplateResponse("business/ledger.html", {
        "request": request, "biz": biz,
        "staff_list": staff_list, "services": services,
        "slot_map": slot_map, "slots": slots,
        "sel_date": sel_date,
        "customer_visits": customer_visits,
    })

@router.get("/panel/istatistikler", response_class=HTMLResponse)
async def statistics(
    request: Request,
    period: str = "hafta",
    staff_id: int = None,
    db: Session = Depends(get_db)
):
    biz = get_biz(request, db)
    today = date.today()
    from datetime import timedelta
    import calendar

    # ── PERSONEL LİSTESİ (dropdown için) ──
    staff_list = db.query(Staff).filter(
        Staff.business_id == biz.id, Staff.is_active == True
    ).order_by(Staff.name).all()

    # ── BASE QUERY FİLTRELERİ ──
    base_filters = [
        Appointment.business_id == biz.id,
        Appointment.status != "iptal"
    ]
    if staff_id:
        base_filters.append(Appointment.staff_id == staff_id)

    # ── PERIYODA GÖRE CHART VERİSİ ──
    chart_labels = []
    chart_values = []
    period_label = ""

    if period == "gun":
        # Bugün saatlik (09:00 - 21:00)
        today_str = today.isoformat()
        for h in range(9, 22):
            hour_str = f"{h:02d}:"
            count = db.query(func.count(Appointment.id)).filter(
                *base_filters,
                Appointment.date == today_str,
                Appointment.time.like(f"{hour_str}%")
            ).scalar() or 0
            chart_labels.append(f"{h:02d}:00")
            chart_values.append(count)
        period_label = "Bugün (Saatlik)"

    elif period == "ay":
        # Bu ayın günleri
        days_in_month = calendar.monthrange(today.year, today.month)[1]
        for d in range(1, days_in_month + 1):
            day_str = date(today.year, today.month, d).isoformat()
            count = db.query(func.count(Appointment.id)).filter(
                *base_filters,
                Appointment.date == day_str
            ).scalar() or 0
            chart_labels.append(f"{d}")
            chart_values.append(count)
        period_label = f"Bu Ay ({today.strftime('%B %Y').capitalize()})"

    elif period == "yil":
        # Bu yılın 12 ayı
        MONTHS = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
        for m in range(1, 13):
            m_start = date(today.year, m, 1).isoformat()
            days = calendar.monthrange(today.year, m)[1]
            m_end = date(today.year, m, days).isoformat()
            count = db.query(func.count(Appointment.id)).filter(
                *base_filters,
                Appointment.date >= m_start,
                Appointment.date <= m_end
            ).scalar() or 0
            chart_labels.append(MONTHS[m - 1])
            chart_values.append(count)
        period_label = f"Bu Yıl ({today.year})"

    else:  # hafta (default)
        # Son 7 gün
        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            day_str = day.isoformat()
            count = db.query(func.count(Appointment.id)).filter(
                *base_filters,
                Appointment.date == day_str
            ).scalar() or 0
            chart_labels.append(day_str)
            chart_values.append(count)
        period_label = "Son 7 Gün"

    # ── PERSONEL İSTATİSTİKLERİ ──
    month_start = today.replace(day=1).isoformat()
    staff_stats = []

    target_staff = [s for s in staff_list if not staff_id or s.id == staff_id]

    for staff in target_staff:
        appt_count = db.query(func.count(Appointment.id)).filter(
            Appointment.business_id == biz.id,
            Appointment.staff_id == staff.id,
            Appointment.status != "iptal"
        ).scalar() or 0
        month_appt_count = db.query(func.count(Appointment.id)).filter(
            Appointment.business_id == biz.id,
            Appointment.staff_id == staff.id,
            Appointment.date >= month_start,
            Appointment.status != "iptal"
        ).scalar() or 0
        staff_stats.append({
            "id": staff.id,
            "name": staff.name,
            "total": appt_count,
            "month": month_appt_count,
        })

    staff_stats.sort(key=lambda x: x["month"], reverse=True)

    # ── ÖZET KARTLAR ──
    # Bu ay
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    month_end = date(today.year, today.month, days_in_month).isoformat()
    this_month = db.query(func.count(Appointment.id)).filter(
        *base_filters,
        Appointment.date >= month_start,
        Appointment.date <= month_end
    ).scalar() or 0

    # Geçen ay
    if today.month == 1:
        prev_year, prev_month = today.year - 1, 12
    else:
        prev_year, prev_month = today.year, today.month - 1
    prev_days = calendar.monthrange(prev_year, prev_month)[1]
    prev_start = date(prev_year, prev_month, 1).isoformat()
    prev_end = date(prev_year, prev_month, prev_days).isoformat()
    last_month = db.query(func.count(Appointment.id)).filter(
        *base_filters,
        Appointment.date >= prev_start,
        Appointment.date <= prev_end
    ).scalar() or 0

    # Büyüme %
    if last_month > 0:
        growth = round(((this_month - last_month) / last_month) * 100, 1)
    else:
        growth = 100 if this_month > 0 else 0

    # ── EN YOĞUN GÜN (son 30 gün) ──
    WEEKDAYS_TR = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
    thirty_days_ago = (today - timedelta(days=30)).isoformat()
    recent_appts = db.query(Appointment.date).filter(
        *base_filters,
        Appointment.date >= thirty_days_ago
    ).all()
    weekday_counts = [0] * 7
    for row in recent_appts:
        d = date.fromisoformat(row.date)
        weekday_counts[d.weekday()] += 1
    busiest_day = WEEKDAYS_TR[weekday_counts.index(max(weekday_counts))] if any(weekday_counts) else "—"

    # ── EN ÇOK TERCİH EDİLEN HİZMET ──
    from sqlalchemy import desc
    top_service_row = db.query(
        Service.name, func.count(Appointment.id).label("cnt")
    ).join(Appointment, Appointment.service_id == Service.id).filter(
        Appointment.business_id == biz.id,
        Appointment.status != "iptal"
    ).group_by(Service.name).order_by(desc("cnt")).first()
    top_service = top_service_row[0] if top_service_row else "—"

    # ── HAFTANIN GÜNLERİ DAĞILIMI (son 30 gün) ──
    weekday_labels = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]

    # ── SAATLİK YOĞUNLUK (son 30 gün) ──
    hourly_data = []
    hourly_labels = []
    for h in range(9, 22):
        hour_str = f"{h:02d}:"
        count = db.query(func.count(Appointment.id)).filter(
            *base_filters,
            Appointment.date >= thirty_days_ago,
            Appointment.time.like(f"{hour_str}%")
        ).scalar() or 0
        hourly_data.append(count)
        hourly_labels.append(f"{h:02d}:00")

    summary = {
        "this_month": this_month,
        "last_month": last_month,
        "growth": growth,
        "busiest_day": busiest_day,
        "top_service": top_service,
    }

    return templates.TemplateResponse("business/statistics.html", {
        "request": request,
        "biz": biz,
        "chart_labels": chart_labels,
        "chart_values": chart_values,
        "period": period,
        "period_label": period_label,
        "staff_id": staff_id,
        "staff_list": staff_list,
        "staff_stats": staff_stats,
        "summary": summary,
        "weekday_labels": weekday_labels,
        "weekday_data": weekday_counts,
        "hourly_labels": hourly_labels,
        "hourly_data": hourly_data,
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

    # ── GİDERLER ──
    expenses = db.query(Expense).filter(
        Expense.business_id == biz.id,
        Expense.date >= month_start,
        Expense.date <= month_end
    ).order_by(Expense.date.desc()).all()
    total_expenses = sum(e.amount for e in expenses)
    net_profit = total_revenue - total_expenses

    # ── ALACAKLAR (ödeme yapılmamış) ──
    today_str = date.today().isoformat()
    unpaid = db.query(Appointment).filter(
        Appointment.business_id == biz.id,
        Appointment.is_paid == False,
        Appointment.status.in_(["tamamlandi", "onaylandi"]),
        Appointment.date <= today_str
    ).order_by(Appointment.date.desc()).all()
    total_receivable = sum(a.service.price for a in unpaid if a.service and a.service.price)

    ay_isimleri = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
                   "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]

    # Services for dropdown
    services = db.query(Service).filter(Service.business_id == biz.id, Service.is_active == True).all()

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
        "expenses": expenses,
        "total_expenses": total_expenses,
        "net_profit": net_profit,
        "unpaid": unpaid,
        "total_receivable": total_receivable,
        "services": services,
    })


@router.post("/panel/gider-ekle")
async def add_expense(
    request: Request,
    amount: int = Form(...),
    category: str = Form("Diğer"),
    description: str = Form(""),
    db: Session = Depends(get_db)
):
    biz = get_biz(request, db)
    today_str = date.today().isoformat()

    expense = Expense(
        business_id=biz.id,
        amount=amount,
        category=category,
        description=description,
        date=today_str
    )
    db.add(expense)
    db.commit()
    return RedirectResponse("/panel/gelir-takibi", status_code=303)


@router.post("/panel/odeme-al/{appointment_id}")
async def mark_as_paid(
    appointment_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    biz = get_biz(request, db)
    appt = db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.business_id == biz.id
    ).first()

    if appt:
        appt.is_paid = True
        db.commit()

    return RedirectResponse("/panel/gelir-takibi", status_code=303)


@router.post("/panel/gider-sil/{expense_id}")
async def delete_expense(
    expense_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    biz = get_biz(request, db)
    expense = db.query(Expense).filter(
        Expense.id == expense_id,
        Expense.business_id == biz.id
    ).first()

    if expense:
        db.delete(expense)
        db.commit()

    return RedirectResponse("/panel/gelir-takibi", status_code=303)


@router.post("/panel/alacak-ekle")
async def add_receivable(
    request: Request,
    customer_name: str = Form(...),
    customer_phone: str = Form(...),
    service_id: int = Form(...),
    date: str = Form(...),
    db: Session = Depends(get_db)
):
    biz = get_biz(request, db)
    service = db.query(Service).filter(Service.id == service_id, Service.business_id == biz.id).first()

    if not service:
        return RedirectResponse("/panel/gelir-takibi", status_code=303)

    # Create appointment without staff assignment
    appointment = Appointment(
        business_id=biz.id,
        service_id=service_id,
        customer_name=customer_name,
        customer_phone=customer_phone,
        date=date,
        time="00:00",  # Placeholder time
        status="onaylandi",
        is_paid=False
    )
    db.add(appointment)
    db.commit()

    return RedirectResponse("/panel/gelir-takibi", status_code=303)


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
    staff_login_id: str = Form(""),
    pin: str = Form(""),
    role: str = Form("personel"),
    db: Session = Depends(get_db)
):
    biz = get_biz(request, db)

    staff = Staff(
        business_id=biz.id,
        name=name,
        staff_login_id=staff_login_id if staff_login_id else None,
        pin=pin if pin else None,
        role=role if role in ("personel", "admin") else "personel"
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
    staff_login_id: str = Form(""),
    pin: str = Form(""),
    role: str = Form("personel"),
    db: Session = Depends(get_db)
):
    biz = get_biz(request, db)
    staff = db.query(Staff).filter(Staff.id == staff_id, Staff.business_id == biz.id).first()
    if not staff:
        return RedirectResponse("/panel/personel", status_code=302)

    staff.name = name
    staff.staff_login_id = staff_login_id if staff_login_id else None
    staff.pin = pin if pin else None
    staff.role = role if role in ("personel", "admin") else "personel"
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

    try:
        s3_url = upload_photo_to_s3(file_content, fname)
    except Exception as e:
        print(f"[UPLOAD] S3 yükleme hatası: {e}")
        raise HTTPException(status_code=500, detail=f"S3 yükleme hatası: {str(e)[:100]}")

    if not s3_url:
        raise HTTPException(status_code=500, detail="AWS ayarlarını kontrol edin (KEY, SECRET, BUCKET)")

    # DB'ye S3 URL'sini kaydet
    try:
        print(f"[UPLOAD] S3 URL: {s3_url}")
        is_cover = not db.query(BusinessPhoto).filter(BusinessPhoto.business_id == biz.id).first()
        db.add(BusinessPhoto(business_id=biz.id, filename=fname, s3_url=s3_url, is_cover=is_cover))
        db.commit()
        print(f"[UPLOAD] Database'e kaydedildi")
    except Exception as e:
        print(f"[UPLOAD] DB hatası: {e}")
        raise HTTPException(status_code=500, detail="Veritabanı hatası")

    return RedirectResponse("/panel/fotolar", status_code=302)


@router.post("/panel/fotograf-sil/{photo_id}")
async def delete_photo(photo_id: int, request: Request, db: Session = Depends(get_db)):
    biz = get_biz(request, db)
    photo = db.query(BusinessPhoto).filter(BusinessPhoto.id == photo_id, BusinessPhoto.business_id == biz.id).first()
    if photo:
        # S3'den sil (başarısız olsa da devam et)
        try:
            delete_photo_from_s3(photo.filename)
        except Exception as e:
            print(f"[S3] Delete hatası (devam ediliyor): {e}")

        # DB'den sil
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


# ═══ ÜRÜN/STOK TAKIBI ═══

@router.get("/panel/urun-stok", response_class=HTMLResponse)
async def products_page(request: Request, db: Session = Depends(get_db)):
    biz = get_biz(request, db)
    products = db.query(Product).filter(Product.business_id == biz.id).order_by(Product.created_at.desc()).all()
    return templates.TemplateResponse("business/products.html", {
        "request": request,
        "biz": biz,
        "products": products
    })


@router.post("/panel/urun-ekle", response_class=HTMLResponse)
async def add_product(
    request: Request,
    name: str = Form(...),
    price: int = Form(default=0),
    stock: int = Form(default=0),
    unit: str = Form(default="adet"),
    db: Session = Depends(get_db)
):
    try:
        biz = get_biz(request, db)

        # Validation
        name = name.strip()
        if not name or len(name) < 2:
            return templates.TemplateResponse("business/products.html", {
                "request": request,
                "biz": biz,
                "products": db.query(Product).filter(Product.business_id == biz.id).all(),
                "error": "Ürün adı en az 2 karakter olmalı."
            })

        if price < 0:
            price = 0
        if stock < 0:
            stock = 0

        unit = unit.strip() or "adet"

        product = Product(
            business_id=biz.id,
            name=name,
            price=price,
            stock=stock,
            unit=unit
        )
        db.add(product)
        db.commit()

        return RedirectResponse("/panel/urun-stok", status_code=302)
    except Exception as e:
        return templates.TemplateResponse("business/products.html", {
            "request": request,
            "biz": get_biz(request, db),
            "products": db.query(Product).filter(Product.business_id == get_biz(request, db).id).all(),
            "error": f"Hata: {str(e)}"
        })


@router.post("/panel/urun-duzenle/{product_id}", response_class=HTMLResponse)
async def edit_product(
    product_id: int,
    request: Request,
    name: str = Form(...),
    price: int = Form(default=0),
    unit: str = Form(default="adet"),
    db: Session = Depends(get_db)
):
    biz = get_biz(request, db)
    product = db.query(Product).filter(Product.id == product_id, Product.business_id == biz.id).first()

    if not product:
        return RedirectResponse("/panel/urun-stok", status_code=302)

    product.name = name.strip() or product.name
    product.price = max(0, price)
    product.unit = unit.strip() or "adet"
    db.commit()

    return RedirectResponse("/panel/urun-stok", status_code=302)


@router.post("/panel/urun-sil/{product_id}", response_class=HTMLResponse)
async def delete_product(product_id: int, request: Request, db: Session = Depends(get_db)):
    biz = get_biz(request, db)
    product = db.query(Product).filter(Product.id == product_id, Product.business_id == biz.id).first()

    if product:
        db.delete(product)
        db.commit()

    return RedirectResponse("/panel/urun-stok", status_code=302)


@router.post("/panel/stok-guncelle/{product_id}", response_class=HTMLResponse)
async def update_stock(
    product_id: int,
    request: Request,
    delta: int = Form(...),
    db: Session = Depends(get_db)
):
    biz = get_biz(request, db)
    product = db.query(Product).filter(Product.id == product_id, Product.business_id == biz.id).first()

    if product:
        product.stock = max(0, product.stock + delta)
        db.commit()

    return RedirectResponse("/panel/urun-stok", status_code=302)


# ── MÜŞTERI SADAKATI ─────────────────────────────────────────────────────────
@router.get("/panel/musteri-sadakati", response_class=HTMLResponse)
async def loyalty_dashboard(request: Request, db: Session = Depends(get_db)):
    biz = get_biz(request, db)

    # Randevulardan müşteri listesi oluştur (phone bazlı, unique)
    appointments = db.query(Appointment).filter(Appointment.business_id == biz.id).all()

    phone_to_customer = {}
    for appt in appointments:
        if appt.customer_phone:
            if appt.customer_phone not in phone_to_customer:
                phone_to_customer[appt.customer_phone] = {
                    "name": appt.customer_name,
                    "phone": appt.customer_phone,
                    "visit_count": 0,
                    "last_visit": appt.date
                }
            phone_to_customer[appt.customer_phone]["visit_count"] += 1
            if appt.date > phone_to_customer[appt.customer_phone]["last_visit"]:
                phone_to_customer[appt.customer_phone]["last_visit"] = appt.date

    # CustomerProfile ile merge et
    profiles = db.query(CustomerProfile).filter(CustomerProfile.business_id == biz.id).all()
    for profile in profiles:
        if profile.phone in phone_to_customer:
            phone_to_customer[profile.phone].update({
                "name": profile.name or phone_to_customer[profile.phone]["name"],
                "vip": profile.vip_status,
                "profile_id": profile.id
            })
        else:
            phone_to_customer[profile.phone] = {
                "name": profile.name,
                "phone": profile.phone,
                "visit_count": profile.total_visits,
                "last_visit": profile.last_visit,
                "vip": profile.vip_status,
                "profile_id": profile.id
            }

    customers = sorted(phone_to_customer.values(), key=lambda x: x.get("visit_count", 0), reverse=True)

    # ── SEVİYE VE GÜN HESAPLA ──
    today = date.today()
    for c in customers:
        # Seviye: ziyaret sayısına göre
        v = c.get("visit_count", 0)
        if v >= 10:
            c["level"] = ("💎", "Platin")
        elif v >= 5:
            c["level"] = ("🥇", "Sadık")
        elif v >= 2:
            c["level"] = ("🥈", "Düzenli")
        else:
            c["level"] = ("🥉", "Başlangıç")

        # Son ziyaretten bu yana geçen gün
        lv = c.get("last_visit")
        if lv:
            if isinstance(lv, str):
                lv = date.fromisoformat(lv)
            elif hasattr(lv, 'date'):
                lv = lv.date()
            c["days_absent"] = (today - lv).days
        else:
            c["days_absent"] = None

    # 30+ gün gelmeyen müşteriler
    reminder_customers = [
        c for c in customers
        if c.get("days_absent") is not None and c["days_absent"] >= 30
    ]
    reminder_customers.sort(key=lambda x: x["days_absent"], reverse=True)

    return templates.TemplateResponse("business/loyalty.html", {
        "request": request,
        "biz": biz,
        "customers": customers,
        "reminder_customers": reminder_customers
    })


@router.get("/panel/musteri-detay/{customer_id}", response_class=HTMLResponse)
async def customer_detail(customer_id: int, request: Request, db: Session = Depends(get_db)):
    biz = get_biz(request, db)

    customer = db.query(CustomerProfile).filter(
        CustomerProfile.id == customer_id,
        CustomerProfile.business_id == biz.id
    ).first()

    if not customer:
        return RedirectResponse("/panel/musteri-sadakati", status_code=302)

    # Randevu geçmişi
    appointments = db.query(Appointment).filter(
        Appointment.business_id == biz.id,
        Appointment.customer_phone == customer.phone
    ).order_by(Appointment.date.desc()).all()

    return templates.TemplateResponse("business/customer_detail.html", {
        "request": request,
        "biz": biz,
        "customer": customer,
        "appointments": appointments
    })


@router.post("/panel/musteri-guncelle/{customer_id}", response_class=HTMLResponse)
async def update_customer(
    customer_id: int,
    request: Request,
    name: str = Form(...),
    notes: str = Form(""),
    preferences: str = Form(""),
    allergies: str = Form(""),
    vip_status: str = Form(""),
    db: Session = Depends(get_db)
):
    biz = get_biz(request, db)

    customer = db.query(CustomerProfile).filter(
        CustomerProfile.id == customer_id,
        CustomerProfile.business_id == biz.id
    ).first()

    if not customer:
        return RedirectResponse("/panel/musteri-sadakati", status_code=302)

    customer.name = name.strip() or customer.name
    customer.notes = notes.strip() or None
    customer.preferences = preferences.strip() or None
    customer.allergies = allergies.strip() or None
    customer.vip_status = bool(vip_status)

    db.commit()

    return RedirectResponse(f"/panel/musteri-detay/{customer_id}", status_code=302)

