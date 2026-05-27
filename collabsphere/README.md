# CollabSphere

Django webová aplikácia na správu projektov, členov tímu a úloh.

## Rýchly štart

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS

pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Aplikácia beží na http://127.0.0.1:8000

## Funkcionality

- **CRUD** pre Project, Task, Team
- **Autentifikácia** cez Django auth
- **Roly**: `manager` (plný prístup) a `team_member` (čítanie + zmena stavu vlastných úloh)
- **M:N vzťah** User ↔ Project cez model `Membership`
- **Filtrovanie** úloh a projektov podľa stavu, priority, projektu, riešiteľa
- **JSON API** na `/api/tasks/` s podporou filtrovania

## Modely

| Model | Popis |
|-------|-------|
| `Team` | Tím s členmi (M:N User) |
| `Project` | Projekt s tímom, stavom a termínom |
| `Membership` | M:N vzťah User ↔ Project s rolou |
| `Task` | Úloha s prioritou, stavom a riešiteľom |

## API

```
GET /api/tasks/
GET /api/tasks/?status=todo&priority=high&project=1&assignee=2
```

## Nasadenie na Render

1. Push do Git repozitára
2. Nový **Web Service** z Git repo
3. Build command: `./build.sh`
4. Start command: `gunicorn config.wsgi`
5. Premenné prostredia:
   - `DJANGO_SECRET_KEY`
   - `DJANGO_DEBUG=false`
   - `DJANGO_ALLOWED_HOSTS=vasa-app.onrender.com`
   - `DJANGO_CSRF_TRUSTED_ORIGINS=https://vasa-app.onrender.com`

## Testy

```bash
python manage.py test
```
