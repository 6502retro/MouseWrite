#!/usr/bin/env python3
"""MouseWrite 3.0 - one-step build from your own MouseWrite disk images.

    python3 build.py                       # reads every disk image in originals/
    python3 build.py DISK1 DISK2 ...       # or name the images yourself
    python3 build.py --install-into A2DeskTop.hdv [--folder MOUSEWRITE]

Needs the MouseWrite 2.6.8b 800K disk (.2mg / .po).  Optional extras, picked up
automatically when present: the 5.25" SPELLER disk (its personal dictionary
words are merged in), the Art Pack disks, and the MouseWrite 1.5.7 disk.

Writes to out/:
  MouseWrite_3.0_Folder.hdv   2 MB ProDOS disk /MWINSTALL holding the MOUSEWRITE
                              folder (and MW.V1.5.7), to copy onto any hard disk
  files/                      every new or changed file, for updating by hand
  <your hard disk>.hdv        with --install-into: a copy of that image with the
                              folders added (the image you name is not changed)
"""
import argparse, hashlib, os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'tools'))
from a2disk import ProDOS, load_raw, dos_to_po, format_prodos      # noqa: E402
import applesoft                                                    # noqa: E402

SHA = {
    'MW.SYSTEM': '5daa80bf0e62e197455731985b1cbb4337c44d80',     # 2.6.8b
    'MW.UI': '57658803ee103a5c932b19ecb8b1e95282baa24f',
    'MW.GP': '5985a65279a7138b344d393eda6bda645eda35c3',
    'STARTUP': 'c46cd30291fa1a1651dccf8a06a94cd65744024f',
    'CF.GLOSS': '33a169534df448bb72fc6ddc1c7c2e79ed8b2dfd',
    'MW.SYSTEM.1.5.7': '104075c04428cdeec01a635d039e8a75e94a4ba4',
}
ART_NAMES = {'ART3': 'ART3.0', 'ARTPAK3.1': 'ART3.1', 'ARTPAK3.2': 'ART3.2', 'ART4': 'ART4'}
sha1 = lambda b: hashlib.sha1(b).hexdigest()


def die(msg):
    sys.exit('build.py: ' + msg)


# ----------------------------------------------------------------- reading disks
class Tree:
    """files of a ProDOS volume in catalog (pre-order) order"""
    def __init__(self, path):
        d, kind, _ = load_raw(path)
        if kind == 'do':
            d = dos_to_po(d)
        self.vol = ProDOS(d)
        self.name = self.vol.volname
        self.files = []      # [path, data, type, aux, access, ctime, mtime]
        for e in self.vol.walk():
            if e['storage'] == 0xD:
                continue
            r = e['raw']
            self.files.append([e['path'], self.vol.read(e), e['type'], e['aux'], e['access'],
                               r[0x18:0x1c], r[0x21:0x25]])

    def get(self, p):
        for f in self.files:
            if f[0].upper() == p.upper():
                return f
        return None


def classify(paths):
    found = {'main': None, 'speller': None, 'art': [], 'v157': None}
    for p in paths:
        try:
            t = Tree(p)
        except Exception:
            print('  skipping %s (not a ProDOS disk image)' % os.path.basename(p))
            continue
        ms = t.get('MW.SYSTEM')
        if ms and sha1(ms[1]) == SHA['MW.SYSTEM']:
            found['main'] = t; what = 'MouseWrite 2.6.8b'
        elif ms and sha1(ms[1]) == SHA['MW.SYSTEM.1.5.7']:
            found['v157'] = t; what = 'MouseWrite 1.5.7'
        elif t.get('AUX.DICT.S') and t.get('MAIN.DICT') and not ms:
            found['speller'] = t; what = 'speller disk'
        elif t.get('DISK.INFO') and any(f[2] == 0xF2 for f in t.files):
            found['art'].append(t); what = 'Art Pack'
        else:
            what = 'not used'
        print('  %-45s /%-12s %s' % (os.path.basename(p)[:45], t.name, what))
    if not found['main']:
        die('no MouseWrite 2.6.8b disk found (its MW.SYSTEM must have SHA-1 %s)' % SHA['MW.SYSTEM'])
    found['art'].sort(key=lambda t: ART_NAMES.get(t.name, t.name))
    return found


# ----------------------------------------------------------------- patches
def check(name, data, key=None):
    if sha1(data) != SHA[key or name]:
        die('%s on your disk is not the expected 2.6.8b release (SHA-1 %s)' % (name, sha1(data)))


def replace_once(buf, old, new):
    i = buf.find(old)
    if i < 0 or buf.find(old, i + 1) >= 0 or len(old) != len(new):
        die('patch site not found: %r' % old[:40])
    buf[i:i + len(old)] = new


def assemble():
    """returns the MW.SYSTEM add-on; re-assembles it if cc65 is installed"""
    pre = os.path.join(HERE, 'prebuilt', 'mwfix3.bin')
    ca65, ld65 = shutil.which('ca65'), shutil.which('ld65')
    if not (ca65 and ld65):
        print('  cc65 not found: using prebuilt/mwfix3.bin')
        return open(pre, 'rb').read()
    b = os.path.join(HERE, 'build'); os.makedirs(b, exist_ok=True)
    src = os.path.join(HERE, 'src')
    run = lambda *a: subprocess.run(a, check=True, cwd=b)
    run(ca65, os.path.join(src, 'mwbody.s'), '-o', 'mwbody.o')
    run(ld65, '-C', os.path.join(src, 'mwbody.cfg'), 'mwbody.o', '-o', 'mwbody.bin')
    run(ca65, os.path.join(src, 'mwfix3.s'), '-I', b, '--bin-include-dir', b, '-o', 'mwfix3.o')
    run(ld65, '-C', os.path.join(src, 'mwfix3.cfg'), 'mwfix3.o', '-o', 'mwfix3.bin')
    out = open(os.path.join(b, 'mwfix3.bin'), 'rb').read()
    same = out == open(pre, 'rb').read()
    print('  assembled src/ with cc65 (%s prebuilt/)' % ('identical to' if same else 'DIFFERS from'))
    return out


def make_mw_system(orig, addon):
    check('MW.SYSTEM', orig)
    m = bytearray(orig)
    hi = lambda s: bytes(c | 0x80 for c in s.encode())

    def boxline(text, width):
        pad = width - 2 - len(text); l = pad // 2
        return '|' + ' ' * l + text + ' ' * (pad - l) + '|'
    old_v = '|                             Version 2.6.8b                               |'
    w = len(old_v)
    replace_once(m, hi(old_v), hi(boxline('Version 3.0', w)))
    i = m.find(hi(boxline('Version 3.0', w)))
    j = m.find(hi('|' + ' ' * (w - 2) + '|'), i)          # the blank line after it
    m[j:j + w] = hi(boxline('Updated by 6502 Retro 2026', w))
    replace_once(m, hi('Expanded Desktop Version 2.6.8b'), hi(' Expanded Desktop Version 3.0  '))
    m += addon
    m[1:3] = b'\x1a\x3e'                                   # JMP $3E1A: the add-on runs first
    return bytes(m)


def make_mw_ui(orig, speller_path):
    check('MW.UI', orig)
    u = bytearray(orig)
    replace_once(u, b'Version 2.6.8b by Steve Cochard', b'Version 3.0 by Steve Cochard   ')
    setpath(u, 0x3A, 0x3B, speller_path, 0x20)
    return bytes(u)


def make_mw_gp(orig, base):
    check('MW.GP', orig)
    g = bytearray(orig)
    setpath(g, 0x3E, 0x00, base + 'SAMPLES/', 0)
    setpath(g, 0x3F, 0x40, base + 'ACCESSORY/', 0)
    return bytes(g)


def setpath(buf, lenoff, stroff, path, fill):
    p = path.encode()
    if len(p) > 61:
        die('folder path too long for MouseWrite: ' + path)
    buf[stroff:stroff + 62] = bytes([fill]) * 62
    buf[stroff:stroff + len(p)] = p
    buf[stroff + len(p)] = 0x20
    buf[lenoff] = len(p)


def make_startup(orig):
    check('STARTUP', orig)
    out = []
    for ln, b in applesoft.parse(orig):
        if ln == 120:
            b = b.replace(b'"verify /MOUSEWRITE/MOUSE.TUTORIAL"', b'"verify STARTUP1"')
            b = b.replace(b':\xba\xe7(4)"prefix /MOUSEWRITE/MOUSE.TUTORIAL"', b'')
            out.append((ln, b))
        elif ln == 210:
            out.append((210, applesoft.tokenize(
                'PRINT CHR$(4)"PREFIX": INPUT P$: FOR I = LEN(P$) - 1 TO 2 STEP - 1: '
                'IF MID$(P$,I,1) <> "/" THEN NEXT')))
            out.append((211, applesoft.tokenize(
                'P$ = LEFT$(P$,I): PRINT CHR$(4)"verify "P$"MW.SYSTEM": POKE 216,0: VTAB 10: '
                'CALL -958: VTAB 15: HTAB 27: INVERSE : PRINT " Now moving to MouseWrite ";: '
                'NORMAL : PRINT CHR$(4)"prefix "P$: PRINT CHR$(4)"-MW.SYSTEM": END')))
        else:
            out.append((ln, b))
    return applesoft.link(out)


def build_folder(found, base, addon):
    """the MOUSEWRITE folder, as an ordered file list relative to the folder"""
    t = found['main']
    files = []
    for f in t.files:
        p, data = f[0], f[1]
        if p == 'PRODOS':
            continue
        f = list(f)
        if p == 'MW.SYSTEM':
            f[1] = make_mw_system(data, addon)
            files.append(f)
            splash = open(os.path.join(HERE, 'prebuilt', 'MW.SPLASH'), 'rb').read()
            files.append(['MW.SPLASH', splash, 0x06, 0x2000, 0xE3, f[5], f[6]])
            continue
        if p == 'MW.UI':
            f[1] = make_mw_ui(data, base + 'SPELLER/')
        elif p == 'MW.GP':
            f[1] = make_mw_gp(data, base)
        elif p == 'SAMPLES/CF.GLOSS':
            check('CF.GLOSS', data)
            f[1] = data.replace(b'/MOUSEWRITE/ACCESSORY/FONTS/', (base + 'ACCESSORY/FONTS/').encode())
        elif p == 'MOUSE.TUTORIAL/STARTUP':
            f[1] = make_startup(data)
        elif p == 'SPELLER/AUX.DICT.S':
            words = set(w for w in data.split(b'\r') if w)
            if found['speller']:
                words |= set(w for w in found['speller'].get('AUX.DICT.S')[1].split(b'\r') if w)
            f[1] = b'\r'.join(sorted(words)) + b'\r'
        files.append(f)
    for a in found['art']:
        for f in a.files:
            f = list(f); f[0] = 'ART.PACKS/%s/%s' % (ART_NAMES.get(a.name, a.name), f[0])
            files.append(f)
    return files


# ----------------------------------------------------------------- writing disks
def install(vol, dest, files):
    """add files (ordered, relative paths) under folder dest of a ProDOS volume"""
    cur = ''
    for part in [p for p in dest.split('/') if p]:
        vol.mkdir(cur, part); cur = (cur + '/' + part).strip('/')
    made = set()
    for p, data, typ, aux, acc, ct, mt in files:
        d = os.path.dirname(p)
        parts = d.split('/') if d else []
        for k in range(len(parts)):
            sub = '/'.join(parts[:k + 1])
            if sub not in made:
                vol.mkdir((cur + '/' + '/'.join(parts[:k])).strip('/'), parts[k]); made.add(sub)
        vol.write((cur + '/' + d).strip('/'), os.path.basename(p), data, typ, aux, acc,
                  ctime=ct, mtime=mt)


def save(path, vol, hdr):
    d = bytes(vol.d)
    if hdr:
        d = hdr[0] + d + hdr[1]
    open(path, 'wb').write(d)


def put_everything(vol, folder, found, addon):
    base = '/%s/%s/' % (vol.volname, folder.strip('/'))
    files = build_folder(found, base, addon)
    install(vol, folder, files)
    if found['v157']:
        install(vol, 'MW.V1.5.7', [f for f in found['v157'].files if f[0] != 'PRODOS'])
    return files


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('disks', nargs='*', help='disk images (default: everything in originals/)')
    ap.add_argument('--install-into', metavar='HDD', help='also install into a copy of this ProDOS hard-disk image')
    ap.add_argument('--folder', default='MOUSEWRITE', help='folder name/path on that disk (default MOUSEWRITE)')
    a = ap.parse_args()

    disks = a.disks or sorted(os.path.join(HERE, 'originals', f) for f in os.listdir(os.path.join(HERE, 'originals'))
                              if re.search(r'\.(2mg|po|dsk|do|hdv)$', f, re.I))
    if not disks:
        die('put your MouseWrite disk images in originals/ (see originals/README.md)')
    print('Disks:')
    found = classify(disks)
    print('Building:')
    addon = assemble()

    out = os.path.join(HERE, 'out'); os.makedirs(out, exist_ok=True)
    vol = ProDOS(format_prodos(4096, 'MWINSTALL'))
    files = put_everything(vol, 'MOUSEWRITE', found, addon)
    save(os.path.join(out, 'MouseWrite_3.0_Folder.hdv'), vol, None)
    print('  out/MouseWrite_3.0_Folder.hdv   /MWINSTALL/MOUSEWRITE (+ MW.V1.5.7)' if found['v157']
          else '  out/MouseWrite_3.0_Folder.hdv   /MWINSTALL/MOUSEWRITE')

    fd = os.path.join(out, 'files'); shutil.rmtree(fd, ignore_errors=True)
    changed = {'MW.SYSTEM', 'MW.SPLASH', 'MW.UI', 'MW.GP', 'SAMPLES/CF.GLOSS',
               'MOUSE.TUTORIAL/STARTUP', 'SPELLER/AUX.DICT.S'}
    for f in files:
        if f[0] in changed:
            p = os.path.join(fd, f[0]); os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, 'wb').write(f[1])
    print('  out/files/                      %d new or changed files' % len(changed))

    if a.install_into:
        d, kind, hdr = load_raw(a.install_into)
        if kind == 'do':
            die('--install-into needs a ProDOS-order hard-disk image (.hdv / .po / .2mg)')
        v = ProDOS(d)
        if v.find(a.folder.strip('/')):
            die('/%s/%s already exists on that disk' % (v.volname, a.folder.strip('/')))
        put_everything(v, a.folder.strip('/'), found, addon)
        dst = os.path.join(out, os.path.basename(a.install_into))
        save(dst, v, hdr)
        print('  out/%-27s /%s/%s added' % (os.path.basename(dst), v.volname, a.folder.strip('/')))

    r = subprocess.run([sys.executable, os.path.join(HERE, 'tools', 'fsck.py'),
                        os.path.join(out, 'MouseWrite_3.0_Folder.hdv')], capture_output=True, text=True)
    print('  ' + r.stdout.strip().splitlines()[0])
    print('Done.')


if __name__ == '__main__':
    main()
