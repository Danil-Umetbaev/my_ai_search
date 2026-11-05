"""Group PDF pages by the document's own bookmarks, not fixed-size windows."""


def section_starts(reader) -> dict[int, str]:
    starts = {}

    def visit(entries):
        for entry in entries:
            if isinstance(entry, list):
                visit(entry)
                continue
            page = reader.get_destination_page_number(entry)
            if page is not None and page >= 0:
                starts.setdefault(page + 1, str(entry.title))

    visit(reader.outline)
    return starts


def group_pages(pages: list[dict], starts: dict[int, str]) -> list[dict]:
    if not starts:
        return pages
    groups = []
    for page in pages:
        number = page['page_number']
        if not groups or number in starts:
            group = dict(page)
            if number in starts:
                model = ' '.join(page['equipment_models'])
                group['title'] = f"{model} — {starts[number]}"
            group['images'] = list(page['images'])
            groups.append(group)
        else:
            groups[-1]['content'] += '\n\n' + page['content']
            groups[-1]['images'].extend(page['images'])
    return groups
