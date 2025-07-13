"""
日誌工具模組
提供統一的日誌記錄功能
"""
import logging
import sys
from typing import Optional


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
    
    # 避免重複添加 handler
    if logger.handlers:
        return logger
    
    # 設定日誌等級
    log_level = getattr(logging, (level or 'INFO').upper(), logging.INFO)
    logger.setLevel(log_level)
    
    # 建立 console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    
    # 設定日誌格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    
    # 添加 handler 到 logger
    logger.addHandler(console_handler)
    
    # 防止日誌向上傳播
    logger.propagate = False
    
    return logger


def setup_root_logger(level: str = 'INFO') -> None:
    """
    設定根日誌記錄器
    
    Args:
        level: 日誌等級
    """
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[logging.StreamHandler(sys.stdout)]
    )