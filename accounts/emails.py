from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse


def send_verification_email(to_email, token, request=None):
    path = reverse("accounts:verify_email", args=[token])
    if request:
        verification_link = request.build_absolute_uri(path)
    else:
        verification_link = f"http://127.0.0.1:8000/auth{path}"
    subject = "Verify Your Email | JJ HALAL FARMS"
    message = f"Hello,\n\nPlease click the link below to verify your email:\n\n{verification_link}\n\nThank you!"
    from_email = settings.DEFAULT_FROM_EMAIL
    send_mail(subject, message, from_email, [to_email])
