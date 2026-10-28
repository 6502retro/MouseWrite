"""Apple II disk image library: ProDOS (read/write) + DOS 3.3 (read).
Handles .dsk/.do (DOS order), .po/.hdv (ProDOS order), .2mg."""
import struct, sys, os, datetime

D2P = [0, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 15]  # prodos sector p lives in dos sector D2P[p]... (used as po[p]=do[D2P[p]])

TYPES = {0x00:'NON',0x04:'TXT',0x06:'BIN',0x0F:'DIR',0x19:'ADB',0x1A:'AWP',0x1B:'ASP',
         0xB3:'S16',0xC0:'PNT',0xC1:'PIC',0xE0:'LBR',0xEF:'PAS',0xF0:'CMD',0xF8:'$F8',
         0xFC:'BAS',0xFD:'VAR',0xFE:'REL',0xFF:'SYS',0x08:'FOT',0xCA:'ICN',0xF1:'$F1',
         0xF2:'$F2',0xF3:'$F3',0xF4:'$F4',0xF5:'$F5',0xF6:'$F6',0xF7:'$F7'}

def dos_to_po(d):
    o = bytearray(len(d))
    for t in range(len(d) // 4096):
        for p in range(16):
            s = D2P[p]
            o[(t*16+p)*256:(t*16+p+1)*256] = d[(t*16+s)*256:(t*16+s+1)*256]
    return o

def po_to_dos(d):
    o = bytearray(len(d))
    for t in range(len(d) // 4096):
        for p in range(16):
            s = D2P[p]
            o[(t*16+s)*256:(t*16+s+1)*256] = d[(t*16+p)*256:(t*16+p+1)*256]
    return o

def load_raw(fn):
    """returns (bytes, kind, header) kind in 'po','do'; header for 2mg"""
    d = open(fn, 'rb').read()
    hdr = None
    if d[:4] == b'2IMG':
        hl = struct.unpack('<H', d[8:10])[0]
        fmt = struct.unpack('<I', d[0x0c:0x10])[0]
        off = struct.unpack('<I', d[0x18:0x1c])[0]
        ln = struct.unpack('<I', d[0x1c:0x20])[0]
        hdr = (d[:off], d[off+ln:])
        d = d[off:off+ln]
        return bytearray(d), ('do' if fmt == 0 else 'po'), hdr
    ext = os.path.splitext(fn)[1].lower()
    if ext in ('.po', '.hdv'):
        return bytearray(d), 'po', None
    if len(d) == 143360:
        # guess: check prodos volume dir at block 2 under each order
        po = dos_to_po(d)
        if (po[0x404] >> 4) == 0xF and po[0x400:0x402] == b'\0\0':
            return po, 'po_from_do', None
        if (d[0x404] >> 4) == 0xF and d[0x400:0x402] == b'\0\0':
            return bytearray(d), 'po', None
        return bytearray(d), 'do', None
    return bytearray(d), 'po', None


class ProDOS:
    def __init__(self, data):
        self.d = data
        vh = self.blk(2)
        assert (vh[4] >> 4) == 0xF, 'not prodos'
        nl = vh[4] & 15
        self.volname = vh[5:5+nl].decode()
        self.bitmap = struct.unpack('<H', vh[0x27:0x29])[0]
        self.total = struct.unpack('<H', vh[0x29:0x2b])[0]

    def blk(self, n):
        return self.d[n*512:(n+1)*512]

    def wblk(self, n, b):
        assert len(b) == 512
        self.d[n*512:(n+1)*512] = b

    def entries(self, key):
        """yield (entry dict) for a directory starting at block key"""
        b = key; first = True
        while b:
            blk = self.blk(b)
            elen, epb = (blk[0x23], blk[0x24]) if first else (self._elen, self._epb)
            if first:
                self._elen, self._epb = elen, epb
            start = 1 if first else 0
            for i in range(start, epb):
                off = 4 + i * elen
                e = blk[off:off+elen]
                st = e[0] >> 4
                if st == 0: continue
                nl = e[0] & 15
                yield dict(name=e[1:1+nl].decode(), storage=st, type=e[0x10],
                           key=struct.unpack('<H', e[0x11:0x13])[0],
                           blocks=struct.unpack('<H', e[0x13:0x15])[0],
                           eof=e[0x15] | e[0x16] << 8 | e[0x17] << 16,
                           aux=struct.unpack('<H', e[0x1f:0x21])[0],
                           access=e[0x1e], dirblk=b, diroff=off, raw=bytes(e))
            first = False
            b = struct.unpack('<H', blk[2:4])[0]

    def walk(self, key=2, path=''):
        for e in self.entries(key):
            e['path'] = path + e['name']
            yield e
            if e['storage'] == 0xD:
                yield from self.walk(e['key'], e['path'] + '/')

    def find(self, path):
        for e in self.walk():
            if e['path'].upper() == path.upper():
                return e

    def _datablocks(self, e):
        st, key, eof = e['storage'], e['key'], e['eof']
        n = (eof + 511) // 512
        if st == 1: return [key]
        if st == 2:
            ib = self.blk(key); return [ib[i] | ib[256+i] << 8 for i in range(min(n, 256))]
        if st == 3:
            mb = self.blk(key); out = []
            for j in range(128):
                ik = mb[j] | mb[256+j] << 8
                if len(out) >= n: break
                if ik == 0: out += [0]*256; continue
                ib = self.blk(ik); out += [ib[i] | ib[256+i] << 8 for i in range(256)]
            return out[:n]
        if st == 0xD:
            out = []; b = key
            while b: out.append(b); b = struct.unpack('<H', self.blk(b)[2:4])[0]
            return out
        if st == 5:
            raise ValueError('forked file')
        raise ValueError('storage %x' % st)

    def read(self, e):
        out = bytearray()
        for b in self._datablocks(e):
            out += self.blk(b) if b else bytes(512)
        return bytes(out[:e['eof']]) if e['storage'] != 0xD else bytes(out)

    # ---------- writing ----------
    def _bm(self):
        nb = (self.total + 4095) // 4096
        return bytearray(b''.join(self.blk(self.bitmap + i) for i in range(nb)))

    def _bm_save(self, bm):
        for i in range(len(bm) // 512):
            self.wblk(self.bitmap + i, bytes(bm[i*512:(i+1)*512]))

    def free_count(self):
        bm = self._bm(); return sum(bin(x).count('1') for x in bm[:(self.total+7)//8])

    def alloc(self, n=1):
        bm = self._bm(); got = []
        for b in range(self.total):
            if bm[b >> 3] & (0x80 >> (b & 7)):
                bm[b >> 3] &= ~(0x80 >> (b & 7)) & 0xFF
                got.append(b)
                if len(got) == n: break
        if len(got) < n: raise IOError('disk full')
        self._bm_save(bm)
        for b in got: self.wblk(b, bytes(512))
        return got

    def free(self, blocks):
        bm = self._bm()
        for b in blocks:
            bm[b >> 3] |= (0x80 >> (b & 7))
        self._bm_save(bm)

    @staticmethod
    def _now():
        t = datetime.datetime(1986, 1, 1, 12, 0)
        d = ((t.year - 1900) % 100) << 9 | t.month << 5 | t.day
        return struct.pack('<HH', d, t.hour << 8 | t.minute)

    def _dir_header(self, key):
        return self.blk(key)

    def _add_entry(self, dirkey, entry_bytes):
        """place a 39-byte entry into directory; extend if needed. returns (blk, off)"""
        b = dirkey; first = True; last = None
        while b:
            blk = bytearray(self.blk(b))
            for i in range(1 if first else 0, 13):
                off = 4 + i * 39
                if blk[off] >> 4 == 0:
                    blk[off:off+39] = entry_bytes
                    self.wblk(b, bytes(blk))
                    self._bump_count(dirkey, +1)
                    return b, off
            first = False; last = b
            b = struct.unpack('<H', blk[2:4])[0]
        # extend directory (not for volume dir beyond fixed blocks)
        if dirkey == 2:
            raise IOError('volume directory full')
        nb = self.alloc(1)[0]
        lb = bytearray(self.blk(last)); lb[2:4] = struct.pack('<H', nb); self.wblk(last, bytes(lb))
        blk = bytearray(512); blk[0:2] = struct.pack('<H', last)
        blk[4:4+39] = entry_bytes; self.wblk(nb, bytes(blk))
        # update parent's entry: blocks & eof
        hdr = self.blk(dirkey)
        pp = struct.unpack('<H', hdr[0x27:0x29])[0]; pe = hdr[0x29]
        pb = bytearray(self.blk(pp)); off = 4 + (pe - 1) * 39
        nblk = struct.unpack('<H', pb[off+0x13:off+0x15])[0] + 1
        pb[off+0x13:off+0x15] = struct.pack('<H', nblk)
        eof = nblk * 512; pb[off+0x15:off+0x18] = bytes([eof & 255, eof >> 8 & 255, eof >> 16])
        self.wblk(pp, bytes(pb))
        self._bump_count(dirkey, +1)
        return nb, 4

    def _bump_count(self, dirkey, d):
        h = bytearray(self.blk(dirkey))
        c = struct.unpack('<H', h[0x25:0x27])[0] + d
        h[0x25:0x27] = struct.pack('<H', c); self.wblk(dirkey, bytes(h))

    def _entry(self, name, st, ftype, key, blocks, eof, aux, dirkey, access=0xE3, ctime=None, mtime=None):
        e = bytearray(39)
        e[0] = st << 4 | len(name); e[1:1+len(name)] = name.upper().encode()
        e[0x10] = ftype; e[0x11:0x13] = struct.pack('<H', key)
        e[0x13:0x15] = struct.pack('<H', blocks)
        e[0x15:0x18] = bytes([eof & 255, eof >> 8 & 255, eof >> 16 & 255])
        e[0x18:0x1c] = ctime or self._now(); e[0x1c] = 0; e[0x1d] = 0
        e[0x1e] = access; e[0x1f:0x21] = struct.pack('<H', aux)
        e[0x21:0x25] = mtime or self._now(); e[0x25:0x27] = struct.pack('<H', dirkey)
        return e

    def dirkey(self, path):
        if path in ('', '/'): return 2
        e = self.find(path.strip('/')); assert e and e['storage'] == 0xD, path
        return e['key']

    def delete(self, path):
        e = self.find(path)
        if not e: return
        assert e['storage'] != 0xD
        blocks = [b for b in self._datablocks(e) if b]
        if e['storage'] == 2: blocks.append(e['key'])
        if e['storage'] == 3:
            mb = self.blk(e['key'])
            blocks += [mb[j] | mb[256+j] << 8 for j in range(128) if mb[j] | mb[256+j] << 8] + [e['key']]
        self.free(blocks)
        blk = bytearray(self.blk(e['dirblk'])); blk[e['diroff']] = 0; self.wblk(e['dirblk'], bytes(blk))
        parent = e['path'].rsplit('/', 1)[0] if '/' in e['path'] else ''
        self._bump_count(self.dirkey(parent), -1)

    def mkdir(self, parent, name):
        pk = self.dirkey(parent)
        ex = [e for e in self.entries(pk) if e['name'].upper() == name.upper()]
        if ex: return ex[0]['key']
        kb = self.alloc(1)[0]
        b, off = self._add_entry(pk, self._entry(name, 0xD, 0x0F, kb, 1, 512, 0, pk))
        h = bytearray(512)
        h[4] = 0xE << 4 | len(name); h[5:5+len(name)] = name.upper().encode()
        h[0x14] = 0x75  # reserved per spec
        h[0x1c:0x20] = self._now(); h[0x22] = 0xE3; h[0x23] = 0x27; h[0x24] = 0x0D
        h[0x27:0x29] = struct.pack('<H', b); h[0x29] = (off - 4) // 39 + 1; h[0x2a] = 0x27
        self.wblk(kb, bytes(h))
        return kb

    def write(self, parent, name, data, ftype, aux, access=0xE3, replace=True, ctime=None, mtime=None):
        pk = self.dirkey(parent)
        ex = [e for e in self.entries(pk) if e['name'].upper() == name.upper()]
        if ex:
            if not replace: raise IOError('exists')
            self.delete((parent.strip('/') + '/' if parent.strip('/') else '') + ex[0]['name'])
        n = max(1, (len(data) + 511) // 512)
        db = self.alloc(n)
        for i, b in enumerate(db):
            self.wblk(b, bytes(data[i*512:(i+1)*512]).ljust(512, b'\0'))
        if n == 1:
            st, key, tot = 1, db[0], 1
        elif n <= 256:
            ib = self.alloc(1)[0]; blk = bytearray(512)
            for i, b in enumerate(db): blk[i] = b & 255; blk[256+i] = b >> 8
            self.wblk(ib, bytes(blk)); st, key, tot = 2, ib, n + 1
        else:
            nib = (n + 255) // 256
            mb = self.alloc(1)[0]; mblk = bytearray(512); ibs = self.alloc(nib)
            for j, ibk in enumerate(ibs):
                blk = bytearray(512)
                for i, b in enumerate(db[j*256:(j+1)*256]): blk[i] = b & 255; blk[256+i] = b >> 8
                self.wblk(ibk, bytes(blk)); mblk[j] = ibk & 255; mblk[256+j] = ibk >> 8
            self.wblk(mb, bytes(mblk)); st, key, tot = 3, mb, n + nib + 1
        self._add_entry(pk, self._entry(name, st, ftype, key, tot, len(data), aux, pk, access, ctime, mtime))


class DOS33:
    def __init__(self, d):
        self.d = d
    def sec(self, t, s):
        o = (t*16+s)*256; return self.d[o:o+256]
    def catalog(self):
        vtoc = self.sec(17, 0); t, s = vtoc[1], vtoc[2]; out = []
        seen = set()
        while t and (t, s) not in seen:
            seen.add((t, s)); c = self.sec(t, s)
            for i in range(7):
                e = c[0x0b + i*35: 0x0b + (i+1)*35]
                if e[0] in (0, 0xFF): continue
                name = bytes(x & 0x7f for x in e[3:33]).decode('latin1').rstrip()
                out.append(dict(name=name, type=e[2], ts=(e[0], e[1]), sectors=e[33] | e[34] << 8))
            t, s = c[1], c[2]
        return out


def ls(fn):
    d, kind, _ = load_raw(fn)
    if kind == 'do':
        try:
            cat = DOS33(d).catalog(); print('  [DOS 3.3]')
            for e in cat: print('   %02X %3d %s' % (e['type'], e['sectors'], e['name']))
            return
        except Exception as ex:
            print('  not DOS 3.3?', ex)
        d = dos_to_po(d)
    try:
        v = ProDOS(d)
    except AssertionError:
        print('  not ProDOS'); return
    print('  [ProDOS] /%s  %d blocks, %d free' % (v.volname, v.total, v.free_count()))
    for e in v.walk():
        print('   %-40s %-4s aux=$%04X eof=%7d st=%X' % (e['path'], TYPES.get(e['type'], '$%02X' % e['type']), e['aux'], e['eof'], e['storage']))

if __name__ == '__main__':
    for f in sys.argv[1:]:
        print('==', f); ls(f)

def format_prodos(nblocks, volname, boot=None):
    """create an empty ProDOS volume image (bytearray)"""
    d = bytearray(nblocks * 512)
    if boot: d[0:1024] = boot[:1024]
    nbm = (nblocks + 4095) // 4096
    for b in range(2, 6):
        blk = bytearray(512)
        blk[0:2] = struct.pack('<H', b - 1 if b > 2 else 0)
        blk[2:4] = struct.pack('<H', b + 1 if b < 5 else 0)
        if b == 2:
            blk[4] = 0xF0 | len(volname); blk[5:5+len(volname)] = volname.encode()
            blk[0x1c:0x20] = ProDOS._now()
            blk[0x22] = 0xC3; blk[0x23] = 0x27; blk[0x24] = 0x0D
            blk[0x27:0x29] = struct.pack('<H', 6); blk[0x29:0x2b] = struct.pack('<H', nblocks)
        d[b*512:(b+1)*512] = blk
    bm = bytearray(nbm * 512)
    for b in range(6 + nbm, nblocks): bm[b >> 3] |= 0x80 >> (b & 7)
    d[6*512:(6+nbm)*512] = bm
    return d
