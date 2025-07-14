"""
日曆服務模組
負責產生 Google 日曆活動的 URL。
"""
from urllib.parse import urlencode
from datetime import datetime
from dateutil import parser


class CalendarService:
    """提供日曆相關功能的服務。"""

    def _format_gcal_time(self, dt_str: str) -> str:
        """將 ISO 格式的時間字串轉換為 Google Calendar URL 所需的格式 (YYYYMMDDTHHMMSSZ)。"""
        try:
            # 解析時間字串
            dt_obj = parser.isoparse(dt_str)
            # 轉換為 UTC 時間
            dt_utc = dt_obj.astimezone(
                datetime.now().astimezone().tzinfo).astimezone(
                tz=None)
            # 格式化為 Google Calendar 所需的格式
            return dt_utc.strftime('%Y%m%dT%H%M%SZ')
        except (ValueError, TypeError):
            return ""

    def create_google_calendar_link(self, event_data: dict) -> str | None:
        """
        根據 AI 解析出的事件資訊，產生一個預先填寫好的 Google 日曆活動連結。
        """
        title = event_data.get('title')
        start_time = event_data.get('start_time')
        end_time = event_data.get('end_time')

        if not all([title, start_time, end_time]):
            return None

        # 格式化時間
        gcal_start = self._format_gcal_time(start_time)
        gcal_end = self._format_gcal_time(end_time)

        if not all([gcal_start, gcal_end]):
            return None

        base_url = "https://www.google.com/calendar/render?"
        params = {
            'action': 'TEMPLATE',
            'text': title,
            'dates': f"{gcal_start}/{gcal_end}",
            'details': '此活動由您的 LINE Bot 助理建立。',
            'sf': 'true',
            'output': 'xml'
        }

        return base_url + urlencode(params)
