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
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.redis_client: Optional[redis.Redis] = None
        self._initialize_redis()
        self._initialize_cloudinary()
    
    def _initialize_redis(self) -> None:
        """初始化 Redis 連線"""
        if not self.config.redis_url:
            logger.warning("Redis URL not provided, memory will not be persistent")
            return
        
        try:
            self.redis_client = redis.from_url(self.config.redis_url, decode_responses=True)
            # 測試連線
            self.redis_client.ping()
            logger.info("Redis client connected successfully")
            
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            self.redis_client = None
    
    def _initialize_cloudinary(self) -> None:
        """初始化 Cloudinary 設定"""
        try:
            cloudinary.config(
                cloud_name=self.config.cloudinary_cloud_name,
                api_key=self.config.cloudinary_api_key,
                api_secret=self.config.cloudinary_api_secret
            )
            logger.info("Cloudinary configured successfully")
            
        except Exception as e:
            logger.error(f"Cloudinary configuration failed: {e}")
            raise
    
    def is_redis_available(self) -> bool:
        """檢查 Redis 是否可用"""
        return self.redis_client is not None
    
    def get_chat_history(self, user_id: str) -> List[Dict[str, Any]]:
        """取得用戶對話歷史"""
        if not self.redis_client:
            return []
        
        try:
            history_json = self.redis_client.get(f"chat_history_{user_id}")
            return json.loads(history_json) if history_json else []
            
        except Exception as e:
            logger.error(f"Failed to get chat history for user {user_id}: {e}")
            return []
    
    def save_chat_history(self, user_id: str, history: List[Dict[str, Any]]) -> bool:
        """儲存用戶對話歷史"""
        if not self.redis_client:
            return False
        
        try:
            # 限制歷史記錄長度，避免記憶體過度使用
            max_history_length = 20
            if len(history) > max_history_length:
                history = history[-max_history_length:]
            
            self.redis_client.set(
                f"chat_history_{user_id}",
                json.dumps(history),
                ex=self.config.chat_history_ttl
            )
            return True
            
        except Exception as e:
            logger.error(f"Failed to save chat history for user {user_id}: {e}")
            return False
    
    def clear_chat_history(self, user_id: str) -> bool:
        """清除用戶對話歷史"""
        if not self.redis_client:
            return False
        
        try:
            self.redis_client.delete(f"chat_history_{user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to clear chat history for user {user_id}: {e}")
            return False
    
    def set_nearby_query(self, user_id: str, keyword: str) -> bool:
        """設定附近搜尋關鍵字"""
        if not self.redis_client:
            return False
        
        try:
            self.redis_client.set(
                f"nearby_query_{user_id}",
                keyword,
                ex=self.config.nearby_query_ttl
            )
            return True
            
        except Exception as e:
            logger.error(f"Failed to set nearby query for user {user_id}: {e}")
            return False
    
    def get_nearby_query(self, user_id: str) -> Optional[str]:
        """取得附近搜尋關鍵字"""
        if not self.redis_client:
            return None
        
        try:
            keyword = self.redis_client.get(f"nearby_query_{user_id}")
            if keyword:
                self.redis_client.delete(f"nearby_query_{user_id}")
            return keyword
            
        except Exception as e:
            logger.error(f"Failed to get nearby query for user {user_id}: {e}")
            return None
    
    def upload_image_to_cloudinary(self, image_data: bytes) -> Tuple[Optional[str], str]:
        """上傳圖片到 Cloudinary"""
        try:
            upload_result = cloudinary.uploader.upload(
                image_data,
                resource_type="image",
                folder="linebot_images",  # 組織圖片到特定資料夾
                quality="auto",  # 自動優化品質
                fetch_format="auto"  # 自動選擇最佳格式
            )
            
            image_url = upload_result.get('secure_url')
            return image_url, "圖片上傳成功"
            
        except Exception as e:
            error_msg = f"圖片上傳失敗: {e}"
            logger.error(error_msg)
            return None, error_msg