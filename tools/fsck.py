"""fsck.py image -- check ProDOS block allocation consistency"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from a2disk import ProDOS, load_raw, dos_to_po
d, kind, _ = load_raw(sys.argv[1])
if kind == 'do': d = dos_to_po(d)
v = ProDOS(d)
used = {}; errs = []
def mark(b, why):
    if b in used: errs.append('block %d twice: %s / %s' % (b, used[b], why))
    used[b] = why
for b in (0, 1): mark(b, 'boot')
b = 2
while b: mark(b, 'voldir'); b = struct.unpack('<H', v.blk(b)[2:4])[0]
for i in range((v.total + 4095) // 4096): mark(v.bitmap + i, 'bitmap')
def walk(key, path):
    cnt = 0
    for e in v.entries(key):
        cnt += 1
        p = path + e['name']
        if e['storage'] == 0xD:
            bl = v._datablocks(e)
            if len(bl) != e['blocks']: errs.append('%s dir blocks %d vs %d' % (p, len(bl), e['blocks']))
            for x in bl: mark(x, p)
            h = v.blk(e['key'])
            if struct.unpack('<H', h[0x27:0x29])[0] != e['dirblk'] or h[0x29] != (e['diroff'] - 4) // 39 + 1:
                errs.append('%s parent pointer wrong' % p)
            walk(e['key'], p + '/')
        else:
            bl = [x for x in v._datablocks(e) if x]
            idx = []
            if e['storage'] == 2: idx = [e['key']]
            if e['storage'] == 3:
                mb = v.blk(e['key']); idx = [e['key']] + [mb[j] | mb[256+j] << 8 for j in range(128) if mb[j] | mb[256+j] << 8]
            for x in bl + idx: mark(x, p)
            if len(bl) + len(idx) != e['blocks']: errs.append('%s blocks %d vs %d' % (p, len(bl) + len(idx), e['blocks']))
    fc = struct.unpack('<H', v.blk(key)[0x25:0x27])[0]
    if fc != cnt: errs.append('%s file count %d vs %d' % (path or '/', fc, cnt))
walk(2, '')
bm = v._bm()
for b in range(v.total):
    free = bool(bm[b >> 3] & (0x80 >> (b & 7)))
    if free and b in used: errs.append('block %d used by %s but marked free' % (b, used[b]))
    if not free and b not in used: errs.append('block %d marked used but unowned' % b)
print('%s: %d errors' % (sys.argv[1], len(errs)))
for e in errs[:30]: print('  ', e)
