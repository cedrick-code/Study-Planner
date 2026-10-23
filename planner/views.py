from datetime import date
from functools import wraps

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import LocalHolidayForm, RegisterForm, TaskForm
from .models import LocalHoliday, Task
from .services import (
    get_definition,
    get_holidays,
    get_quote,
    get_topic,
    get_weather,
    holiday_on,
)


# ---------- Role helpers (must stay above the views) ----------

def is_admin(user):
    return user.is_authenticated and (
        user.is_staff or getattr(user.profile, "role", "") == "admin"
    )


def student_only(view):
    """Send admins to their summary page instead of the student pages."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if is_admin(request.user):
            return redirect("admin_dashboard")
        return view(request, *args, **kwargs)
    return wrapper


def admin_only(view):
    """Only admins may open the page; students are sent to their dashboard."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not is_admin(request.user):
            return redirect("dashboard")
        return view(request, *args, **kwargs)
    return wrapper


# ---------- Auth ----------

def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(
            request, "Registration successful! Please log in with your new account."
        )
        return redirect("login")
    return render(request, "registration/register.html", {"form": form})


@require_POST
def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect("login")


# ---------- Student pages ----------

@login_required
@student_only
def dashboard(request):
    # Remember the city the student chose; default to Iligan
    city = request.GET.get("city", "").strip()
    if city:
        request.session["city"] = city
    city = request.session.get("city", "Iligan")

    # Word lookup is not saved anywhere; it only lives in this request
    word = request.GET.get("word", "").strip()

    qs = Task.objects.filter(user=request.user)
    today = timezone.localdate()

    # Holidays for this year and next, matched against each task's due date
    holidays = get_holidays(date(today.year, 1, 1), date(today.year + 1, 12, 31))
    by_date = {}
    for h in holidays["items"]:
        by_date.setdefault(h["date"], []).append(h["name"])

    task_list = list(qs)
    for task in task_list:
        task.holiday = " / ".join(by_date.get(task.due_date, []))

    context = {
        "tasks": task_list,
        "today_tasks": qs.filter(due_date=today, is_complete=False),
        "total": qs.count(),
        "done": qs.filter(is_complete=True).count(),
        "pending": qs.filter(is_complete=False).count(),
        "city": city,
        "weather": get_weather(city),
        "quote": get_quote(request.user),
        "word": word,
        "definition": get_definition(word) if word else None,
        "upcoming": [h for h in holidays["items"] if h["date"] >= today][:5],
        "holiday_sources": holidays["sources"],
        "holiday_failed": holidays["failed"],
    }
    return render(request, "planner/dashboard.html", context)


@login_required
@student_only
def task_create(request):
    form = TaskForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        task = form.save(commit=False)
        task.user = request.user
        task.save()
        messages.success(request, "Task added.")
        holiday = holiday_on(task.due_date)
        if holiday:
            messages.warning(request, f"Heads up: {task.due_date:%B %d, %Y} is {holiday}.")
        return redirect("dashboard")
    return render(request, "planner/task_form.html", {"form": form, "heading": "Add task"})


@login_required
@student_only
def task_update(request, pk):
    task = get_object_or_404(Task, pk=pk, user=request.user)
    form = TaskForm(request.POST or None, instance=task)
    if request.method == "POST" and form.is_valid():
        task = form.save()
        messages.success(request, "Task updated.")
        holiday = holiday_on(task.due_date)
        if holiday:
            messages.warning(request, f"Heads up: {task.due_date:%B %d, %Y} is {holiday}.")
        return redirect("dashboard")
    return render(request, "planner/task_form.html", {"form": form, "heading": "Edit task"})


@login_required
@student_only
def task_delete(request, pk):
    task = get_object_or_404(Task, pk=pk, user=request.user)
    if request.method == "POST":
        task.delete()
        messages.success(request, "Task deleted.")
        return redirect("dashboard")
    return render(request, "planner/task_confirm_delete.html", {"task": task})


@login_required
@student_only
def task_topic(request, pk):
    # Only the owner can open this; anyone else gets a 404
    task = get_object_or_404(Task, pk=pk, user=request.user)
    query = request.GET.get("q", "").strip() or task.title
    return render(
        request,
        "planner/task_topic.html",
        {"task": task, "query": query, "topic": get_topic(query)},
    )


# ---------- Admin: summary ----------

@login_required
@admin_only
def admin_dashboard(request):
    context = {
        "total_tasks": Task.objects.count(),
        "completed_tasks": Task.objects.filter(is_complete=True).count(),
        "total_users": User.objects.count(),
        "recent_tasks": Task.objects.select_related("user").order_by("-created_at")[:10],
    }
    return render(request, "planner/admin_dashboard.html", context)


# ---------- Admin: Iligan holidays (full CRUD) ----------

@login_required
@admin_only
def holiday_list(request):
    holidays = LocalHoliday.objects.order_by("-date")
    return render(request, "planner/holiday_list.html", {"holidays": holidays})


@login_required
@admin_only
def holiday_create(request):
    form = LocalHolidayForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Holiday added.")
        return redirect("holiday_list")
    return render(
        request, "planner/holiday_form.html", {"form": form, "heading": "Add Iligan holiday"}
    )


@login_required
@admin_only
def holiday_update(request, pk):
    holiday = get_object_or_404(LocalHoliday, pk=pk)
    form = LocalHolidayForm(request.POST or None, instance=holiday)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Holiday updated.")
        return redirect("holiday_list")
    return render(
        request, "planner/holiday_form.html", {"form": form, "heading": "Edit Iligan holiday"}
    )


@login_required
@admin_only
@require_POST
def holiday_delete(request, pk):
    get_object_or_404(LocalHoliday, pk=pk).delete()
    messages.success(request, "Holiday deleted.")
    return redirect("holiday_list")


# ---------- Admin: manage records ----------

@login_required
@admin_only
def manage_records(request):
    users = (
        User.objects.select_related("profile")
        .annotate(task_count=Count("tasks"))
        .order_by("-date_joined")
    )
    tasks = Task.objects.select_related("user").order_by("-created_at")[:100]
    return render(request, "planner/manage_records.html", {"users": users, "tasks": tasks})


@login_required
@admin_only
@require_POST
def user_toggle_role(request, pk):
    target = get_object_or_404(User, pk=pk)
    if target == request.user:
        messages.error(request, "You cannot change your own role.")
        return redirect("manage_records")

    make_admin = not is_admin(target)
    target.is_staff = make_admin
    if not make_admin:
        target.is_superuser = False
    target.save()
    target.profile.role = "admin" if make_admin else "student"
    target.profile.save()

    messages.success(
        request, f"{target.username} is now {'an admin' if make_admin else 'a student'}."
    )
    return redirect("manage_records")


@login_required
@admin_only
@require_POST
def user_delete(request, pk):
    target = get_object_or_404(User, pk=pk)
    if target == request.user:
        messages.error(request, "You cannot delete your own account.")
    else:
        target.delete()
        messages.success(request, f"User {target.username} and their tasks were deleted.")
    return redirect("manage_records")


@login_required
@admin_only
@require_POST
def record_task_delete(request, pk):
    get_object_or_404(Task, pk=pk).delete()
    messages.success(request, "Task deleted.")
    return redirect("manage_records")