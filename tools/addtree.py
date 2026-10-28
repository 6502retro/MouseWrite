"""addtree.py image.(hdv|po|2mg) dest_dir_in_image src_extract_dir [skip,names] -- copy an extracted tree (with _meta.json) into image"""
import sys, os, json, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from a2disk import ProDOS, load_raw

def save(fn, v, kind, hdr):
    d = bytes(v.d)
    if hdr:
        d = hdr[0] + d + hdr[1]
    open(fn, 'wb').write(d)

def add_tree(v, dest, src, skip=(), only=None):
    meta = json.load(open(os.path.join(src, '_meta.json')))
    # create dirs in order
    parts = [p for p in dest.strip('/').split('/') if p]
    cur = ''
    for p in parts:
        v.mkdir(cur, p); cur = (cur + '/' + p).strip('/')
    def level(rel):
        seen = []
        pre = rel + '/' if rel else ''
        for k in meta:
            if k.startswith(pre):
                c = k[len(pre):].split('/')[0]
                if c not in seen: seen.append(c)
        return seen
    def do(rel):
        dest_dir = (cur + '/' + rel).strip('/')
        for name in level(rel):
            k = (rel + '/' + name).strip('/')
            if k in meta:
                if name in skip or (only and k not in only): continue
                m = meta[k]
                raw = bytes.fromhex(m['raw'])
                data = open(os.path.join(src, k), 'rb').read()
                v.write(dest_dir, name, data, m['type'], m['aux'], m['access'],
                        ctime=raw[0x18:0x1c], mtime=raw[0x21:0x25])
            else:
                v.mkdir(dest_dir, name)
                do(k)
    do('')

if __name__ == '__main__':
    img, dest, src = sys.argv[1:4]
    skip = sys.argv[4].split(',') if len(sys.argv) > 4 else ()
    d, kind, hdr = load_raw(img)
    v = ProDOS(d)
    add_tree(v, dest, src, skip)
    save(img, v, kind, hdr)
    print('ok, free blocks', v.free_count())
