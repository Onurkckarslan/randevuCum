from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from ..database import get_db
from ..models import Lead
import re

router = APIRouter()


class LeadFormData(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    business_name: str = Field(..., min_length=2, max_length=150)
    phone: str = Field(..., min_length=10, max_length=20)
    message: str = Field(default="", max_length=500)


def validate_phone(phone: str) -> bool:
    """Telefon numarası doğruluğunu kontrol et"""
    # Sadece rakam ve + - karakterlerine izin ver
    phone = re.sub(r'[\s\-\(\)]', '', phone)
    return len(phone) >= 10 and (phone[0] == '+' or phone[0].isdigit())


@router.post("/api/lead")
async def submit_lead(form_data: LeadFormData, db: Session = Depends(get_db)):
    """Lead formunu kaydet"""

    # Telefon doğrula
    if not validate_phone(form_data.phone):
        raise HTTPException(status_code=400, detail="Geçersiz telefon numarası")

    # Yeni lead kaydı oluştur
    new_lead = Lead(
        full_name=form_data.full_name.strip(),
        business_name=form_data.business_name.strip(),
        phone=form_data.phone.strip(),
        message=form_data.message.strip() if form_data.message else None,
        status="beklemede",
        is_read=False
    )

    db.add(new_lead)
    db.commit()
    db.refresh(new_lead)

    return {
        "success": True,
        "message": "Bilgileriniz alındı, ekibimiz en kısa sürede sizinle iletişime geçecek!",
        "lead_id": new_lead.id
    }
