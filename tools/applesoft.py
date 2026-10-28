"""Minimal Applesoft tokenizer / relinker, enough to rewrite a few program lines."""
T = ("END FOR NEXT DATA INPUT DEL DIM READ GR TEXT PR# IN# CALL PLOT HLIN VLIN HGR2 HGR HCOLOR= HPLOT DRAW XDRAW "
     "HTAB HOME ROT= SCALE= SHLOAD TRACE NOTRACE NORMAL INVERSE FLASH COLOR= POP VTAB HIMEM: LOMEM: ONERR RESUME "
     "RECALL STORE SPEED= LET GOTO RUN IF RESTORE & GOSUB RETURN REM STOP ON WAIT LOAD SAVE DEF POKE PRINT CONT "
     "LIST CLEAR GET NEW TAB( TO FN SPC( THEN AT NOT STEP + - * / ^ AND OR > = < SGN INT ABS USR FRE SCRN( PDL POS "
     "SQR RND LOG EXP COS SIN TAN ATN PEEK LEN STR$ VAL ASC CHR$ LEFT$ RIGHT$ MID$").split()

def parse(d, base=0x801):
    """-> list of (lineno, body_bytes)"""
    out = []; i = 0
    while i + 1 < len(d):
        nxt = d[i] | d[i+1] << 8
        if nxt == 0: break
        ln = d[i+2] | d[i+3] << 8
        j = d.index(0, i + 4)
        out.append((ln, bytes(d[i+4:j])))
        i = j + 1
    return out

def link(lines, base=0x801):
    out = bytearray(); addr = base
    for ln, body in lines:
        nxt = addr + 4 + len(body) + 1
        out += bytes([nxt & 255, nxt >> 8, ln & 255, ln >> 8]) + body + b'\0'
        addr = nxt
    out += b'\0\0'
    return bytes(out)

def tokenize(src):
    """tokenize the text of one line (without the line number), Applesoft rules"""
    s = src; out = bytearray(); i = 0
    order = sorted(range(len(T)), key=lambda k: -len(T[k]))
    while i < len(s):
        c = s[i]
        if c == '"':
            j = s.find('"', i + 1)
            j = len(s) if j < 0 else j + 1
            out += s[i:j].encode(); i = j; continue
        if c == ' ':
            i += 1; continue
        # keyword match ignoring spaces
        matched = False
        for k in order:
            kw = T[k]; p = i; q = 0
            while q < len(kw) and p < len(s):
                if s[p] == ' ': p += 1; continue
                if s[p].upper() != kw[q]: break
                p += 1; q += 1
            if q == len(kw):
                out.append(0x80 + k); i = p; matched = True
                if kw in ('REM', 'DATA'):
                    # rest literal (DATA until ':' outside quotes)
                    if kw == 'REM':
                        out += s[i:].encode(); i = len(s)
                    else:
                        j = i; inq = False
                        while j < len(s) and (inq or s[j] != ':'):
                            if s[j] == '"': inq = not inq
                            j += 1
                        out += s[i:j].encode(); i = j
                break
        if not matched:
            out += c.upper().encode(); i += 1
    return bytes(out)

def detok(body):
    s = ''
    for c in body:
        s += (' ' + T[c - 0x80] + ' ') if c >= 0x80 else chr(c)
    return s
