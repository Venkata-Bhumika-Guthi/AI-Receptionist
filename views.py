from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, JsonResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404
from django.conf import settings
from .models import Call
from bookings.tasks import make_booking
import json

# Simple "slot filling" demo
SERVICES = ["haircut","consultation","cleaning","repair","massage","demo"]

def needs_service(slots): return not slots.get("service")
def needs_when(slots): return not slots.get("when")

def extract_service(text):
    t = (text or "").lower()
    for s in SERVICES:
        if s in t:
            return s
    if "book" in t or "appointment" in t:
        return "demo"
    return None

def normalize_when(text):
    # Keep raw; Celery/dateparser will parse it later
    return (text or "").strip()

def absolute(url_path: str) -> str:
    base = getattr(settings, "PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
    return f"{base}{url_path}"

def gather(prompt_text: str) -> HttpResponse:
    """
    Speak and LISTEN again for speech. Twilio will POST the result to gather-action.
    Using absolute URLs avoids host confusion with tunnels.
    """
    action_url = absolute("/webhooks/twilio/gather-action/")
    # Debug line to verify the exact URL in logs:
    print("DEBUG action_url:", action_url)

    twiml = f"""
<Response>
  <Gather input="speech" speechTimeout="auto" action="{action_url}" method="POST">
    <Say>{prompt_text}</Say>
  </Gather>
  <Say>Sorry, I didn't catch that.</Say>
  <Redirect method="POST">{absolute("/webhooks/twilio/voice/")}</Redirect>
</Response>
""".strip()
    return HttpResponse(twiml, content_type="text/xml")

def say(message: str) -> HttpResponse:
    return HttpResponse(f"<Response><Say>{message}</Say></Response>", content_type="text/xml")

def next_prompt(call: Call) -> HttpResponse:
    """
    Decide the next prompt and return a GATHER so Twilio listens.
    """
    slots = call.slots_json
    if needs_service(slots):
        call.stage = "need_service"; call.save()
        return gather("What service do you need? For example, haircut or consultation.")
    if needs_when(slots):
        call.stage = "need_time"; call.save()
        return gather("When would you like to come in?")
    call.stage = "confirming"; call.save()
    svc = slots.get("service")
    when = slots.get("when")
    return gather(f"Great. You want a {svc} around {when}. Shall I book it? Please say yes or no.")

def continue_dialog(call: Call, user_text: str) -> HttpResponse:
    """
    Update slots from the user's reply, and return either another GATHER or final SAY.
    """
    t = (user_text or "").strip().lower()
    slots = call.slots_json

    if call.stage in ("start", "need_service"):
        svc = extract_service(t)
        if svc:
            slots["service"] = svc
            call.slots_json = slots; call.save()
            return next_prompt(call)
        else:
            return gather("I can help you book. What service do you need? For example, haircut or consultation.")

    if call.stage == "need_time":
        slots["when"] = normalize_when(user_text)
        call.slots_json = slots; call.save()
        return next_prompt(call)

    if call.stage == "confirming":
        if any(x in t for x in ["yes","yeah","yup","please","sure","book","go ahead","confirm"]):
            call.status = "booking"; call.save()
            make_booking.delay(call.id, call.slots_json)
            call.stage = "done"; call.save()
            return say("Awesome, I'm booking that now. You'll get a confirmation soon. Goodbye!")
        elif any(x in t for x in ["no","nope","stop","cancel"]):
            call.stage = "need_service"; call.slots_json = {}; call.save()
            return gather("No problem. Let's start over. What service do you need?")
        else:
            return gather("Sorry, I didn't catch that. Should I book it? Please say yes or no.")

    return gather("Sorry, I didn't get that. Could you repeat?")

@csrf_exempt
def twilio_voice(request):
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")

    from_num = request.POST.get("From", "unknown")
    to_num = request.POST.get("To", "unknown")
    sid = request.POST.get("CallSid")

    # Create or update (idempotent if Twilio retries)
    Call.objects.update_or_create(
        twilio_sid=sid,
        defaults={"from_number": from_num, "to_number": to_num, "status": "in_dialog", "stage": "start", "slots_json": {}}
    )

    return gather("Hi! I can book appointments. What service do you need? For example, haircut or consultation.")

@csrf_exempt
def twilio_gather_action(request):
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")

    sid = request.POST.get("CallSid")
    speech = (request.POST.get("SpeechResult") or "").strip()

    call = Call.objects.filter(twilio_sid=sid).first()
    if not call:
        call = Call.objects.create(twilio_sid=sid, from_number="unknown", to_number="unknown",
                                   status="in_dialog", stage="start", slots_json={})

    call.transcript = speech
    call.save()

    return continue_dialog(call, speech)

@csrf_exempt
def retell_events(request):
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return HttpResponseBadRequest("Invalid JSON")

    call_id = payload.get("call_id")
    intent = (payload.get("intent") or "").lower()
    slots = payload.get("slots") or {}
    call = get_object_or_404(Call, id=call_id)

    if intent == "book":
        call.status = "booking"; call.stage = "confirming"; call.slots_json.update(slots); call.save()
        make_booking.delay(call.id, call.slots_json)
        return JsonResponse({"ok": True, "msg": "booking started"})
    return JsonResponse({"ok": True, "msg": "ignored"})
