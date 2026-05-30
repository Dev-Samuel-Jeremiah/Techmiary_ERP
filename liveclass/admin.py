# liveclass/admin.py
from django.contrib import admin
from .models import LiveClass, LiveClassAttendance, LiveClassMessage


@admin.register(LiveClass)
class LiveClassAdmin(admin.ModelAdmin):
    list_display = ['title', 'course', 'teacher', 'status', 'scheduled_at', 'started_at', 'ended_at']
    list_filter = ['status']
    search_fields = ['title', 'course__name', 'teacher__first_name', 'teacher__last_name']


@admin.register(LiveClassAttendance)
class LiveClassAttendanceAdmin(admin.ModelAdmin):
    list_display = ['live_class', 'student', 'joined_at', 'left_at']


@admin.register(LiveClassMessage)
class LiveClassMessageAdmin(admin.ModelAdmin):
    list_display = ['live_class', 'sender', 'message', 'sent_at']
