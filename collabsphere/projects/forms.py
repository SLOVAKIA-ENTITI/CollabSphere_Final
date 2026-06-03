from django import forms
from django.contrib.auth.models import User, Group
from .models import Project, Task, Team, Membership


class UserCreateForm(forms.ModelForm):
    password1 = forms.CharField(label='Heslo', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Potvrdenie hesla', widget=forms.PasswordInput)
    role = forms.ChoiceField(
        label='Rola',
        choices=[('', 'Člen tímu'), ('manager', 'Manažér')],
        required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name == 'role':
                field.required = False  # Rolu explicitne necháme nepovinnú
            else:
                field.required = True   # Všetko ostatné bude povinné

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']
        labels = {
            'username': 'Používateľské meno',
            'first_name': 'Meno',
            'last_name': 'Priezvisko',
            'email': 'E-mail',
        }

    def clean_password2(self):
        p1 = self.cleaned_data.get('password1')
        p2 = self.cleaned_data.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('Heslá sa nezhodujú.')
        return p2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
            role = self.cleaned_data.get('role')
            if role == 'manager':
                group, _ = Group.objects.get_or_create(name='manager')
                user.groups.add(group)
        return user


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['name', 'description', 'deadline', 'status', 'team']
        widgets = {
            'deadline': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_deadline(self):
        deadline = self.cleaned_data.get('deadline')
        if deadline:
            from .holidays import get_slovak_holidays
            holidays = get_slovak_holidays(deadline.year)
            if deadline in holidays:
                # We don't block it, but we can add a warning or just keep it as info
                # For now, let's just allow it but maybe the user wants a strict check?
                # Let's just keep it as is, or add a note.
                pass
        return deadline


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['name', 'description', 'priority', 'deadline', 'status', 'project', 'assignee']
        widgets = {
            'deadline': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        deadline = cleaned_data.get('deadline')
        project = cleaned_data.get('project')
        
        if deadline and project and project.deadline:
            if deadline > project.deadline:
                self.add_error('deadline', f'Termín úlohy nemôže byť neskorší ako termín projektu ({project.deadline}).')
        
        return cleaned_data


class TaskStatusForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['status']


class TeamForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ['name', 'description', 'members']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'members': forms.CheckboxSelectMultiple(),
        }


class MembershipForm(forms.ModelForm):
    class Meta:
        model = Membership
        fields = ['user', 'role']
