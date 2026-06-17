from django import forms
from django.contrib.auth.models import User, Group
from .models import Project, Task, Team, Membership

class UserCreateForm(forms.ModelForm):
    password1 = forms.CharField(label='Heslo', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Potvrdenie hesla', widget=forms.PasswordInput)
    
    role = forms.ChoiceField(
        label='Rola',
        choices=[('member', 'Člen tímu'), ('manager', 'Manažér')],
        required=True
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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
        
        widgets = {
            'deadline': forms.DateInput(
                format='%Y-%m-%d',
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
    # Pridali sme možnosť 'admin' priamo do výberu rolí
    role = forms.ChoiceField(
        label='Rola',
        choices=[
            ('member', 'Člen tímu'), 
            ('manager', 'Manažér'), 
            ('admin', 'Administrátor (Superuser)')
        ],
        required=True
    )

    # Nové pole na overenie tvojho hesla admina
    admin_password_confirm = forms.CharField(
        label='Vaše administrátorské heslo',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Vyžadované len pri zmene Admin statusu'
        }),
        required=False,
        help_text="Zadajte SVOJE heslo pre potvrdenie udelenia alebo odobratia práv Administrátora."
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
            # Určenie počiatočnej hodnoty roly podľa stavu v DB
            if self.instance.is_superuser:
                self.fields['role'].initial = 'admin'
            elif self.instance.groups.filter(name='manager').exists():
                self.fields['role'].initial = 'manager'
            else:
                self.fields['role'].initial = 'member'

    def save(self, commit=True):
        # Priame spracovanie ukladania (skupiny a superuser príznaky) riešime vo view
        return super().save(commit=commit)


# Formset pre správu rolí používateľa v projektoch priamo v jeho editácii
MembershipFormSet = forms.inlineformset_factory(
    User, 
    Membership,
    fields=('project', 'role'),
    extra=1,
    can_delete=True,
    widgets={
        'project': forms.Select(attrs={'class': 'form-select form-select-sm'}),
        'role': forms.Select(attrs={'class': 'form-select form-select-sm'}),
    }
)
