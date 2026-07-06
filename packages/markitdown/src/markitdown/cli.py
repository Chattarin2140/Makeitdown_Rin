from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="markitdown",
        description="Convert supported files to Markdown.",
    )
    parser.add_argument("input", help="Path to the source file")
    parser.add_argument(
        "-o",
        "--output",
        help="Write the Markdown output to a file instead of stdout",
    )
    args = parser.parse_args(argv)

    source_path = Path(args.input)
    markdown = convert_to_markdown(source_path)

    if args.output:
        Path(args.output).write_text(markdown, encoding="utf-8")
    else:
        sys.stdout.write(markdown)

    return 0


def convert_to_markdown(source_path: Path) -> str:
    if not source_path.exists():
        raise FileNotFoundError(source_path)

    suffix = source_path.suffix.lower()
    if suffix == ".xlsx":
        return xlsx_to_markdown(source_path)

    return source_path.read_text(encoding="utf-8")


def xlsx_to_markdown(source_path: Path) -> str:
    with zipfile.ZipFile(source_path) as archive:
        shared_strings = _read_shared_strings(archive)
        sheets = _read_sheet_targets(archive)

        sections: list[str] = []
        for sheet_name, sheet_target in sheets:
            sheet_xml = archive.read(sheet_target)
            table = _sheet_xml_to_markdown(sheet_xml, shared_strings)
            sections.append(f"## {sheet_name}\n\n{table}")

    return "\n\n".join(sections).rstrip() + "\n"


def _read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        xml = archive.read("xl/sharedStrings.xml")
    except KeyError:
        return []

    root = ET.fromstring(xml)
    namespace = _namespace(root.tag)
    strings: list[str] = []

    for item in root.findall(f"{namespace}si"):
        text = "".join(node.text or "" for node in item.findall(f".//{namespace}t"))
        strings.append(text)

    return strings


def _read_sheet_targets(archive: zipfile.ZipFile) -> list[tuple[str, str]]:
    workbook_root = ET.fromstring(archive.read("xl/workbook.xml"))
    workbook_ns = _namespace(workbook_root.tag)

    rels_root = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    rels_ns = _namespace(rels_root.tag)
    rel_targets = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in rels_root.findall(f"{rels_ns}Relationship")
    }

    sheets: list[tuple[str, str]] = []
    for sheet in workbook_root.findall(f"{workbook_ns}sheets/{workbook_ns}sheet"):
        sheet_name = sheet.attrib["name"]
        rel_id = sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        target = rel_targets[rel_id]
        if not target.startswith("xl/"):
            target = f"xl/{target.lstrip('/') }"
        sheets.append((sheet_name, target))

    return sheets


def _sheet_xml_to_markdown(sheet_xml: bytes, shared_strings: list[str]) -> str:
    root = ET.fromstring(sheet_xml)
    namespace = _namespace(root.tag)

    rows: list[list[str]] = []
    max_columns = 0

    for row in root.findall(f"{namespace}sheetData/{namespace}row"):
        row_values: dict[int, str] = {}
        for cell in row.findall(f"{namespace}c"):
            ref = cell.attrib.get("r", "A1")
            column_index = _column_index(ref)
            row_values[column_index] = _cell_value(cell, namespace, shared_strings)
            max_columns = max(max_columns, column_index)
        rows.append([row_values.get(index, "") for index in range(1, max_columns + 1)])

    if not rows or max_columns == 0:
        return "(empty sheet)"

    header = rows[0]
    data_rows = rows[1:] if len(rows) > 1 else []
    column_count = max(1, len(header))
    header = header + [""] * (column_count - len(header))

    lines = [
        "| " + " | ".join(_escape_markdown_cell(value) for value in header) + " |",
        "| " + " | ".join("---" for _ in range(column_count)) + " |",
    ]

    for row in data_rows:
        row = row + [""] * (column_count - len(row))
        lines.append("| " + " | ".join(_escape_markdown_cell(value) for value in row[:column_count]) + " |")

    return "\n".join(lines)


def _cell_value(cell: ET.Element, namespace: str, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    value = cell.findtext(f"{namespace}v", default="") or ""

    if cell_type == "s":
        try:
            return shared_strings[int(value)]
        except (ValueError, IndexError):
            return value

    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(f".//{namespace}t"))

    if cell_type == "b":
        return "TRUE" if value == "1" else "FALSE"

    return value


def _namespace(tag: str) -> str:
    if tag.startswith("{"):
        return tag.split("}", 1)[0] + "}"
    return ""


def _column_index(cell_reference: str) -> int:
    index = 0
    for character in cell_reference:
        if not character.isalpha():
            break
        index = index * 26 + (ord(character.upper()) - ord("A") + 1)
    return index


def _escape_markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").replace("\r", " ")