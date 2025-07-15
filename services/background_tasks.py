"""
背景任務處理模組
使用 Celery 處理長時間運行的任務，如圖片生成、影片摘要等。
"""
import os
from celery import Celery
from config.settings import load_config
from utils.logger import get_logger

logger = get_logger(__name__)

# 初始化 Celery
def create_celery_app():
    """創建 Celery 應用實例"""
    config = load_config()
    
    # 使用 Redis 作為 broker 和 backend
    broker_url = config.redis_url or 'redis://localhost:6379/0'
    result_backend = config.redis_url or 'redis://localhost:6379/0'
    
    celery_app = Celery(
        'linebot_tasks',
        broker=broker_url,
        backend=result_backend,
        include=['services.background_tasks']
    )
    
    # Celery 配置
    celery_app.conf.update(
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='Asia/Taipei',
        enable_utc=True,
        task_track_started=True,
        task_time_limit=300,  # 5分鐘超時
        task_soft_time_limit=240,  # 4分鐘軟超時
        worker_prefetch_multiplier=1,
        worker_max_tasks_per_child=1000,
    )
    
    return celery_app

# 創建全域 Celery 實例
celery_app = create_celery_app()

@celery_app.task(bind=True, name='generate_image_task')
def generate_image_task(self, prompt: str, user_id: str):
    """背景圖片生成任務"""
    try:
        logger.info(f"開始背景圖片生成任務: user={user_id}, prompt={prompt[:50]}...")
        
        # 這裡需要重新初始化服務，因為 Celery worker 是獨立進程
        from services.ai.image_service import AIImageService
        from services.ai.core import AICoreService
        from services.storage_service import StorageService
        
        config = load_config()
        core_service = AICoreService(config)
        storage_service = StorageService(config)
        image_service = AIImageService(config, core_service)
        image_service.set_storage_service(storage_service)
        
        # 執行圖片生成
        result, message = image_service.generate_image(prompt)
        
        if result:
            logger.info(f"背景圖片生成成功: user={user_id}")
            return {
                'status': 'success',
                'result': result if isinstance(result, str) else 'binary_data',
                'message': message,
                'user_id': user_id
            }
        else:
            logger.error(f"背景圖片生成失敗: user={user_id}, error={message}")
            return {
                'status': 'error',
                'message': message,
                'user_id': user_id
            }
            
    except Exception as e:
        logger.error(f"背景圖片生成任務異常: user={user_id}, error={e}", exc_info=True)
        return {
            'status': 'error',
            'message': f"圖片生成時發生錯誤: {str(e)}",
            'user_id': user_id
        }

@celery_app.task(bind=True, name='analyze_image_task')
def analyze_image_task(self, image_data_b64: str, user_id: str):
    """背景圖片分析任務"""
    try:
        import base64
        logger.info(f"開始背景圖片分析任務: user={user_id}")
        
        # 解碼 base64 圖片資料
        image_data = base64.b64decode(image_data_b64)
        
        # 重新初始化服務
        from services.ai.image_service import AIImageService
        from services.ai.core import AICoreService
        from services.storage_service import StorageService
        
        config = load_config()
        core_service = AICoreService(config)
        storage_service = StorageService(config)
        image_service = AIImageService(config, core_service)
        image_service.set_storage_service(storage_service)
        
        # 執行圖片分析
        result = image_service.analyze_image(image_data)
        
        logger.info(f"背景圖片分析成功: user={user_id}")
        return {
            'status': 'success',
            'result': result,
            'user_id': user_id
        }
        
    except Exception as e:
        logger.error(f"背景圖片分析任務異常: user={user_id}, error={e}", exc_info=True)
        return {
            'status': 'error',
            'message': f"圖片分析時發生錯誤: {str(e)}",
            'user_id': user_id
        }

@celery_app.task(bind=True, name='youtube_summary_task')
def youtube_summary_task(self, url: str, user_id: str):
    """背景 YouTube 影片摘要任務"""
    try:
        logger.info(f"開始背景 YouTube 摘要任務: user={user_id}, url={url}")
        
        # 重新初始化服務
        from services.ai.text_service import AITextService
        from services.ai.core import AICoreService
        from services.web_service import WebService
        
        config = load_config()
        core_service = AICoreService(config)
        web_service = WebService()
        text_service = AITextService(config, core_service, web_service)
        
        # 執行影片摘要
        result = text_service.summarize_youtube_video(url)
        
        logger.info(f"背景 YouTube 摘要成功: user={user_id}")
        return {
            'status': 'success',
            'result': result,
            'user_id': user_id
        }
        
    except Exception as e:
        logger.error(f"背景 YouTube 摘要任務異常: user={user_id}, error={e}", exc_info=True)
        return {
            'status': 'error',
            'message': f"影片摘要時發生錯誤: {str(e)}",
            'user_id': user_id
        }

class BackgroundTaskManager:
    """背景任務管理器"""
    
    def __init__(self, storage_service):
        self.storage_service = storage_service
    
    def submit_image_generation(self, prompt: str, user_id: str) -> str:
        """提交圖片生成任務"""
        task = generate_image_task.delay(prompt, user_id)
        
        # 儲存任務 ID 到 Redis
        self.storage_service.redis_client.set(
            f"linebot:task:{user_id}:image_gen", 
            task.id, 
            ex=600  # 10分鐘過期
        )
        
        logger.info(f"已提交圖片生成任務: task_id={task.id}, user={user_id}")
        return task.id
    
    def submit_image_analysis(self, image_data: bytes, user_id: str) -> str:
        """提交圖片分析任務"""
        import base64
        image_data_b64 = base64.b64encode(image_data).decode('utf-8')
        task = analyze_image_task.delay(image_data_b64, user_id)
        
        # 儲存任務 ID 到 Redis
        self.storage_service.redis_client.set(
            f"linebot:task:{user_id}:image_analysis", 
            task.id, 
            ex=600  # 10分鐘過期
        )
        
        logger.info(f"已提交圖片分析任務: task_id={task.id}, user={user_id}")
        return task.id
    
    def submit_youtube_summary(self, url: str, user_id: str) -> str:
        """提交 YouTube 摘要任務"""
        task = youtube_summary_task.delay(url, user_id)
        
        # 儲存任務 ID 到 Redis
        self.storage_service.redis_client.set(
            f"linebot:task:{user_id}:youtube_summary", 
            task.id, 
            ex=600  # 10分鐘過期
        )
        
        logger.info(f"已提交 YouTube 摘要任務: task_id={task.id}, user={user_id}")
        return task.id
    
    def get_task_result(self, task_id: str):
        """取得任務結果"""
        try:
            result = celery_app.AsyncResult(task_id)
            
            if result.ready():
                if result.successful():
                    return result.result
                else:
                    return {
                        'status': 'error',
                        'message': str(result.result)
                    }
            else:
                return {
                    'status': 'pending',
                    'message': '任務處理中...'
                }
                
        except Exception as e:
            logger.error(f"取得任務結果失敗: task_id={task_id}, error={e}")
            return {
                'status': 'error',
                'message': '無法取得任務狀態'
            }