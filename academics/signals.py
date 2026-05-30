from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import F

from .models import PublicHoliday, Term


@receiver(post_save, sender=PublicHoliday)
def recalculate_term_days(sender, instance, **kwargs):
    """
    When a public holiday is added, automatically
    reduce school days for affected terms.
    """
    Term.objects.filter(
        start_date__lte=instance.date,
        end_date__gte=instance.date
    ).update(
        number_of_school_days=F('number_of_school_days') - 1
    )
