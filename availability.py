from datetime import timedelta
from django.utils import timezone
from .models import Booking

def is_free(start_ts, end_ts):
    overlap = Booking.objects.filter(
        status="confirmed",
        start_ts__lt=end_ts,
        end_ts__gt=start_ts,
    ).exists()
    return not overlap

def default_length_minutes():
    return 30

def suggest_slot_near(desired_start):
    length = default_length_minutes()
    start = desired_start
    for _ in range(6):
        end = start + timedelta(minutes=length)
        if is_free(start, end):
            return start, end
        start = end
    return None, None
