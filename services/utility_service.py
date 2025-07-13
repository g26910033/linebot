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
        # 匯率換算的正則表達式
        self.currency_pattern = re.compile(
            r'([\d\.]+)\s*([A-Z]{3})\s*(?:to|換|轉|等於|到|成)\s*([A-Z]{3})', re.IGNORECASE
        )

    def _get_exchange_rates(self, base_currency: str) -> dict | None:
        """從 API 獲取匯率"""
        try:
            # 更換為支援 TWD 的 ExchangeRate-API
            url = f"https://api.exchangerate-api.com/v4/latest/{base_currency.upper()}"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            if data.get("result") == "success":
                return data.get('rates')
            else:
                # 記錄完整的錯誤回應以供除錯
                logger.error(f"Exchange rate API returned an error: {data}")
                return None
        except requests.RequestException as e:
            logger.error(f"Failed to fetch exchange rates: {e}")
            return None

    def _convert_currency(self, text: str) -> str | None:
        """解析並換算匯率"""
        match = self.currency_pattern.search(text)
        if not match:
            return None

        try:
            value_str, from_currency, to_currency = match.groups()
            value = Decimal(value_str)
            from_currency = from_currency.upper()
            to_currency = to_currency.upper()
        except InvalidOperation:
            return "請輸入有效的數字。"

        rates = self._get_exchange_rates(from_currency)
        if not rates:
            return "抱歉，無法獲取即時匯率，請稍後再試。"

        if to_currency not in rates:
            return f"抱歉，找不到貨幣「{to_currency}」的匯率資訊。"

        rate = Decimal(str(rates[to_currency]))
        converted_value = value * rate
        return f"{value_str} {from_currency} 約等於 {converted_value:.4f} {to_currency}"

    def parse_and_convert(self, text: str) -> str | None:
        """
        解析文字並執行單位換算。
        範例: "100cm等於幾m", "1.5kg轉g"
        """
        # 優先嘗試貨幣換算
        currency_result = self._convert_currency(text)
        if currency_result:
            return currency_result

        # 如果不是貨幣換算，再嘗試單位換算
        match = self.conversion_pattern.search(text.lower())
        if not match:
            return None

        try:
            value_str, from_unit, to_unit = match.groups()
            value = Decimal(value_str)
        except InvalidOperation:
            return "請輸入有效的數字。"
        
        # 判斷單位類型
        if from_unit in self.length_units and to_unit in self.length_units:
            base_value = value * self.length_units[from_unit]
            converted_value = base_value / self.length_units[to_unit]
            # 將結果格式化，移除多餘的零
            return f"{value_str} {from_unit} 等於 {converted_value.normalize():f} {to_unit}"
        
        elif from_unit in self.weight_units and to_unit in self.weight_units:
            base_value = value * self.weight_units[from_unit]
            converted_value = base_value / self.weight_units[to_unit]
            return f"{value_str} {from_unit} 等於 {converted_value.normalize():f} {to_unit}"
        
        else:
            return "無法在不同類型的單位之間換算（例如長度和重量）。"
