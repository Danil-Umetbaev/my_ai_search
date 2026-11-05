"""Download customer documentation with illustrations; index a separate database."""
import argparse
import asyncio
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, Doctype, ProcessingInstruction
from pypdf import PdfReader

from src.ai.ingestion.confluence import ConfluenceKnowledgeSource
from src.schemas.documents import DocumentAddSchema
from src.ai.ingestion.text_cleanup import clean_article, extract_pdf_page
from src.ai.ingestion.pdf_sections import group_pages, section_starts

ROOT = Path(__file__).resolve().parents[3] / "data"
ASSETS = ROOT / "knowledge_assets"


async def download(urls, pirit):
    ASSETS.mkdir(parents=True, exist_ok=True)
    documents, failures = [], []
    async with httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
        for url in urls:
            try:
                response = await client.get(url)
                response.raise_for_status()
                if response.content.startswith(b"%PDF"):
                    path = ASSETS / (hashlib.sha256(url.encode()).hexdigest() + ".pdf")
                    path.write_bytes(response.content)
                    documents.extend(pdf_documents(path, url, "АТОЛ", ["FPrint-22ПТК"], "5.0"))
                    continue
                soup = BeautifulSoup(response.text, "html.parser")
                article = soup.select_one('.articles__page-instructions')
                heading = soup.find('h1')
                if not article or not heading:
                    raise ValueError("No article body; category pages are not documents")
                title = heading.get_text(' ', strip=True)
                images = []
                for position, img in enumerate(article.find_all('img')):
                    src = img.get('data-src') or img.get('src')
                    if not src:
                        continue
                    image_url = urljoin(str(response.url), src)
                    picture = await client.get(image_url)
                    picture.raise_for_status()
                    mime = picture.headers.get('content-type', '').split(';')[0]
                    ext = {'image/png': '.png', 'image/jpeg': '.jpg', 'image/webp': '.webp', 'image/gif': '.gif', 'image/svg+xml': '.svg'}.get(mime)
                    if not ext:
                        raise ValueError(f"Unexpected image content type: {mime}")
                    filename = hashlib.sha256(picture.content).hexdigest() + ext
                    (ASSETS / filename).write_bytes(picture.content)
                    caption = img.get('alt') or img.get('title') or ''
                    images.append(dict(source_url=image_url, local_path=f"knowledge_assets/{filename}", caption=caption, position=position))
                    img.replace_with(soup.new_string(f"\n[Иллюстрация {position + 1}: {caption or title}]\n"))
                for node in article.select('script, style'):
                    node.decompose()
                for node in list(article.descendants):
                    if isinstance(node, (Doctype, ProcessingInstruction)):
                        node.extract()
                content = clean_text(ConfluenceKnowledgeSource()._render(article))
                if len(content) < 80:
                    raise ValueError("Article text is too short")
                documents.append(record(url, title, content, 'Дримкас', [], None, None, images))
                print(f"Downloaded: {title} ({len(images)} images)", flush=True)
            except Exception as error:
                failures.append(dict(url=url, error=str(error)))
                print(f"FAILED {url}: {error}", flush=True)
    if pirit:
        target = ASSETS / 'pirit-2f-manual.pdf'
        target.write_bytes(pirit.read_bytes())
        documents.extend(pdf_documents(target, '/api/v1/knowledge-assets/pirit-2f-manual.pdf', None, ['Пирит 2Ф'], None))
    (ASSETS / 'documents.json').write_text(json.dumps(documents, ensure_ascii=False, indent=2), encoding='utf-8')
    (ASSETS / 'failures.json').write_text(json.dumps(failures, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Prepared {len(documents)} documents; {len(failures)} failures", flush=True)
    return len(failures)


def record(url, title, content, manufacturer, models, version, page, images):
    data = dict(source_type='pdf' if page else 'html', source_url=url, title=title, content=content,
                manufacturer=manufacturer, equipment_models=models, software_version=version,
                page_number=page, images=images)
    data['checksum'] = hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return data


def clean_text(content):
    return clean_article(content)


def pdf_documents(path, url, manufacturer, models, version):
    result = []
    reader = PdfReader(path)
    for number, page in enumerate(reader.pages, 1):
        content = extract_pdf_page(page, number)
        images = []
        for position, picture in enumerate(page.images):
            suffix = Path(picture.name).suffix
            filename = hashlib.sha256(picture.data).hexdigest() + suffix
            (ASSETS / filename).write_bytes(picture.data)
            images.append(dict(source_url=f"{url}#page={number}", local_path=f"knowledge_assets/{filename}",
                               caption=f"Иллюстрация на странице {number}", page_number=number, position=position))
        if len(content.strip()) < 30 and not images:
            continue
        title = f"{' '.join(models)} — руководство, страница {number}"
        headings = re.findall(r'(?m)^##\s+\d+\.\s+(.+)$', content)
        if headings:
            title = f"{' '.join(models)} — {'; '.join(headings)}"[:512]
        content = content.strip() or title + '. Страница содержит иллюстрации; текст требует визуальной проверки.'
        result.append(record(f"{url}#page={number}", title, content, manufacturer, models, version, number, images))
    grouped = group_pages(result, section_starts(reader))
    for document in grouped:
        document.pop('checksum', None)
        document['checksum'] = hashlib.sha256(json.dumps(document, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return grouped


async def index(device='cpu'):
    from src.config import settings
    if settings.DB_NAME != 'customer_knowledge':
        raise RuntimeError('This importer only writes to customer_knowledge')
    from src.ai.chunking.token import TokenChunker
    from src.ai.embeddings.qwen import QwenEmbeddingProvider
    from src.services.document_indexer import DocumentIndexerService
    from src.utils.db import DBManager
    from src.database import async_session_maker
    documents = [DocumentAddSchema.model_validate(x) for x in json.loads((ASSETS / 'documents.json').read_text(encoding='utf-8'))]
    chunker = TokenChunker('Qwen/Qwen3-Embedding-0.6B', 120, 30)
    embedding = QwenEmbeddingProvider()
    if device != 'cpu':
        embedding.model.to(device)
        embedding.device = device
    async with DBManager(async_session_maker) as db:
        indexer = DocumentIndexerService(db, chunker, embedding)
        for position, document in enumerate(documents, 1):
            old = await db.documents.get_one_or_none(source_url=document.source_url)
            if old and old.checksum == document.checksum:
                continue
            saved = await db.documents.update_by_id(old.id, document) if old else await db.documents.add(document)
            count = await indexer.index_document(saved)
            await db.commit()
            print(f'[{position}/{len(documents)}] {document.title}: {count} chunks', flush=True)
        await db.documents.retire_missing_sources([document.source_url for document in documents])
        await db.commit()


def refresh_saved_documents():
    manifest = ASSETS / 'documents.json'
    old_documents = json.loads(manifest.read_text(encoding='utf-8'))
    documents, manuals = [], {}
    for document in old_documents:
        if document['source_type'] == 'pdf':
            manuals.setdefault(document['source_url'].split('#')[0], document)
        else:
            document['content'] = clean_article(document['content'])
            document.pop('checksum', None)
            document['checksum'] = hashlib.sha256(json.dumps(document, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
            documents.append(document)
    for url, sample in manuals.items():
        filename = 'pirit-2f-manual.pdf' if url.startswith('/') else hashlib.sha256(url.encode()).hexdigest() + '.pdf'
        documents.extend(pdf_documents(ASSETS / filename, url, sample['manufacturer'],
                                       sample['equipment_models'], sample['software_version']))
    manifest.write_text(json.dumps(documents, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Prepared {len(documents)} documents from saved files', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['download', 'refresh', 'index'])
    parser.add_argument('--pirit', type=Path)
    parser.add_argument('--device', choices=['cpu', 'cuda'], default='cpu')
    args = parser.parse_args()
    if args.action == 'index':
        asyncio.run(index(args.device))
    elif args.action == 'refresh':
        refresh_saved_documents()
    else:
        urls = [s.strip() for s in (ROOT / 'knowledge_urls.txt').read_text(encoding='utf-8').splitlines() if s.strip() and not s.lstrip().startswith('#')]
        raise SystemExit(bool(asyncio.run(download(urls, args.pirit))))


if __name__ == '__main__':
    main()
