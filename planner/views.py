from functools import wraps

from django.contrib import messages
from django.contrib.auth import login, logout
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from .services import get_weather

from .forms import RegisterForm, TaskForm
from .models import Task


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

    tasks = Task.objects.filter(user=request.user)
    today = timezone.localdate()
    context = {
        "tasks": tasks,
        "today_tasks": tasks.filter(due_date=today, is_complete=False),
        "total": tasks.count(),
        "done": tasks.filter(is_complete=True).count(),
        "pending": tasks.filter(is_complete=False).count(),
        "city": city,
        "weather": get_weather(city),
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
        return redirect("dashboard")
    return render(request, "planner/task_form.html", {"form": form, "heading": "Add task"})


@login_required
@student_only
def task_update(request, pk):
    task = get_object_or_404(Task, pk=pk, user=request.user)
    form = TaskForm(request.POST or None, instance=task)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Task updated.")
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


# ---------- Admin page ----------

@login_required
@user_passes_test(is_admin, login_url="dashboard")
def admin_dashboard(request):
    context = {
        "total_tasks": Task.objects.count(),
        "completed_tasks": Task.objects.filter(is_complete=True).count(),
        "total_users": User.objects.count(),
        "recent_tasks": Task.objects.select_related("user").order_by("-created_at")[:10],
    }
    return render(request, "planner/admin_dashboard.html", context)