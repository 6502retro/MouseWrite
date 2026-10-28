# dis.py FILE LOADADDR START COUNT - 65C02 disassembly (needs: pip install py65)
import sys
from py65.devices.mpu65c02 import MPU
from py65.disassembler import Disassembler
f, la, st, n = sys.argv[1], int(sys.argv[2],16), int(sys.argv[3],16), int(sys.argv[4])
d = open(f,'rb').read()
mpu = MPU(); 
for i,b in enumerate(d):
    if la+i < 0x10000: mpu.memory[la+i] = b
dis = Disassembler(mpu)
pc = st
for _ in range(n):
    l, txt = dis.instruction_at(pc)
    print('%04X  %-9s %s' % (pc, ' '.join('%02X'%mpu.memory[pc+i] for i in range(l)), txt))
    pc += l
