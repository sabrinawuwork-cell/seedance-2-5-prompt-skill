#!/usr/bin/env python3
"""Dependency-free parsing helpers for shotlist tooling."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Sequence


@dataclass(frozen=True)
class Frontmatter:
    values: dict[str, str]
    body_start_line: int
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class MarkdownTable:
    headers: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    header_line: int
    row_lines: tuple[int, ...]
    context: str


def parse_frontmatter(text: str) -> Frontmatter:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return Frontmatter({}, 1, ("缺少以 --- 开始的 frontmatter",))
    closing = next(
        (index for index in range(1, len(lines)) if lines[index].strip() == "---"),
        None,
    )
    if closing is None:
        return Frontmatter({}, 1, ("frontmatter 缺少结束分隔符 ---",))

    values: dict[str, str] = {}
    errors: list[str] = []
    active_mapping: str | None = None
    for line_no, raw in enumerate(lines[1:closing], start=2):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if raw[:1].isspace():
            if active_mapping and ":" in stripped:
                key, value = stripped.split(":", 1)
                entry = f"{key.strip()}: {value.strip()}"
                values[active_mapping] = (
                    values.get(active_mapping, "") + "\n" + entry
                ).strip()
            else:
                errors.append(f"第 {line_no} 行：不支持的 frontmatter 缩进")
            continue
        if ":" not in raw:
            errors.append(f"第 {line_no} 行：frontmatter 字段必须使用 key: value")
            continue
        key, value = raw.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", key):
            errors.append(f"第 {line_no} 行：非法 frontmatter 键 {key!r}")
            continue
        if key in values:
            errors.append(f"第 {line_no} 行：frontmatter 字段 {key!r} 重复")
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key] = value
        active_mapping = key if not value else None
    return Frontmatter(values, closing + 2, tuple(errors))


def split_markdown_row(line: str) -> list[str] | None:
    stripped = line.strip()
    if not stripped.startswith("|"):
        return None
    cells: list[str] = []
    current: list[str] = []
    escaped = False
    in_code = False
    for char in stripped[1:]:
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            current.append(char)
            escaped = True
        elif char == "`":
            current.append(char)
            in_code = not in_code
        elif char == "|" and not in_code:
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    if current or not stripped.endswith("|"):
        cells.append("".join(current).strip())
    return cells


def _separator(cells: Sequence[str]) -> bool:
    return bool(cells) and all(
        re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells
    )


def _visible_lines(lines: Sequence[str]) -> list[str]:
    visible: list[str] = []
    fence: str | None = None
    in_comment = False
    for line in lines:
        stripped = line.lstrip()
        if fence:
            visible.append("")
            if stripped.startswith(fence):
                fence = None
            continue
        marker = re.match(r"^(`{3,}|~{3,})", stripped)
        if marker:
            fence = marker.group(1)
            visible.append("")
            continue
        output = line
        if in_comment:
            if "-->" not in output:
                visible.append("")
                continue
            output = output.split("-->", 1)[1]
            in_comment = False
        while "<!--" in output:
            before, after = output.split("<!--", 1)
            if "-->" in after:
                output = before + after.split("-->", 1)[1]
            else:
                output = before
                in_comment = True
        visible.append(output)
    return visible


def find_tables(text: str) -> list[MarkdownTable]:
    lines = text.splitlines()
    visible = _visible_lines(lines)
    tables: list[MarkdownTable] = []
    index = 0
    while index + 1 < len(lines):
        headers = split_markdown_row(visible[index])
        separator = split_markdown_row(visible[index + 1])
        if not headers or not separator or not _separator(separator):
            index += 1
            continue
        row_index = index + 2
        rows: list[tuple[str, ...]] = []
        row_lines: list[int] = []
        while row_index < len(lines):
            cells = split_markdown_row(visible[row_index])
            if cells is None or _separator(cells):
                break
            rows.append(tuple(cells))
            row_lines.append(row_index + 1)
            row_index += 1
        context = ""
        for prior in range(index - 1, max(-1, index - 12), -1):
            candidate = visible[prior].strip()
            if candidate.startswith("#"):
                context = re.sub(r"^#+\s*", "", candidate).strip()
                break
        tables.append(
            MarkdownTable(
                tuple(headers), tuple(rows), index + 1, tuple(row_lines), context
            )
        )
        index = max(row_index, index + 2)
    return tables
