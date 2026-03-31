from ..templates_config import templates
from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Business, Service, Staff, WorkHour, Appointment, BusinessPhoto, Product, AppointmentProduct, CustomerProfile
from sqlalchemy.orm import joinedload
from ..sms import send_appointment_confirm, send_booking_with_products_customer, send_booking_with_products_business, send_sms
from ..whatsapp import send_whatsapp_message, TWILIO_WHATSAPP_NUMBER
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


@router.get("/cerez-politikasi", response_class=HTMLResponse)
async def cookie_policy(request: Request):
    return templates.TemplateResponse("cookie_policy.html", {"request": request})


@router.get("/{slug}", response_class=HTMLResponse)
async def business_page(slug: str, request: Request, db: Session = Depends(get_db)):
    # Reserved routes — don't try to match as business slugs
    reserved = {"giris", "kayit", "cikis", "sifremi-unuttum", "sifremi-sifirla",
                "admin", "panel", "personel", "isletmeler-icin", "api"}
    if slug.lower() in reserved:
        raise HTTPException(status_code=404, detail="Sayfa bulunamadı")

    biz = db.query(Business).filter(Business.slug == slug, Business.is_active == True).first()
    if not biz:
        raise HTTPException(status_code=404, detail="İşletme bulunamadı")

    services    = db.query(Service).filter(Service.business_id == biz.id, Service.is_active == True).all()
    staff       = db.query(Staff).filter(Staff.business_id == biz.id, Staff.is_active == True).all()
    work_hours  = db.query(WorkHour).filter(WorkHour.business_id == biz.id).order_by(WorkHour.day_of_week).all()
    photos      = db.query(BusinessPhoto).filter(BusinessPhoto.business_id == biz.id).all()
    products    = db.query(Product).filter(Product.business_id == biz.id, Product.is_active == True).all()

    return templates.TemplateResponse("customer/business.html", {
        "request": request, "biz": biz, "services": services,
        "staff": staff, "work_hours": work_hours, "photos": photos, "products": products,
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
    print(f"[BOOK] service_id={service_id}, date={selected_date}, time={selected_time}, staff={staff_id}, name={customer_name}, phone={customer_phone}")
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

        # Notları birleştir: müşteri notu (form) + işletme notu (panel)
        combined_notes = ""

        # Müşteri notu (randevu esnasında yazılan)
        if notes and notes.strip():
            combined_notes = f"Müşteri Notu: {notes}"

        # İşletme notu (panelden kaydedilen)
        business_note = ""
        customer_profile = db.query(CustomerProfile).filter(
            CustomerProfile.business_id == biz.id,
            CustomerProfile.phone == customer_phone
        ).first()
        if customer_profile:
            if customer_profile.notes:
                business_note = customer_profile.notes
            elif customer_profile.preferences:
                business_note = f"Tercihler: {customer_profile.preferences}"

        if business_note:
            if combined_notes:
                combined_notes += " | "
            combined_notes += f"İşletme Notu: {business_note}"

        # Tarih formatlamışı: 2026-03-31 -> 31 Mart 2026
        date_obj = datetime.strptime(selected_date, "%Y-%m-%d")
        months_tr = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
                     "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
        formatted_date = f"{date_obj.day} {months_tr[date_obj.month - 1]} {date_obj.year}"

        # Telefon numarasını international format'a dönüştür (05... → +905...)
        formatted_phone = customer_phone
        if formatted_phone.startswith("0"):
            formatted_phone = "+9" + formatted_phone
        elif not formatted_phone.startswith("+"):
            formatted_phone = "+" + formatted_phone

        # Müşteriye bildirim (plan'a göre WhatsApp veya SMS)
        if biz.plan == "premium" and biz.whatsapp_phone:
            # Premium: WhatsApp (Twilio numarası)
            sender = biz.whatsapp_phone.replace(" ", "")
            print(f"[BOOK] Premium - Müşteriye WhatsApp: {formatted_phone} from {sender}")
            customer_message = (
                f"Merhaba {customer_name},\n\n"
                f"{biz.name} için {formatted_date} {selected_time}'de "
                f"{svc.name} randevunuz onaylandı.\n\n"
                f"Teşekkür ederiz! 😊"
            )
            asyncio.create_task(send_whatsapp_message(
                f"whatsapp:{formatted_phone}",
                customer_message,
                from_number=sender
            ))

            # İşletme sahibine WhatsApp bildirim (kendi personal numarası)
            if biz.phone:
                owner_phone = biz.phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
                if not owner_phone.startswith("+"):
                    if owner_phone.startswith("0"):
                        owner_phone = "+9" + owner_phone
                    else:
                        owner_phone = "+" + owner_phone

                print(f"[BOOK] Premium - İşletmeye WhatsApp: {owner_phone} from {sender}")
                business_message = (
                    f"Yeni randevu!\n\n"
                    f"Müşteri: {customer_name}\n"
                    f"Hizmet: {svc.name}\n"
                    f"Tarih: {formatted_date}\n"
                    f"Saat: {selected_time}"
                )
                asyncio.create_task(send_whatsapp_message(
                    f"whatsapp:{owner_phone}",
                    business_message,
                    from_number=sender
                ))
        else:
            # Temel: SMS
            print(f"[BOOK] Temel - SMS gönderiyor: {customer_phone}")
            sms_message = (
                f"Merhaba {customer_name}, {biz.name} için {formatted_date} {selected_time}'de "
                f"{svc.name} randevunuz onaylandı. Teşekkür ederiz!"
            )
            asyncio.create_task(send_sms(customer_phone, sms_message))

        # Get active products for this business
        products = db.query(Product).filter_by(business_id=biz.id, is_active=True).all()

        return templates.TemplateResponse("customer/booking_success.html", {
            "request": request,
            "biz": biz,
            "apt": apt,
            "service": svc,
            "products": products,
            "products_saved": False,
        })
    except HTTPException:
        raise
    except Exception as e:
        print(f"[BOOKING ERROR] {slug}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Booking error: {str(e)}")


@router.post("/{slug}/randevu-urun-sec/{apt_id}", response_class=HTMLResponse)
async def select_products(
    slug: str,
    apt_id: int,
    request: Request,
    product_ids: Optional[list[int]] = Form(None),
    db: Session = Depends(get_db)
):
    """Müşteri randevu sonrası ürün seçer"""
    try:
        # Get appointment & business
        apt = db.query(Appointment).filter_by(id=apt_id).first()
        if not apt:
            raise HTTPException(status_code=404, detail="Randevu bulunamadı")

        biz = db.query(Business).filter_by(id=apt.business_id, slug=slug).first()
        if not biz:
            raise HTTPException(status_code=404, detail="İşletme bulunamadı")

        svc = db.query(Service).filter_by(id=apt.service_id).first()

        # Save selected products if any
        selected_products = []
        if product_ids:
            for pid in product_ids:
                prod = db.query(Product).filter_by(id=pid, business_id=biz.id).first()
                if prod:
                    app_prod = AppointmentProduct(
                        appointment_id=apt_id,
                        product_id=pid,
                        quantity=1
                    )
                    db.add(app_prod)
                    selected_products.append(app_prod)
            db.commit()

        # Refresh to load relationships
        db.refresh(apt)
        apt_products = db.query(AppointmentProduct).filter_by(appointment_id=apt_id).all()

        # Notları birleştir: müşteri notu (randevu) + işletme notu (panel)
        combined_notes = ""

        # Müşteri notu (randevu esnasında yazılan)
        if apt.notes and apt.notes.strip():
            combined_notes = f"Müşteri Notu: {apt.notes}"

        # İşletme notu (panelden kaydedilen)
        business_note = ""
        customer_profile = db.query(CustomerProfile).filter(
            CustomerProfile.business_id == biz.id,
            CustomerProfile.phone == apt.customer_phone
        ).first()
        if customer_profile:
            if customer_profile.notes:
                business_note = customer_profile.notes
            elif customer_profile.preferences:
                business_note = f"Tercihler: {customer_profile.preferences}"

        if business_note:
            if combined_notes:
                combined_notes += " | "
            combined_notes += f"İşletme Notu: {business_note}"

        # Send SMS to customer and business owner
        asyncio.create_task(send_booking_with_products_customer(
            apt.customer_phone, apt.customer_name,
            biz.name, svc.name,
            apt.date, apt.time, apt_products
        ))

        if biz.phone:
            asyncio.create_task(send_booking_with_products_business(
                biz.phone, apt.customer_name,
                svc.name, apt.date, apt.time, apt_products, combined_notes
            ))

        # Redirect to success page with flag
        products = db.query(Product).filter_by(business_id=biz.id, is_active=True).all()
        return templates.TemplateResponse("customer/booking_success.html", {
            "request": request,
            "biz": biz,
            "apt": apt,
            "service": svc,
            "products": products,
            "products_saved": True,
        })
    except HTTPException:
        raise
    except Exception as e:
        print(f"[PRODUCT SELECT ERROR] {slug}/{apt_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Product selection error: {str(e)}")

