# Daily Study Planner

A Django web app for students to organize study tasks. Students can register and manage their own tasks; staff users have an activity summary and Django admin access.

## Run locally

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open http://127.0.0.1:8000/. Create a student account from the registration page. Sign in with the superuser account to access the admin summary and `/admin/`.

## Initial features

- Django registration, login, logout, and password change
- User-owned study task create, read, update, and delete
- Student dashboard with task counts
- Staff-only activity summary and Django admin task management
- SQLite database for local development

## Planned API integrations

- Open-Meteo for weather
- Quotable for a motivational quote
- Free Dictionary API for definitions
- LibreTranslate for translation
- JSONPlaceholder for sample study tips

API integrations will be added in a later development step. JSONPlaceholder returns demonstration data, so it will be labeled as sample tips.
