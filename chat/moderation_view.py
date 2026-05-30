# add to chat/views.py — paste at bottom
from django.contrib.admin.views.decorators import staff_member_required
from .models import BlockedMessage


@staff_member_required
def moderation_log(request):
    """Admin-only view of all blocked messages for this tenant."""
    tenant = get_current_tenant()
    category = request.GET.get('category', '')
    reviewed = request.GET.get('reviewed', '')

    qs = BlockedMessage.objects.filter(tenant=tenant).select_related('sender', 'conversation')

    if category:
        qs = qs.filter(category=category)
    if reviewed == '1':
        qs = qs.filter(reviewed=True)
    elif reviewed == '0':
        qs = qs.filter(reviewed=False)

    # Mark as reviewed via POST
    if request.method == 'POST':
        msg_id = request.POST.get('mark_reviewed')
        note = request.POST.get('admin_note', '')
        if msg_id:
            BlockedMessage.objects.filter(id=msg_id, tenant=tenant).update(
                reviewed=True, admin_note=note
            )
        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(request.path + '?' + request.GET.urlencode())

    unreviewed_count = BlockedMessage.objects.filter(tenant=tenant, reviewed=False).count()

    return render(request, 'chat/moderation_log.html', {
        'blocked_messages': qs[:100],
        'unreviewed_count': unreviewed_count,
        'category_filter': category,
        'reviewed_filter': reviewed,
        'categories': BlockedMessage.CATEGORY_CHOICES,
    })
