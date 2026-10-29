#!/usr/bin/env python3
"""mw2odt.py - convert a MouseWrite document to OpenDocument Text (.odt).

    python3 tools/mw2odt.py DOCUMENT [OUT.odt]

This is the reference for the 6502 exporter in src/mwod.s (File > Export ODT):
it uses exactly the same rules and writes exactly the same content.xml, so the
two can be compared byte for byte.  It also works on a PC, on documents copied
off an Apple II disk.

MouseWrite stores text as fixed-width rows (the ruler width, header byte $41).
A row holding a Return ($0D) ends a paragraph and is padded with spaces; a full
row without one is a soft line wrap.  Style markers are toggles inside the text.
"""
import sys, zlib, struct

MIMETYPE = b'application/vnd.oasis.opendocument.text'

MANIFEST = (b'<?xml version="1.0" encoding="UTF-8"?>'
            b'<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2">'
            b'<manifest:file-entry manifest:full-path="/" manifest:version="1.2" manifest:media-type="application/vnd.oasis.opendocument.text"/>'
            b'<manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>'
            b'</manifest:manifest>')

TP = b'<style:style style:name="%s" style:family="text"><style:text-properties %s/></style:style>'
PROLOGUE = (b'<?xml version="1.0" encoding="UTF-8"?>'
            b'<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
            b'xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" '
            b'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
            b'xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" office:version="1.2">'
            b'<office:automatic-styles>'
            b'<style:style style:name="P" style:family="paragraph"><style:text-properties fo:font-family="Courier New" fo:font-size="12pt"/></style:style>'
            b'<style:style style:name="Q" style:family="paragraph"><style:paragraph-properties fo:break-before="page"/><style:text-properties fo:font-family="Courier New" fo:font-size="12pt"/></style:style>'
            b'<style:style style:name="F" style:family="paragraph"><style:text-properties fo:font-family="Courier New" fo:font-size="10pt"/></style:style>'
            + TP % (b'B', b'fo:font-weight="bold"')
            + TP % (b'U', b'style:text-underline-style="solid" style:text-underline-width="auto" style:text-underline-color="font-color"')
            + TP % (b'I', b'fo:font-style="italic"')
            + TP % (b'K', b'fo:font-variant="small-caps"')
            + TP % (b'S', b'style:text-position="super 58%"')
            + TP % (b'D', b'style:text-position="sub 58%"')
            + TP % (b'N', b'style:text-scale="75%"')
            + TP % (b'W', b'style:text-scale="200%"')
            + b''.join(TP % (b'C%d' % (i + 1), b'fo:color="#%s"' % c) for i, c in
                       enumerate([b'cc0000', b'0000cc', b'cccc00', b'ff8000', b'00a000', b'8000a0']))
            + b'</office:automatic-styles><office:body><office:text>')
EPILOGUE = b'</office:text></office:body></office:document-content>'

# style bits, in the nesting order spans are opened
BITS = [(0x05, b'B'), (0x04, b'U'), (0x0A, b'I'), (0x0B, b'K'), (0x08, b'S'), (0x09, b'D'),
        (0x06, b'N'), (0x07, b'W')]
COLOURS = range(0x13, 0x19)          # red blue yellow orange green purple


def convert(rows_text, width):
    """rows_text: the document text (multiple of width bytes). returns content.xml body"""
    out = bytearray()
    on = set(); colour = 0          # current style state
    opened = 0                      # spans currently open in the output
    dirty = False
    inpara = False; pending = 0; skipping = False; nextq = False; para_style = b'P'

    def close_spans():
        nonlocal opened
        out.extend(b'</text:span>' * opened); opened = 0

    def open_para():
        nonlocal inpara, nextq
        out.extend(b'<text:p text:style-name="' + para_style + b'">')
        inpara = True

    for r in range(0, len(rows_text), width):
        row = rows_text[r:r + width]
        start = 0
        if not inpara:
            if row[0] == 0x1E:                       # custom font command row
                skipping = True
            para_style = b'F' if row[0] == 0x1A else (b'Q' if nextq else b'P')
        if skipping:
            if 0x0D in row:
                skipping = False
            continue
        ended = False
        for c in row[start:]:
            if c == 0x0D:
                if not inpara:
                    out.extend(b'<text:p text:style-name="' + para_style + b'"/>')
                else:
                    close_spans(); out.extend(b'</text:p>')
                inpara = False; pending = 0; nextq = False; dirty = bool(on or colour)
                ended = True
                break
            if c == 0x20:
                pending += 1; continue
            if c == 0x0C:
                nextq = True
                if not inpara: para_style = b'Q'
                continue
            if c < 0x20:
                if c in COLOURS:
                    colour = 0 if colour == c else c; dirty = True
                else:
                    for code, _ in BITS:
                        if c == code:
                            on ^= {code}; dirty = True
                continue
            # printable
            if not inpara:
                open_para()
            if dirty:
                close_spans()
            if pending:
                if pending == 1 and out[-1:] != b'>':
                    out.extend(b' ')
                else:
                    out.extend(b'<text:s text:c="%d"/>' % pending)
                pending = 0
            if dirty:
                for code, name in BITS:
                    if code in on:
                        out.extend(b'<text:span text:style-name="' + name + b'">'); opened += 1
                if colour:
                    out.extend(b'<text:span text:style-name="C%d">' % (colour - 0x12)); opened += 1
                dirty = False
            c &= 0x7F
            out.extend(b'&amp;' if c == 0x26 else b'&lt;' if c == 0x3C else b'&gt;' if c == 0x3E else bytes([c]))
        if not ended and inpara:
            # soft wrap = one space, except straight after a hyphenated word
            t = row.rstrip(b' ')
            pending = 0 if (pending == len(row) - len(t) and len(t) >= 2 and t[-1] == 0x2D and t[-2] != 0x20) else 1
    if inpara:
        close_spans(); out.extend(b'</text:p>')
    return bytes(out)


def zip_odt(content):
    """the exact ZIP layout the 6502 exporter writes (all entries stored)"""
    files = [(b'mimetype', MIMETYPE), (b'META-INF/manifest.xml', MANIFEST), (b'content.xml', content)]
    out = bytearray(); cd = bytearray()
    for name, data in files:
        crc = zlib.crc32(data) & 0xffffffff
        off = len(out)
        out += struct.pack('<IHHHHHIIIHH', 0x04034b50, 10, 0, 0, 0, 0x21, crc, len(data), len(data), len(name), 0) + name + data
        cd += struct.pack('<IHHHHHHIIIHHHHHII', 0x02014b50, 10, 10, 0, 0, 0, 0x21, crc, len(data), len(data),
                          len(name), 0, 0, 0, 0, 0, off) + name
    eocd = struct.pack('<IHHHHIIH', 0x06054b50, 0, 0, 3, 3, len(cd), len(out), 0)
    return bytes(out + cd + eocd)


def document_to_odt(doc):
    if doc[:2] != b'MW':
        raise ValueError('not a MouseWrite document')
    width = doc[0x41]
    text = doc[0x200:]
    text = text[:len(text) // width * width]
    return zip_odt(PROLOGUE + convert(text, width) + EPILOGUE)


if __name__ == '__main__':
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else src + '.odt'
    open(dst, 'wb').write(document_to_odt(open(src, 'rb').read()))
    print(dst)
