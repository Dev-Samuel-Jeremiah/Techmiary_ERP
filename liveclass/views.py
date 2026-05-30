# liveclass/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from classroom.models import Course
from .models import LiveClass, LiveClassAttendance, LiveClassMessage


@login_required
def teacher_live_classes(request, course_id):
    course = get_object_or_404(Course, id=course_id, teacher=request.user)
    live_classes = LiveClass.objects.filter(course=course)
    return render(request, 'liveclass/teacher_live_classes.html', {
        'course': course,
        'live_classes': live_classes,
    })


@login_required
def create_live_class(request, course_id):
    course = get_object_or_404(Course, id=course_id, teacher=request.user)
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        scheduled_at = request.POST.get('scheduled_at')

        if not title or not scheduled_at:
            messages.error(request, "Title and scheduled time are required.")
            return redirect('liveclass:teacher_live_classes', course_id=course_id)

        from tenants.middleware import get_current_tenant
        tenant = get_current_tenant()

        LiveClass.objects.create(
            course=course,
            teacher=request.user,
            title=title,
            description=description,
            scheduled_at=scheduled_at,
            tenant=tenant,
        )
        messages.success(request, "Live class scheduled successfully.")
        return redirect('liveclass:teacher_live_classes', course_id=course_id)

    return render(request, 'liveclass/create_live_class.html', {'course': course})


@login_required
def enter_live_class(request, room_id):
    live_class = get_object_or_404(LiveClass, room_id=room_id)
    user = request.user
    is_teacher = live_class.teacher == user

    # Check access: teacher or enrolled student
    if not is_teacher:
        enrolled = live_class.course.students.filter(id=user.id).exists()
        if not enrolled:
            messages.error(request, "You are not enrolled in this course.")
            return redirect('classroom:student_courses')

    # Record attendance for students
    if not is_teacher and live_class.status == 'live':
        LiveClassAttendance.objects.get_or_create(
            live_class=live_class,
            student=user,
            defaults={'tenant': live_class.tenant}
        )

    # Load last 50 chat messages
    chat_messages = live_class.messages.select_related('sender').order_by('sent_at')[:50]

    return render(request, 'liveclass/live_room.html', {
        'live_class': live_class,
        'is_teacher': is_teacher,
        'chat_messages': chat_messages,
        'jitsi_room': live_class.jitsi_room_name,
    })


@login_required
@require_POST
def start_live_class(request, room_id):
    live_class = get_object_or_404(LiveClass, room_id=room_id, teacher=request.user)
    live_class.status = 'live'
    live_class.started_at = timezone.now()
    live_class.save()
    return JsonResponse({'status': 'live'})


@login_required
@require_POST
def end_live_class(request, room_id):
    live_class = get_object_or_404(LiveClass, room_id=room_id, teacher=request.user)
    live_class.status = 'ended'
    live_class.ended_at = timezone.now()
    live_class.save()
    return JsonResponse({'status': 'ended'})


@login_required
def delete_live_class(request, room_id):
    live_class = get_object_or_404(LiveClass, room_id=room_id, teacher=request.user)
    course_id = live_class.course.id
    live_class.delete()
    messages.success(request, "Live class deleted.")
    return redirect('liveclass:teacher_live_classes', course_id=course_id)


@login_required
def student_live_classes(request):
    """All upcoming/live classes for courses the student is enrolled in."""
    courses = request.user.enrolled_courses.all()
    live_classes = LiveClass.objects.filter(
        course__in=courses,
        status__in=['scheduled', 'live']
    ).select_related('course', 'teacher').order_by('scheduled_at')
    return render(request, 'liveclass/student_live_classes.html', {
        'live_classes': live_classes,
    })


@login_required
def live_class_attendance(request, room_id):
    live_class = get_object_or_404(LiveClass, room_id=room_id, teacher=request.user)
    attendances = live_class.attendances.select_related('student').order_by('joined_at')
    return render(request, 'liveclass/attendance.html', {
        'live_class': live_class,
        'attendances': attendances,
    })
