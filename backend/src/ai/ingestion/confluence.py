import hashlib
import httpx
from bs4 import BeautifulSoup
from src.ai.ingestion.base import KnowledgeSource
from src.schemas.documents import DocumentAddSchema
class ConfluenceKnowledgeSource(KnowledgeSource):


    async def fetch(self, url: str) -> DocumentAddSchema:
        page_id = self._extract_page_id(url)
        api_url = f'https://crystals.atlassian.net/wiki/rest/api/content/{page_id}'

        async with httpx.AsyncClient() as client:
            response = await client.get(
                api_url,
                params={'expand': 'body.storage'}
            )
            response.raise_for_status()
            data = response.json()
            title = data['title']
            html = data['body']['storage']['value']
            content = self._clear_html(html)

            checksum = hashlib.sha256(content.encode('utf-8')).hexdigest()

            return DocumentAddSchema(
                source_type='confluence',
                source_url=url,
                title=title,
                content=content,
                checksum=checksum
            )
        



    def _extract_page_id(self, url: str) -> str:
        return url.split('/pages/', 1)[1].split('/', 1)[0]

    def _clear_html(self, html: str) -> str:
        soup = BeautifulSoup(html, 'html.parser')
        for image in soup.find_all('ac:image'):
            image.decompose()

        for macro in soup.find_all('ac:structured-macro'):
            if macro.get('ac:name') in {'jira', 'status', 'toc', 'anchor'}:
                macro.decompose()
        text = soup.get_text(separator=" ", strip=True)

        return ' '.join(text.split())






