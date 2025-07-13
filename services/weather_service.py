"""
天氣服務模組
負責從 OpenWeatherMap API 獲取天氣資訊。
"""
import requests
from utils.logger import get_logger

logger = get_logger(__name__)

class WeatherService:
    """提供天氣查詢功能的服務。"""

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("OpenWeatherMap API key is required.")
        self.api_key = api_key
        self.base_url = "http://api.openweathermap.org/data/2.5/weather"
        self.geo_url = "http://api.openweathermap.org/geo/1.0/direct"

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

    def get_weather(self, city_name: str) -> str:
        """獲取指定城市的天氣資訊。"""
        coords = self._get_coordinates(city_name)
        if not coords:
            return f"抱歉，找不到「{city_name}」這個地點的資訊。"

        params = {
            'lat': coords['lat'],
            'lon': coords['lon'],
            'appid': self.api_key,
            'units': 'metric',  # 使用攝氏溫度
            'lang': 'zh_tw'     # 結果使用繁體中文
        }
        try:
            response = requests.get(self.base_url, params=params, timeout=5)
            response.raise_for_status()
            weather_data = response.json()

            # 解析並格式化天氣資訊
            description = weather_data['weather'][0]['description']
            temp = weather_data['main']['temp']
            feels_like = weather_data['main']['feels_like']
            humidity = weather_data['main']['humidity']
            wind_speed = weather_data['wind']['speed']

            return (
                f"「{city_name}」目前的天氣資訊：\n"
                f"天氣狀況：{description}\n"
                f"溫度：{temp}°C\n"
                f"體感溫度：{feels_like}°C\n"
                f"濕度：{humidity}%\n"
                f"風速：{wind_speed} m/s"
            )
        except requests.RequestException as e:
            logger.error(f"Failed to get weather for {city_name}: {e}")
            return "抱歉，無法獲取天氣資訊，請稍後再試。"
        except (IndexError, KeyError) as e:
            logger.error(f"Error parsing weather data for {city_name}: {e}")
            return "抱歉，解析天氣資料時發生錯誤。"
