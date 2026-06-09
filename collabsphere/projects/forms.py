from django import forms
from django.contrib.auth.models import User, Group
from .models import Project, Task, Team, Membership
from django import forms
from django.contrib.auth.models import User
from .models import Project
from django import forms
from django.contrib.auth.models import User
from .models import Membership, Project

class UserCreateForm(forms.ModelForm):
    password1 = forms.CharField(label='Heslo', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Potvrdenie hesla', widget=forms.PasswordInput)
    
    # Zmenili sme prázdny reťazec '' na 'member'
    role = forms.ChoiceField(
        label='Rola',
        choices=[('member', 'Člen tímu'), ('manager', 'Manažér')],
        required=True # Pokojne môže byť True, keďže 'member' je platná hodnota
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Tento cyklus teraz bezpečne hodí 'required' na úplne všetky polia
        for field_name, field in self.fields.items():
            field.required = True

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
            # Ak je manažér, pridá ho do skupiny manažérov, inak zostane bežným členom
            if role == 'manager':
                group, _ = Group.objects.get_or_create(name='manager')
                user.groups.add(group)
        return user

class ProjectForm(forms.ModelForm):
    external_members = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        required=False,
        label="Externí riešitelia",
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )

    class Meta:
        model = Project
        fields = ['name', 'team', 'description', 'deadline', 'status'] 
        
        # Pridáme definíciu widgetu pre deadline, aby rešpektoval formát a zobrazil HTML5 kalendár
        widgets = {
            'deadline': forms.DateInput(
                format='%Y-%m-%d', # Django vnútorne pre input type="date" potrebuje tento formát
                attrs={
                    'type': 'date',
                    'class': 'form-control'
                }
            ),
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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['members'].queryset = User.objects.all().order_by('last_name', 'first_name', 'username')
        self.fields['members'].label_from_instance = lambda u: (
            f"{u.last_name} {u.first_name}".strip() or u.username
        )

    class Meta:
        model = Team
        fields = ['name', 'description', 'members']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'members': forms.CheckboxSelectMultiple(),
        }


class MembershipForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['user'].queryset = User.objects.all().order_by('last_name', 'first_name', 'username')
        self.fields['user'].label_from_instance = lambda u: (
            f"{u.last_name} {u.first_name}".strip() or u.username
        )

    class Meta:
        model = Membership
        fields = ['user', 'role']


class UserEditForm(forms.ModelForm):
    role = forms.ChoiceField(
        label='Rola',
        choices=[('member', 'Člen tímu'), ('manager', 'Manažér')],
        required=True
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']
        labels = {
            'username': 'Používateľské meno',
            'first_name': 'Meno',
            'last_name': 'Priezvisko',
            'email': 'E-mail',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            is_manager = self.instance.groups.filter(name='manager').exists()
            self.fields['role'].initial = 'manager' if is_manager else 'member'

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            from django.contrib.auth.models import Group
            role = self.cleaned_data.get('role')
            manager_group, _ = Group.objects.get_or_create(name='manager')
            if role == 'manager':
                user.groups.add(manager_group)
            else:
                user.groups.remove(manager_group)
        return user



# Formset pre správu rolí používateľa v projektoch priamo v jeho editácii
MembershipFormSet = forms.inlineformset_factory(
    User, 
    Membership,
    fields=('project', 'role'),
    extra=1, # Koľko prázdnych riadkov pre pridanie nového projektu sa zobrazí
    can_delete=True,
    widgets={
        'project': forms.Select(attrs={'class': 'form-select form-select-sm'}),
        'role': forms.Select(attrs={'class': 'form-select form-select-sm'}),
    }
)
