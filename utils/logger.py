"""
日誌工具模組
提供統一、可擴展的日誌記錄功能，支援多模組、可自訂等級與格式。
"""

import logging
import sys
from typing import Optional

# 新的、更詳細的日誌格式
DETAILED_LOG_FORMAT = (
    '%(asctime)s - %(name)s - [%(levelname)s] - '
    '[%(filename)s:%(lineno)d (%(funcName)s)] - %(message)s'
)
DEFAULT_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'


def get_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """
    取得日誌記錄器，避免重複 handler，支援自訂等級。

    Args:
        name (str): 記錄器名稱。
        level (Optional[str]): 日誌等級 (DEBUG, INFO, WARNING, ERROR,
                                       CRITICAL)。

    Returns:
        logging.Logger: 配置好的日誌記錄器。
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    log_level: int = getattr(logging, (level or 'INFO').upper(), logging.INFO)
    logger.setLevel(log_level)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    formatter = logging.Formatter(
        DETAILED_LOG_FORMAT,  # 使用新的詳細格式
        datefmt=DEFAULT_DATE_FORMAT)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    logger.propagate = False
    return logger


def setup_root_logger(level: str = 'INFO') -> None:
    """
    設定根日誌記錄器，建議於應用啟動時呼叫一次。

    Args:
        level (str): 日誌等級 (DEBUG, INFO, WARNING, ERROR, CRITICAL)。
    """
    logging.basicConfig(
        level=getattr(
            logging,
            level.upper(),
            logging.INFO),
        format=DETAILED_LOG_FORMAT,  # 使用新的詳細格式
        datefmt=DEFAULT_DATE_FORMAT,
        handlers=[
            logging.StreamHandler(
                sys.stdout)])
