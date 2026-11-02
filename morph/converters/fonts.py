"""Font conversions with fontTools: TTF ⇄ OTF and desktop ⇄ web fonts (WOFF/WOFF2)."""
from core.registry import ConversionError, converter

FONTS = ["ttf", "otf", "woff", "woff2"]


def _reqs(s, d):
    r = ["py:fontTools"]
    if "woff2" in (s, d):
        r.append("py:brotli")
    return r


def cff_to_glyf(font):
    """OpenType/CFF (cubic curves) -> TrueType (quadratic curves)."""
    from fontTools.pens.cu2quPen import Cu2QuPen
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from fontTools.ttLib import newTable

    order = font.getGlyphOrder()
    gs = font.getGlyphSet()
    quad = {}
    for name in order:
        tt = TTGlyphPen(gs)
        gs[name].draw(Cu2QuPen(tt, max_err=1.0, reverse_direction=True))
        quad[name] = tt.glyph()
    font["loca"] = newTable("loca")
    font["glyf"] = glyf = newTable("glyf")
    glyf.glyphOrder = order
    glyf.glyphs = quad
    for t in ("CFF ", "VORG"):
        if t in font:
            del font[t]
    glyf.compile(font)
    hmtx = font["hmtx"]
    for name, g in glyf.glyphs.items():
        if hasattr(g, "xMin"):
            hmtx[name] = (hmtx[name][0], g.xMin)
    font["maxp"] = maxp = newTable("maxp")
    maxp.tableVersion = 0x00010000
    for attr in ("maxZones", "maxTwilightPoints", "maxStorage", "maxFunctionDefs", "maxInstructionDefs",
                 "maxStackElements", "maxSizeOfInstructions", "maxComponentElements"):
        setattr(maxp, attr, 0)
    maxp.maxZones = 1
    maxp.compile(font)
    post = font["post"]
    post.formatType = 2.0
    post.extraNames, post.mapping, post.glyphOrder = [], {}, order
    try:
        post.compile(font)
    except OverflowError:
        post.formatType = 3.0
    font["head"].glyphDataFormat = 0
    font.sfntVersion = "\x00\x01\x00\x00"


def glyf_to_cff(font, fallback_name):
    """TrueType (quadratic) -> OpenType/CFF (cubic)."""
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.t2CharStringPen import T2CharStringPen

    order = font.getGlyphOrder()
    gs = font.getGlyphSet()
    hmtx = font["hmtx"]
    charstrings = {}
    for name in order:
        pen = T2CharStringPen(hmtx[name][0], gs)
        gs[name].draw(pen)
        charstrings[name] = pen.getCharString()
    names = font["name"]
    ps = (names.getDebugName(6) or fallback_name).replace(" ", "")[:60]
    info = {"FullName": names.getDebugName(4) or ps, "FamilyName": names.getDebugName(1) or ps,
            "Weight": names.getDebugName(2) or "Regular"}
    for t in ("glyf", "loca", "fpgm", "prep", "cvt ", "hdmx", "LTSH", "VDMX", "gvar", "cvar"):
        if t in font:
            del font[t]
    fb = FontBuilder(font=font, isTTF=False)
    fb.setupCFF(ps, info, charstrings, {})
    font["maxp"].tableVersion = 0x00005000
    font["post"].formatType = 3.0
    font.sfntVersion = "OTTO"


def convert_font(ctx):
    from fontTools.ttLib import TTFont, TTLibError
    try:
        font = TTFont(str(ctx.src), recalcBBoxes=True)
    except TTLibError as e:
        raise ConversionError(f"This font couldn't be read: {e}")
    if "fvar" in font and ctx.dst_fmt in ("ttf", "otf") and (
            ("CFF2" in font) or (ctx.dst_fmt == "otf" and "glyf" in font)):
        raise ConversionError("Variable fonts can only be wrapped as WOFF/WOFF2, not re-outlined.")
    is_cff = "CFF " in font or "CFF2" in font
    d = ctx.dst_fmt
    ctx.progress(None, "Rebuilding glyphs…")
    try:
        if d in ("woff", "woff2"):
            font.flavor = d
        else:
            font.flavor = None
            if d == "ttf" and is_cff:
                if "CFF2" in font:
                    raise ConversionError("CFF2 fonts can't be turned into TTF yet.")
                cff_to_glyf(font)
            elif d == "otf" and not is_cff:
                glyf_to_cff(font, ctx.stem)
        out = ctx.out()
        font.save(str(out))
    except ConversionError:
        raise
    except Exception as e:
        raise ConversionError(f"fontTools couldn't convert this font: {e}")
    return out


for _s in FONTS:
    for _d in FONTS:
        if _s != _d:
            converter([_s], [_d], requires=_reqs(_s, _d), engine="fontTools")(convert_font)
