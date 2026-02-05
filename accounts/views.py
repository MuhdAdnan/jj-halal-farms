from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from .models import PendingUser, CustomerProfile
from django.contrib.auth.models import User
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_str, force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
from django.contrib.auth.hashers import make_password
from .emails import send_verification_email
from .models import CustomerMessage
from django.contrib.auth.decorators import login_required



# ------------------USER ACCOUNT VIEWS---------------------

# User Registration View
def register(request):
    if request.method == "POST":
        full_name = request.POST.get("full_name")
        email = request.POST.get("email")
        phone_number = request.POST.get("phone")
        password = request.POST.get("password")
        confirm_password = request.POST.get("password2")

        # Check passwords match
        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect("accounts:register")

        # Check email not already used
        if User.objects.filter(email=email).exists() or PendingUser.objects.filter(email=email).exists():
            messages.error(request, "Email already exists.")
            return redirect("accounts:register")

        # Save pending user
        pending_user = PendingUser.objects.create(
            full_name=full_name,
            email=email,
            phone_number=phone_number,
            password=make_password(password),
        )

        # Send verification email
        send_verification_email(email, pending_user.verification_token, request)

        messages.success(request, "Check your email to verify your account.")
        return redirect("accounts:register")

    return render(request, "accounts/register.html")



# Email Verification View
def verify_email(request, token):
    try:
        pending_user = PendingUser.objects.get(verification_token=token)

        # Create real user
        user = User.objects.create(
            username=pending_user.email,
            email=pending_user.email,
            password=pending_user.password,
            first_name=pending_user.full_name,
        )
        CustomerProfile.objects.get_or_create(
            user=user,
            defaults={"phone": pending_user.phone_number, "is_email_verified": True},
        )

        # Delete pending user
        pending_user.delete()

        messages.success(request, "Your email is verified! You can now login.")
        return redirect("accounts:login")

    except PendingUser.DoesNotExist:
        messages.error(request, "Invalid or expired verification link.")
        return redirect("accounts:register")

def resend_verification(request):
    if request.method == "POST":
        email = request.POST.get("email")

        try:
            pending_user = PendingUser.objects.get(email=email)
        except PendingUser.DoesNotExist:
            messages.error(request, "No pending account found with this email.")
            return redirect("accounts:resend_verification")

        send_verification_email(
            pending_user.email,
            pending_user.verification_token,
            request,
        )

        messages.success(request, "Verification email has been resent.")
        return redirect("accounts:login")

    return render(request, "accounts/resend_verification.html")

# User Login View
def login_view(request):
    if request.method == "POST":
        email = request.POST["email"]
        password = request.POST["password"]

        user = authenticate(request, username=email, password=password)

        if user is not None:
            if not user.is_active:
                messages.error(request, "Please verify your email first.")
                return redirect("accounts:login")

            login(request, user)
            return redirect("core:home")

        messages.error(request, "Invalid login credentials")
        return redirect("accounts:login")

    return render(request, "accounts/login.html")

# Password Reset Request View
def password_reset_request(request):
    if request.method == "POST":
        email = request.POST.get("email")

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, "No account found with this email.")
            return redirect("accounts:password_reset")

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        reset_link = request.build_absolute_uri(
            reverse("accounts:password_reset_confirm", args=[uid, token])
        )

        send_mail(
            "Password Reset",
            f"Click the link to reset your password:\n{reset_link}",
            settings.DEFAULT_FROM_EMAIL,
            [email],
        )

        messages.success(request, "Password reset link sent to your email.")
        return redirect("accounts:login")

    return render(request, "accounts/password_reset.html")


# Password Reset Confirm View
def password_reset_confirm(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except:
        user = None

    if user and default_token_generator.check_token(user, token):
        if request.method == "POST":
            password = request.POST.get("password")
            password2 = request.POST.get("password2")

            if password != password2:
                messages.error(request, "Passwords do not match.")
                return redirect(request.path)

            user.set_password(password)
            user.save()

            messages.success(request, "Password reset successful. You can login.")
            return redirect("accounts:login")

        return render(request, "accounts/password_reset_confirm.html")

    messages.error(request, "Invalid or expired reset link.")
    return redirect("accounts:login")


def logout_view(request):
    logout(request)
    return redirect("core:home")


@login_required(login_url="accounts:login")
def inbox(request):
    if request.user.is_staff:
        messages.error(request, "Admins cannot access customer inbox.")
        return redirect("core:home")
    messages_qs = CustomerMessage.objects.filter(recipient=request.user).order_by("-created_at")
    messages_qs.update(is_read=True)
    return render(request, "accounts/inbox.html", {"messages_list": messages_qs})
