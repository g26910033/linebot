    """
日誌工具模組
提供統一的日誌記錄功能
"""
import logging
import sys
from typing import Optional

# 定義日誌格式字串和日期格式字串為常數，提高可維護性並避免重複
DEFAULT_LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
DEFAULT_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'


def get_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """
    取得日誌記錄器
    
    Args:
        name: 記錄器名稱
        level: 日誌等級 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    
    Returns:
        配置好的日誌記錄器
    """
    logger = logging.getLogger(name)
    
    # 避免重複添加 handler，防止日誌重複輸出
    if logger.handlers:
        return logger
    
    # 設定日誌等級，若未指定則預設為 INFO
    log_level = getattr(logging, (level or 'INFO').upper(), logging.INFO)
    logger.setLevel(log_level)
    
    # 建立 console handler，將日誌輸出到標準輸出 (sys.stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    
    # 設定日誌格式
    formatter = logging.Formatter(
        DEFAULT_LOG_FORMAT,
        datefmt=DEFAULT_DATE_FORMAT
    )
    console_handler.setFormatter(formatter)
    
    # 添加 handler 到 logger
    logger.addHandler(console_handler)
    
    # 防止日誌向上傳播到根記錄器，避免重複輸出（如果根記錄器也配置了handler）
    logger.propagate = False
    
    return logger


def setup_root_logger(level: str = 'INFO') -> None:
    """
    設定根日誌記錄器。
    此函數應在應用程式啟動時呼叫一次，以配置全局日誌行為。
    
    Args:
        level: 日誌等級 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=DEFAULT_LOG_FORMAT,
        datefmt=DEFAULT_DATE_FORMAT,
        handlers=[logging.StreamHandler(sys.stdout)]
    )
