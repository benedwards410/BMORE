"""Write cell values into an .xlsm by patching sheet XML in place.

Why not openpyxl: it drops the workbook's x14 data validations (the dependent
dropdowns), form controls and other parts it doesn't model. Here every zip entry
except the patched sheets and workbook.xml is copied byte-for-byte, including
vbaProject.bin, and a cell that holds a formula is never overwritten.
"""

import re
import zipfile
from xml.sax.saxutils import escape

from ._xlsx import column_index_from_string

NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


class FormulaCellError(Exception):
    """Refused to overwrite a formula: the cell map no longer matches the template."""


class IfNotFormula:
    """Write this value only where the template cell is NOT a formula (else leave the formula)."""

    def __init__(self, value):
        self.value = value


def _split_ref(ref):
    m = re.fullmatch(r"([A-Z]+)(\d+)", ref)
    if not m:
        raise ValueError(f"bad cell reference {ref!r}")
    return m.group(1), int(m.group(2))


def sheet_parts(z):
    """{sheet name: zip path of its XML} from workbook.xml + its rels."""
    wb = z.read("xl/workbook.xml").decode("utf-8")
    rels = z.read("xl/_rels/workbook.xml.rels").decode("utf-8")
    targets = {}
    for m in re.finditer(r"<Relationship\b[^>]*>", rels):
        tag = m.group(0)
        rid = re.search(r'\bId="([^"]+)"', tag)
        tgt = re.search(r'\bTarget="([^"]+)"', tag)
        if rid and tgt:
            t = tgt.group(1)
            targets[rid.group(1)] = t.lstrip("/") if t.startswith("/") else "xl/" + t
    out = {}
    for m in re.finditer(r"<sheet\b[^>]*/>", wb):
        tag = m.group(0)
        name = re.search(r'\bname="([^"]+)"', tag).group(1)
        rid = re.search(r'\br:id="([^"]+)"', tag).group(1)
        out[_unescape(name)] = targets[rid]
    return out


def _unescape(s):
    return s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&apos;", "'")


def _cell_xml(ref, attrs, value):
    attrs = {k: v for k, v in attrs.items() if k != "t"}
    head = "<c " + " ".join(f'{k}="{v}"' for k, v in [("r", ref)] + [(k, v) for k, v in attrs.items() if k != "r"])
    if value is None:
        return head + "/>"
    if isinstance(value, bool):
        return head + f' t="b"><v>{int(value)}</v></c>'
    if isinstance(value, (int, float)):
        num = str(int(value)) if float(value).is_integer() else repr(float(value))
        return head + f"><v>{num}</v></c>"
    text = escape(str(value))
    return head + f' t="inlineStr"><is><t xml:space="preserve">{text}</t></is></c>'


def _attrs(start_tag):
    return dict(re.findall(r'(\w+(?::\w+)?)="([^"]*)"', start_tag))


def _find_row(xml, row):
    """(start, end, self_closing) of <row r="N">, or None."""
    m = re.search(rf'<row r="{row}"(?=[\s/>])[^>]*?(/?)>', xml)
    if not m:
        return None
    if m.group(1) == "/":
        return m.start(), m.end(), True
    end = xml.index("</row>", m.end()) + len("</row>")
    return m.start(), end, False


def _patch_row(row_xml, row, cells):
    """row_xml is the full <row>...</row> element. cells: {ref: value}."""
    head_m = re.match(r"<row\b[^>]*?/?>", row_xml)
    head = head_m.group(0)
    if head.endswith("/>"):
        head = head[:-2] + ">"
        body = ""
    else:
        body = row_xml[len(head):-len("</row>")]
    for ref, value in cells.items():
        m = re.search(rf'<c r="{ref}"(?=[\s/>])[^>]*?(/?)>', body)
        if m:
            start = m.start()
            if m.group(1) == "/":
                end = m.end()
            else:
                end = body.index("</c>", m.end()) + len("</c>")
            old = body[start:end]
            if "<f" in old:
                if isinstance(value, IfNotFormula):
                    continue
                raise FormulaCellError(f"{ref} holds a formula in the template; refusing to overwrite it")
            if isinstance(value, IfNotFormula):
                value = value.value
            body = body[:start] + _cell_xml(ref, _attrs(m.group(0)[2:]), value) + body[end:]
        else:
            if isinstance(value, IfNotFormula):
                value = value.value
            col = column_index_from_string(_split_ref(ref)[0])
            pos = len(body)
            for cm in re.finditer(r'<c r="([A-Z]+)\d+"', body):
                if column_index_from_string(cm.group(1)) > col:
                    pos = cm.start()
                    break
            body = body[:pos] + _cell_xml(ref, {}, value) + body[pos:]
    return head + body + "</row>"


def patch_sheet_xml(xml, cells):
    """Apply {ref: value} to one sheet's XML string."""
    by_row = {}
    for ref, value in cells.items():
        by_row.setdefault(_split_ref(ref)[1], {})[ref] = value
    for row in sorted(by_row):
        found = _find_row(xml, row)
        if found:
            s, e, _ = found
            xml = xml[:s] + _patch_row(xml[s:e], row, by_row[row]) + xml[e:]
        else:
            new_row = _patch_row(f'<row r="{row}">' + "</row>", row, by_row[row])
            pos = None
            for rm in re.finditer(r'<row r="(\d+)"', xml):
                if int(rm.group(1)) > row:
                    pos = rm.start()
                    break
            if pos is None:
                pos = xml.index("</sheetData>")
            xml = xml[:pos] + new_row + xml[pos:]
    return xml


# Tempered so a match can never run past its own </f>, </v> or </c>.
_FORMULA_CELL = re.compile(
    r"<c\b([^>]*[^/>])>"
    r"(<f\b[^>]*/>|<f\b[^>]*(?<!/)>(?:(?!</f>|</c>).)*</f>)"
    r"(?:<v\b[^>]*/>|<v\b[^>]*(?<!/)>(?:(?!</v>|</c>).)*</v>)?"
    r"</c>",
    re.S,
)


def strip_cached_values(xml):
    """Drop cached results from formula cells so nothing shows a stale number
    before Excel recalculates (fullCalcOnLoad does that on open)."""
    def repl(m):
        attrs = re.sub(r'\s+t="[^"]*"', "", m.group(1))
        return f"<c{attrs}>{m.group(2)}</c>"
    return _FORMULA_CELL.sub(repl, xml)


def _force_full_calc(wb_xml):
    m = re.search(r"<calcPr\b[^>]*/>", wb_xml)
    if m:
        tag = m.group(0)
        if "fullCalcOnLoad" in tag:
            new = re.sub(r'fullCalcOnLoad="[^"]*"', 'fullCalcOnLoad="1"', tag)
        else:
            new = tag[:-2] + ' fullCalcOnLoad="1"/>'
        return wb_xml[: m.start()] + new + wb_xml[m.end():]
    return wb_xml.replace("</workbook>", '<calcPr fullCalcOnLoad="1"/></workbook>')


def read_cells(path, sheet, refs):
    """Raw XML of the named cells (for checks/tests): {ref: element or None}."""
    with zipfile.ZipFile(path) as z:
        xml = z.read(sheet_parts(z)[sheet]).decode("utf-8")
    out = {}
    for ref in refs:
        m = re.search(rf'<c r="{ref}"(?=[\s/>])[^>]*?(/?)>', xml)
        if not m:
            out[ref] = None
        elif m.group(1) == "/":
            out[ref] = m.group(0)
        else:
            out[ref] = xml[m.start(): xml.index("</c>", m.end()) + 4]
    return out


def write(template_path, out_path, edits, strip_sheets=()):
    """edits: {sheet name: {ref: value}}. Writes a new file; the template is untouched."""
    with zipfile.ZipFile(template_path) as zin:
        parts = sheet_parts(zin)
        patched = {}
        for sheet, cells in edits.items():
            if sheet not in parts:
                raise KeyError(f"sheet {sheet!r} not in workbook")
            xml = zin.read(parts[sheet]).decode("utf-8")
            xml = patch_sheet_xml(xml, cells)
            patched[parts[sheet]] = xml
        for sheet in strip_sheets:
            part = parts[sheet]
            xml = patched.get(part) or zin.read(part).decode("utf-8")
            patched[part] = strip_cached_values(xml)
        patched["xl/workbook.xml"] = _force_full_calc(zin.read("xl/workbook.xml").decode("utf-8"))

        with zipfile.ZipFile(out_path, "w") as zout:
            for info in zin.infolist():
                data = patched[info.filename].encode("utf-8") if info.filename in patched else zin.read(info.filename)
                zout.writestr(info, data, compress_type=info.compress_type)
    return out_path
