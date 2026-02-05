from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages

def staff_required(view_func):
    """
    Decorator to restrict access to admin/staff users only.
    Redirects non-staff users to the admin login page with a message.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_staff:
            # User is admin, allow access
            return view_func(request, *args, **kwargs)
        else:
            # Not admin, redirect to admin login
            messages.error(request, "You must be an admin to access this page.")
            return redirect("admin_panel:login")

    return _wrapped_view
