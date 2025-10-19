from django.contrib import admin
from .models import Call

@admin.register(Call)
class CallAdmin(admin.ModelAdmin):
    list_display = ("id","from_number","to_number","status","stage","created_at")
    search_fields = ("from_number","twilio_sid")
