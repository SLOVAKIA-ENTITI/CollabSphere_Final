from django.contrib import admin
from .models import Team, Project, Membership, Task


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    filter_horizontal = ('members',)


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 1


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'team', 'deadline', 'created_at')
    list_filter = ('status', 'team')
    inlines = [MembershipInline]


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'project', 'role', 'joined_at')
    list_filter = ('role',)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('name', 'project', 'assignee', 'priority', 'status', 'deadline')
    list_filter = ('status', 'priority', 'project')
