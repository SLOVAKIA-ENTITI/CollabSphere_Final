from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def manager_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.groups.filter(name='manager').exists() or request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        messages.error(request, 'Táto akcia vyžaduje rolu manažéra.')
        return redirect('dashboard')
    return wrapper
