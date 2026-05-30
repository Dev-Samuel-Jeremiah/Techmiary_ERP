# chat/migrations/0002_blockedmessage.py
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0001_initial'),
        ('tenants', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='BlockedMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content', models.TextField()),
                ('category', models.CharField(
                    choices=[
                        ('sexual',      'Sexual / Explicit Content'),
                        ('hate_speech', 'Hate Speech / Discrimination'),
                        ('threat',      'Threats / Violence'),
                        ('bullying',    'Bullying / Harassment'),
                        ('self_harm',   'Self-Harm / Suicide Content'),
                    ],
                    max_length=30,
                )),
                ('matched_pattern', models.CharField(blank=True, max_length=200)),
                ('matched_word', models.CharField(blank=True, max_length=100)),
                ('blocked_at', models.DateTimeField(auto_now_add=True)),
                ('reviewed', models.BooleanField(default=False)),
                ('admin_note', models.TextField(blank=True)),
                ('conversation', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='blocked_messages',
                    to='chat.conversation',
                )),
                ('sender', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='blocked_messages',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('tenant', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='tenants.tenant',
                )),
            ],
            options={'ordering': ['-blocked_at']},
        ),
    ]
