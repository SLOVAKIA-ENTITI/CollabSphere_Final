from django.test import TestCase, Client
from django.contrib.auth.models import User, Group
from django.urls import reverse
from .models import Team, Project, Membership, Task


def make_manager(username='manager_user', password='pass123'):
    user = User.objects.create_user(username=username, password=password)
    group, _ = Group.objects.get_or_create(name='manager')
    user.groups.add(group)
    return user


def make_member(username='member_user', password='pass123'):
    user = User.objects.create_user(username=username, password=password)
    group, _ = Group.objects.get_or_create(name='team_member')
    user.groups.add(group)
    return user


class ModelTests(TestCase):
    def test_team_str(self):
        team = Team.objects.create(name='Backend')
        self.assertEqual(str(team), 'Backend')

    def test_project_str(self):
        project = Project.objects.create(name='Alpha', status='active')
        self.assertEqual(str(project), 'Alpha')

    def test_membership_str(self):
        user = User.objects.create_user(username='jan')
        project = Project.objects.create(name='Beta')
        m = Membership.objects.create(user=user, project=project, role='developer')
        self.assertIn('jan', str(m))
        self.assertIn('Beta', str(m))

    def test_task_str(self):
        project = Project.objects.create(name='Gamma')
        task = Task.objects.create(name='Fix bug', project=project)
        self.assertEqual(str(task), 'Fix bug')


class ViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.manager = make_manager()
        self.member = make_member()
        self.project = Project.objects.create(name='Test Project', status='active')
        Membership.objects.create(user=self.manager, project=self.project, role='manager')
        Membership.objects.create(user=self.member, project=self.project, role='developer')
        self.task = Task.objects.create(
            name='Test Task', project=self.project,
            assignee=self.member, status='todo', priority='medium'
        )

    def test_redirect_unauthenticated(self):
        resp = self.client.get(reverse('dashboard'))
        self.assertRedirects(resp, '/login/?next=/')

    def test_dashboard_manager(self):
        self.client.login(username='manager_user', password='pass123')
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 200)

    def test_dashboard_member(self):
        self.client.login(username='member_user', password='pass123')
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 200)

    def test_project_list(self):
        self.client.login(username='manager_user', password='pass123')
        resp = self.client.get(reverse('project_list'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Test Project')

    def test_project_create_manager(self):
        self.client.login(username='manager_user', password='pass123')
        resp = self.client.post(reverse('project_create'), {
            'name': 'New Project', 'status': 'planning',
        })
        self.assertEqual(Project.objects.filter(name='New Project').count(), 1)

    def test_project_create_member_forbidden(self):
        self.client.login(username='member_user', password='pass123')
        resp = self.client.get(reverse('project_create'))
        self.assertRedirects(resp, reverse('dashboard'))

    def test_task_list(self):
        self.client.login(username='manager_user', password='pass123')
        resp = self.client.get(reverse('task_list'))
        self.assertEqual(resp.status_code, 200)

    def test_task_filter_by_status(self):
        self.client.login(username='manager_user', password='pass123')
        resp = self.client.get(reverse('task_list') + '?status=todo')
        self.assertContains(resp, 'Test Task')

    def test_member_can_change_own_task_status(self):
        self.client.login(username='member_user', password='pass123')
        resp = self.client.post(
            reverse('task_change_status', args=[self.task.pk]),
            {'status': 'in_progress'}
        )
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, 'in_progress')

    def test_api_tasks_json(self):
        self.client.login(username='manager_user', password='pass123')
        resp = self.client.get('/api/tasks/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('results', data)
        self.assertIn('count', data)

    def test_api_tasks_filter(self):
        self.client.login(username='manager_user', password='pass123')
        resp = self.client.get(f'/api/tasks/?status=todo')
        data = resp.json()
        self.assertTrue(all(t['status'] == 'todo' for t in data['results']))

    def test_team_crud_manager(self):
        self.client.login(username='manager_user', password='pass123')
        resp = self.client.post(reverse('team_create'), {'name': 'Dev Team', 'description': ''})
        self.assertEqual(Team.objects.filter(name='Dev Team').count(), 1)

    def test_membership_add(self):
        new_user = User.objects.create_user(username='new_dev', password='pass123')
        self.client.login(username='manager_user', password='pass123')
        resp = self.client.post(
            reverse('membership_add', args=[self.project.pk]),
            {'user': new_user.pk, 'role': 'developer'}
        )
        self.assertTrue(Membership.objects.filter(user=new_user, project=self.project).exists())
