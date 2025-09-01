from django.contrib import admin
from .models import ChatSession, ChatMessage, ToolCallLog


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "session_key", "created_at")
    search_fields = ("session_key", "user__username", "user__email")
    list_filter = ("created_at",)


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "session", "role", "created_at")
    search_fields = ("content",)
    list_filter = ("role", "created_at")


@admin.register(ToolCallLog)
class ToolCallLogAdmin(admin.ModelAdmin):
    list_display = ("id", "session", "tool_name", "created_at")
    search_fields = ("tool_name", "session__session_key")
    list_filter = ("tool_name", "created_at")

