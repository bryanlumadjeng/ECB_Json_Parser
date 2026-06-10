"""Dependency-free PDF text extraction (standard library only).

This is a focused PDF reader good enough to pull positioned text out of
modern PDFs such as the ECB supervisory guide: cross-reference streams,
compressed object streams, FlateDecode (with PNG/TIFF predictors) and
Type0/CID fonts with ToUnicode CMaps.

It is intentionally not a complete PDF implementation. It extracts text
fragments with their page, position and effective font size, groups them
into lines and then into blocks, and returns objects shaped like the rest
of the pipeline expects.

Only the Python standard library is used (``zlib`` for FlateDecode).
"""

from __future__ import annotations

import re
import zlib
from dataclasses import dataclass

WHITESPACE = b"\x00\t\n\x0c\r "
DELIMITERS = b"()<>[]{}/%"


# ---------------------------------------------------------------------------
# Low-level object model
# ---------------------------------------------------------------------------

class Ref:
    __slots__ = ("num", "gen")

    def __init__(self, num: int, gen: int):
        self.num = num
        self.gen = gen

    def __repr__(self):
        return f"Ref({self.num},{self.gen})"

    def __eq__(self, other):
        return isinstance(other, Ref) and other.num == self.num and other.gen == self.gen

    def __hash__(self):
        return hash((self.num, self.gen))


class Name(str):
    """A PDF /Name, kept distinct from ordinary strings."""


class Stream:
    __slots__ = ("dict", "raw")

    def __init__(self, d: dict, raw: bytes):
        self.dict = d
        self.raw = raw


# ---------------------------------------------------------------------------
# Tokenizer / object parser
# ---------------------------------------------------------------------------

class Lexer:
    """Parses PDF objects out of a byte buffer starting at a given position."""

    def __init__(self, buf: bytes, pos: int = 0):
        self.buf = buf
        self.pos = pos

    def _skip_ws(self):
        buf, n = self.buf, len(self.buf)
        while self.pos < n:
            c = buf[self.pos]
            if c in WHITESPACE:
                self.pos += 1
            elif c == 0x25:  # % comment
                while self.pos < n and buf[self.pos] not in b"\r\n":
                    self.pos += 1
            else:
                break

    def parse(self):
        self._skip_ws()
        buf = self.buf
        if self.pos >= len(buf):
            raise EOFError("unexpected end of PDF object")
        c = buf[self.pos]
        if c == 0x2F:  # /
            return self._name()
        if c == 0x28:  # (
            return self._literal_string()
        if c == 0x3C:  # <
            if buf[self.pos + 1:self.pos + 2] == b"<":
                return self._dict_or_stream()
            return self._hex_string()
        if c == 0x5B:  # [
            return self._array()
        if c == 0x5D or c == 0x3E:  # ] or >
            raise ValueError("unexpected closing token")
        return self._keyword_or_number()

    def _read_token(self) -> bytes:
        buf, n = self.buf, len(self.buf)
        start = self.pos
        while self.pos < n and buf[self.pos] not in WHITESPACE and buf[self.pos] not in DELIMITERS:
            self.pos += 1
        return buf[start:self.pos]

    def _name(self) -> Name:
        self.pos += 1  # skip /
        buf, n = self.buf, len(self.buf)
        out = bytearray()
        while self.pos < n:
            c = buf[self.pos]
            if c in WHITESPACE or c in DELIMITERS:
                break
            if c == 0x23 and self.pos + 2 < n:  # #xx hex escape
                out.append(int(buf[self.pos + 1:self.pos + 3], 16))
                self.pos += 3
                continue
            out.append(c)
            self.pos += 1
        return Name(out.decode("latin-1"))

    def _literal_string(self) -> bytes:
        self.pos += 1  # skip (
        buf, n = self.buf, len(self.buf)
        out = bytearray()
        depth = 1
        while self.pos < n:
            c = buf[self.pos]
            self.pos += 1
            if c == 0x5C:  # backslash escape
                e = buf[self.pos]
                self.pos += 1
                simple = {0x6E: 10, 0x72: 13, 0x74: 9, 0x62: 8, 0x66: 12,
                          0x28: 0x28, 0x29: 0x29, 0x5C: 0x5C}
                if e in simple:
                    out.append(simple[e])
                elif 0x30 <= e <= 0x37:  # octal
                    oct_digits = bytes([e])
                    for _ in range(2):
                        if self.pos < n and 0x30 <= buf[self.pos] <= 0x37:
                            oct_digits += buf[self.pos:self.pos + 1]
                            self.pos += 1
                    out.append(int(oct_digits, 8) & 0xFF)
                elif e in b"\r\n":  # line continuation
                    if e == 0x0D and self.pos < n and buf[self.pos] == 0x0A:
                        self.pos += 1
                else:
                    out.append(e)
            elif c == 0x28:
                depth += 1
                out.append(c)
            elif c == 0x29:
                depth -= 1
                if depth == 0:
                    break
                out.append(c)
            else:
                out.append(c)
        return bytes(out)

    def _hex_string(self) -> bytes:
        self.pos += 1  # skip <
        buf, n = self.buf, len(self.buf)
        digits = bytearray()
        while self.pos < n and buf[self.pos] != 0x3E:
            c = buf[self.pos]
            if c not in WHITESPACE:
                digits.append(c)
            self.pos += 1
        self.pos += 1  # skip >
        if len(digits) % 2:
            digits.append(0x30)
        return bytes(int(digits[i:i + 2], 16) for i in range(0, len(digits), 2))

    def _array(self) -> list:
        self.pos += 1  # skip [
        out = []
        while True:
            self._skip_ws()
            if self.pos >= len(self.buf):
                break
            if self.buf[self.pos] == 0x5D:  # ]
                self.pos += 1
                break
            out.append(self.parse())
        return out

    def _dict_or_stream(self):
        self.pos += 2  # skip <<
        d = {}
        while True:
            self._skip_ws()
            if self.buf[self.pos:self.pos + 2] == b">>":
                self.pos += 2
                break
            key = self.parse()  # a Name
            value = self.parse()
            d[key] = value
        # stream?
        save = self.pos
        self._skip_ws()
        if self.buf[self.pos:self.pos + 6] == b"stream":
            self.pos += 6
            if self.buf[self.pos:self.pos + 2] == b"\r\n":
                self.pos += 2
            elif self.buf[self.pos:self.pos + 1] in (b"\n", b"\r"):
                self.pos += 1
            return ("__stream__", d, self.pos)
        self.pos = save
        return d

    def _keyword_or_number(self):
        token = self._read_token()
        if token == b"true":
            return True
        if token == b"false":
            return False
        if token == b"null":
            return None
        if re.fullmatch(rb"[+-]?\d+", token):
            # Could be "num gen R" or "num gen obj" reference.
            save = self.pos
            self._skip_ws()
            t2 = self._read_token()
            if re.fullmatch(rb"\d+", t2):
                self._skip_ws()
                t3 = self._read_token()
                if t3 == b"R":
                    return Ref(int(token), int(t2))
                if t3 == b"obj":
                    return ("__objstart__", int(token), int(t2))
            self.pos = save
            return int(token)
        if re.fullmatch(rb"[+-]?\d*\.\d+", token) or re.fullmatch(rb"[+-]?\d+\.\d*", token):
            return float(token)
        return Name(token.decode("latin-1"))  # bare keyword/operator


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

def apply_predictor(data: bytes, predictor: int, colors: int, bpc: int, columns: int) -> bytes:
    if predictor < 2:
        return data
    bpp = max(1, (colors * bpc + 7) // 8)
    row_len = (colors * bpc * columns + 7) // 8
    if predictor == 2:  # TIFF predictor 2
        out = bytearray(data)
        for r in range(0, len(out), row_len):
            row = out[r:r + row_len]
            for i in range(bpp, len(row)):
                row[i] = (row[i] + row[i - bpp]) & 0xFF
            out[r:r + row_len] = row
        return bytes(out)
    # PNG predictors (10..15): each row prefixed with a filter-type byte.
    out = bytearray()
    prev = bytearray(row_len)
    stride = row_len + 1
    for r in range(0, len(data), stride):
        ftype = data[r]
        row = bytearray(data[r + 1:r + stride])
        if len(row) < row_len:
            row.extend(b"\x00" * (row_len - len(row)))
        for i in range(row_len):
            a = row[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            x = row[i]
            if ftype == 0:
                row[i] = x
            elif ftype == 1:
                row[i] = (x + a) & 0xFF
            elif ftype == 2:
                row[i] = (x + b) & 0xFF
            elif ftype == 3:
                row[i] = (x + (a + b) // 2) & 0xFF
            elif ftype == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                row[i] = (x + pr) & 0xFF
        out.extend(row)
        prev = row
    return bytes(out)


def decode_stream(d: dict, raw: bytes, resolve) -> bytes:
    filters = resolve(d.get("Filter"))
    if filters is None:
        return raw
    if isinstance(filters, (Name, str)):
        filters = [filters]
    parms = resolve(d.get("DecodeParms")) or resolve(d.get("DP"))
    if not isinstance(parms, list):
        parms = [parms] * len(filters)
    data = raw
    for filt, parm in zip(filters, parms):
        parm = resolve(parm) or {}
        if filt in ("FlateDecode", "Fl"):
            data = zlib.decompress(data)
            pred = resolve(parm.get("Predictor")) or 1
            if pred and pred > 1:
                data = apply_predictor(
                    data, pred,
                    resolve(parm.get("Colors")) or 1,
                    resolve(parm.get("BitsPerComponent")) or 8,
                    resolve(parm.get("Columns")) or 1,
                )
        elif filt in ("ASCIIHexDecode", "AHx"):
            data = bytes.fromhex(re.sub(rb"[^0-9A-Fa-f]", b"", data.split(b">")[0]).decode())
        elif filt in ("ASCII85Decode", "A85"):
            import base64
            data = base64.a85decode(data, adobe=True)
        else:
            # Image filters (DCT/CCITT/etc.) — not text, leave as-is.
            break
    return data


# ---------------------------------------------------------------------------
# Document: xref, object streams, object resolution
# ---------------------------------------------------------------------------

class PDFDocument:
    def __init__(self, data: bytes):
        self.data = data
        self.xref: dict[int, tuple] = {}   # objnum -> ('n', offset) | ('c', stmnum, idx)
        self.trailer: dict = {}
        self.cache: dict[int, object] = {}
        self._objstm_cache: dict[int, list] = {}
        self._load_xref()

    # -- xref loading -------------------------------------------------------

    def _load_xref(self):
        m = list(re.finditer(rb"startxref\s+(\d+)", self.data))
        if not m:
            raise ValueError("no startxref found")
        offset = int(m[-1].group(1))
        seen = set()
        while offset is not None and offset not in seen:
            seen.add(offset)
            offset = self._read_xref_at(offset)

    def _read_xref_at(self, offset: int):
        lex = Lexer(self.data, offset)
        lex._skip_ws()
        if self.data[lex.pos:lex.pos + 4] == b"xref":
            return self._read_xref_table(lex)
        return self._read_xref_stream(offset)

    def _read_xref_table(self, lex: Lexer):
        lex.pos += 4
        data = self.data
        while True:
            lex._skip_ws()
            if data[lex.pos:lex.pos + 7] == b"trailer":
                lex.pos += 7
                trailer = lex.parse()
                for k, v in trailer.items():
                    self.trailer.setdefault(k, v)
                if "XRefStm" in trailer:
                    self._read_xref_stream(int(trailer["XRefStm"]))
                prev = trailer.get("Prev")
                return int(prev) if prev is not None else None
            start = lex.parse()
            count = lex.parse()
            lex._skip_ws()
            for i in range(count):
                entry = data[lex.pos:lex.pos + 20]
                lex.pos += 20
                off = int(entry[0:10])
                typ = entry[17:18]
                num = start + i
                if typ == b"n" and num not in self.xref:
                    self.xref[num] = ("n", off)

    def _read_xref_stream(self, offset: int):
        obj = self._parse_indirect_at(offset)
        if not isinstance(obj, Stream):
            return None
        d = obj.dict
        data = decode_stream(d, obj.raw, self.resolve)
        w = [int(x) for x in d["W"]]
        size = int(self.resolve(d.get("Size")) or 0)
        index = d.get("Index")
        index = [int(x) for x in index] if index else [0, size]
        widths = w
        rec_len = sum(widths)
        pos = 0
        pairs = list(zip(index[0::2], index[1::2]))
        for start, count in pairs:
            for i in range(count):
                rec = data[pos:pos + rec_len]
                pos += rec_len
                if len(rec) < rec_len:
                    break
                f = []
                k = 0
                for wlen in widths:
                    f.append(int.from_bytes(rec[k:k + wlen], "big") if wlen else None)
                    k += wlen
                t = f[0] if widths[0] else 1
                num = start + i
                if num in self.xref:
                    continue
                if t == 1:
                    self.xref[num] = ("n", f[1])
                elif t == 2:
                    self.xref[num] = ("c", f[1], f[2])
        for k, v in d.items():
            self.trailer.setdefault(k, v)
        prev = d.get("Prev")
        return int(prev) if prev is not None else None

    # -- object access ------------------------------------------------------

    def _parse_indirect_at(self, offset: int):
        lex = Lexer(self.data, offset)
        head = lex.parse()
        if isinstance(head, tuple) and head[0] == "__objstart__":
            body = lex.parse()
            return self._finish(body, lex)
        return self._finish(head, lex)

    def _finish(self, body, lex: Lexer):
        if isinstance(body, tuple) and body[0] == "__stream__":
            _, d, start = body
            length = self.resolve(d.get("Length"))
            if isinstance(length, int):
                raw = self.data[start:start + length]
                # Trust Length but verify it lands on endstream-ish bytes.
                tail = self.data[start + length:start + length + 20]
                if b"endstream" not in tail:
                    length = None
            if not isinstance(length, int):
                end = self.data.find(b"endstream", start)
                raw = self.data[start:end]
                if raw.endswith(b"\r\n"):
                    raw = raw[:-2]
                elif raw.endswith(b"\n") or raw.endswith(b"\r"):
                    raw = raw[:-1]
            return Stream(d, raw)
        return body

    def get_object(self, num: int):
        if num in self.cache:
            return self.cache[num]
        entry = self.xref.get(num)
        if entry is None:
            return None
        if entry[0] == "n":
            obj = self._parse_indirect_at(entry[1])
        else:  # compressed in object stream
            obj = self._object_from_stream(entry[1], num)
        self.cache[num] = obj
        return obj

    def _object_from_stream(self, stm_num: int, want: int):
        objs = self._objstm_cache.get(stm_num)
        if objs is None:
            stm = self.get_object(stm_num)
            data = decode_stream(stm.dict, stm.raw, self.resolve)
            n = int(self.resolve(stm.dict["N"]))
            first = int(self.resolve(stm.dict["First"]))
            header = Lexer(data, 0)
            offsets = []
            for _ in range(n):
                onum = header.parse()
                ooff = header.parse()
                offsets.append((int(onum), int(ooff)))
            objs = {}
            for onum, ooff in offsets:
                objs[onum] = Lexer(data, first + ooff).parse()
            self._objstm_cache[stm_num] = objs
        return objs.get(want)

    def resolve(self, obj):
        seen = 0
        while isinstance(obj, Ref):
            obj = self.get_object(obj.num)
            seen += 1
            if seen > 50:
                break
        return obj

    # -- page tree ----------------------------------------------------------

    def pages(self):
        root = self.resolve(self.trailer.get("Root"))
        pages_node = self.resolve(root["Pages"])
        result = []
        self._walk_pages(pages_node, {}, result)
        return result

    INHERITABLE = ("Resources", "MediaBox", "CropBox", "Rotate")

    def _walk_pages(self, node, inherited, out):
        node = self.resolve(node)
        if node is None:
            return
        inh = dict(inherited)
        for key in self.INHERITABLE:
            if key in node:
                inh[key] = node[key]
        typ = node.get("Type")
        if typ == "Pages" or "Kids" in node:
            for kid in self.resolve(node.get("Kids")) or []:
                self._walk_pages(kid, inh, out)
        else:  # a /Page leaf
            page = dict(node)
            for key in self.INHERITABLE:
                if key not in page and key in inh:
                    page[key] = inh[key]
            out.append(page)

    def page_content(self, page: dict) -> bytes:
        contents = self.resolve(page.get("Contents"))
        if contents is None:
            return b""
        if isinstance(contents, list):
            chunks = []
            for ref in contents:
                stm = self.resolve(ref)
                if isinstance(stm, Stream):
                    chunks.append(decode_stream(stm.dict, stm.raw, self.resolve))
            return b"\n".join(chunks)
        if isinstance(contents, Stream):
            return decode_stream(contents.dict, contents.raw, self.resolve)
        return b""


# ---------------------------------------------------------------------------
# Fonts: build a byte-sequence -> unicode decoder per page font resource
# ---------------------------------------------------------------------------

STANDARD_ENCODING_OVERRIDES = {
    0x91: "‘", 0x92: "’", 0x93: "“", 0x94: "”",
    0x95: "•", 0x96: "–", 0x97: "—", 0x85: "…",
    0xA0: " ", 0xAD: "-",
}


class Font:
    """Decodes content-stream byte strings to unicode for one font."""

    def __init__(self, two_byte: bool, tounicode: dict[int, str] | None,
                 bold: bool, simple_map: dict[int, str] | None = None):
        self.two_byte = two_byte
        self.tounicode = tounicode or {}
        self.bold = bold
        self.simple_map = simple_map or {}

    def decode(self, raw: bytes) -> str:
        out = []
        if self.two_byte:
            for i in range(0, len(raw) - 1, 2):
                code = (raw[i] << 8) | raw[i + 1]
                out.append(self.tounicode.get(code, ""))
        else:
            for byte in raw:
                if byte in self.tounicode:
                    out.append(self.tounicode[byte])
                elif byte in self.simple_map:
                    out.append(self.simple_map[byte])
                elif byte in STANDARD_ENCODING_OVERRIDES:
                    out.append(STANDARD_ENCODING_OVERRIDES[byte])
                else:
                    out.append(chr(byte))
        return "".join(out)


def parse_tounicode(data: bytes):
    """Parse a ToUnicode CMap into {code -> unicode} and detect byte width."""
    text = data
    mapping: dict[int, str] = {}
    two_byte = False

    # codespacerange gives the code width
    m = re.search(rb"begincodespacerange(.*?)endcodespacerange", text, re.S)
    if m:
        first = re.search(rb"<([0-9A-Fa-f]+)>", m.group(1))
        if first and len(first.group(1)) > 2:
            two_byte = True

    def to_unicode(hexstr: bytes) -> str:
        b = bytes.fromhex(hexstr.decode())
        try:
            return b.decode("utf-16-be")
        except UnicodeDecodeError:
            return b.decode("latin-1", "replace")

    for block in re.findall(rb"beginbfchar(.*?)endbfchar", text, re.S):
        for src, dst in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", block):
            mapping[int(src, 16)] = to_unicode(dst)

    for block in re.findall(rb"beginbfrange(.*?)endbfrange", text, re.S):
        # form: <lo> <hi> <dst>
        for lo, hi, dst in re.findall(
            rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", block
        ):
            lo_i, hi_i = int(lo, 16), int(hi, 16)
            base = int(dst, 16)
            if hi_i - lo_i > 0x10000:  # guard against malformed ranges
                continue
            for k, code in enumerate(range(lo_i, hi_i + 1)):
                cp = base + k
                if cp <= 0x10FFFF:
                    mapping[code] = chr(cp)
        # form: <lo> <hi> [<d1> <d2> ...]
        for lo, hi, arr in re.findall(
            rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*\[(.*?)\]", block, re.S
        ):
            lo_i = int(lo, 16)
            dsts = re.findall(rb"<([0-9A-Fa-f]+)>", arr)
            for k, dst in enumerate(dsts):
                mapping[lo_i + k] = to_unicode(dst)
    return mapping, two_byte


def build_font(doc: PDFDocument, font_obj) -> Font:
    font_obj = doc.resolve(font_obj)
    if not isinstance(font_obj, dict):
        return Font(False, None, False)
    subtype = font_obj.get("Subtype")
    basefont = str(font_obj.get("BaseFont", ""))
    bold = "bold" in basefont.lower()

    tounicode = None
    two_byte = subtype == "Type0"
    tu = doc.resolve(font_obj.get("ToUnicode"))
    if isinstance(tu, Stream):
        raw = decode_stream(tu.dict, tu.raw, doc.resolve)
        tounicode, tb = parse_tounicode(raw)
        if subtype == "Type0":
            two_byte = True
        else:
            two_byte = tb

    if subtype == "Type0" and not tounicode:
        # Identity encoding without ToUnicode: best effort, treat code as cid.
        enc = doc.resolve(font_obj.get("Encoding"))
        two_byte = True

    simple_map = _simple_encoding(doc, font_obj) if subtype != "Type0" else None
    return Font(two_byte, tounicode, bold, simple_map)


WINANSI_HIGH = {
    0x80: "€", 0x82: "‚", 0x83: "ƒ", 0x84: "„",
    0x85: "…", 0x86: "†", 0x87: "‡", 0x88: "ˆ",
    0x89: "‰", 0x8A: "Š", 0x8B: "‹", 0x8C: "Œ",
    0x91: "‘", 0x92: "’", 0x93: "“", 0x94: "”",
    0x95: "•", 0x96: "–", 0x97: "—", 0x98: "˜",
    0x99: "™", 0x9A: "š", 0x9B: "›", 0x9C: "œ",
    0x9F: "Ÿ",
}

GLYPH_NAMES = {
    "quoteright": "’", "quoteleft": "‘", "quotedblleft": "“",
    "quotedblright": "”", "endash": "–", "emdash": "—",
    "bullet": "•", "ellipsis": "…", "space": " ", "hyphen": "-",
    "fi": "fi", "fl": "fl",
}


def _simple_encoding(doc: PDFDocument, font_obj: dict) -> dict[int, str]:
    mapping: dict[int, str] = {}
    enc = doc.resolve(font_obj.get("Encoding"))
    base_name = enc if isinstance(enc, (Name, str)) else (
        enc.get("BaseEncoding") if isinstance(enc, dict) else None
    )
    if base_name == "WinAnsiEncoding" or base_name is None:
        mapping.update(WINANSI_HIGH)
    if isinstance(enc, dict) and "Differences" in enc:
        code = 0
        for item in doc.resolve(enc["Differences"]) or []:
            if isinstance(item, (int, float)):
                code = int(item)
            else:
                name = str(item)
                if name in GLYPH_NAMES:
                    mapping[code] = GLYPH_NAMES[name]
                elif name.startswith("uni") and len(name) >= 7:
                    try:
                        mapping[code] = chr(int(name[3:7], 16))
                    except ValueError:
                        pass
                code += 1
    return mapping


# ---------------------------------------------------------------------------
# Content stream interpreter -> positioned text fragments
# ---------------------------------------------------------------------------

@dataclass
class Fragment:
    page: int
    x: float
    y_top: float       # distance from top of page
    size: float
    bold: bool
    text: str


def mat_mul(a, b):
    a0, a1, a2, a3, a4, a5 = a
    b0, b1, b2, b3, b4, b5 = b
    return (
        a0 * b0 + a1 * b2,
        a0 * b1 + a1 * b3,
        a2 * b0 + a3 * b2,
        a2 * b1 + a3 * b3,
        a4 * b0 + a5 * b2 + b4,
        a4 * b1 + a5 * b3 + b5,
    )


def interpret_page(doc: PDFDocument, page: dict, page_no: int) -> list[Fragment]:
    content = doc.page_content(page)
    if not content:
        return []
    resources = doc.resolve(page.get("Resources")) or {}
    fonts_dict = doc.resolve(resources.get("Font")) or {}
    font_cache: dict[str, Font] = {}

    def get_font(name: str) -> Font:
        if name not in font_cache:
            font_cache[name] = build_font(doc, fonts_dict.get(name))
        return font_cache[name]

    media = doc.resolve(page.get("MediaBox")) or [0, 0, 612, 792]
    page_height = float(media[3]) - float(media[1])

    frags: list[Fragment] = []
    lex = Lexer(content, 0)
    stack = []  # operand stack
    gs_stack = []
    ctm = (1, 0, 0, 1, 0, 0)
    tm = (1, 0, 0, 1, 0, 0)
    tlm = (1, 0, 0, 1, 0, 0)
    cur_font = None
    font_size = 0.0
    leading = 0.0
    char_space = 0.0
    word_space = 0.0
    n = len(content)

    def show(text_bytes):
        nonlocal tm
        if cur_font is None:
            return
        s = cur_font.decode(text_bytes)
        if not s:
            return
        trm = mat_mul(mat_mul((font_size, 0, 0, font_size, 0, 0), tm), ctm)
        x = trm[4]
        y = trm[5]
        eff_size = font_size * (abs(tm[3]) or 1) * (abs(ctm[3]) or 1)
        frags.append(Fragment(page_no, x, page_height - y, eff_size, cur_font.bold, s))

    while lex.pos < n:
        lex._skip_ws()
        if lex.pos >= n:
            break
        c = content[lex.pos]
        if c in b"/([<+-.0123456789" or (c == 0x5B):
            try:
                stack.append(lex.parse())
            except Exception:
                lex.pos += 1
            continue
        # operator keyword
        op = lex._read_token()
        if not op:
            lex.pos += 1
            continue
        op = op.decode("latin-1")
        if op == "q":
            gs_stack.append(ctm)
        elif op == "Q":
            if gs_stack:
                ctm = gs_stack.pop()
        elif op == "cm" and len(stack) >= 6:
            ctm = mat_mul(tuple(float(v) for v in stack[-6:]), ctm)
        elif op == "BT":
            tm = (1, 0, 0, 1, 0, 0)
            tlm = tm
        elif op == "ET":
            pass
        elif op == "Tf" and len(stack) >= 2:
            cur_font = get_font(str(stack[-2]))
            font_size = float(stack[-1])
        elif op == "Td" and len(stack) >= 2:
            tlm = mat_mul((1, 0, 0, 1, float(stack[-2]), float(stack[-1])), tlm)
            tm = tlm
        elif op == "TD" and len(stack) >= 2:
            leading = -float(stack[-1])
            tlm = mat_mul((1, 0, 0, 1, float(stack[-2]), float(stack[-1])), tlm)
            tm = tlm
        elif op == "Tm" and len(stack) >= 6:
            tm = tuple(float(v) for v in stack[-6:])
            tlm = tm
        elif op == "T*":
            tlm = mat_mul((1, 0, 0, 1, 0, -leading), tlm)
            tm = tlm
        elif op == "TL" and stack:
            leading = float(stack[-1])
        elif op == "Tc" and stack:
            char_space = float(stack[-1])
        elif op == "Tw" and stack:
            word_space = float(stack[-1])
        elif op == "Tj" and stack:
            if isinstance(stack[-1], bytes):
                show(stack[-1])
        elif op == "'" and stack:
            tlm = mat_mul((1, 0, 0, 1, 0, -leading), tlm)
            tm = tlm
            if isinstance(stack[-1], bytes):
                show(stack[-1])
        elif op == '"' and len(stack) >= 3:
            tlm = mat_mul((1, 0, 0, 1, 0, -leading), tlm)
            tm = tlm
            if isinstance(stack[-1], bytes):
                show(stack[-1])
        elif op == "TJ" and stack and isinstance(stack[-1], list):
            for el in stack[-1]:
                if isinstance(el, bytes):
                    show(el)
                elif isinstance(el, (int, float)) and el <= -200:
                    # Large negative adjustment -> inter-word space.
                    frags.append(Fragment(page_no, tm[4], 0, font_size, False, " "))
        stack.clear()
    return frags


# ---------------------------------------------------------------------------
# Grouping fragments -> lines -> blocks
# ---------------------------------------------------------------------------

def _dominant(values):
    from collections import Counter
    return Counter(values).most_common(1)[0][0]


def group_lines(frags: list[Fragment], y_tol: float = 3.0) -> list[dict]:
    """Cluster fragments with near-equal vertical position into text lines."""
    if not frags:
        return []
    frags = sorted(frags, key=lambda f: (round(f.y_top, 1), f.x))
    lines = []
    current = [frags[0]]
    base_y = frags[0].y_top
    for frag in frags[1:]:
        if abs(frag.y_top - base_y) <= y_tol:
            current.append(frag)
        else:
            lines.append(_finish_line(current))
            current = [frag]
            base_y = frag.y_top
    lines.append(_finish_line(current))
    return lines


def _finish_line(frags: list[Fragment]) -> dict:
    frags = sorted(frags, key=lambda f: f.x)
    text = re.sub(r"\s+", " ", "".join(f.text for f in frags)).strip()
    sizes = [round(f.size, 1) for f in frags if f.text.strip()]
    bold_chars = sum(len(f.text) for f in frags if f.bold)
    total_chars = sum(len(f.text) for f in frags) or 1
    return {
        "text": text,
        "x": min(f.x for f in frags),
        "y_top": min(f.y_top for f in frags),
        "size": _dominant(sizes) if sizes else 0.0,
        "bold": bold_chars > total_chars / 2,
        "page": frags[0].page,
    }


def group_blocks(lines: list[dict], page_height: float) -> list[dict]:
    """Merge consecutive lines into blocks, breaking on vertical gaps, font
    size changes or paragraph indentation."""
    lines = [ln for ln in lines if ln["text"]]
    if not lines:
        return []
    line_heights = [
        lines[i + 1]["y_top"] - lines[i]["y_top"]
        for i in range(len(lines) - 1)
        if 0 < lines[i + 1]["y_top"] - lines[i]["y_top"] < 40
    ]
    line_heights.sort()
    median_h = line_heights[len(line_heights) // 2] if line_heights else 12.0

    blocks = []
    current = [lines[0]]
    for prev, ln in zip(lines, lines[1:]):
        gap = ln["y_top"] - prev["y_top"]
        size_changed = abs(ln["size"] - prev["size"]) > 0.6
        big_gap = gap > median_h * 1.6 or gap < 0
        if big_gap or size_changed:
            blocks.append(_finish_block(current, page_height))
            current = [ln]
        else:
            current.append(ln)
    blocks.append(_finish_block(current, page_height))
    return blocks


def _finish_block(lines: list[dict], page_height: float) -> dict:
    text = " ".join(ln["text"] for ln in lines)
    # undo end-of-line hyphenation within the block
    text = re.sub(r"(\w)-\s+([a-zà-ÿ])", r"\1\2", text)
    text = re.sub(r"\s+", " ", text).strip()
    sizes = [ln["size"] for ln in lines]
    bold = sum(ln["bold"] for ln in lines) > len(lines) / 2
    return {
        "text": text,
        "page": lines[0]["page"],
        "font_size": _dominant([round(s, 1) for s in sizes]),
        "bold": bold,
        "y0": min(ln["y_top"] for ln in lines),
        "page_height": page_height,
    }


def extract_blocks(pdf_path) -> list[dict]:
    """Extract the document as a flat list of block dicts (reading order).

    Each dict has: text, page, font_size, bold, y0, page_height — matching the
    Block dataclass used by the segmentation stage.
    """
    data = open(pdf_path, "rb").read()
    doc = PDFDocument(data)
    pages = doc.pages()
    blocks: list[dict] = []
    for page_no, page in enumerate(pages, start=1):
        media = doc.resolve(page.get("MediaBox")) or [0, 0, 612, 792]
        page_height = float(media[3]) - float(media[1])
        frags = interpret_page(doc, page, page_no)
        lines = group_lines(frags)
        blocks.extend(group_blocks(lines, page_height))
    return blocks
