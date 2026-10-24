import hashlib
import re
import httpx
from bs4 import BeautifulSoup, Comment, NavigableString, Tag
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
        for element in soup.find_all(['ac:image', 'img', 'script', 'style', 'ac:parameter']):
            element.decompose()

        for macro in soup.find_all('ac:structured-macro'):
            if macro.get('ac:name') in {'jira', 'status', 'toc', 'anchor'}:
                macro.decompose()
        text = self._render(soup)
        return re.sub(r'\n[ \t]*\n(?:[ \t]*\n)+', '\n\n', text).strip()

    def _render(self, node) -> str:
        if isinstance(node, Comment):
            return ''
        if isinstance(node, NavigableString):
            return re.sub(r'\s+', ' ', str(node))
        if not isinstance(node, Tag):
            return ''
        if node.name == 'br':
            return '\n'
        if node.name in {'pre', 'ac:plain-text-body'}:
            return '\n\n```\n' + node.get_text().strip() + '\n```\n\n'
        if node.name == 'ac:link':
            body = node.find(['ac:link-body', 'ac:plain-text-link-body'])
            if body is not None:
                return self._render(body)
            page = node.find('ri:page')
            return page.get('ri:content-title', '') if page else ''
        if node.name in {'ul', 'ol'}:
            items = []
            for index, item in enumerate(node.find_all('li', recursive=False), 1):
                value = self._render(item).strip()
                prefix = f'{index}. ' if node.name == 'ol' else '- '
                items.append(prefix + value.replace('\n', '\n  '))
            return '\n\n' + '\n'.join(items) + '\n\n'
        if node.name == 'table':
            rows = []
            headers = []
            for row in node.find_all('tr'):
                if row.find_parent('table') is not node:
                    continue
                cells = row.find_all(['th', 'td'], recursive=False)
                values = [self._render(cell).strip() for cell in cells]
                if not values:
                    continue
                if all(cell.name == 'th' for cell in cells):
                    headers = [' '.join(value.split()) for value in values]
                    continue
                values = [value.replace('\n', '; ') for value in values]
                if headers and len(headers) == len(values):
                    values = [f'{label}: {value}' for label, value in zip(headers, values)]
                rows.append(' | '.join(values))
            return '\n\n' + '\n'.join(rows) + '\n\n'
        value = ''.join(self._render(child) for child in node.children)
        if node.name in {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}:
            return '\n\n' + '#' * int(node.name[1]) + ' ' + value.strip() + '\n\n'
        if node.name in {'p', 'div', 'section', 'blockquote', 'ac:rich-text-body'}:
            return '\n\n' + value.strip() + '\n\n'
        return value






