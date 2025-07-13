
"""
儲存服務模組
負責 Redis 快取與 Cloudinary 圖片上傳，並提供快取/歷史/圖片等高階操作。
"""
import time
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
    _CHAT_HISTORY_PREFIX: str = "chat_history_"
    _NEARBY_QUERY_PREFIX: str = "nearby_query_"
    _TODO_LIST_PREFIX: str = "todo_list_"
    _LAST_IMAGE_ID_PREFIX: str = "last_image_id_"
    _USER_STATE_PREFIX: str = "user_state_"
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
            if len(history) > self.config.max_chat_history_length:
                history = history[-self.config.max_chat_history_length:]
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

    def get_todo_list(self, user_id: str) -> List[str]:
        """取得用戶的待辦清單"""
        if not self.is_redis_available():
            return []
        try:
            # LRANGE 0 -1 表示獲取列表所有元素
            items = self.redis_client.lrange(f"{self._TODO_LIST_PREFIX}{user_id}", 0, -1)
            return items
        except Exception as e:
            logger.error(f"Failed to get todo list for user {user_id}: {e}")
            return []

    def add_todo_item(self, user_id: str, item: str) -> bool:
        """新增一個待辦事項到清單尾部"""
        if not self.is_redis_available():
            return False
        try:
            # RPUSH 將元素添加到列表尾部
            self.redis_client.rpush(f"{self._TODO_LIST_PREFIX}{user_id}", item)
            return True
        except Exception as e:
            logger.error(f"Failed to add todo item for user {user_id}: {e}")
            return False

    def remove_todo_item(self, user_id: str, item_index: int) -> Optional[str]:
        """
        根據索引完成 (移除) 一個待辦事項。
        Redis 列表操作較複雜，這裡採用 get/set/remove 的方式模擬。
        """
        if not self.is_redis_available():
            return None
        key = f"{self._TODO_LIST_PREFIX}{user_id}"
        try:
            # LINDEX 獲取指定索引的元素
            item_to_remove = self.redis_client.lindex(key, item_index)
            if item_to_remove is None:
                return None # 索引超出範圍

            # LREM 移除指定數量的特定元素。這裡我們用一個唯一的佔位符來確保只刪除一個。
            # 這是因為 LREM 是按值刪除，如果有多個相同內容的待辦事項，需要精確控制。
            placeholder = f"__DELETING_{item_to_remove}_{time.time()}__"
            self.redis_client.lset(key, item_index, placeholder)
            self.redis_client.lrem(key, 1, placeholder)
            return item_to_remove
        except Exception as e:
            logger.error(f"Failed to remove todo item for user {user_id}: {e}")
            return None

    def clear_todo_list(self, user_id: str) -> bool:
        """清除用戶的所有待辦事項"""
        if not self.is_redis_available():
            return False
        try:
            self.redis_client.delete(f"{self._TODO_LIST_PREFIX}{user_id}")
            return True
        except Exception as e:
            logger.error("Failed to clear todo list for user %s: %s", user_id, e)
            return False

    def set_user_last_image_id(self, user_id: str, message_id: str, ttl: int = 600) -> bool:
        """儲存使用者最後傳送的圖片 message_id，預設10分鐘後過期"""
        if not self.is_redis_available():
            return False
        try:
            self.redis_client.set(f"{self._LAST_IMAGE_ID_PREFIX}{user_id}", message_id, ex=ttl)
            return True
        except Exception as e:
            logger.error(f"Failed to set last image id for user {user_id}: {e}")
            return False

    def get_user_last_image_id(self, user_id: str) -> Optional[str]:
        """取得使用者最後傳送的圖片 message_id"""
        if not self.is_redis_available():
            return None
        try:
            return self.redis_client.get(f"{self._LAST_IMAGE_ID_PREFIX}{user_id}")
        except Exception as e:
            logger.error(f"Failed to get last image id for user {user_id}: {e}")
            return None

    def set_user_state(self, user_id: str, state: str, ttl: int = 300) -> bool:
        """設定使用者的當前狀態，例如等待輸入"""
        if not self.is_redis_available():
            return False
        try:
            self.redis_client.set(f"{self._USER_STATE_PREFIX}{user_id}", state, ex=ttl)
            return True
        except Exception as e:
            logger.error(f"Failed to set state for user {user_id}: {e}")
            return False

    def get_user_state(self, user_id: str, delete: bool = True) -> Optional[str]:
        """取得並選擇性地刪除使用者的當前狀態"""
        if not self.is_redis_available():
            return None
        key = f"{self._USER_STATE_PREFIX}{user_id}"
        try:
            state = self.redis_client.get(key)
            if state and delete:
                self.redis_client.delete(key)
            return state
        except Exception as e:
            logger.error(f"Failed to get state for user {user_id}: {e}")
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
