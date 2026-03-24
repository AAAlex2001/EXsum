from django.db.models import F

def reset_bills_to_initial(queryset):
    """
    Мгновенно обновляет остатки и курсы
    для всех объектов во входном queryset.
    """
    queryset.update(
        remainder=F('initial_remainder'),
        rate=F('initial_rate')
    )