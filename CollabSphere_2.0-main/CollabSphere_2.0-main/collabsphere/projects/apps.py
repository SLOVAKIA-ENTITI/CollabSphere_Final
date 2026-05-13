from django.apps import AppConfig


class ProjectsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'projects'

    def ready(self):
        from django.db.models.signals import post_migrate
        post_migrate.connect(create_default_groups, sender=self)


def create_default_groups(sender, **kwargs):
    from django.contrib.auth.models import Group, Permission
    from django.contrib.contenttypes.models import ContentType

    manager_group, _ = Group.objects.get_or_create(name='manager')
    member_group, _ = Group.objects.get_or_create(name='team_member')
