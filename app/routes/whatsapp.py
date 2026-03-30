"""
WhatsApp Twilio webhook ve mesaj işleme
"""
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Business, Service, WhatsAppConversation, Appointment, WorkHour, Staff
from ..whatsapp import (
    send_whatsapp_message, format_service_list, format_date_list,
    format_slot_list, parse_selection, get_next_available_date_str
)
from .booking import generate_slots
from ..sms import send_appointment_confirm, send_booking_with_products_business
from datetime import datetime, timedelta
import asyncio

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])


@router.post("/webhook")
async def whatsapp_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Twilio'dan gelen WhatsApp mesajlarını işle.
    """
    try:
        data = await request.form()
        from_number = data.get("From")  # whatsapp:+905551234567
        to_number = data.get("To")      # whatsapp:+1415523xxxx (gelen numara)
        message_body = data.get("Body", "").strip()

        print(f"[WhatsApp Webhook] From: {from_number}, To: {to_number}, Body: {message_body}")

        # Production: Gelen numaraya (To) göre işletme bul
        # Sandbox: whatsapp_phone boş olabilir, ilk active business'e geri fallback
        clean_to = to_number.replace("whatsapp:", "") if to_number else None

        # Normalize: boşlukları kaldır (database'de boşluksuz ve boşluklu mix olabilir)
        normalized_to = clean_to.replace(" ", "") if clean_to else None

        print(f"[WhatsApp] Looking for number: {clean_to} -> normalized: {normalized_to}")

        biz = None
        if normalized_to:
            # Production mode: Numaraya göre işletme ara
            candidates = db.query(Business).filter(
                Business.is_active == True,
                Business.whatsapp_enabled == True
            ).all()
            print(f"[WhatsApp] Candidates with WhatsApp enabled: {len(candidates)}")

            # Python'da normalize edip karşılaştır
            for b in candidates:
                print(f"[WhatsApp] Business {b.id}: phone='{b.whatsapp_phone}'")
                if b.whatsapp_phone:
                    normalized_stored = b.whatsapp_phone.replace(" ", "")
                    print(f"[WhatsApp]   normalized: '{normalized_stored}' vs looking for '{normalized_to}'")
                    if normalized_stored == normalized_to:
                        biz = b
                        print(f"[WhatsApp] ✓ MATCH! Found business {b.id}")
                        break

        if not biz:
            # Sandbox fallback: İlk active işletme
            print("[WhatsApp] Production number not found, using first active business (sandbox mode)")
            biz = db.query(Business).filter(Business.is_active == True).first()

        if not biz:
            print("[WhatsApp] İşletme bulunamadı")
            return JSONResponse({"status": "ok"}, status_code=200)

        # Telefon numarasından "whatsapp:" prefixini kaldır
        clean_phone = from_number.replace("whatsapp:", "")

        # Conversation kaydını bul veya oluştur
        conv = db.query(WhatsAppConversation).filter(
            WhatsAppConversation.business_id == biz.id,
            WhatsAppConversation.customer_phone == clean_phone
        ).first()

        if not conv:
            conv = WhatsAppConversation(
                business_id=biz.id,
                customer_phone=clean_phone,
                status="waiting_service"
            )
            db.add(conv)
            db.commit()
            db.refresh(conv)

        conv.message_count += 1
        conv.last_message_at = datetime.utcnow()

        # Mesajı işle
        response = await handle_message(message_body, conv, biz, db)

        db.commit()

        # Yanıt gönder (işletme'nin numarasından, normalize et)
        sender = biz.whatsapp_phone.replace(" ", "") if biz.whatsapp_phone else None
        await send_whatsapp_message(from_number, response, from_number=sender)

        return JSONResponse({"status": "ok"}, status_code=200)

    except Exception as e:
        print(f"[WhatsApp Webhook Error] {str(e)}")
        import traceback
        traceback.print_exc()
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


async def handle_message(message: str, conv: WhatsAppConversation, biz: Business, db: Session) -> str:
    """
    Conversation state'e göre mesajı işle.
    """
    message_lower = message.lower()

    # "Randevu Al" veya başlangıç komutu
    if message_lower in ["randevu al", "randevu", "selamlar", "merhaba", "hi", "hello"]:
        conv.status = "waiting_service"
        services = db.query(Service).filter(
            Service.business_id == biz.id,
            Service.is_active == True
        ).all()

        response = f"Merhaba! {biz.name}'e hoşgeldiniz.\n\n"
        response += format_service_list(services)
        return response

    # Hizmet bekliyoruz
    if conv.status == "waiting_service":
        services = db.query(Service).filter(
            Service.business_id == biz.id,
            Service.is_active == True
        ).all()

        choice = parse_selection(message, len(services))
        if choice is None:
            return "Lütfen geçerli bir numara girin (1-" + str(len(services)) + ")"

        selected_service = services[choice - 1]
        conv.selected_service_id = selected_service.id
        conv.status = "waiting_date"

        response = f"✅ {selected_service.name} seçildi.\n\n"
        response += format_date_list()
        return response

    # Tarih bekliyoruz
    if conv.status == "waiting_date":
        choice = parse_selection(message, 7)
        if choice is None:
            return "Lütfen geçerli bir tarih seçin (1-7)"

        selected_date = get_next_available_date_str(choice)
        conv.selected_date = selected_date
        conv.status = "waiting_staff"

        # Personelleri listele
        staff = db.query(Staff).filter(
            Staff.business_id == biz.id,
            Staff.is_active == True
        ).all()

        if staff:
            response = f"✅ {selected_date} seçildi.\n\n*Hangi personelden hizmet almak istersiniz?*\n"
            for i, s in enumerate(staff, 1):
                response += f"{i}. {s.name}\n"
            return response
        else:
            # Personel yoksa saat seçimine geç
            conv.status = "waiting_time"
            return f"✅ {selected_date} seçildi.\n\nUygun saatleri gösterileri hazırlanıyor..."

    # Personel bekliyoruz (tarih seçildikten sonra)
    if conv.status == "waiting_staff":
        staff = db.query(Staff).filter(
            Staff.business_id == biz.id,
            Staff.is_active == True
        ).all()

        choice = parse_selection(message, len(staff))
        if choice is None:
            return "Lütfen geçerli bir personel seçin (1-" + str(len(staff)) + ")"

        selected_staff = staff[choice - 1]
        conv.selected_staff_id = selected_staff.id
        conv.status = "waiting_time"

        # Personelden SONRA uygun saatleri göster
        service = db.query(Service).filter(Service.id == conv.selected_service_id).first()
        if not service:
            return "Hizmet bulunamadı"

        day_of_week = datetime.strptime(conv.selected_date, "%Y-%m-%d").weekday()
        wh = db.query(WorkHour).filter(
            WorkHour.business_id == biz.id,
            WorkHour.day_of_week == day_of_week
        ).first()

        if wh and wh.is_closed:
            conv.status = "waiting_date"
            return "Bu gün kapalı. Lütfen başka bir tarih seçin.\n\n" + format_date_list()

        if not wh:
            open_time, close_time = "09:00", "19:00"
        else:
            open_time, close_time = wh.open_time, wh.close_time

        # Dolu saatleri bul (bu personel + bu tarih)
        booked = db.query(Appointment).filter(
            Appointment.business_id == biz.id,
            Appointment.staff_id == conv.selected_staff_id,
            Appointment.date == conv.selected_date,
            Appointment.status != "iptal"
        ).all()
        booked_times = [a.time for a in booked]

        slots = generate_slots(open_time, close_time, service.duration, booked_times)
        available_slots = [s for s in slots if s.get("available")]

        if not available_slots:
            conv.status = "waiting_staff"
            return f"✅ {selected_staff.name} seçildi.\n\nMaalesef bu tarihte uygun saat yok. Lütfen başka bir personel seçin ya da tarih değiştirin.\n\n*Başka bir personel seçin?*\n"

        response = f"✅ {selected_staff.name} seçildi.\n\n*Uygun saatler:*\n"
        for i, slot in enumerate(available_slots, 1):
            response += f"{i}. {slot['time']}\n"

        return response

    # Saat bekliyoruz (personel seçildikten sonra)
    if conv.status == "waiting_time":
        # Saatleri tekrar bul
        service = db.query(Service).filter(Service.id == conv.selected_service_id).first()
        day_of_week = datetime.strptime(conv.selected_date, "%Y-%m-%d").weekday()
        wh = db.query(WorkHour).filter(
            WorkHour.business_id == biz.id,
            WorkHour.day_of_week == day_of_week
        ).first()

        if not wh:
            open_time, close_time = "09:00", "19:00"
        else:
            open_time, close_time = wh.open_time, wh.close_time

        # Personel seçilmişse, o personelin dolu saatlerini say
        if conv.selected_staff_id:
            booked = db.query(Appointment).filter(
                Appointment.business_id == biz.id,
                Appointment.staff_id == conv.selected_staff_id,
                Appointment.date == conv.selected_date,
                Appointment.status != "iptal"
            ).all()
        else:
            # Personel seçilmemişse tüm personelleri say
            booked = db.query(Appointment).filter(
                Appointment.business_id == biz.id,
                Appointment.date == conv.selected_date,
                Appointment.status != "iptal"
            ).all()

        booked_times = [a.time for a in booked]
        slots = generate_slots(open_time, close_time, service.duration, booked_times)
        available_slots = [s for s in slots if s.get("available")]

        choice = parse_selection(message, len(available_slots))
        if choice is None:
            return "Lütfen geçerli bir saat seçin (1-" + str(len(available_slots)) + ")"

        selected_time = available_slots[choice - 1]["time"]
        conv.selected_time = selected_time
        conv.status = "waiting_name"

        return f"✅ {selected_time} seçildi.\n\nAdınız nedir?"

    # Ad bekliyoruz
    if conv.status == "waiting_name":
        conv.customer_name = message
        conv.status = "completed"

        # Randevu oluştur
        # Telefon numarası WhatsApp'tan geliyor
        customer_phone = conv.customer_phone.replace("whatsapp:", "")

        apt = Appointment(
            business_id=biz.id,
            service_id=conv.selected_service_id,
            staff_id=conv.selected_staff_id if conv.selected_staff_id else None,
            customer_name=conv.customer_name,
            customer_phone=customer_phone,
            date=conv.selected_date,
            time=conv.selected_time,
            status="bekliyor"
        )
        db.add(apt)
        db.commit()
        db.refresh(apt)

        # Bildirim gönder
        service = db.query(Service).filter(Service.id == conv.selected_service_id).first()

        # Tarih formatlama: 2026-03-31 -> 31 Mart 2026
        date_obj = datetime.strptime(conv.selected_date, "%Y-%m-%d")
        months_tr = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
                     "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
        formatted_date = f"{date_obj.day} {months_tr[date_obj.month - 1]} {date_obj.year}"

        # Müşteriye SMS
        asyncio.create_task(send_appointment_confirm(
            conv.customer_name, customer_phone,
            biz.name, service.name,
            conv.selected_date, conv.selected_time
        ))

        # İşletmeye SMS
        if biz.phone:
            asyncio.create_task(send_booking_with_products_business(
                biz.phone, conv.customer_name,
                service.name, conv.selected_date, conv.selected_time, [], ""
            ))

        response = (
            f"✅ Randevunuz onaylandı!\n\n"
            f"İşletme: {biz.name}\n"
            f"Hizmet: {service.name}\n"
            f"Tarih: {formatted_date}\n"
            f"Saat: {conv.selected_time}\n\n"
            f"Teşekkür ederiz! 😊"
        )
        return response

    # Bilinmeyen komut
    return "Anlamadım. 'Randevu Al' yazarak başlayabilirsiniz."
