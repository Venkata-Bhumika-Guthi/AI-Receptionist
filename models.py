from django.db import models

class Call(models.Model):
    twilio_sid = models.CharField(max_length=64, unique=True, null=True, blank=True)
    from_number = models.CharField(max_length=32, db_index=True)
    to_number = models.CharField(max_length=32)
    status = models.CharField(max_length=32, default="initiated")  # initiated|in_dialog|booking|completed|failed|handoff
    transcript = models.TextField(null=True, blank=True)

    # conversational fields
    stage = models.CharField(max_length=32, default="start")  # start|need_service|need_time|confirming|done
    slots_json = models.JSONField(default=dict, blank=True)   # {"service": "...", "when": "tomorrow 3pm"}

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.from_number} -> {self.to_number} [{self.status}/{self.stage}]"
