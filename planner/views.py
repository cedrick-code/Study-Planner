from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import SignUpForm, StudyTaskForm
from .models import StudyTask


def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = SignUpForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect('dashboard')
    return render(request, 'registration/register.html', {'form': form})


@login_required
def dashboard(request):
    tasks = StudyTask.objects.filter(user=request.user)
    today = timezone.localdate()
    context = {
        'tasks': tasks,
        'total_count': tasks.count(),
        'completed_count': tasks.filter(completed=True).count(),
        'today_count': tasks.filter(due_date=today, completed=False).count(),
    }
    return render(request, 'planner/dashboard.html', context)


@login_required
def task_create(request):
    form = StudyTaskForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        task = form.save(commit=False)
        task.user = request.user
        task.save()
        messages.success(request, 'Study task added.')
        return redirect('dashboard')
    return render(request, 'planner/task_form.html', {'form': form, 'heading': 'Add a study task'})


@login_required
def task_update(request, pk):
    task = get_object_or_404(StudyTask, pk=pk, user=request.user)
    form = StudyTaskForm(request.POST or None, instance=task)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Study task updated.')
        return redirect('dashboard')
    return render(request, 'planner/task_form.html', {'form': form, 'heading': 'Edit study task'})


@login_required
def task_delete(request, pk):
    task = get_object_or_404(StudyTask, pk=pk, user=request.user)
    if request.method == 'POST':
        task.delete()
        messages.success(request, 'Study task deleted.')
        return redirect('dashboard')
    return render(request, 'planner/task_confirm_delete.html', {'task': task})


def is_admin(user):
    return user.is_staff


@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    tasks = StudyTask.objects.select_related('user')
    return render(request, 'planner/admin_dashboard.html', {
        'user_count': StudyTask.objects.values('user_id').distinct().count(),
        'task_count': tasks.count(),
        'completed_count': tasks.filter(completed=True).count(),
        'recent_tasks': tasks.order_by('-created_at')[:10],
    })
