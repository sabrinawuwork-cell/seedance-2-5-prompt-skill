"""Parse the blocks of a canvas prompt, preserving quoted dialogue."""
from __future__ import annotations

from dataclasses import dataclass
import re


CATEGORY_NAMES = ('画面', '动作/表情', '情感解析', '声音', '光影', '背景', '环境', '群演', '外观')
KNOWN_NAMES = CATEGORY_NAMES + ('音色', '音色状态', '固定类别', '剪辑')
_QUOTE_PAIRS = {'“': '”', '‘': '’', '「': '」', '『': '』', '"': '"'}


def normalized_text(text: str) -> str:
    return re.sub(r'<br\s*/?>', '\n', text, flags=re.I).replace('\r\n', '\n').replace('\r', '\n')


@dataclass(frozen=True)
class PromptBlock:
    text: str
    label: str | None
    body: str


def prompt_blocks(text: str) -> list[PromptBlock]:
    """Blank-line blocks, respecting quoted text; labels only at block starts."""
    raw = normalized_text(text).strip()
    chunks: list[str] = []
    start = 0
    index = 0
    closing: list[str] = []
    while index < len(raw):
        char = raw[index]
        if char == '\\' and index + 1 < len(raw):
            index += 2
            continue
        if closing and char == closing[-1]:
            closing.pop()
        elif char in _QUOTE_PAIRS:
            closing.append(_QUOTE_PAIRS[char])
        separator = re.match(r'\n(?:[ \t]*\n)+', raw[index:]) if char == '\n' and not closing else None
        if separator:
            chunks.append(raw[start:index].strip())
            index += separator.end()
            start = index
            continue
        index += 1
    chunks.append(raw[start:].strip())
    result = []
    for chunk in chunks:
        if not chunk:
            continue
        label = next((name for name in KNOWN_NAMES if chunk.startswith(name + '：')), None)
        body = chunk[len(label) + 1:].strip() if label else chunk
        result.append(PromptBlock(chunk, label, body))
    return result
