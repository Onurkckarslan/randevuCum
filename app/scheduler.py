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


async def check_subscriptions():
    """PayTR Abonelik kontrol — Trial biten işletmeleri yönet."""
    db: Session = SessionLocal()
    try:
        now = datetime.utcnow()

        # 1. Trial biten, kart eklenmemiş → Suspend
        expired_trials_no_card = db.query(Business).filter(
            Business.subscription_status == "trial",
            Business.subscription_end_date != None,
            Business.subscription_end_date < now,
            (Business.paytr_card_token == None) | (Business.paytr_card_token == "")
        ).all()

        for biz in expired_trials_no_card:
            biz.subscription_status = "suspended"
            biz.plan_type = "temel"
            print(f"[Scheduler] Trial süresi doldu, kart yok, suspend: {biz.name} (ID: {biz.id})")

        if expired_trials_no_card:
            db.commit()

        # 2. Trial biten, kart var → Otomatik ilk ödeme dene
        # (Şimdilik basit: status'u active yap, webhook ile gerçek ödeme olur)
        trial_with_card = db.query(Business).filter(
            Business.subscription_status == "trial",
            Business.subscription_end_date != None,
            Business.subscription_end_date < now,
            Business.paytr_card_token != None,
            Business.paytr_card_token != ""
        ).all()

        for biz in trial_with_card:
            # Recurring ödeme API çağrısı yapılması gerekir, şimdilik skip
            # (Frontend'de / webhook'da yapılıp, buradan manual tetikleyebiliriz)
            biz.subscription_status = "active"
            biz.next_billing_date = now + timedelta(days=30)
            print(f"[Scheduler] Trial süresi doldu, kart var, active: {biz.name} (ID: {biz.id})")

        if trial_with_card:
            db.commit()

        # 3. Active, ödeme başarısız too many times → Suspend
        failed_subscriptions = db.query(Business).filter(
            Business.subscription_status == "active",
            Business.payment_failed_count >= 3
        ).all()

        for biz in failed_subscriptions:
            biz.subscription_status = "suspended"
            biz.plan_type = "temel"
            print(f"[Scheduler] 3x ödeme başarısız, suspend: {biz.name} (ID: {biz.id})")

        if failed_subscriptions:
            db.commit()

    except Exception as e:
        print(f"[Scheduler] Abonelik kontrol hatası: {e}")
    finally:
        db.close()


async def scheduler_loop():
    """Uygulama başladığında arka planda çalışır."""
    print("[Scheduler] SMS hatırlatma + plan kontrol + abonelik servisi başladı.")
    while True:
        await check_reminders()
        await check_expired_plans()
        await check_subscriptions()
        await asyncio.sleep(600)  # 10 dakikada bir kontrol

