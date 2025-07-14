"""
儲存服務模組
負責與 Redis 和 Cloudinary 互動。
"""
import redis
import json
import cloudinary
import cloudinary.uploader
from typing import List, Dict, Any, Optional, Tuple
from utils.logger import get_logger

logger = get_logger(__name__)

class StorageService:
    """提供與 Redis 和 Cloudinary 互動的儲存服務。"""

    def __init__(self, config):
        # Redis 初始化
        try:
            self.redis_client = redis.from_url(config.redis_url, decode_responses=True)
            self.redis_client.ping()
            logger.info("Redis client connected successfully")
        except (redis.exceptions.ConnectionError, TypeError) as e:
            logger.error(f"Redis connection failed: {e}", exc_info=True)
            self.redis_client = None
        
        # Cloudinary 初始化
        try:
            if all([config.cloudinary_cloud_name, config.cloudinary_api_key, config.cloudinary_api_secret]):
                cloudinary.config(
                    cloud_name=config.cloudinary_cloud_name,
                    api_key=config.cloudinary_api_key,
                    api_secret=config.cloudinary_api_secret
                )
                logger.info("Cloudinary configured successfully")
                self.cloudinary_enabled = True
            else:
                self.cloudinary_enabled = False
                logger.warning("Cloudinary credentials not fully provided. Image upload will be disabled.")
        except Exception as e:
            self.cloudinary_enabled = False
            logger.error(f"Cloudinary configuration failed: {e}", exc_info=True)

        self.chat_history_ttl = config.chat_history_ttl
        self.max_chat_history_length = config.max_chat_history_length
        self.nearby_query_ttl = config.nearby_query_ttl
        self.location_ttl = 600

    def upload_image(self, image_bytes: bytes) -> Tuple[Optional[str], str]:
        """上傳圖片到 Cloudinary"""
        if not self.cloudinary_enabled:
            return None, "Cloudinary service is not configured."
        try:
            upload_result = cloudinary.uploader.upload(image_bytes)
            image_url = upload_result.get('secure_url')
            if image_url:
                return image_url, "Upload successful."
            else:
                return None, "Upload to Cloudinary failed, no URL returned."
        except Exception as e:
            logger.error(f"Failed to upload image to Cloudinary: {e}", exc_info=True)
            return None, str(e)

    def _get_key(self, user_id: str, key_type: str) -> str:
        return f"{user_id}:{key_type}"

    def get_chat_history(self, user_id: str) -> List[Dict[str, Any]]:
        if not self.redis_client: return []
        key = self._get_key(user_id, "chat_history")
        try:
            history_json = self.redis_client.get(key)
            return json.loads(history_json) if history_json else []
        except (redis.exceptions.RedisError, json.JSONDecodeError) as e:
            logger.error(f"Failed to get chat history for {user_id}: {e}", exc_info=True)
            return []

    def save_chat_history(self, user_id: str, history: List[Dict[str, Any]]) -> None:
        if not self.redis_client: return
        key = self._get_key(user_id, "chat_history")
        try:
            if len(history) > self.max_chat_history_length:
                history = history[-self.max_chat_history_length:]
            self.redis_client.set(key, json.dumps(history), ex=self.chat_history_ttl)
        except redis.exceptions.RedisError as e:
            logger.error(f"Failed to save chat history for {user_id}: {e}", exc_info=True)

    def clear_chat_history(self, user_id: str) -> None:
        if not self.redis_client: return
        key = self._get_key(user_id, "chat_history")
        try:
            self.redis_client.delete(key)
        except redis.exceptions.RedisError as e:
            logger.error(f"Failed to clear chat history for {user_id}: {e}", exc_info=True)

    def set_user_last_image_id(self, user_id: str, message_id: str) -> None:
        if not self.redis_client: return
        key = self._get_key(user_id, "last_image_id")
        try:
            self.redis_client.set(key, message_id, ex=300)
        except redis.exceptions.RedisError as e:
            logger.error(f"Failed to set last image ID for {user_id}: {e}", exc_info=True)

    def get_user_last_image_id(self, user_id: str) -> Optional[str]:
        if not self.redis_client: return None
        key = self._get_key(user_id, "last_image_id")
        try:
            return self.redis_client.get(key)
        except redis.exceptions.RedisError as e:
            logger.error(f"Failed to get last image ID for {user_id}: {e}", exc_info=True)
            return None

    def set_user_state(self, user_id: str, state: str) -> None:
        if not self.redis_client: return
        key = self._get_key(user_id, "state")
        try:
            self.redis_client.set(key, state, ex=300)
        except redis.exceptions.RedisError as e:
            logger.error(f"Failed to set user state for {user_id}: {e}", exc_info=True)

    def get_user_state(self, user_id: str) -> Optional[str]:
        if not self.redis_client: return None
        key = self._get_key(user_id, "state")
        try:
            return self.redis_client.get(key)
        except redis.exceptions.RedisError as e:
            logger.error(f"Failed to get user state for {user_id}: {e}", exc_info=True)
            return None

    def set_nearby_query(self, user_id: str, query: str) -> None:
        if not self.redis_client: return
        key = self._get_key(user_id, "nearby_query")
        try:
            self.redis_client.set(key, query, ex=self.nearby_query_ttl)
        except redis.exceptions.RedisError as e:
            logger.error(f"Failed to set nearby query for {user_id}: {e}", exc_info=True)

    def get_nearby_query(self, user_id: str) -> Optional[str]:
        if not self.redis_client: return None
        key = self._get_key(user_id, "nearby_query")
        try:
            return self.redis_client.get(key)
        except redis.exceptions.RedisError as e:
            logger.error(f"Failed to get nearby query for {user_id}: {e}", exc_info=True)
            return None

    def set_user_last_location(self, user_id: str, latitude: float, longitude: float) -> None:
        if not self.redis_client: return
        key = self._get_key(user_id, "last_location")
        location_data = {"latitude": latitude, "longitude": longitude}
        try:
            self.redis_client.set(key, json.dumps(location_data), ex=self.location_ttl)
        except redis.exceptions.RedisError as e:
            logger.error(f"Failed to set last location for {user_id}: {e}", exc_info=True)

    def get_user_last_location(self, user_id: str) -> Optional[Dict[str, float]]:
        if not self.redis_client: return None
        key = self._get_key(user_id, "last_location")
        try:
            location_json = self.redis_client.get(key)
            return json.loads(location_json) if location_json else None
        except (redis.exceptions.RedisError, json.JSONDecodeError) as e:
            logger.error(f"Failed to get last location for {user_id}: {e}", exc_info=True)
            return None

    def add_todo_item(self, user_id: str, item: str) -> bool:
        if not self.redis_client: return False
        key = self._get_key(user_id, "todo_list")
        try:
            self.redis_client.rpush(key, item)
            return True
        except redis.exceptions.RedisError as e:
            logger.error(f"Failed to add todo item for {user_id}: {e}", exc_info=True)
            return False

    def get_todo_list(self, user_id: str) -> List[str]:
        if not self.redis_client: return []
        key = self._get_key(user_id, "todo_list")
        try:
            return self.redis_client.lrange(key, 0, -1)
        except redis.exceptions.RedisError as e:
            logger.error(f"Failed to get todo list for {user_id}: {e}", exc_info=True)
            return []

    def remove_todo_item(self, user_id: str, index: int) -> Optional[str]:
        if not self.redis_client: return None
        key = self._get_key(user_id, "todo_list")
        try:
            item = self.redis_client.lindex(key, index)
            if item:
                placeholder = "__DELETED__"
                self.redis_client.lset(key, index, placeholder)
                self.redis_client.lrem(key, 1, placeholder)
                return item
            return None
        except redis.exceptions.RedisError as e:
            logger.error(f"Failed to remove todo item for {user_id}: {e}", exc_info=True)
            return None
