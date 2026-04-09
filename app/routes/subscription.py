from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timedelta
import hashlib
import hmac
import os
import json
import requests
import uuid

from ..database import get_db
from ..models import Business, Payment
from ..auth import get_current_business_id
from ..templates_config import templates

router = APIRouter()

# ── PayTR Konfigürasyonu ──
PAYTR_MERCHANT_ID = os.getenv("PAYTR_MERCHANT_ID", "")
PAYTR_MERCHANT_KEY = os.getenv("PAYTR_MERCHANT_KEY", "")
PAYTR_MERCHANT_SALT = os.getenv("PAYTR_MERCHANT_SALT", "")
PAYTR_API_URL = "https://www.paytr.com/odeme/api/payment"

# Test modu (if no env vars)
TEST_MODE = not all([PAYTR_MERCHANT_ID, PAYTR_MERCHANT_KEY, PAYTR_MERCHANT_SALT])


def generate_paytr_hash(merchant_oid: str, amount: int, currency: str = "TRY") -> dict:
    """PayTR iframe token için HMAC hash üret"""
    if TEST_MODE:
        return {
            "merchant_oid": merchant_oid,
            "user_ip": "0.0.0.0",
            "merchant_id": PAYTR_MERCHANT_ID or "test",
            "user_name": "Test User",
            "user_email": "test@example.com",
            "user_address": "Test Address",
            "user_phone": "1234567890",
            "amount": amount,
            "paytr_token": f"test_token_{merchant_oid}",
            "test_mode": 1,
            "hash_str": "test_hash"
        }

    # Gerçek mod
    hash_str = f"{PAYTR_MERCHANT_ID}{merchant_oid}{amount}{PAYTR_MERCHANT_SALT}"
    hash_object = hashlib.sha256(hash_str.encode())
    paytr_hash = hash_object.hexdigest()

    return {
        "merchant_oid": merchant_oid,
        "hash_str": paytr_hash,
        "amount": amount
    }


def verify_paytr_webhook(webhook_data: dict) -> bool:
    """PayTR webhook hash'ini doğrula"""
    if TEST_MODE:
        return True

    merchant_oid = webhook_data.get("merchant_oid", "")
    status = webhook_data.get("status", "")
    total_amount = webhook_data.get("total_amount", "")
    returned_hash = webhook_data.get("hash_str", "")

    hash_str = f"{PAYTR_MERCHANT_ID}{merchant_oid}{status}{total_amount}{PAYTR_MERCHANT_SALT}"
    hash_object = hashlib.sha256(hash_str.encode())
    calculated_hash = hash_object.hexdigest()

    return returned_hash == calculated_hash


@router.get("/panel/billing", response_class=HTMLResponse)
async def billing_page(
    request: Request,
    db: Session = Depends(get_db),
    business_id: int = Depends(get_current_business_id)
):
    """Abonelik & Ödeme yönetim sayfası"""
    if not business_id:
        return HTMLResponse(status_code=401, content="Unauthorized")

    biz = db.query(Business).filter(Business.id == business_id).first()
    if not biz:
        return HTMLResponse(status_code=404, content="Business not found")

    # Ödeme geçmişi
    payments = db.query(Payment).filter(
        Payment.business_id == business_id
    ).order_by(Payment.created_at.desc()).all()

    # Abonelik durum mapping
    status_display = {
        "trial": ("⏳", "Trial (Ücretsiz)"),
        "active": ("✅", "Aktif"),
        "suspended": ("⚠️", "Askıda"),
        "cancelled": ("❌", "İptal")
    }

    context = {
        "request": request,
        "biz": biz,
        "payments": payments,
        "status_display": status_display,
        "has_card": bool(biz.paytr_card_token)
    }

    return templates.TemplateResponse("business/billing.html", context)


@router.post("/panel/billing/start-payment")
async def start_payment(
    request: Request,
    db: Session = Depends(get_db),
    business_id: int = Depends(get_current_business_id)
):
    """PayTR iframe token'ı üret"""
    if not business_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    biz = db.query(Business).filter(Business.id == business_id).first()
    if not biz:
        raise HTTPException(status_code=404, detail="Business not found")

    # Merchant OID (unique per transaction)
    merchant_oid = f"biz_{business_id}_{int(datetime.utcnow().timestamp())}"
    amount = 99900  # 999 TL in kuruş

    hash_data = generate_paytr_hash(merchant_oid, amount)

    return {
        "token": hash_data.get("hash_str", "test_hash"),
        "merchant_oid": merchant_oid,
        "merchant_id": PAYTR_MERCHANT_ID or "test",
        "amount": amount
    }


@router.post("/webhook/paytr")
async def paytr_webhook(request: Request, db: Session = Depends(get_db)):
    """PayTR webhook — ödeme sonucu"""
    try:
        # Webhook data form-data olarak geliyor
        form_data = await request.form()
        webhook_data = {key: value for key, value in form_data.items()}

        # Hash doğru
        if not verify_paytr_webhook(webhook_data):
            print(f"[WEBHOOK] Invalid hash from PayTR")
            return JSONResponse(status_code=400, content={"status": "error", "reason": "Invalid hash"})

        merchant_oid = webhook_data.get("merchant_oid", "")
        status = webhook_data.get("status", "")
        total_amount = int(webhook_data.get("total_amount", "0"))
        utoken = webhook_data.get("utoken", "")  # Card token
        card_name = webhook_data.get("card_name", "")  # Card brand
        card_unique_id = webhook_data.get("card_unique_id", "")  # Last 4 digits

        # merchant_oid'den business_id extract et
        # Format: "biz_{business_id}_{timestamp}"
        parts = merchant_oid.split("_")
        if len(parts) < 2 or parts[0] != "biz":
            print(f"[WEBHOOK] Invalid merchant_oid format: {merchant_oid}")
            return JSONResponse(status_code=400, content={"status": "error"})

        try:
            business_id = int(parts[1])
        except ValueError:
            print(f"[WEBHOOK] Invalid business_id in merchant_oid: {merchant_oid}")
            return JSONResponse(status_code=400, content={"status": "error"})

        biz = db.query(Business).filter(Business.id == business_id).first()
        if not biz:
            print(f"[WEBHOOK] Business not found: {business_id}")
            return JSONResponse(status_code=404, content={"status": "error", "reason": "Business not found"})

        if status == "success":
            # Ödeme başarılı
            biz.subscription_status = "active"
            biz.paytr_card_token = utoken
            biz.card_last4 = card_unique_id[-4:] if card_unique_id else ""
            biz.card_brand = card_name or "Unknown"
            biz.subscription_end_date = datetime.utcnow() + timedelta(days=30)
            biz.next_billing_date = datetime.utcnow() + timedelta(days=30)
            biz.payment_failed_count = 0

            # Payment kaydı
            payment = Payment(
                business_id=business_id,
                amount=total_amount,
                plan_type=biz.plan_type,
                status="completed",
                paytr_ref_no=merchant_oid,
                paid_at=datetime.utcnow()
            )
            db.add(payment)

            db.commit()
            print(f"[WEBHOOK] Payment successful for business {business_id}")
            return JSONResponse(status_code=200, content={"status": "ok"})

        else:
            # Ödeme başarısız
            biz.payment_failed_count = (biz.payment_failed_count or 0) + 1

            # 3 kez başarısız olursa suspend
            if biz.payment_failed_count >= 3:
                biz.subscription_status = "suspended"
                biz.plan_type = "temel"

            # Payment kaydı
            payment = Payment(
                business_id=business_id,
                amount=total_amount,
                plan_type=biz.plan_type,
                status="failed",
                paytr_ref_no=merchant_oid,
                error_msg=webhook_data.get("error_message", "Unknown error")
            )
            db.add(payment)

            db.commit()
            print(f"[WEBHOOK] Payment failed for business {business_id}. Failed count: {biz.payment_failed_count}")
            return JSONResponse(status_code=200, content={"status": "ok"})

    except Exception as e:
        print(f"[WEBHOOK] Exception: {str(e)}")
        return JSONResponse(status_code=500, content={"status": "error", "reason": str(e)})


@router.post("/panel/billing/cancel")
async def cancel_subscription(
    request: Request,
    db: Session = Depends(get_db),
    business_id: int = Depends(get_current_business_id)
):
    """Aboneliği iptal et"""
    if not business_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    biz = db.query(Business).filter(Business.id == business_id).first()
    if not biz:
        raise HTTPException(status_code=404, detail="Business not found")

    biz.subscription_status = "cancelled"
    biz.plan_type = "temel"
    biz.paytr_card_token = None
    biz.next_billing_date = None

    db.commit()

    return JSONResponse(status_code=200, content={"status": "ok", "message": "Abonelik iptal edildi"})


@router.post("/panel/billing/remove-card")
async def remove_card(
    request: Request,
    db: Session = Depends(get_db),
    business_id: int = Depends(get_current_business_id)
):
    """Kartı sil"""
    if not business_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    biz = db.query(Business).filter(Business.id == business_id).first()
    if not biz:
        raise HTTPException(status_code=404, detail="Business not found")

    biz.paytr_card_token = None
    biz.card_last4 = None
    biz.card_brand = None

    db.commit()

    return JSONResponse(status_code=200, content={"status": "ok", "message": "Kart silindi"})
