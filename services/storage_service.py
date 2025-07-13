    """
儲存服務模組
負責處理 Redis 快取和 Cloudinary 圖片上傳
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
    """儲存服務類別"""

    # Constants for configuration and keys to improve readability and maintainability
    MAX_CHAT_HISTORY_LENGTH: int = 20
    _CHAT_HISTORY_PREFIX: str = "chat_history_"
    _NEARBY_QUERY_PREFIX: str = "nearby_query_"
    _CLOUDINARY_FOLDER: str = "linebot_images"

    def __init__(self, config: AppConfig):
        self.config = config
        self.redis_client: Optional[redis.Redis] = None
        self._initialize_redis()
        self._initialize_cloudinary()

    def _initialize_redis(self) -> None:
        """初始化 Redis 連線"""
        if not self.config.redis_url:
            logger.warning("Redis URL not provided, memory will not be persistent. Skipping Redis initialization.")
            return

        try:
            # Using from_url directly handles connection pooling in most cases for long-lived applications.
            self.redis_client = redis.from_url(self.config.redis_url, decode_responses=True)
            # Test connection
            self.redis_client.ping()
            logger.info("Redis client connected successfully")

        except redis.exceptions.ConnectionError as e:  # More specific exception for connection issues
            logger.error(f"Redis connection failed: {e}. Please check Redis server and URL.")
            self.redis_client = None
        except Exception as e:  # Catch other potential errors during initialization
            logger.error(f"An unexpected error occurred during Redis initialization: {e}")
            self.redis_client = None

    def _initialize_cloudinary(self) -> None:
        """初始化 Cloudinary 設定"""
        # Basic check for essential config values
        if not all([self.config.cloudinary_cloud_name,
                    self.config.cloudinary_api_key,
                    self.config.cloudinary_api_secret]):
            logger.warning("Cloudinary credentials not fully provided. Image upload functionality may be limited.")
            # Depending on severity, you might want to raise an error here too if Cloudinary is mandatory.

        try:
            cloudinary.config(
                cloud_name=self.config.cloudinary_cloud_name,
                api_key=self.config.cloudinary_api_key,
                api_secret=self.config.cloudinary_api_secret
            )
            logger.info("Cloudinary configured successfully")

        except Exception as e:
            logger.error(f"Cloudinary configuration failed: {e}. Please check Cloudinary credentials.")
            raise  # Re-raise, as Cloudinary is critical for image uploads and setup failure means critical functionality is broken.

    def is_redis_available(self) -> bool:
        """檢查 Redis 是否可用，並測試連線"""
        if self.redis_client is None:
            return False
        try:
            # Ping Redis to ensure it's still alive and accessible
            self.redis_client.ping()
            return True
        except redis.exceptions.ConnectionError:
            logger.error("Redis client lost connection. Marking as unavailable.")
            self.redis_client = None  # Mark as unavailable for subsequent calls
            return False
        except Exception as e:
            logger.error(f"Error checking Redis availability: {e}")
            self.redis_client = None
            return False

    def get_chat_history(self, user_id: str) -> List[Dict[str, Any]]:
        """取得用戶對話歷史"""
        if not self.is_redis_available():  # Use the more robust availability check
            return []

        try:
            history_json = self.redis_client.get(f"{self._CHAT_HISTORY_PREFIX}{user_id}")
            # Ensure history_json is not None before attempting json.loads
            if history_json:
                return json.loads(history_json)
            return []

        except json.JSONDecodeError as e:  # More specific exception for JSON parsing issues
            logger.error(f"Failed to decode chat history JSON for user {user_id}: {e}")
            return []
        except Exception as e:
            logger.error(f"Failed to get chat history for user {user_id}: {e}")
            return []

    def save_chat_history(self, user_id: str, history: List[Dict[str, Any]]) -> bool:
        """儲存用戶對話歷史"""
        if not self.is_redis_available():  # Use the more robust availability check
            return False

        try:
            # Limit history length to prevent excessive memory usage in Redis
            if len(history) > self.MAX_CHAT_HISTORY_LENGTH:
                history = history[-self.MAX_CHAT_HISTORY_LENGTH:]

            self.redis_client.set(
                f"{self._CHAT_HISTORY_PREFIX}{user_id}",
                json.dumps(history),
                ex=self.config.chat_history_ttl
            )
            return True

        except Exception as e:
            logger.error(f"Failed to save chat history for user {user_id}: {e}")
            return False

    def clear_chat_history(self, user_id: str) -> bool:
        """清除用戶對話歷史"""
        if not self.is_redis_available():  # Use the more robust availability check
            return False

        try:
            self.redis_client.delete(f"{self._CHAT_HISTORY_PREFIX}{user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to clear chat history for user {user_id}: {e}")
            return False

    def set_nearby_query(self, user_id: str, keyword: str) -> bool:
        """設定附近搜尋關鍵字"""
        if not self.is_redis_available():  # Use the more robust availability check
            return False

        try:
            self.redis_client.set(
                f"{self._NEARBY_QUERY_PREFIX}{user_id}",
                keyword,
                ex=self.config.nearby_query_ttl
            )
            return True

        except Exception as e:
            logger.error(f"Failed to set nearby query for user {user_id}: {e}")
            return False

    def get_nearby_query(self, user_id: str) -> Optional[str]:
        """
        取得附近搜尋關鍵字。
        成功取得後，該關鍵字會從 Redis 中刪除，確保其為一次性使用。
        """
        if not self.is_redis_available():  # Use the more robust availability check
            return None

        try:
            keyword = self.redis_client.get(f"{self._NEARBY_QUERY_PREFIX}{user_id}")
            # If keyword exists, delete it as it's typically a one-time use query
            if keyword:
                self.redis_client.delete(f"{self._NEARBY_QUERY_PREFIX}{user_id}")
            return keyword

        except Exception as e:
            logger.error(f"Failed to get nearby query for user {user_id}: {e}")
            return None

    def upload_image_to_cloudinary(self, image_data: bytes) -> Tuple[Optional[str], str]:
        """上傳圖片到 Cloudinary"""
        # Verify Cloudinary credentials before attempting upload, in case initialization warnings were ignored.
        if not all([self.config.cloudinary_cloud_name,
                    self.config.cloudinary_api_key,
                    self.config.cloudinary_api_secret]):
            error_msg = "Cloudinary credentials not fully configured for image upload. Please check settings."
            logger.error(error_msg)
            return None, error_msg

        try:
            upload_result = cloudinary.uploader.upload(
                image_data,
                resource_type="image",
                folder=self._CLOUDINARY_FOLDER,  # Using constant for folder name
                quality="auto",  # 自動優化品質
                fetch_format="auto"  # 自動選擇最佳格式
            )

            image_url = upload_result.get('secure_url')
            if image_url:
                return image_url, "圖片上傳成功"
            else:
                error_msg = "Cloudinary upload succeeded but no URL was returned. Unexpected behavior."
                logger.error(error_msg)
                return None, error_msg

        except Exception as e:
            error_msg = f"圖片上傳失敗: {e}"
            logger.error(error_msg)
            return None, error_msg
