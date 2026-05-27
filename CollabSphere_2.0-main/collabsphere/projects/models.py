from django.db import models
from django.contrib.auth.models import User


class Team(models.Model):
    name = models.CharField(max_length=100, verbose_name='Názov')
    description = models.TextField(blank=True, verbose_name='Popis')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Dátum vytvorenia')
    members = models.ManyToManyField(User, related_name='teams', blank=True, verbose_name='Členovia')

    class Meta:
        verbose_name = 'Tím'
        verbose_name_plural = 'Tímy'
        ordering = ['name']

    def __str__(self):
        return self.name


class Project(models.Model):
    STATUS_CHOICES = [
        ('planning', 'Plánovanie'),
        ('active', 'Aktívny'),
        ('on_hold', 'Pozastavený'),
        ('completed', 'Dokončený'),
        ('cancelled', 'Zrušený'),
    ]

    name = models.CharField(max_length=200, verbose_name='Názov')
    description = models.TextField(blank=True, verbose_name='Popis')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Dátum vytvorenia')
    deadline = models.DateField(null=True, blank=True, verbose_name='Termín odovzdania')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planning', verbose_name='Stav')
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name='projects', verbose_name='Tím')
    members = models.ManyToManyField(User, through='Membership', related_name='projects', verbose_name='Členovia')

    class Meta:
        verbose_name = 'Projekt'
        verbose_name_plural = 'Projekty'
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class Membership(models.Model):
    ROLE_CHOICES = [
        ('manager', 'Manažér'),
        ('developer', 'Vývojár'),
        ('designer', 'Dizajnér'),
        ('tester', 'Tester'),
        ('analyst', 'Analytik'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Používateľ')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, verbose_name='Projekt')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='developer', verbose_name='Rola v projekte')
    joined_at = models.DateField(auto_now_add=True, verbose_name='Dátum priradenia')

    class Meta:
        verbose_name = 'Členstvo'
        verbose_name_plural = 'Členstvá'
        unique_together = ('user', 'project')

    def __str__(self):
        return f'{self.user.username} – {self.project.name} ({self.get_role_display()})'


class Task(models.Model):
    PRIORITY_CHOICES = [
        ('low', 'Nízka'),
        ('medium', 'Stredná'),
        ('high', 'Vysoká'),
        ('critical', 'Kritická'),
    ]
    STATUS_CHOICES = [
        ('todo', 'Na urobenie'),
        ('in_progress', 'V riešení'),
        ('review', 'Na kontrole'),
        ('done', 'Hotovo'),
    ]

    name = models.CharField(max_length=200, verbose_name='Názov')
    description = models.TextField(blank=True, verbose_name='Popis')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium', verbose_name='Priorita')
    deadline = models.DateField(null=True, blank=True, verbose_name='Termín')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='todo', verbose_name='Stav')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tasks', verbose_name='Projekt')
    assignee = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,related_name='tasks', verbose_name='Riešiteľ')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Úloha'
        verbose_name_plural = 'Úlohy'
        ordering = ['-created_at']

    def __str__(self):
        return self.name
