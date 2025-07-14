"""
實用工具服務模組
提供各種實用工具，例如單位換算、匯率查詢等。
"""
import re
import requests
from decimal import Decimal, InvalidOperation
from utils.logger import get_logger

logger = get_logger(__name__)

class UtilityService:
    """提供雜項實用功能的服務。"""

    def __init__(self):
        # 長度單位 (以公尺為基準)
        self.length_units = {
            '公里': Decimal('1000'), 'km': Decimal('1000'),
            '公尺': Decimal('1'), 'm': Decimal('1'),
            '公分': Decimal('0.01'), 'cm': Decimal('0.01'),
            '毫米': Decimal('0.001'), 'mm': Decimal('0.001'),
            '英里': Decimal('1609.34'), 'mi': Decimal('1609.34'),
            '碼': Decimal('0.9144'), 'yd': Decimal('0.9144'),
            '英尺': Decimal('0.3048'), 'ft': Decimal('0.3048'),
            '英寸': Decimal('0.0254'), 'in': Decimal('0.0254'),
        }
        # 重量單位 (以公斤為基準)
        self.weight_units = {
            '公噸': Decimal('1000'),
            '公斤': Decimal('1'), 'kg': Decimal('1'),
            '公克': Decimal('0.001'), 'g': Decimal('0.001'),
            '毫克': Decimal('0.000001'), 'mg': Decimal('0.000001'),
            '磅': Decimal('0.453592'), 'lb': Decimal('0.453592'),
            '盎司': Decimal('0.0283495'), 'oz': Decimal('0.0283495'),
        }
        # 建立所有單位的列表，用於正則表達式
        all_units = list(self.length_units.keys()) + list(self.weight_units.keys())
        self.conversion_pattern = re.compile(
            r'([\d\.]+)\s*(' + '|'.join(all_units) + r')\s*(?:=|轉|換|等於|到|成)\s*(' + '|'.join(all_units) + r')'
        )

    def _get_exchange_rates(self, base_currency: str) -> dict | None:
        """從 API 獲取匯率"""
        try:
            url = f"https://open.er-api.com/v6/latest/{base_currency.upper()}"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            if data.get("result") == "success":
                return data.get('rates')
            else:
                logger.error(f"Exchange rate API returned an error: {data}")
                return None
        except requests.RequestException as e:
            logger.error(f"Failed to fetch exchange rates: {e}")
            return None

    def _convert_currency(self, value: Decimal, from_currency: str, to_currency: str) -> str | None:
        """執行匯率換算"""
        rates = self._get_exchange_rates(from_currency)
        if not rates:
            return "抱歉，無法獲取即時匯率，請稍後再試。"

        if to_currency not in rates:
            return f"抱歉，找不到貨幣「{to_currency}」的匯率資訊。"

        rate = Decimal(str(rates[to_currency]))
        converted_value = value * rate
        return f"{value} {from_currency} 約等於 {converted_value:.4f} {to_currency}"

    def parse_and_convert(self, text: str, ai_service=None) -> str | None:
        """
        解析文字並執行單位換算或匯率換算。
        """
        # 優先嘗試貨幣換算 (透過 AI 服務)
        if ai_service:
            currency_query = ai_service.parse_currency_conversion_query(text)
            if currency_query and currency_query.get("value") and currency_query.get("from_currency") and currency_query.get("to_currency"):
                try:
                    value = Decimal(str(currency_query["value"]))
                    from_currency = currency_query["from_currency"]
                    to_currency = currency_query["to_currency"]
                    return self._convert_currency(value, from_currency, to_currency)
                except InvalidOperation:
                    return "請輸入有效的數字。"
                except Exception as e:
                    logger.error(f"Error during AI-assisted currency conversion: {e}")
                    return "抱歉，匯率換算時發生錯誤。"

        # 如果不是貨幣換算，再嘗試單位換算 (透過正則表達式)
        match = self.conversion_pattern.search(text.lower())
        if not match:
            return None

        try:
            value_str, from_unit, to_unit = match.groups()
            value = Decimal(value_str)
        except InvalidOperation:
            return "請輸入有效的數字。"
        
        if from_unit in self.length_units and to_unit in self.length_units:
            base_value = value * self.length_units[from_unit]
            converted_value = base_value / self.length_units[to_unit]
            return f"{value_str} {from_unit} 等於 {converted_value.normalize():f} {to_unit}"
        
        elif from_unit in self.weight_units and to_unit in self.weight_units:
            base_value = value * self.weight_units[from_unit]
            converted_value = base_value / self.weight_units[to_unit]
            return f"{value_str} {from_unit} 等於 {converted_value.normalize():f} {to_unit}"
        
        else:
            return "無法在不同類型的單位之間換算（例如長度和重量）。"
