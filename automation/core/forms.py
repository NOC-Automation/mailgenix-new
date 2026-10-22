# automation/core/forms.py
from django import forms
from django.contrib.auth.forms import AuthenticationForm

class TailwindAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label="Username",
        widget=forms.TextInput(attrs={
            "autofocus": True,
            "class": "block w-full rounded-md border-gray-300 shadow-sm "
                     "focus:border-indigo-500 focus:ring-indigo-500 px-3 py-2 text-sm",
            "placeholder": "Username",
        })
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={
            "class": "block w-full rounded-md border-gray-300 shadow-sm "
                     "focus:border-indigo-500 focus:ring-indigo-500 px-3 py-2 text-sm",
            "placeholder": "Password",
        })
    )


from django.contrib.auth.forms import AuthenticationForm
from django import forms as django_forms

class MailGenixAuthenticationForm(AuthenticationForm):
    """Login form with a friendly, non-enumerating invalid credential message."""
    error_messages = {
        "invalid_login": "Username atau password salah. Silakan periksa kembali dan coba lagi.",
        "inactive": "Akun ini tidak aktif. Silakan hubungi administrator.",
    }

    username = django_forms.CharField(required=True)
    password = django_forms.CharField(required=True, strip=False, widget=django_forms.PasswordInput)
