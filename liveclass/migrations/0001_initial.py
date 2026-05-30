# liveclass/migrations/0001_initial.py
import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('classroom', '0002_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('tenants', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='LiveClass',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('scheduled_at', models.DateTimeField()),
                ('started_at', models.DateTimeField(null=True, blank=True)),
                ('ended_at', models.DateTimeField(null=True, blank=True)),
                ('status', models.CharField(choices=[('scheduled', 'Scheduled'), ('live', 'Live'), ('ended', 'Ended')], default='scheduled', max_length=20)),
                ('room_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='live_classes', to='classroom.course')),
                ('teacher', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='hosted_live_classes', to=settings.AUTH_USER_MODEL)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant')),
            ],
            options={
                'ordering': ['-scheduled_at'],
            },
        ),
        migrations.CreateModel(
            name='LiveClassAttendance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('joined_at', models.DateTimeField(auto_now_add=True)),
                ('left_at', models.DateTimeField(null=True, blank=True)),
                ('live_class', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attendances', to='liveclass.liveclass')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='live_class_attendances', to=settings.AUTH_USER_MODEL)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant')),
            ],
            options={
                'unique_together': {('live_class', 'student')},
            },
        ),
        migrations.CreateModel(
            name='LiveClassMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('message', models.TextField()),
                ('sent_at', models.DateTimeField(auto_now_add=True)),
                ('live_class', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='liveclass.liveclass')),
                ('sender', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant')),
            ],
            options={
                'ordering': ['sent_at'],
            },
        ),
    ]
