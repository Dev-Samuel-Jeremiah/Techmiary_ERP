# chat/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib.auth import get_user_model
from django.db.models import Q, Max, OuterRef, Subquery
from tenants.middleware import get_current_tenant

from .models import Conversation, Message

User = get_user_model()


@login_required
def inbox(request):
    """Show all conversations for current user."""
    user = request.user
    conversations = Conversation.objects.filter(
        participants=user
    ).prefetch_related('participants').order_by('-updated_at')

    conv_data = []
    for conv in conversations:
        other = conv.other_participant(user)
        last = conv.last_message()
        unread = conv.unread_count(user)
        if other:
            conv_data.append({
                'conv': conv,
                'other': other,
                'last': last,
                'unread': unread,
            })

    return render(request, 'chat/inbox.html', {
        'conv_data': conv_data,
    })


@login_required
def conversation(request, conv_id):
    user = request.user
    conv = get_object_or_404(Conversation, id=conv_id, participants=user)
    other = conv.other_participant(user)
    messages = conv.messages.select_related('sender').order_by('sent_at')

    # Mark messages read
    conv.messages.filter(is_read=False).exclude(sender=user).update(is_read=True)

    # Sidebar data
    conversations = Conversation.objects.filter(participants=user).prefetch_related('participants').order_by('-updated_at')
    conv_data = []
    for c in conversations:
        o = c.other_participant(user)
        if o:
            conv_data.append({'conv': c, 'other': o, 'last': c.last_message(), 'unread': c.unread_count(user)})

    return render(request, 'chat/conversation.html', {
        'conv': conv,
        'other': other,
        'messages': messages,
        'conv_data': conv_data,
    })


@login_required
def start_conversation(request, user_id):
    """Get or create a conversation with a user, redirect to it."""
    user = request.user
    tenant = get_current_tenant()
    other = get_object_or_404(User, id=user_id)

    if other == user:
        return redirect('chat:inbox')

    # Find existing conversation between these two users in this tenant
    conv = Conversation.objects.filter(
        participants=user, tenant=tenant
    ).filter(
        participants=other
    ).first()

    if not conv:
        conv = Conversation.objects.create(tenant=tenant)
        conv.participants.add(user, other)

    return redirect('chat:conversation', conv_id=conv.id)


@login_required
def people(request):
    """List all users in the tenant that the current user can chat with."""
    user = request.user
    tenant = get_current_tenant()

    # Get all users associated with this tenant via Staff or Student profiles
    from users.models import Staff, Student
    staff_user_ids = Staff.objects.filter(tenant=tenant).values_list('user_id', flat=True)
    student_user_ids = Student.objects.filter(tenant=tenant).values_list('user_id', flat=True)
    all_ids = set(list(staff_user_ids) + list(student_user_ids))
    all_ids.discard(user.id)

    users = User.objects.filter(id__in=all_ids).order_by('first_name', 'last_name')

    # Annotate with existing conversation ids
    existing = {
        conv.other_participant(user).id: conv.id
        for conv in Conversation.objects.filter(participants=user, tenant=tenant).prefetch_related('participants')
        if conv.other_participant(user)
    }

    people_data = []
    for u in users:
        role = 'Student' if u.id in set(student_user_ids) else 'Staff'
        people_data.append({
            'user': u,
            'role': role,
            'conv_id': existing.get(u.id),
        })

    return render(request, 'chat/people.html', {'people_data': people_data})


@login_required
def unread_count(request):
    """API endpoint — returns total unread count for badge."""
    user = request.user
    count = Message.objects.filter(
        conversation__participants=user,
        is_read=False,
    ).exclude(sender=user).count()
    return JsonResponse({'count': count})


@login_required
def conversations_api(request):
    """API endpoint — returns conversations list for popup widget."""
    user = request.user
    conversations = Conversation.objects.filter(
        participants=user
    ).prefetch_related('participants').order_by('-updated_at')[:15]

    data = []
    for conv in conversations:
        other = conv.other_participant(user)
        last = conv.last_message()
        unread = conv.unread_count(user)
        if other:
            initials = (
                (other.first_name[:1] if other.first_name else '') +
                (other.last_name[:1] if other.last_name else '')
            ).upper() or other.username[:2].upper()
            preview = ''
            if last:
                prefix = 'You: ' if last.sender == user else ''
                preview = prefix + last.content[:40]
            data.append({
                'id': conv.id,
                'other_id': other.id,
                'other_name': other.get_full_name() or other.username,
                'initials': initials,
                'preview': preview or 'No messages yet',
                'unread': unread,
            })

    return JsonResponse({'conversations': data})


# ── Moderation log (staff only) ──────────────────────────────────────────────
from django.contrib.admin.views.decorators import staff_member_required
from .models import BlockedMessage


@staff_member_required
def moderation_log(request):
    """Staff-only view of all blocked messages for this tenant."""
    tenant = get_current_tenant()
    category = request.GET.get('category', '')
    reviewed  = request.GET.get('reviewed', '')

    qs = BlockedMessage.objects.filter(tenant=tenant).select_related('sender', 'conversation')

    if category:
        qs = qs.filter(category=category)
    if reviewed == '1':
        qs = qs.filter(reviewed=True)
    elif reviewed == '0':
        qs = qs.filter(reviewed=False)

    # Mark reviewed via POST
    if request.method == 'POST':
        msg_id = request.POST.get('mark_reviewed')
        note   = request.POST.get('admin_note', '').strip()
        if msg_id:
            BlockedMessage.objects.filter(id=msg_id, tenant=tenant).update(
                reviewed=True, admin_note=note
            )
        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(request.get_full_path())

    unreviewed_count = BlockedMessage.objects.filter(tenant=tenant, reviewed=False).count()

    return render(request, 'chat/moderation_log.html', {
        'blocked_messages': qs[:100],
        'unreviewed_count': unreviewed_count,
        'category_filter': category,
        'reviewed_filter': reviewed,
        'categories': BlockedMessage.CATEGORY_CHOICES,
    })
