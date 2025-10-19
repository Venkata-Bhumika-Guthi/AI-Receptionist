from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from dateparser import parse as parse_when

from .models import Booking
from .availability import is_free, suggest_slot_near, default_length_minutes
from calls.models import Call

try:
    from twilio.rest import Client
except Exception:
    Client = None

@shared_task(autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, max_retries=3)
def make_booking(call_id, slots: dict):
    call = Call.objects.get(id=call_id)

    when_text = slots.get("when") or "tomorrow 3pm"
    desired = parse_when(when_text, settings={"TIMEZONE":"UTC", "RETURN_AS_TIMEZONE_AWARE": True})
    if not desired:
        desired = timezone.now() + timedelta(hours=1)

    length = default_length_minutes()
    start_ts = desired
    end_ts = start_ts + timedelta(minutes=length)

    if not is_free(start_ts, end_ts):
        alt_start, alt_end = suggest_slot_near(start_ts)
        if alt_start:
            start_ts, end_ts = alt_start, alt_end
        else:
            Booking.objects.create(call=call, status="failed", provider="demo",
                                   meta_json={"reason":"no slots","requested":slots})
            call.status = "failed"; call.stage = "done"; call.save()
            return {"status":"failed","reason":"no slots"}

    booking = Booking.objects.create(
        call=call, status="confirmed", provider="demo",
        start_ts=start_ts, end_ts=end_ts, meta_json={"requested": slots},
    )
    call.status = "completed"; call.stage = "done"; call.save()

    # Optional SMS via Twilio
    if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_FROM_NUMBER and call.from_number and Client:
        try:
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            msg = f"Confirmed: {start_ts.strftime('%a %b %d %I:%M %p UTC')} for {length} mins."
            client.messages.create(
                to=call.from_number,
                from_=settings.TWILIO_FROM_NUMBER,
                body=msg
            )
        except Exception:
            pass

    # Email(console backend prints to logs for free)
    if getattr(settings, "NOTIFY_EMAIL", None):
        send_mail(
            subject="New Booking Confirmed",
            message=f"Caller {call.from_number}\nTime: {start_ts} (UTC)\nLength: {length} mins",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.NOTIFY_EMAIL],
            fail_silently=True,
        )

    return {"status":"confirmed","booking_id": booking.id}
