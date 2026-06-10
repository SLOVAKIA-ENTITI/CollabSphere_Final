import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User, Group
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Value
from django.db.models.functions import Concat
from .models import Project, Task, Team, Membership

# Import formulárov
from .forms import ProjectForm, TaskForm, TeamForm, MembershipForm, UserEditForm, MembershipFormSet
from .decorators import manager_required


# ─── Dashboard ────────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    is_manager = request.user.groups.filter(name='manager').exists()
    if is_manager:
        projects = Project.objects.select_related('team').prefetch_related('members')
        tasks = Task.objects.select_related('project', 'assignee')
    else:
        projects = Project.objects.filter(members=request.user).select_related('team')
        tasks = Task.objects.filter(
            Q(assignee=request.user) | Q(project__members=request.user)
        ).distinct().select_related('project', 'assignee')

    # Workload per user
    PRIORITY_WEIGHT = {'low': 1, 'medium': 2, 'high': 3, 'critical': 5}
    if is_manager:
        all_users = User.objects.filter(tasks__isnull=False).distinct()
    else:
        all_users = User.objects.filter(projects__in=projects).distinct()

    workload = []
    for u in all_users:
        user_tasks = Task.objects.filter(assignee=u).exclude(status='done')
        score = sum(PRIORITY_WEIGHT.get(t.priority, 1) for t in user_tasks)
        done_count = Task.objects.filter(assignee=u, status='done').count()
        workload.append({
            'user': u,
            'total': user_tasks.count(),
            'score': score,
            'done': done_count,
        })
    
    # OPRAVA: Zoradenie členov na Dashboarde podľa priezviska a mena
    workload.sort(key=lambda x: (x['user'].last_name.lower(), x['user'].first_name.lower(), x['user'].username.lower()))

    max_score = max((w['score'] for w in workload), default=1) or 1
    for w in workload:
        w['percent'] = round(w['score'] / max_score * 100)
        w['color'] = 'success' if w['percent'] < 30 else ('warning' if w['percent'] < 65 else 'danger')

    context = {
        'projects': projects[:5],
        'tasks': tasks[:10],
        'total_projects': projects.count(),
        'total_tasks': tasks.count(),
        'todo_tasks': tasks.filter(status='todo').count(),
        'done_tasks': tasks.filter(status='done').count(),
        'is_manager': is_manager,
        'workload': workload,
    }
    return render(request, 'projects/dashboard.html', context)


# ─── Projects ─────────────────────────────────────────────────────────────────

@login_required
def project_list(request):
    is_manager = request.user.groups.filter(name='manager').exists()
    if is_manager:
        projects = Project.objects.select_related('team').prefetch_related('members')
    else:
        projects = Project.objects.filter(members=request.user).select_related('team')

    status_filter = request.GET.get('status', '')
    if status_filter:
        projects = projects.filter(status=status_filter)

    return render(request, 'projects/project_list.html', {
        'projects': projects,
        'status_filter': status_filter,
        'status_choices': Project.STATUS_CHOICES,
        'is_manager': is_manager,
    })


@login_required
def project_detail(request, pk):
    is_manager = request.user.groups.filter(name='manager').exists()
    if is_manager:
        project = get_object_or_404(Project, pk=pk)
    else:
        project = get_object_or_404(Project, pk=pk, members=request.user)

    tasks = project.tasks.select_related('assignee')
    memberships = Membership.objects.filter(project=project).select_related('user')

    status_filter = request.GET.get('status', '')
    priority_filter = request.GET.get('priority', '')
    assignee_filter = request.GET.get('assignee', '')

    if status_filter:
        tasks = tasks.filter(status=status_filter)
    if priority_filter:
        tasks = tasks.filter(priority=priority_filter)
    if assignee_filter:
        tasks = tasks.filter(assignee_id=assignee_filter)

    return render(request, 'projects/project_detail.html', {
        'project': project,
        'tasks': tasks,
        'memberships': memberships,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'assignee_filter': assignee_filter,
        'task_status_choices': Task.STATUS_CHOICES,
        'task_priority_choices': Task.PRIORITY_CHOICES,
        'is_manager': is_manager,
    })


@login_required
@manager_required
def project_create(request):
    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save()
            members_to_add = set()

            if project.team:
                team_users = project.team.members.all()
                for user in team_users:
                    members_to_add.add(user)

            external_users = form.cleaned_data.get('external_members')
            if external_users:
                for user in external_users:
                    members_to_add.add(user)

            members_to_add.add(request.user)

            for user in members_to_add:
                role_type = 'manager' if user == request.user else 'developer'
                Membership.objects.get_or_create(
                    user=user,
                    project=project,
                    defaults={'role': role_type}
                )

            messages.success(request, f'Projekt „{project.name}“ bol úspešne vytvorený.')
            return redirect('project_detail', pk=project.pk)
    else:
        form = ProjectForm()
        
    return render(request, 'projects/project_form.html', {'form': form, 'title': 'Nový projekt'})


@login_required
@manager_required
def project_edit(request, pk):
    project = get_object_or_404(Project, pk=pk)
    
    # Ak nie si Admin a zároveň nie si v tíme, ktorý vlastní tento projekt -> STOP
    if not request.user.is_superuser and (not project.team or request.user not in project.team.members.all()):
        messages.error(request, 'Môžete upravovať iba projekty vášho tímu.')
        return redirect('project_detail', pk=pk)

    if request.method == 'POST':
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            messages.success(request, 'Projekt bol aktualizovaný.')
            return redirect('project_detail', pk=pk)
    else:
        form = ProjectForm(instance=project)
    return render(request, 'projects/project_form.html', {'form': form, 'title': 'Upraviť projekt', 'project': project})


@login_required
@manager_required
def project_delete(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if request.method == 'POST':
        name = project.name
        project.delete()
        messages.success(request, f'Projekt „{name}" bol vymazaný.')
        return redirect('project_list')
    return render(request, 'projects/confirm_delete.html', {'object': project, 'type': 'projekt'})


# ─── Tasks ────────────────────────────────────────────────────────────────────

@login_required
def task_list(request):
    is_manager = request.user.groups.filter(name='manager').exists()
    if is_manager:
        tasks = Task.objects.select_related('project', 'assignee')
    else:
        tasks = Task.objects.filter(
            Q(assignee=request.user) | Q(project__members=request.user)
        ).distinct().select_related('project', 'assignee')

    status_f = request.GET.get('status', '')
    priority_f = request.GET.get('priority', '')
    project_f = request.GET.get('project', '')
    assignee_f = request.GET.get('assignee', '')

    if status_f:
        tasks = tasks.filter(status=status_f)
    if priority_f:
        tasks = tasks.filter(priority=priority_f)
    if project_f:
        tasks = tasks.filter(project_id=project_f)
    if assignee_f:
        tasks = tasks.filter(assignee_id=assignee_f)

    projects = Project.objects.all() if is_manager else Project.objects.filter(members=request.user)
    users = User.objects.all() if is_manager else User.objects.filter(projects__in=projects).distinct()

    return render(request, 'tasks/task_list.html', {
        'tasks': tasks,
        'status_f': status_f,
        'priority_f': priority_f,
        'project_f': project_f,
        'assignee_f': assignee_f,
        'status_choices': Task.STATUS_CHOICES,
        'priority_choices': Task.PRIORITY_CHOICES,
        'projects': projects,
        'users': users,
        'is_manager': is_manager,
    })


@login_required
def task_detail(request, pk):
    is_manager = request.user.groups.filter(name='manager').exists()
    if is_manager:
        task = get_object_or_404(Task, pk=pk)
    else:
        task = get_object_or_404(Task.objects.filter(Q(assignee=request.user) | Q(project__members=request.user)).distinct(), pk=pk)
    return render(request, 'tasks/task_detail.html', {'task': task, 'is_manager': is_manager})


@login_required
@manager_required
def task_create(request, project_pk=None):
    project = get_object_or_404(Project, pk=project_pk) if project_pk else None
    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save()
            messages.success(request, f'Úloha „{task.name}" bola vytvorená.')
            return redirect('project_detail', pk=task.project.pk)
    else:
        initial = {'project': project} if project else {}
        form = TaskForm(initial=initial)
        
    # OPRAVA: Filtrovanie používateľov iba pre daný projekt (platí aj keď project_pk príde z URL)
    if project and 'assignee' in form.fields:
        form.fields['assignee'].queryset = User.objects.filter(projects=project)
            
    # Zmena username na Meno Priezvisko
    if 'assignee' in form.fields:
        form.fields['assignee'].label_from_instance = lambda obj: f"{obj.get_full_name() or obj.username}"
        
    return render(request, 'tasks/task_form.html', {'form': form, 'title': 'Nová úloha', 'project': project})


@login_required
def task_edit(request, pk):
    is_manager = request.user.groups.filter(name='manager').exists()
    task = get_object_or_404(Task, pk=pk)
    if not is_manager and task.assignee != request.user:
        messages.error(request, 'Nemáte oprávnenie upravovať túto úlohu.')
        return redirect('task_list')

    if request.method == 'POST':
        if is_manager:
            form = TaskForm(request.POST, instance=task)
        else:
            from .forms import TaskStatusForm
            form = TaskStatusForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            messages.success(request, 'Úloha bola aktualizovaná.')
            return redirect('task_detail', pk=pk)
    else:
        form = TaskForm(instance=task) if is_manager else __import__('projects.forms', fromlist=['TaskStatusForm']).TaskStatusForm(instance=task)
    
    # KĽÚČOVÁ OPRAVA: Pri editácii vyfiltrujeme ľudí iba z projektu, ktorému táto úloha patrí
    if 'assignee' in form.fields and task.project:
        form.fields['assignee'].queryset = User.objects.filter(projects=task.project)

    # Zmena username na Meno Priezvisko
    if 'assignee' in form.fields:
        form.fields['assignee'].label_from_instance = lambda obj: f"{obj.get_full_name() or obj.username}"
        
    return render(request, 'tasks/task_form.html', {'form': form, 'title': 'Upraviť úlohu', 'task': task, 'is_manager': is_manager})


@login_required
@manager_required
def task_delete(request, pk):
    task = get_object_or_404(Task, pk=pk)
    project_pk = task.project.pk
    if request.method == 'POST':
        name = task.name
        task.delete()
        messages.success(request, f'Úloha „{name}" bola vymazaná.')
        return redirect('project_detail', pk=project_pk)
    return render(request, 'projects/confirm_delete.html', {'object': task, 'type': 'úlohu'})


@login_required
def task_change_status(request, pk):
    task = get_object_or_404(Task, pk=pk)
    is_manager = request.user.groups.filter(name='manager').exists()
    if not is_manager and task.assignee != request.user:
        messages.error(request, 'Nemáte oprávnenie meniť stav tejto úlohy.')
        return redirect('task_list')
    if request.method == 'POST':
        new_status = request.POST.get('status')
        valid = [s[0] for s in Task.STATUS_CHOICES]
        if new_status in valid:
            task.status = new_status
            task.save()
            messages.success(request, 'Stav úlohy bol zmenený.')
    return redirect(request.META.get('HTTP_REFERER', 'task_list'))


# ─── Teams ────────────────────────────────────────────────────────────────────

@login_required
def team_list(request):
    is_manager = request.user.groups.filter(name='manager').exists()
    teams = Team.objects.prefetch_related('members')
    return render(request, 'teams/team_list.html', {'teams': teams, 'is_manager': is_manager})


@login_required
def team_detail(request, pk):
    team = get_object_or_404(Team, pk=pk)
    is_manager = request.user.groups.filter(name='manager').exists()
    return render(request, 'teams/team_detail.html', {'team': team, 'is_manager': is_manager})


@login_required
@manager_required
def team_create(request):
    if request.method == 'POST':
        form = TeamForm(request.POST)
        if form.is_valid():
            team = form.save()
            messages.success(request, f'Tím „{team.name}" bol vytvorený.')
            return redirect('team_detail', pk=team.pk)
    else:
        form = TeamForm()
    return render(request, 'teams/team_form.html', {'form': form, 'title': 'Nový tím'})


@login_required
@manager_required
def team_edit(request, pk):
    team = get_object_or_404(Team, pk=pk)
    if request.method == 'POST':
        form = TeamForm(request.POST, instance=team)
        if form.is_valid():
            form.save()
            messages.success(request, 'Tím bol aktualizovaný.')
            return redirect('team_detail', pk=pk)
    else:
        form = TeamForm(instance=team)
    return render(request, 'teams/team_form.html', {'form': form, 'title': 'Upraviť tím', 'team': team})


@login_required
@manager_required
def team_delete(request, pk):
    team = get_object_or_404(Team, pk=pk)
    if request.method == 'POST':
        name = team.name
        team.delete()
        messages.success(request, f'Tím „{name}" bol vymazaný.')
        return redirect('team_list')
    return render(request, 'projects/confirm_delete.html', {'object': team, 'type': 'tím'})


# ─── Memberships ──────────────────────────────────────────────────────────────

@login_required
@manager_required
def membership_add(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if request.method == 'POST':
        form = MembershipForm(request.POST)
        if form.is_valid():
            membership = form.save(commit=False)
            membership.project = project
            try:
                membership.save()
                full_name = membership.user.get_full_name() or membership.user.username
                messages.success(request, f'{full_name} bol pridaný do projektu.')
            except Exception:
                messages.error(request, 'Tento používateľ je už členom projektu.')
            return redirect('project_detail', pk=project_pk)
    else:
        form = MembershipForm()
        existing = project.members.all()
        form.fields['user'].queryset = User.objects.exclude(pk__in=existing)
        
    # OPRAVA: Zmena na Meno Priezvisko pri pridávaní člena do projektu
    if 'user' in form.fields:
        form.fields['user'].label_from_instance = lambda obj: f"{obj.get_full_name() or obj.username}"
        
    return render(request, 'projects/membership_form.html', {'form': form, 'project': project})


@login_required
@manager_required
def membership_remove(request, project_pk, user_pk):
    membership = get_object_or_404(Membership, project_id=project_pk, user_id=user_pk)
    if request.method == 'POST':
        membership.delete()
        messages.success(request, 'Člen bol odstránený z projektu.')
    return redirect('project_detail', pk=project_pk)


# ─── API ──────────────────────────────────────────────────────────────────────

@login_required
def api_tasks(request):
    is_manager = request.user.groups.filter(name='manager').exists()
    if is_manager:
        tasks = Task.objects.select_related('project', 'assignee')
    else:
        tasks = Task.objects.filter(
            Q(assignee=request.user) | Q(project__members=request.user)
        ).distinct().select_related('project', 'assignee')

    status_f = request.GET.get('status', '')
    priority_f = request.GET.get('priority', '')
    project_f = request.GET.get('project', '')
    assignee_f = request.GET.get('assignee', '')

    if status_f:
        tasks = tasks.filter(status=status_f)
    if priority_f:
        tasks = tasks.filter(priority=priority_f)
    if project_f:
        tasks = tasks.filter(project_id=project_f)
    if assignee_f:
        tasks = tasks.filter(assignee_id=assignee_f)

    data = []
    for t in tasks:
        data.append({
            'id': t.pk,
            'name': t.name,
            'description': t.description,
            'priority': t.priority,
            'status': t.status,
            'deadline': str(t.deadline) if t.deadline else None,
            'project': {'id': t.project.pk, 'name': p.project.name},
            'assignee': {'id': t.assignee.pk, 'username': t.assignee.username} if t.assignee else None,
        })
    return JsonResponse({'count': len(data), 'results': data})


# ─── User Create / List / Edit / Delete ──────────────────────────────────────

@login_required
@manager_required
def user_create(request):
    from .forms import UserCreateForm
    if request.method == 'POST':
        form = UserCreateForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f'Používateľ „{user.username}" bol vytvorený.')
            return redirect('user_list')
    else:
        form = UserCreateForm()
    return render(request, 'registration/user_create.html', {'form': form})


@login_required
@manager_required
def user_list(request):
    query = request.GET.get('search', '').strip()
    order_by = request.GET.get('order_by', 'last_name')
    
    # Pre-fetchovanie skupín, tímov a projektov pre efektivitu
    users = User.objects.all().prefetch_related('groups', 'teams', 'projects')
    
    # Výpočet vyťaženosti (workloadu) pre každého používateľa
    PRIORITY_WEIGHT = {'low': 1, 'medium': 2, 'high': 3, 'critical': 5}
    user_workloads = {}
    
    # Predpočítame skóre z otvorených úloh
    for u in users:
        u.is_manager = u.groups.filter(name='manager').exists()
        
        user_tasks = Task.objects.filter(assignee=u).exclude(status='done')
        score = sum(PRIORITY_WEIGHT.get(t.priority, 1) for t in user_tasks)
        user_workloads[u.pk] = score
        u.workload_score = score

    if query:
        users = users.annotate(
            full_name_space=Concat('first_name', Value(' '), 'last_name'),
            full_name_reverse=Concat('last_name', Value(' '), 'first_name')
        ).filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(username__icontains=query) |
            Q(full_name_space__icontains=query) |
            Q(full_name_reverse__icontains=query)
        )
        
    users_list = list(users)
    
    # Priradenie farieb a percent podľa maximálneho skóre v systéme
    max_score = max(user_workloads.values(), default=1) or 1
    for u in users_list:
        u.workload_percent = round((user_workloads.get(u.pk, 0) / max_score) * 100)
        u.workload_color = 'success' if u.workload_percent < 30 else ('warning' if u.workload_percent < 65 else 'danger')
    
    # Radenie zoznamu
    if order_by == 'first_name':
        users_list.sort(key=lambda x: (x.first_name.lower(), x.last_name.lower(), x.username.lower()))
    elif order_by == '-first_name':
        users_list.sort(key=lambda x: (x.first_name.lower(), x.last_name.lower(), x.username.lower()), reverse=True)
    elif order_by == 'last_name':
        users_list.sort(key=lambda x: (x.last_name.lower(), x.first_name.lower(), x.username.lower()))
    elif order_by == '-last_name':
        users_list.sort(key=lambda x: (x.last_name.lower(), x.first_name.lower(), x.username.lower()), reverse=True)
    elif order_by == 'role':
        users_list.sort(key=lambda x: (not x.is_manager, x.last_name.lower()))
    elif order_by == '-role':
        users_list.sort(key=lambda x: (x.is_manager, x.last_name.lower()))
    elif order_by == 'workload':
        users_list.sort(key=lambda x: (x.workload_score, x.last_name.lower()))
    elif order_by == '-workload':
        users_list.sort(key=lambda x: (x.workload_score, x.last_name.lower()), reverse=True)
    else:
        users_list.sort(key=lambda x: (x.last_name.lower(), x.first_name.lower()))

    return render(request, 'registration/user_list.html', {
        'users': users_list,
        'search_query': query,
        'current_order': order_by
    })


@login_required
@manager_required
def user_edit(request, pk):
    edit_user = get_object_or_404(User, pk=pk)
    
    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=edit_user)
        formset = MembershipFormSet(request.POST, instance=edit_user)
        
        if form.is_valid() and formset.is_valid():
            user = form.save()
            formset.save()
            
            # Nastavenie/Odstránenie zo skupiny manager podľa zaškrtávacieho poľa vo formulári
            manager_group, created = Group.objects.get_or_create(name='manager')
            if form.cleaned_data.get('is_manager'):
                user.groups.add(manager_group)
            else:
                user.groups.remove(manager_group)
                
            messages.success(request, f'Používateľ {edit_user.get_full_name() or edit_user.username} bol úspešne upravený.')
            
            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)
                
            return redirect('user_list')
    else:
        # Predvyplnenie políčka is_manager na základe reálneho stavu v databáze
        is_manager_status = edit_user.groups.filter(name='manager').exists()
        form = UserEditForm(instance=edit_user, initial={'is_manager': is_manager_status})
        formset = MembershipFormSet(instance=edit_user)
        
    return render(request, 'registration/user_edit.html', {
        'form': form,
        'formset': formset,
        'profile_user': edit_user,
        'title': 'Upraviť používateľa'
    })


@login_required
@manager_required
def user_delete(request, pk):
    profile_user = get_object_or_404(User, pk=pk)
    if profile_user == request.user:
        messages.error(request, 'Nemôžete vymazať vlastný účet.')
        return redirect('user_list')
    if request.method == 'POST':
        username = profile_user.username
        profile_user.delete()
        messages.success(request, f'Používateľ „{username}" bol vymazaný.')
        return redirect('user_list')
    return render(request, 'projects/confirm_delete.html', {'object': profile_user, 'type': 'používateľa'})


# ─── Calendar ─────────────────────────────────────────────────────────────────

@login_required
def calendar_view(request):
    import json
    from datetime import date
    is_manager = request.user.groups.filter(name='manager').exists()

    if is_manager:
        projects = Project.objects.exclude(deadline__isnull=True)
        tasks = Task.objects.exclude(deadline__isnull=True)
    else:
        projects = Project.objects.filter(members=request.user).exclude(deadline__isnull=True)
        tasks = Task.objects.filter(
            Q(assignee=request.user) | Q(project__members=request.user)
        ).distinct().exclude(deadline__isnull=True)

    from .holidays import get_slovak_holidays
    
    events = []
    current_year = date.today().year
    for y in [current_year - 1, current_year, current_year + 1]:
        sk_holidays = get_slovak_holidays(y)
        for h_date, h_name in sk_holidays.items():
            events.append({
                'title': h_name,
                'date': str(h_date),
                'type': 'holiday',
                'url': '#',
            })

    for p in projects:
        events.append({
            'title': p.name,
            'date': str(p.deadline),
            'type': 'project',
            'status': p.status,
            'url': f'/projects/{p.pk}/',
        })
    for t in tasks:
        events.append({
            'title': t.name,
            'date': str(t.deadline),
            'type': 'task',
            'priority': t.priority,
            'status': t.status,
            'url': f'/tasks/{t.pk}/',
        })

    return render(request, 'projects/calendar.html', {
        'events_json': json.dumps(events),
        'is_manager': is_manager,
        'days': ['Po', 'Ut', 'St', 'Št', 'Pi', 'So', 'Ne'],  
    })


# ─── User Detail ──────────────────────────────────────────────────────────────

@login_required
@manager_required
def user_detail(request, pk):
    import json
    from datetime import timedelta
    from django.utils import timezone

    profile_user = get_object_or_404(User, pk=pk)
    all_tasks = Task.objects.filter(assignee=profile_user).select_related('project').order_by('deadline')

    PRIORITY_WEIGHT = {'low': 1, 'medium': 2, 'high': 3, 'critical': 5}

    by_status = {s: 0 for s, _ in Task.STATUS_CHOICES}
    by_priority = {'low': 0, 'medium': 0, 'high': 0, 'critical': 0}
    score = 0
    for t in all_tasks:
        by_status[t.status] = by_status.get(t.status, 0) + 1
        by_priority[t.priority] = by_priority.get(t.priority, 0) + 1
        if t.status != 'done':
            score += PRIORITY_WEIGHT.get(t.priority, 1)

    now = timezone.now().date()
    weeks = []
    for i in range(7, -1, -1):
        week_start = now - timedelta(days=now.weekday()) - timedelta(weeks=i)
        week_end = week_start + timedelta(days=6)
        count = all_tasks.filter(status='done', deadline__gte=week_start, deadline__lte=week_end).count()
        weeks.append({'label': week_start.strftime('%d.%m'), 'count': count})

    projects = Project.objects.filter(members=profile_user).distinct()

    context = {
        'profile_user': profile_user,
        'all_tasks': all_tasks,
        'by_status': by_status,
        'by_priority': by_priority,
        'score': score,
        'projects': projects,
        'weeks_json': json.dumps(weeks),
        'total': all_tasks.count(),
        'done': by_status.get('done', 0),
        'open': all_tasks.exclude(status='done').count(),
    }
    return render(request, 'projects/user_detail.html', context)
