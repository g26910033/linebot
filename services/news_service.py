"""
新聞服務模組
負責從 NewsAPI.org 獲取最新的頭條新聞。
"""
import requests
from utils.logger import get_logger

logger = get_logger(__name__)


class NewsService:
    """提供新聞查詢功能的服務。"""

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("NewsAPI.org API key is required.")
        self.api_key = api_key
        self.base_url = "https://newsapi.org/v2/top-headlines"

    def get_top_headlines(self, page_size: int = 5) -> str:
        """
        獲取台灣相關的頭條新聞。
        """
        # 改為使用 everything 端點並以關鍵字搜尋
        self.base_url = "https://newsapi.org/v2/everything"
        params = {
            'q': '台灣',
            'language': 'zh',  # 優先顯示中文內容
            'sortBy': 'publishedAt',  # 按發布時間排序
            'pageSize': page_size,
            'apiKey': self.api_key
        }
        try:
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            news_data = response.json()

            articles = news_data.get('articles')
            if not articles:
                return "抱歉，目前找不到任何新聞頭條。"

            # 格式化新聞訊息
            formatted_news = ["為您帶來最新的台灣頭條新聞：\n"]
            for i, article in enumerate(articles):
                title = article.get('title', '無標題')
                url = article.get('url', '#')
                # 移除標題中可能存在的來源資訊
                title_parts = title.split(' - ')
                if len(title_parts) > 1:
                    title = ' - '.join(title_parts[:-1])

                formatted_news.append(f"{i + 1}. {title}\n{url}\n")

            return "\n".join(formatted_news)

        except requests.RequestException as e:
            logger.error(f"Failed to get news headlines: {e}")
            return "抱歉，無法獲取新聞資訊，請稍後再試。"
        except (IndexError, KeyError) as e:
            logger.error(f"Error parsing news data: {e}")
            return "抱歉，解析新聞資料時發生錯誤。"
