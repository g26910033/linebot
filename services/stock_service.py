"""
股市服務模組
負責從 Finnhub API 獲取股票資訊。
"""
import requests
from utils.logger import get_logger

logger = get_logger(__name__)

class APIKeyError(Exception):
    """自訂 API 金鑰相關錯誤。"""
    pass

class StockService:
    """提供股市查詢功能的服務。"""

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("Finnhub API key is required.")
        self.api_key = api_key
        self.base_url = "https://finnhub.io/api/v1"

    def get_stock_quote(self, symbol: str) -> str:
        """
        獲取指定股票的即時報價和公司資訊。
        """
        try:
            symbol = symbol.upper()
            profile = self._get_company_profile(symbol)
            quote = self._get_quote(symbol)

            if not profile and not quote:
                return f"抱歉，找不到股票代碼為「{symbol}」的相關資訊。"

            company_name = profile.get('name', symbol)
            currency = profile.get('currency', 'USD')
            
            current_price = quote.get('c', 'N/A')
            change = quote.get('d', 'N/A')
            percent_change = quote.get('dp', 'N/A')
            high_price = quote.get('h', 'N/A')
            low_price = quote.get('l', 'N/A')
            open_price = quote.get('o', 'N/A')
            prev_close = quote.get('pc', 'N/A')

            # 根據漲跌決定表情符號
            emoji = "📈" if (isinstance(change, (int, float)) and change > 0) else "📉" if (isinstance(change, (int, float)) and change < 0) else "📊"

            return (
                f"{emoji} {company_name} ({symbol}) 的即時股價：\n\n"
                f"目前價格：{current_price} {currency}\n"
                f"漲跌：{change} ({percent_change:.2f}%)\n"
                f"--------------------\n"
                f"開盤價：{open_price}\n"
                f"最高價：{high_price}\n"
                f"最低價：{low_price}\n"
                f"昨收價：{prev_close}"
            )
        except APIKeyError:
            return "抱歉，股市查詢功能目前暫停服務，可能是因為 API 金鑰設定有誤。"
        except Exception as e:
            logger.error(f"An unexpected error occurred in get_stock_quote for {symbol}: {e}", exc_info=True)
            return f"抱歉，查詢「{symbol}」時發生未預期的錯誤。"


    def _get_company_profile(self, symbol: str) -> dict | None:
        """獲取公司基本資料。"""
        try:
            response = requests.get(
                f"{self.base_url}/stock/profile2",
                params={'symbol': symbol, 'token': self.api_key},
                timeout=5
            )
            if response.status_code in [401, 403]:
                raise APIKeyError(f"Invalid API Key. Status: {response.status_code}")
            response.raise_for_status()
            data = response.json()
            return data if data else None
        except requests.RequestException as e:
            logger.error(f"Failed to get company profile for {symbol}: {e}")
            # 如果是 APIKeyError，重新引發它讓上層處理
            if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code in [401, 403]:
                 raise APIKeyError from e
            return None
        except (IndexError, KeyError) as e:
            logger.error(f"Error parsing company profile data for {symbol}: {e}")
            return None

    def _get_quote(self, symbol: str) -> dict | None:
        """獲取即時報價。"""
        try:
            response = requests.get(
                f"{self.base_url}/quote",
                params={'symbol': symbol, 'token': self.api_key},
                timeout=5
            )
            if response.status_code in [401, 403]:
                raise APIKeyError(f"Invalid API Key. Status: {response.status_code}")
            response.raise_for_status()
            data = response.json()
            return data if data.get('c', 0) != 0 else None # Finnhub 對無資料的股票會回傳 0
        except requests.RequestException as e:
            logger.error(f"Failed to get quote for {symbol}: {e}")
            if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code in [401, 403]:
                 raise APIKeyError from e
            return None
        except (IndexError, KeyError) as e:
            logger.error(f"Error parsing quote data for {symbol}: {e}")
            return None
