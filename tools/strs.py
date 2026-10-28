import sys,re
d=open(sys.argv[1],'rb').read(); mn=int(sys.argv[2]) if len(sys.argv)>2 else 5
b=bytes(x&0x7f for x in d)
for m in re.finditer(rb'[\x20-\x7e]{%d,}'%mn,b): print('%05X %s'%(m.start(),m.group().decode()))
