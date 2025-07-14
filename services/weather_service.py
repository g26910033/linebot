"""
天氣服務模組
負責從 OpenWeatherMap API 獲取天氣資訊。
"""
import requests
from utils.logger import get_logger
from datetime import datetime

logger = get_logger(__name__)

class WeatherService:
    """提供天氣查詢功能的服務。"""

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("OpenWeatherMap API key is required.")
        self.api_key = api_key
        self.current_weather_url = "https://api.openweathermap.org/data/2.5/weather"
        self.forecast_url = "https://api.openweathermap.org/data/2.5/forecast"
        self.geo_url = "https://api.openweathermap.org/geo/1.0/direct"

    def _get_coordinates(self, city_name: str) -> dict | None:
        """使用城市名稱獲取經緯度。"""
        params = {
            'q': city_name,
            'limit': 1,
            'appid': self.api_key
        }
        try:
            response = requests.get(self.geo_url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            if data:
                return {"lat": data[0]['lat'], "lon": data[0]['lon']}
            return None
        except requests.RequestException as e:
            logger.error(f"Failed to get coordinates for {city_name}: {e}")
            return None
        except (IndexError, KeyError) as e:
            logger.error(f"Error parsing coordinate data for {city_name}: {e}")
            return None

    def get_current_weather(self, city_name: str) -> str:
        """獲取指定城市的「即時」天氣資訊。"""
        coords = self._get_coordinates(city_name)
        if not coords:
            return f"抱歉，找不到「{city_name}」這個地點的資訊。"

        params = {
            'lat': coords['lat'],
            'lon': coords['lon'],
            'appid': self.api_key,
            'units': 'metric',
            'lang': 'zh_tw'
        }
        try:
            response = requests.get(self.current_weather_url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            desc = data['weather'][0]['description']
            temp = data['main']['temp']
            return f"「{city_name}」現在的天氣是 {desc}，溫度 {temp}°C。"
        except requests.RequestException as e:
            logger.error(f"Failed to get current weather for {city_name}: {e}")
            return "抱歉，無法獲取即時天氣資訊，請稍後再試。"
        except (IndexError, KeyError) as e:
            logger.error(f"Error parsing current weather data for {city_name}: {e}")
            return "抱歉，解析即時天氣資料時發生錯誤。"

    def get_weather_forecast(self, city_name: str) -> dict | str:
        """獲取指定城市的「五日」天氣預報。"""
        coords = self._get_coordinates(city_name)
        if not coords:
            return f"抱歉，找不到「{city_name}」這個地點的資訊。"

        params = {
            'lat': coords['lat'],
            'lon': coords['lon'],
            'appid': self.api_key,
            'units': 'metric',
            'lang': 'zh_tw'
        }
        try:
            response = requests.get(self.forecast_url, params=params, timeout=5)
            response.raise_for_status()
            forecast_data = response.json()

            # 處理並簡化預報資料，每天只取一筆中午的資料
            daily_forecasts = {}
            for item in forecast_data.get('list', []):
                date_str = datetime.fromtimestamp(item['dt']).strftime('%Y-%m-%d')
                # 只選擇每天最接近中午 12:00 的預報
                if date_str not in daily_forecasts or abs(datetime.fromtimestamp(item['dt']).hour - 12) < abs(datetime.fromtimestamp(daily_forecasts[date_str]['dt']).hour - 12):
                    daily_forecasts[date_str] = {
                        'dt': item['dt'],
                        'temp': item['main']['temp'],
                        'temp_min': item['main']['temp_min'],
                        'temp_max': item['main']['temp_max'],
                        'description': item['weather'][0]['description'],
                        'icon': item['weather'][0]['icon']
                    }
            
            # 轉換為列表並排序
            sorted_forecasts = sorted(daily_forecasts.values(), key=lambda x: x['dt'])
            
            return {"city": city_name, "forecasts": sorted_forecasts}

        except requests.RequestException as e:
            logger.error(f"Failed to get weather forecast for {city_name}: {e}")
            return "抱歉，無法獲取天氣預報資訊，請稍後再試。"
        except (IndexError, KeyError) as e:
            logger.error(f"Error parsing weather forecast data for {city_name}: {e}")
            return "抱歉，解析天氣預報資料時發生錯誤。"
