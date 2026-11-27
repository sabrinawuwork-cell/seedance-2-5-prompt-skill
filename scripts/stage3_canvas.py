"""Read scene-global cells and their adjacent shot tables in editing order."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from content_contract import prompt_blocks
from shotlist_common import find_tables, parse_frontmatter

HEADERS = ('镜号', '片段', '时长', '分镜内容', 'Seedance提示词')


def scenes(text):
    if parse_frontmatter(text).values.get('stage2_content') == 'categories-only':
        raise ValueError('请提供对应场次的全局提示词正文，当前文件只有类别')
    tables = [t for t in find_tables(text) if '镜号' in t.headers or any('全局提示词' in h for h in t.headers)]
    if not tables or len(tables) % 2:
        raise ValueError('每场必须先有全局提示词单元格，再有逐镜表')
    result = {}
    for global_table, shots in zip(tables[::2], tables[1::2]):
        match = re.fullmatch(r'场次\s*(\d+(?:-\d+)?)(（续(?:[2-9]\d*|1\d+)?）)?\s*全局提示词', global_table.headers[0])
        if not match or len(global_table.headers) != 1 or len(global_table.rows) != 1 or len(global_table.rows[0]) != 1:
            raise ValueError('全局表须有场号、一列和一个正文单元格')
        scene = match[1]
        section = scene + (match[2] or '')
        if match[2] and scene not in result:
            raise ValueError(f'续场 {section} 缺少首段')
        if section in result or not shots.rows or shots.headers not in (HEADERS, HEADERS + ('备注',)):
            raise ValueError(f'场次 {scene} 的逐镜表或场次顺序错误')
        cell = re.sub(r'<br\s*/?>', '\n', global_table.rows[0][0], flags=re.I)
        if not cell.strip():
            raise ValueError(f'场次 {scene} 缺少全局提示词正文')
        for row in shots.rows:
            if len(row) != len(shots.headers) or not all(x.strip() for x in row[:5]) or not re.match(rf'^{scene}[A-Za-z]', row[0]):
                raise ValueError(f'场次 {scene} 出现错场或不完整的镜头行')
            blocks = prompt_blocks(row[4])
            labels = [b.label for b in blocks]
            if ('动作/表情' not in labels or labels.count('情感解析') != 1
                    or labels.index('情感解析') != labels.index('动作/表情') + 1
                    or not blocks[labels.index('情感解析')].body.strip()):
                raise ValueError(f'{row[0]} 动作/表情后须紧接情感解析')
        result[section] = (cell, shots)
    headers = next(iter(result.values()))[1].headers
    if any(t.headers != headers for _, t in result.values()):
        raise ValueError('各场逐镜表须统一五列或条件六列')
    if len(headers) == 6 and not any(r[5].strip() for _, t in result.values() for r in t.rows):
        raise ValueError('全表无备注时请使用五列')
    return result


if __name__ == '__main__':
    text = Path(sys.argv[1]).read_text(encoding='utf-8-sig')
    groups = scenes(text)
    print(json.dumps([dict(scene=k, globalPrompt=c, headers=t.headers, rows=t.rows) for k, (c,t) in groups.items()], ensure_ascii=False))
