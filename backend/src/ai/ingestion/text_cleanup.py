"""Text normalization shared by document importers."""
import re


def clean_article(text: str) -> str:
    text = re.sub(r'^html PUBLIC[^\n]*', '', text)
    text = re.sub(r'\[Иллюстрация \d+:[^\n]*\]', '', text)
    return re.sub(r'\n[ \t]*\n(?:[ \t]*\n)+', '\n\n', text).strip()


def clean_pdf_page(text: str, page_number: int) -> str:
    """Join visual line wraps, keeping paragraph and list boundaries."""
    lines = text.splitlines()
    nonempty = [i for i, line in enumerate(lines) if line.strip()]
    for index in nonempty[:1] + nonempty[-1:]:
        if lines[index].strip() == str(page_number):
            lines[index] = ''
    paragraphs, current = [], []
    for line in lines:
        line = re.sub(r'[ \t]+', ' ', line).strip()
        starts_item = bool(re.match(r'^(?:[●•]|\d+[.)])\s', line))
        if not line or starts_item:
            if current:
                paragraphs.append(' '.join(current))
                current = []
        if line:
            current.append(line)
    if current:
        paragraphs.append(' '.join(current))
    return '\n\n'.join(paragraphs)
