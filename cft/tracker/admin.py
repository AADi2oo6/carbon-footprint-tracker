from django.contrib import admin
from .models import Profile, Activity, Emission

# Register your models here to make them accessible in the Django admin panel.

# This will allow you to see and edit Profile objects in the admin.
admin.site.register(Profile)

# This will allow you to see and edit Activity objects.
class ActivityAdmin(admin.ModelAdmin):
    list_display = ('user', 'category', 'description', 'value', 'unit', 'timestamp')
    list_filter = ('category', 'user', 'timestamp')
    search_fields = ('description', 'user__username')
    ordering = ('-timestamp',)

admin.site.register(Activity, ActivityAdmin)

# This will allow you to see and edit Emission objects.
admin.site.register(Emission)
