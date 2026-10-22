"""
Notification Service
Dispatches Windows Desktop notifications and Telegram alerts.
"""
import sys
import subprocess
import asyncio
import httpx
from typing import Optional
from app.config.settings import settings

class NotificationService:
    def __init__(self):
        self.desktop_enabled = settings.DESKTOP_NOTIFICATIONS_ENABLED
        self.telegram_enabled = settings.TELEGRAM_ENABLED
        self.telegram_token = settings.TELEGRAM_BOT_TOKEN
        self.telegram_chat_id = settings.TELEGRAM_CHAT_ID

    def send_desktop_toast(self, title: str, message: str):
        """Displays Windows notification toast via PowerShell."""
        if not self.desktop_enabled or sys.platform != "win32":
            return

        ps_script = f"""
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
        $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
        $textNodes = $template.GetElementsByTagName("text")
        $textNodes.Item(0).AppendChild($template.CreateTextNode('{title}')) > $null
        $textNodes.Item(1).AppendChild($template.CreateTextNode('{message}')) > $null
        $toast = [Windows.UI.Notifications.ToastNotification]::new($template)
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('AI Binance Trading').Show($toast)
        """
        try:
            subprocess.Popen(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception:
            pass

    async def send_telegram_alert(self, title: str, message: str):
        """Sends alert message to configured Telegram chat."""
        if not (self.telegram_enabled and self.telegram_token and self.telegram_chat_id):
            return

        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        text = f"🚨 *{title}*\n\n{message}"
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                await client.post(url, json={
                    "chat_id": self.telegram_chat_id,
                    "text": text,
                    "parse_mode": "Markdown"
                })
        except Exception:
            pass

    async def notify(self, event_type: str, title: str, message: str):
        """Broadcast alert to all enabled channels."""
        self.send_desktop_toast(title, message)
        if self.telegram_enabled:
            asyncio.create_task(self.send_telegram_alert(title, message))

notifier = NotificationService()
