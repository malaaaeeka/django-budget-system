from django.contrib import admin
from typing import Any
from django.http import HttpRequest
from .models import Brand, Campaign, DaypartingSchedule, SpendRecord, BudgetSummary

@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('name', 'daily_budget', 'monthly_budget', 'timezone', 'is_active', 'created_at')
    list_filter = ('is_active', 'timezone', 'created_at')
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'is_active')
        }),
        ('Budget Settings', {
            'fields': ('daily_budget', 'monthly_budget', 'timezone')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ('name', 'brand', 'status', 'created_at', 'updated_at')
    list_filter = ('status', 'brand', 'created_at')
    search_fields = ('name', 'brand__name')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'brand', 'status')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request: HttpRequest) -> Any:
        return super().get_queryset(request).select_related('brand')

@admin.register(DaypartingSchedule)
class DaypartingScheduleAdmin(admin.ModelAdmin):
    list_display = ('campaign', 'day_of_week', 'start_hour', 'end_hour', 'is_active')
    list_filter = ('day_of_week', 'is_active', 'campaign__brand')
    search_fields = ('campaign__name', 'campaign__brand__name')
    
    fieldsets = (
        ('Schedule Information', {
            'fields': ('campaign', 'day_of_week', 'start_hour', 'end_hour', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')
    
    def get_queryset(self, request: HttpRequest) -> Any:
        return super().get_queryset(request).select_related('campaign', 'campaign__brand')

@admin.register(SpendRecord)
class SpendRecordAdmin(admin.ModelAdmin):
    list_display = ('brand', 'campaign', 'amount', 'spend_date', 'record_type', 'created_at')
    list_filter = ('spend_date', 'record_type', 'brand', 'created_at')
    search_fields = ('campaign__name', 'brand__name')
    readonly_fields = ('created_at',)
    date_hierarchy = 'spend_date'
    
    fieldsets = (
        ('Spend Information', {
            'fields': ('brand', 'campaign', 'amount', 'spend_date', 'spend_datetime', 'record_type')
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request: HttpRequest) -> Any:
        return super().get_queryset(request).select_related('campaign', 'campaign__brand')

@admin.register(BudgetSummary)
class BudgetSummaryAdmin(admin.ModelAdmin):
    list_display = ('brand', 'date', 'daily_spend', 'monthly_spend', 'updated_at')
    list_filter = ('date', 'brand', 'updated_at')
    search_fields = ('brand__name',)
    readonly_fields = ('updated_at',)
    date_hierarchy = 'date'
    
    fieldsets = (
        ('Summary Information', {
            'fields': ('brand', 'date', 'daily_spend', 'monthly_spend')
        }),
        ('Metadata', {
            'fields': ('updated_at',),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request: HttpRequest) -> Any:
        return super().get_queryset(request).select_related('brand')

# Customize the admin site header and title
admin.site.site_header = "Budget Management System"
admin.site.site_title = "Budget Admin"
admin.site.index_title = "Welcome to Budget Management System"