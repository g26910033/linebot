#!/usr/bin/env python3
"""
Celery Worker 啟動腳本
用於在 Render 平台或本地環境啟動背景任務處理器
"""
import os
import sys
from services.background_tasks import celery_app

if __name__ == '__main__':
    # 設定 Celery worker 參數
    worker_args = [
        'worker',
        '--loglevel=info',
        '--concurrency=2',  # Render 免費方案資源有限
        '--max-tasks-per-child=100',
        '--time-limit=300',  # 5分鐘任務超時
        '--soft-time-limit=240',  # 4分鐘軟超時
    ]
    
    # 如果是生產環境，加入額外參數
    if os.getenv('RENDER'):
        worker_args.extend([
            '--without-gossip',
            '--without-mingle',
            '--without-heartbeat'
        ])
    
    # 啟動 Celery worker
    celery_app.worker_main(worker_args)