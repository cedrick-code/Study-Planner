from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render

from .forms import RegisterForm, TaskForm
from .models import Task


def is_admin(user):
    return user.is_authenticated and (
        user.is_staff or getattr(user.profile, "role", "") == "admin"
    )


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Welcome! Your account is ready.")
        return redirect("dashboard")
    return render(request, "registration/register.html", {"form": form})


@login_required
def dashboard(request):
    tasks = Task.objects.filter(user=request.user)
    return render(request, "planner/dashboard.html", {"tasks": tasks})


@login_required
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
def task_update(request, pk):
    task = get_object_or_404(Task, pk=pk, user=request.user)
    form = TaskForm(request.POST or None, instance=task)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Task updated.")
        return redirect("dashboard")
    return render(request, "planner/task_form.html", {"form": form, "heading": "Edit task"})


@login_required
def task_delete(request, pk):
    task = get_object_or_404(Task, pk=pk, user=request.user)
    if request.method == "POST":
        task.delete()
        messages.success(request, "Task deleted.")
        return redirect("dashboard")
    return render(request, "planner/task_confirm_delete.html", {"task": task})


@user_passes_test(is_admin, login_url="dashboard")
def admin_dashboard(request):
    context = {
        "total_tasks": Task.objects.count(),
        "completed_tasks": Task.objects.filter(is_complete=True).count(),
        "total_users": User.objects.count(),
        "recent_tasks": Task.objects.select_related("user").order_by("-created_at")[:10],
    }
    return render(request, "planner/admin_dashboard.html", context)