import json
import re
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class EvidencePassage:
    title: str
    section: str
    text: str

    @property
    def ranking_text(self):
        return f"{self.title}\n{self.section}\n{self.text}"


def compatible_title(title, question):
    query = question.casefold()
    platforms = {
        'setretail10', 'setretail', 'set10', 'settouch', 'setcentrum',
        'setcentrum10', 'setkit', 'setloyalty', 'pos', 'касса', 'клавиатурная касса',
    }
    formats = {'XML', 'JSON', 'CSV', 'HTTP', 'HTTPS', 'HTML', 'HTML5', 'PDF', 'SQL', 'POS'}
    parts = [p.strip(' ▪️◾️') for p in re.split('[▪◾]', title) if p.strip(' ▪️◾️')]
    if len(parts) > 1 and parts[0].casefold() not in platforms:
        prefix = parts[0].casefold()
        words = re.findall(r'[а-яёa-z]{4,}', prefix)
        if prefix not in query and not any(word[:5] in query for word in words):
            return False
    for name in re.findall(r'\b[A-Za-z][A-Za-z0-9_-]{2,}\b', title):
        if (not name.islower() and not name.startswith('Set')
                and name.upper() not in formats and name.casefold() not in platforms
                and name.casefold() not in query):
            return False
    return True


def _units(body):
    path, label, result = [], '', []
    body = body.replace('\n[… ]\n', '\n\n')
    for paragraph in re.split(r'\n\s*\n', body):
        text = paragraph.strip()
        if not text or re.fullmatch(r'[#*\-\s]+', text):
            continue
        if text.startswith('Раздел документа: '):
            first, _, text = text.partition('\n')
            path = list(enumerate(first.removeprefix('Раздел документа: ').split(' → '), 1))
            label = ''
            text = text.strip()
            if not text:
                continue
        if re.fullmatch(r'#{1,6} [^\n]+', text):
            level = len(text) - len(text.lstrip('#'))
            while path and path[-1][0] >= level:
                path.pop()
            path.append((level, text[level:].strip()))
            label = ''
            continue
        if text.endswith(':') and '\n' not in text and len(text) < 100:
            label = text
            continue
        table = ' | ' in text and '```' not in text
        pieces = text.splitlines() if table else [text]
        for piece in pieces:
            value = piece.strip()
            if value:
                names = [name for _, name in path] + ([label.rstrip(':')] if label else [])
                result.append((' → '.join(names),
                               (label + '\n' if label else '') + value, table))
        label = ''
    return result


def collect_evidence(context, question, max_section_chars=4500):
    passages = []
    for block in context.split('\n\n---\n\n'):
        title, _, body = block.partition('\n')
        title = title.removeprefix('Документ: ').strip()
        if not compatible_title(title, question):
            continue
        units = _units(body)
        if (len(body) <= 3500 and '[… ]' not in body and 'Раздел документа:' not in body
                and re.search(r'(?m)^#{1,6} ', body)):
            passages.append(EvidencePassage(title, '', body.strip()))
        groups = {}
        for index, (section, text, table) in enumerate(units):
            groups.setdefault((section, index if table else None), []).append(text)
        for (section, row), texts in groups.items():
            joined = '\n\n'.join(texts)
            bodies = [joined] if len(joined) <= max_section_chars else texts
            passages.extend(EvidencePassage(title, section, text) for text in bodies)
            if section and row is None:
                descendants = [(scope, text) for scope, text, _ in units
                               if scope == section or scope.startswith(section + ' → ')]
                if any(scope != section for scope, _ in descendants):
                    parts, previous = [], section
                    for scope, text in descendants:
                        if scope != previous:
                            parts.append('### ' + scope.removeprefix(section + ' → '))
                            previous = scope
                        parts.append(text)
                    combined = '\n\n'.join(parts)
                    if len(combined) <= max_section_chars:
                        passages.append(EvidencePassage(title, section, combined))
    return list(dict.fromkeys(passages))


def serialize_evidence(passages):
    return json.dumps({'evidence': [asdict(p) for p in passages]}, ensure_ascii=False)


def deserialize_evidence(context):
    data = json.loads(context)
    if not isinstance(data, dict) or not isinstance(data.get('evidence'), list):
        raise ValueError('Invalid evidence context')
    passages = []
    for item in data['evidence']:
        if (not isinstance(item, dict)
                or not all(isinstance(item.get(k), str) for k in ('title', 'section', 'text'))):
            raise ValueError('Invalid evidence passage')
        passages.append(EvidencePassage(item['title'], item['section'], item['text']))
    return passages


def render_answer(passage):
    answer = (passage.section + '\n\n' if passage.section else '') + passage.text
    if re.search(r'(?:нажмите|кликните|клавиш[ау]|кнопк[ау])\s*[.→)]', answer, re.I):
        answer += '\n\nВ текстовой выгрузке пропущены обозначения некоторых кнопок; они доступны в исходной инструкции.'
    return answer


def split_evidence_blocks(passages):
    blocks = []
    seen = set()
    for passage in passages:
        parent = passage.section.split(' → ') if passage.section else []
        for scope, text, _ in _units(passage.text):
            child = scope.split(' → ') if scope else []
            overlap = next((size for size in range(min(len(parent), len(child)), 0, -1)
                            if parent[-size:] == child[:size]), 0)
            section = ' → '.join(parent + child[overlap:])
            identity = (passage.title, section, text)
            if identity not in seen:
                blocks.append(EvidencePassage(passage.title, section, text))
                seen.add(identity)
    return blocks


def render_evidence_blocks(passages):
    parts, previous, seen = [], None, set()
    for passage in passages:
        identity = (passage.title, passage.section, passage.text)
        if identity in seen:
            continue
        seen.add(identity)
        scope = (passage.title, passage.section)
        if scope != previous and passage.section:
            parts.append(passage.section)
        parts.append(passage.text)
        previous = scope
    answer = '\n\n'.join(parts)
    if re.search(r'(?:нажмите|кликните|клавиш[ау]|кнопк[ау])\s*[.→)]', answer, re.I):
        answer += '\n\nВ текстовой выгрузке пропущены обозначения некоторых кнопок; они доступны в исходной инструкции.'
    return answer
