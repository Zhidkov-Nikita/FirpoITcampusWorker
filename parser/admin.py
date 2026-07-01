from django.contrib import admin
from parser.models import ExerciseRecord

admin.site.site_header = "IT campus Administration"
admin.site.site_title = "IT campus Admin"
admin.site.index_title = "Добро пожаловать в панель управления IT campus"

@admin.register(ExerciseRecord)
class ExerciseRecordAdmin(admin.ModelAdmin):
    list_display = ("record_id", "user_name", "module_title", "answer")
    