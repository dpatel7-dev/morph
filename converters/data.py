"""Structured data: JSON, YAML, XML, TOML, INI, PLIST, CSV/TSV, Excel, SQL, HTML/Markdown tables."""
import base64
import configparser
import csv
import datetime as dt
import html
import io
import json
import math
import plistlib
import re
import xml.etree.ElementTree as ET

from core.registry import ConversionError, converter

try:
    import tomllib
except ImportError:  # Python < 3.11
    tomllib = None

DATA_IN = ["json", "jsonl", "yaml", "xml", "toml", "ini", "plist", "csv", "tsv", "xlsx", "xlsm"]
DATA_OUT = ["json", "jsonl", "yaml", "xml", "toml", "ini", "plist", "csv", "tsv", "xlsx", "htmltable", "mdtable", "sql"]
TABULAR_IN = {"csv", "tsv", "xlsx", "xlsm"}


def data_options(src, dst):
    opts = []
    if src in ("csv", "tsv"):
        opts.append("infer")
    if src in ("xlsx", "xlsm"):
        opts.append("sheet")
    if dst == "json":
        opts.append("indent")
    return opts


def data_requires(src, dst):
    req = []
    if "yaml" in (src, dst):
        req.append("py:yaml")
    if src in ("xlsx", "xlsm") or dst == "xlsx":
        req.append("py:openpyxl")
    if src == "toml" and tomllib is None:
        req.append("py:tomllib")
    return req


# --------------------------------------------------------------------------
# Reading
# --------------------------------------------------------------------------

INT_RE = re.compile(r"-?(0|[1-9]\d{0,17})")
FLOAT_RE = re.compile(r"-?(0|[1-9]\d*)?\.\d+([eE][-+]?\d+)?|-?(0|[1-9]\d*)[eE][-+]?\d+")


def infer(v):
    if not isinstance(v, str):
        return v
    s = v.strip()
    if INT_RE.fullmatch(s):
        return int(s)
    if FLOAT_RE.fullmatch(s):
        return float(s)
    low = s.lower()
    if low in ("true", "false"):
        return low == "true"
    if low in ("null", "none"):
        return None
    return v


def read_text(path):
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-16"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return raw.decode("cp1252", errors="replace")


def _strip_ns(tag):
    return tag.split("}", 1)[1] if tag.startswith("{") else tag


def xml_to_obj(el):
    d, listed = {}, set()
    for k, v in el.attrib.items():
        d["@" + _strip_ns(k)] = v
    for child in el:
        tag = _strip_ns(child.tag)
        val = xml_to_obj(child)
        if tag in d:
            if tag not in listed:
                d[tag] = [d[tag]]
                listed.add(tag)
            d[tag].append(val)
        else:
            d[tag] = val
    text = (el.text or "").strip()
    if text:
        if d:
            d["#text"] = text
        else:
            return text
    return d or None


def _unique_headers(row):
    seen, out = {}, []
    for i, h in enumerate(row):
        h = str(h).strip() if h is not None else ""
        h = h or f"column_{i + 1}"
        if h in seen:
            seen[h] += 1
            h = f"{h}_{seen[h]}"
        else:
            seen[h] = 1
        out.append(h)
    return out


def _column_kind(values):
    """Decide one type per column, so '01234' and '10001' stay text together."""
    filled = [v.strip() for v in values if isinstance(v, str) and v.strip()]
    if not filled or len(filled) != len([v for v in values if v not in (None, "")]):
        return None  # mixed with non-text cells (e.g. from Excel): leave as is
    if all(INT_RE.fullmatch(v) for v in filled):
        return "int"
    if all(INT_RE.fullmatch(v) or FLOAT_RE.fullmatch(v) for v in filled):
        return "float"
    if all(v.lower() in ("true", "false") for v in filled):
        return "bool"
    return None


def _cast(v, kind):
    if v is None or (isinstance(v, str) and not v.strip()):
        return None if kind else ("" if v is None else v)
    s = v.strip()
    if kind == "int":
        return int(s)
    if kind == "float":
        return float(s) if not INT_RE.fullmatch(s) else int(s)
    if kind == "bool":
        return s.lower() == "true"
    return v


def _rows_to_records(rows, do_infer):
    rows = [r for r in rows if any(c not in (None, "") for c in r)]
    if not rows:
        return []
    headers = _unique_headers(rows[0])
    body = [[(r[i] if i < len(r) else "") for i in range(len(headers))] for r in rows[1:]]
    kinds = [_column_kind([row[i] for row in body]) if do_infer else None for i in range(len(headers))]
    return [{h: _cast(row[i], kinds[i]) if do_infer else ("" if row[i] is None else row[i])
             for i, h in enumerate(headers)} for row in body]


def load(ctx):
    f, path = ctx.src_fmt, ctx.src
    try:
        if f == "json":
            text = read_text(path)
            try:
                return json.loads(text)
            except json.JSONDecodeError as e:
                lines = [l for l in text.splitlines() if l.strip()]
                try:
                    return [json.loads(l) for l in lines]  # maybe it's JSON Lines
                except Exception:
                    raise ConversionError(f"This JSON has a mistake on line {e.lineno}, column {e.colno}: {e.msg}.")
        if f == "jsonl":
            out = []
            for n, line in enumerate(read_text(path).splitlines(), 1):
                if line.strip():
                    try:
                        out.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        raise ConversionError(f"Line {n} isn't valid JSON: {e.msg}.")
            return out
        if f == "yaml":
            import yaml
            docs = list(yaml.safe_load_all(read_text(path)))
            return docs[0] if len(docs) == 1 else docs
        if f == "xml":
            root = ET.fromstring(path.read_bytes())
            return {_strip_ns(root.tag): xml_to_obj(root)}
        if f == "toml":
            return tomllib.loads(read_text(path))
        if f == "ini":
            cp = configparser.ConfigParser(interpolation=None)
            cp.optionxform = str
            cp.read_string(read_text(path))
            out = {}
            if cp.defaults():
                out["DEFAULT"] = dict(cp.defaults())
            for s in cp.sections():
                out[s] = {k: v for k, v in cp.items(s, raw=True) if k not in cp.defaults() or s == "DEFAULT"}
            return out
        if f == "plist":
            return plistlib.loads(path.read_bytes())
        if f in ("csv", "tsv"):
            text = read_text(path)
            if f == "tsv":
                delim = "\t"
            else:
                try:
                    delim = csv.Sniffer().sniff(text[:20000], delimiters=",;|\t").delimiter
                except csv.Error:
                    delim = ","
            rows = list(csv.reader(io.StringIO(text), delimiter=delim))
            return _rows_to_records(rows, ctx.opts.get("infer", True))
        if f in ("xlsx", "xlsm"):
            import openpyxl
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            want = (ctx.opts.get("sheet") or "").strip()
            if want and want not in wb.sheetnames:
                raise ConversionError(f"There's no sheet called “{want}”. Sheets: {', '.join(wb.sheetnames)}.")
            ws = wb[want] if want else wb.worksheets[0]
            rows = [list(r) for r in ws.iter_rows(values_only=True)]
            title = ws.title
            wb.close()
            if any(v is None for r in rows for v in r):
                # Formulas saved without a cached result read as empty: show the formula instead
                wbf = openpyxl.load_workbook(path, read_only=True, data_only=False)
                frows = [list(r) for r in wbf[title].iter_rows(values_only=True)]
                wbf.close()
                for r, fr in zip(rows, frows):
                    for i, v in enumerate(r):
                        if v is None and i < len(fr) and isinstance(fr[i], str) and fr[i].startswith("="):
                            r[i] = fr[i]
            for r in rows:
                for i, v in enumerate(r):
                    if isinstance(v, (dt.datetime, dt.date, dt.time)):
                        r[i] = v.isoformat()
            return _rows_to_records(rows, False)
    except ConversionError:
        raise
    except Exception as e:
        raise ConversionError(f"I couldn't read this {f.upper()} file: {e}")
    raise ConversionError("Unsupported input.")


# --------------------------------------------------------------------------
# Writing
# --------------------------------------------------------------------------

def plain(o):
    """Make data JSON-safe (dates -> text, bytes -> base64, NaN -> null)."""
    if isinstance(o, dict):
        return {str(k): plain(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, set)):
        return [plain(v) for v in o]
    if isinstance(o, (dt.datetime, dt.date, dt.time)):
        return o.isoformat()
    if isinstance(o, bytes):
        return base64.b64encode(o).decode()
    if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
        return None
    return o


def flat(d, prefix=""):
    out = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else str(k)
        if isinstance(v, dict):
            out.update(flat(v, key) if v else {key: ""})
        elif isinstance(v, list):
            out[key] = json.dumps(v, ensure_ascii=False) if any(isinstance(x, (dict, list)) for x in v) \
                else "; ".join("" if x is None else str(x) for x in v)
        else:
            out[key] = v
    return out


def to_table(data):
    if isinstance(data, dict):
        lists = [v for v in data.values() if isinstance(v, list)]
        if len(data) == 1 and lists:
            data = lists[0]
        elif data and all(isinstance(v, dict) for v in data.values()):
            data = [{"key": k, **v} for k, v in data.items()]
        else:
            data = [data]
    if not isinstance(data, list):
        data = [{"value": data}]
    rows = []
    for item in data:
        if isinstance(item, dict):
            rows.append(flat(item))
        elif isinstance(item, list):
            rows.append({f"column_{i + 1}": v for i, v in enumerate(item)})
        else:
            rows.append({"value": item})
    headers = []
    for r in rows:
        for k in r:
            if k not in headers:
                headers.append(k)
    return headers, [[r.get(h) for h in headers] for r in rows]


def cell_text(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


TAG_BAD = re.compile(r"[^A-Za-z0-9_.\-]")


def safe_tag(k):
    t = TAG_BAD.sub("_", str(k)) or "item"
    if not re.match(r"[A-Za-z_]", t) or t.lower().startswith("xml"):
        t = "_" + t
    return t


def build_xml(parent, key, value):
    if isinstance(value, list):
        for v in value:
            build_xml(parent, key, v)
        return
    el = ET.SubElement(parent, safe_tag(key))
    if isinstance(value, dict):
        for k, v in value.items():
            if str(k).startswith("@"):
                el.set(safe_tag(str(k)[1:]), cell_text(v))
            elif k == "#text":
                el.text = cell_text(v)
            else:
                build_xml(el, k, v)
    else:
        el.text = cell_text(value)


def toml_dumps(data):
    if not isinstance(data, dict):
        data = {"items": data}

    def key(k):
        k = str(k)
        return k if re.fullmatch(r"[A-Za-z0-9_\-]+", k) else json.dumps(k, ensure_ascii=False)

    def val(v):
        if v is None:
            return '""'
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (int, float)):
            return repr(v)
        if isinstance(v, list):
            return "[" + ", ".join(val(x) for x in v) + "]"
        if isinstance(v, dict):
            return "{ " + ", ".join(f"{key(k)} = {val(x)}" for k, x in v.items()) + " }"
        return json.dumps(str(v), ensure_ascii=False)

    lines = []

    def is_table_array(v):
        return isinstance(v, list) and v and all(isinstance(x, dict) for x in v)

    def emit(d, path, array=False):
        scalars = [(k, v) for k, v in d.items() if not isinstance(v, dict) and not is_table_array(v)]
        tables = [(k, v) for k, v in d.items() if isinstance(v, dict)]
        arrays = [(k, v) for k, v in d.items() if is_table_array(v)]
        dotted = ".".join(key(p) for p in path)
        if array:
            lines.append(f"[[{dotted}]]")
        elif path and (scalars or not (tables or arrays)):
            lines.append(f"[{dotted}]")
        for k, v in scalars:
            lines.append(f"{key(k)} = {val(v)}")
        if scalars or array:
            lines.append("")
        for k, v in tables:
            emit(v, path + [k])
        for k, arr in arrays:
            for item in arr:
                emit(item, path + [k], array=True)

    emit(data, [])
    return "\n".join(lines).strip() + "\n"


def sql_dump(table, headers, rows):
    def ident(s):
        return '"' + str(s).replace('"', '""') + '"'

    def lit(v):
        if v is None or v == "":
            return "NULL"
        if isinstance(v, bool):
            return "TRUE" if v else "FALSE"
        if isinstance(v, (int, float)):
            return repr(v)
        return "'" + str(v).replace("'", "''") + "'"

    types = []
    for i in range(len(headers)):
        col = [r[i] for r in rows if r[i] not in (None, "")]
        if col and all(isinstance(v, int) and not isinstance(v, bool) for v in col):
            types.append("INTEGER")
        elif col and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in col):
            types.append("REAL")
        elif col and all(isinstance(v, bool) for v in col):
            types.append("BOOLEAN")
        else:
            types.append("TEXT")
    out = [f"CREATE TABLE IF NOT EXISTS {ident(table)} (",
           ",\n".join(f"  {ident(h)} {t}" for h, t in zip(headers, types)), ");", ""]
    cols = ", ".join(ident(h) for h in headers)
    for r in rows:
        out.append(f"INSERT INTO {ident(table)} ({cols}) VALUES ({', '.join(lit(v) for v in r)});")
    return "\n".join(out) + "\n"


def write(ctx, data):
    d, out = ctx.dst_fmt, ctx.out()
    data = plain(data)
    if d == "json":
        ind = int(ctx.opts.get("indent", "2"))
        text = json.dumps(data, ensure_ascii=False, indent=ind or None, separators=(",", ":") if not ind else None)
        out.write_text(text + "\n", encoding="utf-8")
    elif d == "jsonl":
        items = data if isinstance(data, list) else [data]
        out.write_text("".join(json.dumps(i, ensure_ascii=False) + "\n" for i in items), encoding="utf-8")
    elif d == "yaml":
        import yaml
        out.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False),
                       encoding="utf-8")
    elif d == "xml":
        if isinstance(data, dict) and len(data) == 1 and not str(next(iter(data))).startswith(("@", "#")):
            k, v = next(iter(data.items()))
            if isinstance(v, list):
                root = ET.Element("root")
                build_xml(root, k, v)
            else:
                holder = ET.Element("holder")
                build_xml(holder, k, v)
                root = holder[0]
        else:
            root = ET.Element("root")
            if isinstance(data, list):
                build_xml(root, "item", data)
            elif isinstance(data, dict):
                for k, v in data.items():
                    build_xml(root, k, v)
            else:
                root.text = cell_text(data)
        ET.indent(root)
        out.write_bytes(b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="utf-8") + b"\n")
    elif d == "toml":
        out.write_text(toml_dumps(data), encoding="utf-8")
    elif d == "ini":
        if not isinstance(data, dict):
            raise ConversionError("INI files need named sections, but this data is a list. Try JSON or YAML instead.")
        cp = configparser.ConfigParser(interpolation=None)
        cp.optionxform = str
        loose = {k: v for k, v in data.items() if not isinstance(v, dict)}
        for k, v in data.items():
            if isinstance(v, dict):
                cp[str(k)] = {str(a): (json.dumps(b, ensure_ascii=False) if isinstance(b, (dict, list)) else cell_text(b))
                              for a, b in v.items()}
        if loose:
            cp["general"] = {str(a): (json.dumps(b, ensure_ascii=False) if isinstance(b, (dict, list)) else cell_text(b))
                             for a, b in loose.items()}
        with open(out, "w", encoding="utf-8") as fh:
            cp.write(fh)
    elif d == "plist":
        def fix(o):
            if isinstance(o, dict):
                return {str(k): fix(v) for k, v in o.items() if v is not None}
            if isinstance(o, list):
                return [fix(v) for v in o if v is not None]
            return o
        out.write_bytes(plistlib.dumps(fix(data) if isinstance(data, (dict, list)) else {"value": data}))
    else:
        headers, rows = to_table(data)
        if not headers:
            raise ConversionError("There's no data in this file to make a table from.")
        if d in ("csv", "tsv"):
            with open(out, "w", encoding="utf-8-sig" if d == "csv" else "utf-8", newline="") as fh:
                w = csv.writer(fh, delimiter="," if d == "csv" else "\t")
                w.writerow(headers)
                for r in rows:
                    w.writerow([cell_text(v) for v in r])
        elif d == "xlsx":
            import openpyxl
            from openpyxl.styles import Font
            from openpyxl.utils import get_column_letter
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = (ctx.stem or "Sheet1")[:31].translate(str.maketrans("", "", "[]:*?/\\")) or "Sheet1"
            ws.append(headers)
            for c in ws[1]:
                c.font = Font(bold=True)
            for r in rows:
                ws.append([v if isinstance(v, (int, float, bool)) or v is None else str(v) for v in r])
            for row in ws.iter_rows(min_row=2):
                for c in row:
                    if isinstance(c.value, str) and c.value.startswith("="):
                        c.data_type = "s"  # show text, never run it as a formula
            for i, h in enumerate(headers, 1):
                width = max([len(str(h))] + [len(cell_text(r[i - 1])) for r in rows[:500]])
                ws.column_dimensions[get_column_letter(i)].width = min(60, max(8, width + 2))
            ws.freeze_panes = "A2"
            wb.save(out)
        elif d == "htmltable":
            head = "".join(f"<th>{html.escape(str(h))}</th>" for h in headers)
            body = "\n".join("<tr>" + "".join(f"<td>{html.escape(cell_text(v))}</td>" for v in r) + "</tr>" for r in rows)
            out.write_text(f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{html.escape(ctx.stem)}</title>
<style>
body{{font:14px/1.5 system-ui,sans-serif;margin:2rem;color:#1d1d1f}}
table{{border-collapse:collapse;width:100%}}
th,td{{padding:.5rem .75rem;border-bottom:1px solid #e5e5ea;text-align:left;vertical-align:top}}
th{{background:#f5f5f7;position:sticky;top:0}}
tr:hover td{{background:#fafafa}}
</style></head><body>
<table><thead><tr>{head}</tr></thead>
<tbody>
{body}
</tbody></table></body></html>
""", encoding="utf-8")
        elif d == "mdtable":
            def esc(v):
                return cell_text(v).replace("|", "\\|").replace("\n", "<br>")
            lines = ["| " + " | ".join(esc(h) for h in headers) + " |",
                     "| " + " | ".join("---" for _ in headers) + " |"]
            lines += ["| " + " | ".join(esc(v) for v in r) + " |" for r in rows]
            out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        elif d == "sql":
            table = re.sub(r"\W+", "_", ctx.stem).strip("_") or "data"
            out.write_text(sql_dump(table, headers, rows), encoding="utf-8")
    return out


for _s in DATA_IN:
    for _d in DATA_OUT:
        if _s == _d or (_s, _d) == ("xlsm", "xlsx"):  # LibreOffice keeps formatting for that one
            continue
        if _s in TABULAR_IN and _d == "ini":  # rows of data have no sections to become INI
            continue
        converter([_s], [_d], options=data_options(_s, _d), requires=data_requires(_s, _d),
                  priority=1, engine="Python")(lambda ctx: write(ctx, load(ctx)))
