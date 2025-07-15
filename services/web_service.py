"""
Web Service Module
Handles fetching content from URLs.
"""
import os
import re
import requests
import json
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import yt_dlp
from utils.logger import get_logger

logger = get_logger(__name__)


class WebService:
    """A service for fetching and parsing web content."""

    _URL_PATTERN = re.compile(r'https?://\S+')
    _YOUTUBE_PATTERN = re.compile(r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})')

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def is_url(self, text: str) -> bool:
        """Checks if the given text is a URL."""
        return self._URL_PATTERN.match(text) is not None

    def _get_youtube_transcript(self, url: str) -> str | None:
        """使用 yt-dlp 獲取 YouTube 影片的逐字稿。"""
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['zh-TW', 'en'], # 優先下載繁中，其次英文
            'subtitlesformat': 'vtt',
            'outtmpl': '/tmp/%(id)s.%(ext)s' # 暫存位置
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                video_id = info.get('id')
                if not video_id:
                    return None
                
                # 尋找下載的字幕檔
                subtitle_path_zh = f"/tmp/{video_id}.zh-TW.vtt"
                subtitle_path_en = f"/tmp/{video_id}.en.vtt"
                
                subtitle_path = None
                if os.path.exists(subtitle_path_zh):
                    subtitle_path = subtitle_path_zh
                elif os.path.exists(subtitle_path_en):
                    subtitle_path = subtitle_path_en

                if subtitle_path:
                    with open(subtitle_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                    # 清理 VTT 格式，只保留文字
                    transcript = " ".join([line.strip() for line in lines if '-->' not in line and line.strip().isdigit() is False and line.strip() != 'WEBVTT' and line.strip()])
                    os.remove(subtitle_path) # 刪除暫存檔
                    return transcript
                else:
                    logger.warning(f"Could not find downloaded subtitle file for {url}")
                    return "抱歉，此 YouTube 影片沒有可用的字幕檔。"
        except Exception as e:
            logger.error(f"Error fetching YouTube transcript with yt-dlp for {url}: {e}")
            return "抱歉，此 YouTube 影片因地區或版權限制，無法進行分析。"

    def fetch_url_content(self, url: str) -> str | None:
        """
        Fetches the main text content from a given URL.
        Uses yt-dlp for YouTube videos.
        """
        if self._YOUTUBE_PATTERN.match(url):
            logger.info(f"Detected YouTube URL, using yt-dlp to fetch transcript for: {url}")
            return self._get_youtube_transcript(url)

        try:
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            for script_or_style in soup(['script', 'style']):
                script_or_style.decompose()
            text = soup.get_text()
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)
            return text
        except requests.RequestException as e:
            logger.error(f"Error fetching URL {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error processing URL content from {url}: {e}")
            return None
