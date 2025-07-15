"""
Web Service Module
Handles fetching content from URLs.
"""
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled
from utils.logger import get_logger

logger = get_logger(__name__)


class WebService:
    """A service for fetching and parsing web content."""

    _URL_PATTERN = re.compile(r'https?://\S+')

    def __init__(self, timeout: int = 10):
        """
        Initializes the WebService.
        Args:
            timeout (int): Request timeout in seconds.
        """
        self.timeout = timeout
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def is_url(self, text: str) -> bool:
        """Checks if the given text is a URL."""
        return self._URL_PATTERN.match(text) is not None

    def _get_youtube_video_id(self, url: str) -> str | None:
        """從 YouTube 連結中提取影片 ID。"""
        parsed_url = urlparse(url)
        if parsed_url.hostname in [
            'www.youtube.com',
            'youtube.com',
                'm.youtube.com']:
            if parsed_url.path == '/watch':
                return parse_qs(parsed_url.query).get('v', [None])[0]
            elif parsed_url.path.startswith('/youtu.be/'):
                return parsed_url.path.split('/')[-1]
        return None

    def _get_youtube_transcript(self, video_id: str) -> str | None:
        """獲取 YouTube 影片的字幕。"""
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            transcript = None
            if 'zh-TW' in transcript_list._generated_transcripts:
                transcript = transcript_list.find_transcript(['zh-TW'])
            elif 'en' in transcript_list._generated_transcripts:
                transcript = transcript_list.find_transcript(['en'])
            else:
                for t in transcript_list:
                    transcript = t
                    break

            if transcript:
                if transcript.is_generated and transcript.language_code != 'zh-TW':
                    try:
                        translated_transcript = transcript.translate('zh-TW')
                        full_transcript = " ".join(
                            [entry['text'] for entry in translated_transcript.fetch()])
                        logger.info(
                            f"Translated YouTube transcript to zh-TW for video {video_id}")
                        return full_transcript
                    except Exception as e:
                        logger.warning(
                            f"Failed to translate YouTube transcript for {video_id}: {e}")
                        full_transcript = " ".join(
                            [entry['text'] for entry in transcript.fetch()])
                        return full_transcript
                else:
                    full_transcript = " ".join(
                        [entry['text'] for entry in transcript.fetch()])
                    logger.info(
                        f"Fetched YouTube transcript for video {video_id}")
                    return full_transcript
            return None
        except NoTranscriptFound:
            logger.warning(
                f"No transcript found for YouTube video ID: {video_id}")
            return None
        except TranscriptsDisabled:
            logger.warning(
                f"Transcripts are disabled for YouTube video ID: {video_id}")
            return None
        except Exception as e:
            logger.error(
                f"Error fetching YouTube transcript for {video_id}: {e}")
            return None

    def fetch_url_content(self, url: str) -> str | None:
        """
        Fetches the main text content from a given URL.
        Prioritizes YouTube transcript if it's a YouTube video.
        """
        video_id = self._get_youtube_video_id(url)
        if video_id:
            logger.info(
                f"Detected YouTube URL, attempting to fetch transcript for video ID: {video_id}")
            transcript = self._get_youtube_transcript(video_id)
            if transcript:
                return transcript
            else:
                logger.warning(
                    f"Could not get YouTube transcript for {video_id}.")
                return "抱歉，無法獲取此 YouTube 影片的字幕內容。"

        try:
            response = requests.get(
                url, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')
            for script_or_style in soup(['script', 'style']):
                script_or_style.decompose()

            text = soup.get_text()
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip()
                      for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)

            return text
        except requests.RequestException as e:
            logger.error(f"Error fetching URL {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error processing URL content from {url}: {e}")
            return None
