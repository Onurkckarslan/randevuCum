"""
SMS HatÄ±rlatma Scheduler
Her 10 dakikada bir Ã§alÄ±ÅŸÄ±r:
- YarÄ±n randevusu olanlar â†’ 1 gÃ¼n Ã¶nce SMS
- 2 saat sonra randevusu olanlar â†’ 2 saat Ã¶nce SMS
"""
import asyncio
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from .database import SessionLocal
from .models import Appointment, Business
from .sms import send_day_before_reminder, send_2h_reminder


async def check_reminders():
    db: Session = SessionLocal()
    try:
        now = datetime.now()
        today = date.today().isoformat()
        tomorrow = (date.today() + timedelta(days=1)).isoformat()

        # 1 GÃœN Ã–NCE: YarÄ±n randevusu olanlar, henÃ¼z SMS gÃ¶nderilmemiÅŸ
        day_before = db.query(Appointment).filter(
            Appointment.date == tomorrow,
            Appointment.status != "iptal",
            Appointment.sms_day_before_sent == False
        ).all()

        for apt in day_before:
            ok = await send_day_before_reminder(
                apt.customer_name, apt.customer_phone,
                apt.business.name if apt.business else "Salon",
                apt.date, apt.time
            )
            if ok:
                apt.sms_day_before_sent = True
                db.commit()
            await asyncio.sleep(0.5)

        # 2 SAAT Ã–NCE: BugÃ¼n, 2 saat sonraki randevular
        target_time = (now + timedelta(hours=2)).strftime("%H:%M")
        two_hour = db.query(Appointment).filter(
            Appointment.date == today,
            Appointment.time == target_time,
            Appointment.status != "iptal",
            Appointment.sms_2h_before_sent == False
        ).all()

        for apt in two_hour:
            ok = await send_2h_reminder(
                apt.customer_name, apt.customer_phone,
                apt.business.name if apt.business else "Salon",
                apt.time
            )
            if ok:
                apt.sms_2h_before_sent = True
                db.commit()
            await asyncio.sleep(0.5)

    except Exception as e:
        print(f"[Scheduler] Hata: {e}")
    finally:
        db.close()


async def check_expired_plans():
    """Süresi dolan planları pasife al."""
    db: Session = SessionLocal()
    try:
        now = datetime.utcnow()
        expired = db.query(Business).filter(
            Business.is_active == True,
            Business.plan_expires_at != None,
            Business.plan_expires_at < now
        ).all()
        for biz in expired:
            biz.is_active = False
            print(f"[Scheduler] Plan süresi doldu, pasife alındı: {biz.name}")
        if expired:
            db.commit()
    except Exception as e:
        print(f"[Scheduler] Plan kontrol hatası: {e}")
    finally:
        db.close()


async def scheduler_loop():
    """Uygulama başladığında arka planda çalışır."""
    print("[Scheduler] SMS hatırlatma + plan kontrol servisi başladı.")
    while True:
        await check_reminders()
        await check_expired_plans()
        await asyncio.sleep(600)  # 10 dakikada bir kontrol

