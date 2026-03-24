from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from .models import *
from django.contrib.auth.models import User, Group


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


@admin.register(Bill)
class BillAdmin(ModelAdmin):
	list_display = ['id', 'name', 'short_name', 'currency', 'status', 'remainder', 'rate']
	list_display_links = ('id', 'name',)
	fields = ['name', 'short_name', 'currency', 'status', 'remainder', 'rate', 'initial_remainder', 'initial_rate']
	search_fields = ['id']

	def get_list_display(self, request):
		if request.user.groups.filter(name='restricted').exists():
			return ['id', 'name', 'short_name', 'currency']
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

class ContractorHistoryInline(TabularInline):
	model = ContractorHistory
	fields = ['date_create', 'duty', 'duty_cost', 'deal']
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
	fields = ['name', 'status', 'duty']
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
