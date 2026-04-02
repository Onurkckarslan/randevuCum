# WhatsApp Notification System - Current Setup

## Overview
The WhatsApp notification system has been simplified to use a single global number (+15108718367 / TWILIO_WHATSAPP_NUMBER) for basic tier businesses, while premium businesses can optionally use their own registered Twilio numbers.

## Implementation Details

### Customer Booking Notifications
When a customer books an appointment from the website:

**Premium Businesses:**
- Uses their own Twilio number (if available from `biz.whatsapp_phone`)
- Sends confirmation to customer's WhatsApp
- Sends notification to business owner's personal phone number

**Basic Businesses:**
- Uses global +15108718367
- Sends confirmation to customer's WhatsApp only

### Message Format
```
Merhaba {customer_name},

{business_name} için {date} {time}'de {service_name} randevunuz onaylandı.

Teşekkür ederiz! 😊
```

For business owner (premium only):
```
Yeni randevu!

Müşteri: {customer_name}
Hizmet: {service_name}
Tarih: {formatted_date}
Saat: {selected_time}
```

## Code Changes

### File: `app/routes/booking.py`
- Lines 213-255: Unified notification logic
- Removed SMS fallback for basic tier
- Consolidated message sending to eliminate code duplication
- Phone number formatting: Converts `05...` to `+905...` for Twilio API

### Related Files
- `app/whatsapp.py`: `send_whatsapp_message()` function
- `app/templates/customer/business.html`: Booking forms (both desktop & mobile)

## Testing Checklist

- [ ] Test booking from desktop form
- [ ] Test booking from mobile form
- [ ] Verify customer receives WhatsApp notification
- [ ] Test premium booking (with own Twilio number if assigned)
- [ ] Test basic booking (using global +15108718367)
- [ ] Check that form validation errors are logged properly
- [ ] Verify date formatting: "31 Mart 2026" format

## Known Issues

1. **Form validation**: If 400/422 errors occur, check browser console for missing form fields
2. **SMS to Turkey**: Twilio trial accounts don't support SMS to +90 numbers (use WhatsApp instead)
3. **Phone number format**: Customer phone input should auto-format or handle both `05...` and `+905...` formats

## Environment Variables Required

```bash
TWILIO_ACCOUNT_SID=xxx
TWILIO_AUTH_TOKEN=xxx
TWILIO_WHATSAPP_NUMBER=+15108718367
TWILIO_ENABLED=true
```

## Phone Number Pool (Premium Assignments)

Available Twilio numbers that can be assigned to premium businesses:
- +1 415 691 2998
- +1 510 871 8367
- +14155238886 (if needed)

These numbers must have WhatsApp capability enabled in Twilio.

## Deployment

Changes pushed to: `main` branch
Commit: `69c17a3` - "Simplify WhatsApp notifications: use global +15108718367 for all users"

Auto-deployed to Render when merged.
