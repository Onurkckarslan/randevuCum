from ..templates_config import templates
from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Business, PasswordResetToken
from ..auth import hash_password, verify_password, create_token, get_current_business_id
from ..mail import send_password_reset_email
from datetime import datetime, timedelta
import re
import secrets
import os

router = APIRouter()


def slugify(text: str) -> str:
    tr = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosucgiosu")
    text = text.translate(tr).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text


@router.get("/kayit", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("business/register.html", {"request": request, "error": None})


@router.post("/kayit", response_class=HTMLResponse)
async def register(
    request: Request,
    name: str = Form(...),
    category: str = Form(...),
    phone: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    address: str = Form(""),
    district: str = Form(""),
    db: Session = Depends(get_db)
):
    if db.query(Business).filter(Business.email == email).first():
        return templates.TemplateResponse("business/register.html", {
            "request": request, "error": "Bu e-posta zaten kayıtlı."
        })

    slug_base = slugify(name)
    slug = slug_base
    count = 1
    while db.query(Business).filter(Business.slug == slug).first():
        slug = f"{slug_base}-{count}"
        count += 1

    biz = Business(
        name=name, slug=slug, category=category,
        phone=phone, email=email,
        password_hash=hash_password(password),
        address=address, district=district, city="Uşak",
        plan="temel",
        plan_expires_at=datetime.utcnow() + timedelta(days=30)  # 30 gün ücretsiz
    )
    db.add(biz)
    db.commit()
    db.refresh(biz)

    response = RedirectResponse("/panel", status_code=302)
    response.set_cookie("token", create_token(biz.id), max_age=60*60*24*30, httponly=True, secure=False, samesite="lax")
    return response


@router.get("/giris", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("business/login.html", {"request": request, "error": None})


@router.post("/giris", response_class=HTMLResponse)
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    biz = db.query(Business).filter(Business.email == email).first()
    if not biz or not verify_password(password, biz.password_hash):
        return templates.TemplateResponse("business/login.html", {
            "request": request, "error": "E-posta veya şifre hatalı."
        })

    response = RedirectResponse("/panel", status_code=302)
    response.set_cookie("token", create_token(biz.id), max_age=60*60*24*30, httponly=True, secure=False, samesite="lax")
    return response


@router.get("/cikis")
async def logout():
    response = RedirectResponse("/", status_code=302)
    response.delete_cookie("token")
    return response


@router.get("/sifremi-unuttum", response_class=HTMLResponse)
async def forgot_password_page(request: Request):
    return templates.TemplateResponse("business/forgot_password.html", {"request": request, "message": None})


@router.post("/sifremi-unuttum", response_class=HTMLResponse)
async def forgot_password(
    request: Request,
    email: str = Form(...),
    db: Session = Depends(get_db)
):
    biz = db.query(Business).filter(Business.email == email).first()
    if not biz:
        return templates.TemplateResponse("business/forgot_password.html", {
            "request": request, "message": "Eğer bu e-posta sistemde kayıtlıysa, reset linki gönderilmiştir."
        })

    # Eski token'ları temizle
    db.query(PasswordResetToken).filter(PasswordResetToken.email == email).delete()

    # Yeni token oluştur (1 saatlik)
    token = secrets.token_urlsafe(32)
    reset_token = PasswordResetToken(
        email=email,
        token=token,
        expires_at=datetime.utcnow() + timedelta(hours=1)
    )
    db.add(reset_token)
    db.commit()

    # Reset linki oluştur
    reset_link = f"https://www.randevucum.com/sifremi-sifirla/{token}"

    # Email gönder
    send_password_reset_email(email, reset_link)

    return templates.TemplateResponse("business/forgot_password.html", {
        "request": request, "message": "Eğer bu e-posta sistemde kayıtlıysa, reset linki gönderilmiştir."
    })


@router.get("/sifremi-sifirla/{token}", response_class=HTMLResponse)
async def reset_password_page(request: Request, token: str, db: Session = Depends(get_db)):
    reset_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == token,
        PasswordResetToken.expires_at > datetime.utcnow()
    ).first()

    if not reset_token:
        return templates.TemplateResponse("business/reset_password.html", {
            "request": request, "error": "Geçersiz veya süresi dolmuş reset linki.", "token": None
        })

    return templates.TemplateResponse("business/reset_password.html", {
        "request": request, "error": None, "token": token
    })


@router.post("/sifremi-sifirla/{token}", response_class=HTMLResponse)
async def reset_password(
    request: Request,
    token: str,
    password: str = Form(...),
    password_confirm: str = Form(...),
    db: Session = Depends(get_db)
):
    if password != password_confirm:
        return templates.TemplateResponse("business/reset_password.html", {
            "request": request, "error": "Şifreler eşleşmiyor.", "token": token
        })

    reset_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == token,
        PasswordResetToken.expires_at > datetime.utcnow()
    ).first()

    if not reset_token:
        return templates.TemplateResponse("business/reset_password.html", {
            "request": request, "error": "Geçersiz veya süresi dolmuş reset linki.", "token": None
        })

    # Şifreyi güncelle
    biz = db.query(Business).filter(Business.email == reset_token.email).first()
    if biz:
        biz.password_hash = hash_password(password)
        db.commit()

    # Token'ı sil
    db.delete(reset_token)
    db.commit()

    return templates.TemplateResponse("business/reset_password.html", {
        "request": request, "error": "Şifreniz başarıyla sıfırlanmıştır. Giriş yapmak için lütfen yeni şifrenizi kullanın.",
        "token": None, "success": True
    })

