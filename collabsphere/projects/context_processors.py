def is_manager(request):
    if request.user.is_authenticated:
        return {'is_manager': request.user.groups.filter(name='manager').exists() or request.user.is_superuser}
    return {'is_manager': False}
