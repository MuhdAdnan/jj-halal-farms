from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse


def send_verification_email(email, token, request=None):
    path = reverse("accounts:verify_email", args=[token])
    if request:
        verification_link = request.build_absolute_uri(path)
    else:
        verification_link = f"http://127.0.0.1:8000/auth{path}"

    send_mail(
        subject="Verify your JJ Halal Farms account",
        message=f"Click the link below to verify your account:\n{verification_link}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )
