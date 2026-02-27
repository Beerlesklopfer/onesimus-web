from django.contrib import admin

# Register your models here.
from .models import Job, JobFile, JobLog


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    """Admin interface for Job model."""
    list_display = ('bareos_id', 'name', 'client', 'status', 'level', 'actual_time', 'bytes', 'files', 'errors')
    list_filter = ('status', 'level', 'actual_time')
    search_fields = ('name', 'client__name', 'bareos_id')
    ordering = ('-actual_time',)
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Basic Info', {'fields': ('bareos_id', 'name', 'client', 'job_type')}),
        ('Status', {'fields': ('status', 'level')}),
        ('Timing', {'fields': ('scheduled_time', 'actual_time', 'end_time')}),
        ('Statistics', {'fields': ('bytes', 'files', 'errors')}),
        ('Storage', {'fields': ('filesets', 'pool_name', 'storage_name')}),
        ('Metadata', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )


@admin.register(JobFile)
class JobFileAdmin(admin.ModelAdmin):
    """Admin interface for JobFile model."""
    list_display = ('name', 'job', 'size', 'is_dir')
    list_filter = ('is_dir', 'mod_time')
    search_fields = ('name', 'path', 'job__name')


@admin.register(JobLog)
class JobLogAdmin(admin.ModelAdmin):
    """Admin interface for JobLog model."""
    list_display = ('job', 'message', 'timestamp')
    list_filter = ('timestamp', 'job')
    search_fields = ('message', 'job__name')
    ordering = ('-timestamp',)

