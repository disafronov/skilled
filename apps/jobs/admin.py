from django.contrib import admin
from apps.jobs.models import Job


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = [
        'pk', 'bot', 'received_at', 'llm_started_at',
        'llm_finished_at', 'sent_at', 'error',
    ]
    list_select_related = ['bot']
    list_filter = ['received_at', 'llm_started_at', 'llm_finished_at', 'sent_at']
    search_fields = ['raw_input']
    readonly_fields = [
        'bot', 'reply_target', 'raw_input', 'raw_output',
        'error', 'received_at', 'llm_started_at',
        'llm_finished_at', 'sent_at',
    ]
