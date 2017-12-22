import sys
import struct
from collections import Counter

# magic.bin          - dictionary length array of bitNums indexed by instruction
# before_encoded.bin - ranged instructions (32-bit form) in dictionary indexed by
#                      frequency

def translate_bl_blx():
    global buff
    ptr = 0
    bl_count = 0
    blx_count = 0
    while ptr < len(buff)/2-1:
        if (ptr+1) % 32 == 0:
            ptr += 1
            continue

        instr = buff[ptr*2] | (buff[ptr*2+1] << 8)
        instr2 = buff[ptr*2+2] | (buff[ptr*2+3] << 8)

        if (instr & 0xf800) == 0xf000:
            if (instr2 & 0xf800) == 0xf800:
                upbits = 0xf800
                bl_count += 1
            elif (instr2 & 0xf800) == 0xe800:
                upbits = 0xe800
                blx_count += 1
            else:
                ptr += 1
                continue

            if instr & 0x400:
                v10 = 2 * (ptr + ((instr & 0x7ff) << 0x0b) + (instr2 & 0x7ff)) - 0x7ffffffe
            else:
                v10 = 2 * (ptr + ((instr & 0x7ff) << 0x0b) + (instr2 & 0x7ff)) + 0x00000002

            instr = (v10 >> 0x0c) & 0x7ff | 0xf000
            instr2 = (v10 >> 1) & 0x7ff | upbits

#            print("-translated 0x%04x to 0x%04x at 0x%x"%(buff[ptr*2] | buff[ptr*2+1] << 8, instr, ptr*2))
            buff[ptr*2] = instr & 0xff
            buff[ptr*2+1] = (instr >> 8) & 0xff
#            print("-translated 0x%04x to 0x%04x at 0x%x"%(buff[ptr*2+2] | buff[ptr*2+3] << 8, instr2, ptr*2+2))
            buff[ptr*2+2] = instr2 & 0xff
            buff[ptr*2+3] = (instr2 >> 8) & 0xff

            ptr += 1
        ptr += 1

    print("translated %d bl and %d blx instructions"%(bl_count*2, blx_count*2))

def compress(bitNum, instr):
    print("in compress 0x%02x 0x%08x"%(bitNum, instr))
    global buff, edi12h, ptr

    instrAndSeven0ch = instr & 0xff
    if bitNum != 0:
        if bitNum > 8:
            compress(bitNum - 8, instr >> 8)
            bitNum = 8

        var1 = instrAndSeven0ch & ((1 << bitNum) - 1) & 0xff
        var2 = bitNum - edi12h - 1
        instrAndSeven0ch = var2

        if var2 < 0:
            # Output
            print("%d b %02x | %02x -> %02x"%(ptr, buff[ptr], (var1 << -var2) & 0xff, (buff[ptr] | (var1 << -var2) & 0xff) & 0xff))
            buff[ptr] |= (var1 << -var2) & 0xff
            edi12h -= bitNum
        elif var2 == 0:
            # Output
            print("%d a %02x | %02x -> %02x"%(ptr, buff[ptr], var1, (buff[ptr] | var1) & 0xff))
            buff[ptr] |= var1
            ptr += 1
            buff.append(0x00)
            edi12h = 7
        elif var2 > 0:
            # Output
            print("%d c %02x | %02x -> %02x"%(ptr, buff[ptr], (var1 >> var2) & 0xff, (buff[ptr] | (var1 >> var2)) & 0xff))
            buff[ptr] |= (var1 >> var2) & 0xff
            ptr += 1
            buff.append(0x00)
            if (ptr+1) % 0x100 == 0:
                ptr += 1
                buff.append(0x00)
                var2 = instrAndSeven0ch
            # Output
            print("%d d %02x | %02x -> %02x"%(ptr, buff[ptr], var1  << (8 - var2 & 0xff) & 0xff, (buff[ptr] | var1  << (8 - var2 & 0xff) & 0xff) & 0xff))
            buff[ptr] |= var1  << ((8 - var2) & 0xff) & 0xff
            edi12h = 0x07 - var2
'''
        if var2 == 0:
            # Output
            print("%d a %02x | %02x -> %02x"%(ptr, buff[ptr], var1 & 0xff, (buff[ptr] | var1) & 0xff))
            buff[ptr] |= var1 & 0xff
            ptr += 1
            buff.append(0x00)
            edi12h = 7
        elif (0xff & var2) >> 7:
            var3 = var2
            if (0xff & var2) >> 7:
                var3 = var2 | 0xFFFFFF00
            var3 = -var3 & 0xffffffff
            var1 = var1 << var3
            # Output
            print("%d b %02x | %02x -> %02x"%(ptr, buff[ptr], var1 & 0xff, (buff[ptr] | var1) & 0xff))
            buff[ptr] |= var1 & 0xff
            edi12h -= bitNum
        else:
            var5 = var1 >> var2
            # Output
            print("%d c %02x | %02x -> %02x"%(ptr, buff[ptr], var5 & 0xff, (buff[ptr] | var5) & 0xff))
            buff[ptr] |= var5 & 0xff
            ptr += 1
            buff.append(0x00)
#            if ptr % 0x100 == 0 and ptr > 0:
#                ptr += 1
#                buff.append(0x00)
#                var2 = instrAndSeven0ch
            var3 = var2
            if (0xff & var2) >> 7:
                var3 = var2 | 0xFFFFFF00
            var4 = 8 - var3
            var1 = var1 << var4
            var4 = 0x07
            # Output
            print("%d d %02x | %02x -> %02x"%(ptr, buff[ptr], var1 & 0xff, (buff[ptr] | var1) & 0xff))
            buff[ptr] |= var1 & 0xff
            var4 = var4 - var2
            edi12h = var4 & 0xff
'''

edi12h = 0x07
#buff = bytearray([0x00])
ptr = 0

# Read ALICE.bin

f = open(sys.argv[1], "rb")
buff = bytearray(f.read())
f.close()

# Translate BL and BLX instructions

translate_bl_blx()

f = open("translated-py.bin", "wb")
f.write(buff)
f.close()

# Generate histogram
# Need to make sure it is sorted in the same way ALICE.exe sorts,
# that being that first by frequency, then for instructions of the
# same frequency, possibly by instruction value, first location 
# in ALICE.bin, or something else?
# Most likely ALICE.exe gets the order from the way the BST
# is traversed.

# Construct fake ALICE.bin with a desired histogram and try to match
# the output.

instrs=[bytes(buff[i*2:i*2+2]) for i in range(int(len(buff)/2))]
hist=Counter(instrs)
shist=sorted(hist.items(), key=lambda x: (-x[1], x[0]))
shist_f=[freq for instr,freq in shist]
shist=[instr for instr,freq in shist]

# hist.get(b'\x00(')
# sorted(hist, key=hist.get, reverse=True)

# Generate magic vector, funked instructions dictionary (before_encode.bin)
range_regs = [0x0, 0x10, 0x50, 0xd0, 0x1d0, 0x3d0, 0xbd0, 0x1bd0]
codes = [0x07, 0x09, 0x0A, 0x0B, 0x0C, 0x0E, 0x0F, 0x13]
starts = [0x0, 0x40, 0x100, 0x300, 0x800, 0x2800, 0x6000, 0x70000]

magic = bytearray(0x10000)
fshist = dict()

for r in range(len(range_regs)-1):
    instrnr = 0
    for i in range(range_regs[r], range_regs[r+1]):
        instr_idx = struct.unpack("<H", shist[i])[0]
        print("0x%02x 0x%04x 0x%08x %d %d"%(codes[r], instr_idx, (instrnr | starts[r]), shist_f[i], i))
        # Magic
        magic[ instr_idx ] = codes[r]
        # Instr
        fshist[ instr_idx ] = instrnr | starts[r]
        instrnr += 1

offset = len(range_regs)-1
for i in range(range_regs[offset], len(hist)):
    instr_idx = struct.unpack("<H", shist[i])[0]
    print("0x%02x 0x%04x 0x%08x %d %d"%(codes[offset], instr_idx, (instr_idx | starts[offset]), shist_f[i], i))
    # Magic
    magic[ instr_idx ] = codes[offset]
    fshist[ instr_idx ] = instr_idx | starts[offset]

f=open("magic-py.bin", "wb")
f.write(magic)
f.close()

f=open("before_encode-py.bin", "wb")
for l,v in fshist.items():
    f.seek(l*4)
    f.write(struct.pack("<L", v))

f.close()


# Try to encode!

if len(sys.argv) == 4:
    f=open(sys.argv[2], "rb")
    magic=bytearray(f.read())
    f.close()

    fshist=dict()
    f=open(sys.argv[3], "rb")
    for instr_idx in range(0x10000):
        instr = struct.unpack("<L", f.read(4))[0]
        fshist[ instr_idx ] = instr
    f.close()

ptr = 0
buff = bytearray([0x00])
count = 0
for instr in instrs:
    instr_idx = struct.unpack("<H", instr)[0]
    print("instr_idx %d 0x%04x total %d"%(instr_idx, instr_idx, len(fshist)))
    bitnum = magic[ instr_idx ]
    finstr = fshist [ instr_idx ]
    print("calling compress 0x%02x 0x%08x"%(bitnum, finstr))
    compress(bitnum, finstr)

    count += 1
    if count % 0x20 == 0 and count > 0:
        ptr += 1
        buff.append(0x00)
        # Do some stuff here...
        print("encoded count %04x at blocksize 0x20"%(count))

f=open("alice-py", "wb")
len = f.write(buff[0:ptr])
print("wrote alice-py %d bytes"%len)
f.close()
