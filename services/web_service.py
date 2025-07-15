"""
Web Service Module
Handles fetching content from URLs.
"""
import re
import requests
from bs4 import BeautifulSoup
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled
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

    def is_youtube_url(self, text: str) -> bool:
        """Checks if the given text is a YouTube URL."""
        return self._YOUTUBE_PATTERN.match(text) is not None

    def fetch_url_content(self, url: str) -> str | None:
        """
        Fetches the main text content from a given URL.
        """
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

    def get_youtube_transcript(self, url: str) -> str | None:
        """
        Fetches the transcript for a given YouTube URL.
        """
        video_id_match = self._YOUTUBE_PATTERN.search(url)
        if not video_id_match:
            return None
        video_id = video_id_match.group(6)

        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            # 優先尋找繁體中文，其次是英文，最後是任何可用的語言
            transcript = None
            try:
                transcript = transcript_list.find_transcript(['zh-Hant', 'zh-TW'])
            except NoTranscriptFound:
                try:
                    transcript = transcript_list.find_transcript(['en'])
                except NoTranscriptFound:
                    # 抓取第一個可用的自動生成字幕
                    for trans in transcript_list:
                        if trans.is_generated:
                            transcript = trans
                            break
                    if not transcript:
                        raise NoTranscriptFound("No suitable transcript found.")

            transcript_text = ' '.join([item['text'] for item in transcript.fetch()])
            return transcript_text
        except (NoTranscriptFound, TranscriptsDisabled):
            logger.warning(f"No transcript found or transcripts are disabled for YouTube video: {video_id}")
            return "這部影片沒有可用的字幕。"
        except Exception as e:
            logger.error(f"Error fetching YouTube transcript for video {video_id}: {e}")
            return "抱歉，獲取影片字幕時發生錯誤。"
