"""
Web Service Module
Handles fetching content from URLs.
"""
import requests
from bs4 import BeautifulSoup
from utils.logger import get_logger

logger = get_logger(__name__)

class WebService:
    """A service for fetching and parsing web content."""

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

    def fetch_url_content(self, url: str) -> str | None:
        """
        Fetches the main text content from a given URL.
        Args:
            url (str): The URL to fetch.
        Returns:
            str | None: The extracted text content, or None if fetching fails.
        """
        try:
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()  # Raise an exception for bad status codes

            # Use BeautifulSoup to parse HTML and extract text
            soup = BeautifulSoup(response.content, 'html.parser')

            # Remove script and style elements
            for script_or_style in soup(['script', 'style']):
                script_or_style.decompose()

            # Get text and clean it up
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
