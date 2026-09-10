"""Compile .po translation files into binary .mo files without external dependencies."""

import os
import re
import struct


def parse_po(file_path):
    translations = {}
    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    # Match msgid and msgstr pairs (including multi-line strings)
    pattern = re.compile(
        r'msgid\s+((?:".*?"\s*)+)\s+msgstr\s+((?:".*?"\s*)+)',
        re.MULTILINE,
    )

    def unescape_po(s):
        parts = re.findall(r'"((?:[^"\\]|\\.)*)"', s)
        joined = "".join(parts)
        return (
            joined.replace("\\n", "\n")
            .replace("\\t", "\t")
            .replace('\\"', '"')
            .replace("\\\\", "\\")
        )

    for match in pattern.finditer(content):
        raw_id = match.group(1)
        raw_str = match.group(2)
        msgid = unescape_po(raw_id)
        msgstr = unescape_po(raw_str)
        translations[msgid] = msgstr

    return translations


def compile_to_mo(translations, mo_path):
    keys = sorted(translations.keys())
    num_strings = len(keys)

    orig_table_offset = 28
    trans_table_offset = orig_table_offset + num_strings * 8
    strings_offset = trans_table_offset + num_strings * 8

    orig_entries = []
    trans_entries = []
    strings_data = bytearray()

    for k in keys:
        b = k.encode("utf-8") + b"\x00"
        orig_entries.append((len(k.encode("utf-8")), strings_offset + len(strings_data)))
        strings_data.extend(b)

    for k in keys:
        v = translations[k]
        b = v.encode("utf-8") + b"\x00"
        trans_entries.append((len(v.encode("utf-8")), strings_offset + len(strings_data)))
        strings_data.extend(b)

    header = struct.pack(
        "<Iiiiiii",
        0x950412DE,
        0,
        num_strings,
        orig_table_offset,
        trans_table_offset,
        0,
        0,
    )

    orig_table = bytearray()
    for length, offset in orig_entries:
        orig_table.extend(struct.pack("<ii", length, offset))

    trans_table = bytearray()
    for length, offset in trans_entries:
        trans_table.extend(struct.pack("<ii", length, offset))

    with open(mo_path, "wb") as f:
        f.write(header + orig_table + trans_table + strings_data)


def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    locale_dir = os.path.join(base_dir, "locale")
    for lang in ("tr", "en"):
        po_path = os.path.join(locale_dir, lang, "LC_MESSAGES", "messages.po")
        mo_path = os.path.join(locale_dir, lang, "LC_MESSAGES", "messages.mo")
        if os.path.exists(po_path):
            trans = parse_po(po_path)
            compile_to_mo(trans, mo_path)
            print(f"Compiled {len(trans)} entries for {lang} -> {mo_path}")


if __name__ == "__main__":
    main()
