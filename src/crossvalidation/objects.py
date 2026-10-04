"""Which building (object) a piece of a real document talks about.

A project package often describes several buildings in one explanatory note.
Objects are discovered from numbered headings ("5.2 Здание цеха") that are not
inside a table and contain an object noun. A position in the text is then
attributed to an object by, in order of priority:

1. a mention in the same sentence ("объём здания цеха равен ..."), if exactly
   one object is mentioned — by abbreviation of the name ("АБК" for
   "Административно-бытовой корпус") or by a word stem that belongs to one
   object only;
2. the nearest preceding object heading; a heading of the same or a higher
   level that is not an object ends its scope.

Otherwise the position is unresolved and callers must not guess.
"""

from __future__ import annotations

import bisect
import re
from dataclasses import dataclass, field

from src.ingestion.real import Page, TextLine

OBJECT_NOUN_RE = re.compile(
    r"здани|корпус|\bцех|блок|сооружени|склад|пристройк|котельн|гараж|навес|ғимарат|ангар", re.IGNORECASE
)
TRAILING_VALUE_RE = re.compile(r"\d[.,]\d+$")  # a table row the table finder missed, not a heading
HEADING_RE = re.compile(r"^(\d{1,2}(?:\.\d{1,2})*)\.?\s*([^\W\d_].{2,80}?)\s*\.?$")
# words too common to identify an object on their own
GENERIC_WORDS = frozenset({"здание", "здания", "сооружение", "объект", "строение", "ғимарат", "ғимараты", "блок"})
SITE_RE = re.compile(r"площадк\w*|участ\w* строительств\w*|алаң\w*", re.IGNORECASE)


def _stem(word: str) -> str:
    return word[: max(3, min(7, len(word) - 2))].lower()


def _words(name: str) -> list[str]:
    return [w for w in re.split(r"[\s\-–]+", name) if w]


@dataclass
class DocObject:
    id: str
    name: str
    abbrev: str
    stems: set[str] = field(default_factory=set)


@dataclass
class ObjectIndex:
    objects: list[DocObject]

    def by_id(self) -> dict[str, DocObject]:
        return {o.id: o for o in self.objects}

    def mentioned(self, text: str) -> set[str]:
        found = set()
        for o in self.objects:
            if len(o.abbrev) >= 2 and re.search(rf"(?<!\w){re.escape(o.abbrev)}(?!\w)", text):
                found.add(o.id)
            elif any(re.search(rf"(?<!\w){re.escape(s)}\w*", text, re.IGNORECASE) for s in o.stems):
                found.add(o.id)
        return found


def _in_table(page: Page, line: TextLine) -> bool:
    return any(t.bbox[1] - 1 <= line.top <= t.bbox[3] for t in page.tables)


def _heading(page: Page, line: TextLine) -> tuple[int, str] | None:
    """(level, title) if the line looks like a numbered heading outside tables."""
    m = HEADING_RE.match(line.text)
    if not m or _in_table(page, line) or len(m.group(2).split()) > 8 or TRAILING_VALUE_RE.search(m.group(2)):
        return None
    return m.group(1).count(".") + 1, m.group(2).strip(" .")


def _is_object_title(title: str) -> bool:
    return bool(OBJECT_NOUN_RE.search(title)) and len(title.split()) <= 6


def object_headings(pages: list[Page]) -> list[str]:
    names: list[str] = []
    for page in pages:
        for line in page.lines:
            h = _heading(page, line)
            if h and _is_object_title(h[1]) and h[1].lower() not in (n.lower() for n in names):
                names.append(h[1])
    return names


def build_index(names: list[str]) -> ObjectIndex:
    """Objects obj1..objN with abbreviations and word stems unique to one object."""
    objects = []
    for i, name in enumerate(names, start=1):
        words = _words(name)
        abbrev = "".join(w[0].upper() for w in words) if len(words) >= 2 else ""
        stems = {_stem(w) for w in words if len(w) >= 3 and w.lower() not in GENERIC_WORDS}
        objects.append(DocObject(f"obj{i}", name, abbrev, stems))
    # a stem shared by several objects identifies none of them
    for o in objects:
        o.stems = {s for s in o.stems if sum(s in p.stems for p in objects) == 1}
    return ObjectIndex(objects)


def discover_objects(pages: list[Page]) -> ObjectIndex:
    return build_index(object_headings(pages))


@dataclass
class PageText:
    """Whitespace-normalized page text with the heading context of every line."""

    page: int
    text: str
    line_starts: list[int]
    line_tops: list[float]
    line_ctx: list[str | None]
    ctx_after: str | None  # context carried to the next page

    def context_at(self, pos: int) -> str | None:
        i = bisect.bisect_right(self.line_starts, pos) - 1
        return self.line_ctx[max(i, 0)] if self.line_ctx else None

    def context_above(self, top: float, carried: str | None) -> str | None:
        ctx = carried
        for t, c in zip(self.line_tops, self.line_ctx, strict=True):
            if t < top:
                ctx = c
        return ctx

    def sentence(self, start: int, end: int) -> str:
        s = max(self.text.rfind(". ", 0, start) + 2, 0)
        e = self.text.find(". ", end)
        return self.text[s: e if e >= 0 else len(self.text)]


def page_texts(pages: list[Page], index: ObjectIndex) -> list[PageText]:
    by_name = {o.name.lower(): o.id for o in index.objects}
    out = []
    ctx: str | None = None
    ctx_level = 0
    for page in pages:
        text, starts, tops, ctxs = "", [], [], []
        for line in page.lines:
            h = _heading(page, line)
            if h:
                level, title = h
                if title.lower() in by_name:
                    ctx, ctx_level = by_name[title.lower()], level
                elif ctx is not None and level <= ctx_level:
                    ctx, ctx_level = None, 0
            if text:
                text += " "
            starts.append(len(text))
            tops.append(line.top)
            ctxs.append(ctx)
            text += line.text
        carried = out[-1].ctx_after if out else None
        out.append(PageText(page.number, text, starts, tops, ctxs, ctx if page.lines else carried))
    return out


def resolve(pt: PageText, index: ObjectIndex, start: int, end: int) -> tuple[str | None, str]:
    """(object id or None, how it was resolved) for a span of ``pt.text``."""
    mentioned = index.mentioned(pt.sentence(start, end))
    if len(mentioned) == 1:
        return next(iter(mentioned)), "mention"
    ctx = pt.context_at(start)
    if ctx is not None:
        return ctx, "heading"
    return None, "ambiguous mention" if mentioned else "no heading or mention"
