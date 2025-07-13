
"""
儲存服務模組
負責 Redis 快取與 Cloudinary 圖片上傳，並提供快取/歷史/圖片等高階操作。
"""
import json
import redis
import cloudinary
import cloudinary.uploader
from typing import Optional, List, Dict, Any, Tuple
from config.settings import AppConfig
from utils.logger import get_logger

logger = get_logger(__name__)



class StorageService:
    """
    儲存服務類別，封裝 Redis 快取與 Cloudinary 圖片上傳。
    支援對話歷史、附近查詢、圖片上傳等功能。
    """
    MAX_CHAT_HISTORY_LENGTH: int = 20
    _CHAT_HISTORY_PREFIX: str = "chat_history_"
    _NEARBY_QUERY_PREFIX: str = "nearby_query_"
    _CLOUDINARY_FOLDER: str = "linebot_images"

    def __init__(self, config: AppConfig) -> None:
        """
        初始化 StorageService。
        Args:
            config (AppConfig): 應用設定物件。
        """
        self.config: AppConfig = config
        self.redis_client: Optional[redis.Redis] = None
        self._initialize_redis()
        self._initialize_cloudinary()

    def _initialize_redis(self) -> None:
        """
        初始化 Redis 連線。
        若無 redis_url 則略過。
        """
        if not self.config.redis_url:
            logger.warning("Redis URL not provided, memory will not be persistent. Skipping Redis initialization.")
            return
        try:
            self.redis_client = redis.from_url(self.config.redis_url, decode_responses=True)
            self.redis_client.ping()
            logger.info("Redis client connected successfully")
        except redis.exceptions.ConnectionError as e:
            logger.error("Redis connection failed: %s. Please check Redis server and URL.", e)
            self.redis_client = None
        except Exception as e:
            logger.error("An unexpected error occurred during Redis initialization: %s", e)
            self.redis_client = None

    def _initialize_cloudinary(self) -> None:
        """
        初始化 Cloudinary 設定。
        若缺少必要參數則警告。
        """
        if not all([
            self.config.cloudinary_cloud_name,
            self.config.cloudinary_api_key,
            self.config.cloudinary_api_secret
        ]):
            logger.warning("Cloudinary credentials not fully provided. Image upload functionality may be limited.")
        try:
            cloudinary.config(
                cloud_name=self.config.cloudinary_cloud_name,
                api_key=self.config.cloudinary_api_key,
                api_secret=self.config.cloudinary_api_secret
            )
            logger.info("Cloudinary configured successfully")
        except Exception as e:
            logger.error("Cloudinary configuration failed: %s. Please check Cloudinary credentials.", e)
            raise

    def is_redis_available(self) -> bool:
        """
        檢查 Redis 是否可用，並測試連線。
        Returns:
            bool: Redis 可用則 True。
        """
        if self.redis_client is None:
            return False
        try:
            self.redis_client.ping()
            return True
        except redis.exceptions.ConnectionError:
            logger.error("Redis client lost connection. Marking as unavailable.")
            self.redis_client = None
            return False
        except Exception as e:
            logger.error("Error checking Redis availability: %s", e)
            self.redis_client = None
            return False

    def get_chat_history(self, user_id: str) -> List[Dict[str, Any]]:
        """
        取得用戶對話歷史。
        Args:
            user_id (str): 用戶 ID。
        Returns:
            List[Dict[str, Any]]: 對話歷史。
        """
        if not self.is_redis_available():
            return []
        try:
            history_json = self.redis_client.get(f"{self._CHAT_HISTORY_PREFIX}{user_id}")
            if history_json:
                return json.loads(history_json)
            return []
        except json.JSONDecodeError as e:
            logger.error("Failed to decode chat history JSON for user %s: %s", user_id, e)
            return []
        except Exception as e:
            logger.error("Failed to get chat history for user %s: %s", user_id, e)
            return []

    def save_chat_history(self, user_id: str, history: List[Dict[str, Any]]) -> bool:
        """
        儲存用戶對話歷史。
        Args:
            user_id (str): 用戶 ID。
            history (List[Dict[str, Any]]): 對話歷史。
        Returns:
            bool: 儲存成功則 True。
        """
        if not self.is_redis_available():
            return False
        try:
            if len(history) > self.MAX_CHAT_HISTORY_LENGTH:
                history = history[-self.MAX_CHAT_HISTORY_LENGTH:]
            self.redis_client.set(
                f"{self._CHAT_HISTORY_PREFIX}{user_id}",
                json.dumps(history),
                ex=self.config.chat_history_ttl
            )
            return True
        except Exception as e:
            logger.error("Failed to save chat history for user %s: %s", user_id, e)
            return False

    def clear_chat_history(self, user_id: str) -> bool:
        """
        清除用戶對話歷史。
        Args:
            user_id (str): 用戶 ID。
        Returns:
            bool: 清除成功則 True。
        """
        if not self.is_redis_available():
            return False
        try:
            self.redis_client.delete(f"{self._CHAT_HISTORY_PREFIX}{user_id}")
            return True
        except Exception as e:
            logger.error("Failed to clear chat history for user %s: %s", user_id, e)
            return False

    def set_nearby_query(self, user_id: str, keyword: str) -> bool:
        """
        設定附近搜尋關鍵字。
        Args:
            user_id (str): 用戶 ID。
            keyword (str): 關鍵字。
        Returns:
            bool: 設定成功則 True。
        """
        if not self.is_redis_available():
            return False
        try:
            self.redis_client.set(
                f"{self._NEARBY_QUERY_PREFIX}{user_id}",
                keyword,
                ex=self.config.nearby_query_ttl
            )
            return True
        except Exception as e:
            logger.error("Failed to set nearby query for user %s: %s", user_id, e)
            return False

    def get_nearby_query(self, user_id: str) -> Optional[str]:
        """
        取得附近搜尋關鍵字，成功後自動刪除。
        Args:
            user_id (str): 用戶 ID。
        Returns:
            Optional[str]: 關鍵字或 None。
        """
        if not self.is_redis_available():
            return None
        try:
            keyword = self.redis_client.get(f"{self._NEARBY_QUERY_PREFIX}{user_id}")
            if keyword:
                self.redis_client.delete(f"{self._NEARBY_QUERY_PREFIX}{user_id}")
            return keyword
        except Exception as e:
            logger.error("Failed to get nearby query for user %s: %s", user_id, e)
            return None

    def upload_image_to_cloudinary(self, image_data: bytes) -> Tuple[Optional[str], str]:
        """
        上傳圖片到 Cloudinary。
        Args:
            image_data (bytes): 圖片二進位資料。
        Returns:
            Tuple[Optional[str], str]: (圖片網址, 狀態訊息)
        """
        if not all([
            self.config.cloudinary_cloud_name,
            self.config.cloudinary_api_key,
            self.config.cloudinary_api_secret
        ]):
            error_msg = "Cloudinary credentials not fully configured for image upload. Please check settings."
            logger.error(error_msg)
            return None, error_msg
        try:
            upload_result = cloudinary.uploader.upload(
                image_data,
                resource_type="image",
                folder=self._CLOUDINARY_FOLDER,
                quality="auto",
                fetch_format="auto"
            )
            image_url = upload_result.get('secure_url')
            if image_url:
                return image_url, "圖片上傳成功"
            error_msg = "Cloudinary upload succeeded but no URL was returned. Unexpected behavior."
            logger.error(error_msg)
            return None, error_msg
        except Exception as e:
            error_msg = f"圖片上傳失敗: {e}"
            logger.error(error_msg)
            return None, error_msg
