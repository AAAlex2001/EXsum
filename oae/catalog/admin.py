from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from .models import *
from django.contrib.auth.models import User, Group
from operation.models import HistoryBill
from django.utils.safestring import mark_safe
from django.db.models import Q


admin.site.unregister(User)
admin.site.unregister(Group)

@admin.register(Currency)
class CurrencyAdmin(ModelAdmin):
    list_display = ['id', 'name', 'short_name', 'rate', 'zeros_after', 'zeros_after_rate', 'status']
    list_display_links = ('id', )
    fields = ['name', 'short_name', 'zeros_after', 'rate', 'zeros_after_rate', 'status']

    def get_list_display(self, request):
        if request.user.groups.filter(name='restricted').exists():
            return ['id', 'name', 'short_name',]
        return super().get_list_display(request)

    def has_view_permission(self, request, obj=None):
        if request.user.groups.filter(name='restricted').exists():
            return False
        return super().has_view_permission(request, obj=obj)

    def has_change_permission(self, request, obj=None):
        if request.user.groups.filter(name='restricted').exists():
            return False
        return super().has_change_permission(request, obj=obj)

    def has_delete_permission(self, request, obj=None):
        if request.user.groups.filter(name='restricted').exists():
            return False
        return super().has_delete_permission(request, obj=obj)



class HistoryBillInline(admin.TabularInline):
    model = HistoryBill
    extra = 0
    can_delete = False
    show_change_link = False

    readonly_fields = (
        'income_before', 'income_after',
        'expense_before', 'expense_after',
        'deal_link',
    )

    fields = (
        'income_before', 'income_after',
        'expense_before', 'expense_after',
        'deal_link',
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        bill = getattr(request, '_bill_obj', None)

        if not bill:
            return qs.none()

        return qs.filter(
            Q(in_ex__income_account=bill) |
            Q(in_ex__expense_account=bill)
        ).select_related('in_ex__deal')

    def deal_link(self, obj):
        deal_url = f'/admin/operation/deal/{obj.in_ex.deal.id}/change/'
        return mark_safe(f'<a href="{deal_url}">Сделка</a>')

    deal_link.short_description = 'Сделка'


@admin.register(Bill)
class BillAdmin(ModelAdmin):
    list_display = ['id', 'name', 'short_name', 'currency', 'status', 'remainder', 'rate']
    list_display_links = ('id', 'name',)
    fields = ['name', 'short_name', 'currency', 'status', 'remainder', 'rate', 'initial_remainder', 'initial_rate']
    search_fields = ['id']
    #inlines = [HistoryBillInline]

    def get_form(self, request, obj=None, **kwargs):
        request._bill_obj = obj
        return super().get_form(request, obj, **kwargs)

    def get_list_display(self, request):
        if request.user.groups.filter(name='restricted').exists() and request.user.id != 3:
            return ['id', 'name', 'short_name', 'currency']
        return super().get_list_display(request)

    def has_view_permission(self, request, obj=None):
        if request.user.groups.filter(name='restricted').exists() and request.user.id != 3:
            return False
        return super().has_view_permission(request, obj=obj)

    def has_change_permission(self, request, obj=None) :
        if request.user.groups.filter(name='restricted').exists() and request.user.id != 3:
            return False
        return super().has_change_permission(request, obj=obj)

    def has_delete_permission(self, request, obj=None):
        if request.user.groups.filter(name='restricted').exists() and request.user.id != 3:
            return False
        return super().has_delete_permission(request, obj=obj)

    change_form_template = 'bill_change_form.html'

    def change_view(self, request, object_id, form_url='', extra_context=None):
        bill = self.get_object(request, object_id)

        history = HistoryBill.objects.filter(
            Q(in_ex__income_account=bill) |
            Q(in_ex__expense_account=bill)
        ).select_related('in_ex__deal').order_by('-in_ex__deal__date_create')

        extra_context = extra_context or {}
        extra_context['history_bills'] = history
        extra_context['bill_id'] = int(object_id)

        return super().change_view(
            request, object_id, form_url, extra_context=extra_context
        )



class ContractorHistoryInline(TabularInline):
    model = ContractorHistory
    fields = ['date_create', 'duty','duty_usdt', 'duty_cost', 'deal']
    readonly_fields = ['date_create', 'duty', 'duty_cost']
    can_delete = False
    extra = 0
    show_change_link = False
    ordering = ('-date_create', )

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Contractor)
class ContractorAdmin(ModelAdmin):
    list_display = ['id', 'name', 'status']
    list_display_links = ('id', 'name',)
    fields = ['name', 'status', 'duty', 'duty_usdt', ]
    inlines = [ContractorHistoryInline]

@admin.register(CashFlow)
class CashFlowAdmin(ModelAdmin):
    list_display = ['id', 'name', 'type_cf', 'status']
    list_display_links = ('id', 'name',)
    fields = ['name', 'type_cf', 'status']
    
@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = ['id', 'name']
    list_display_links = ('id', 'name', )
    fields = ['name', 'status']
