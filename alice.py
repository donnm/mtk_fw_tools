import sys
import struct
from collections import Counter

'''
ALICE.exe encoder
    1. Read instructions from ALICE.bin
    2. Translate BL/BLX
    3. Generate dictionary
    4. Generate magic.bin bitnums, before_encoded.bin encoded instructions
    5. Compress - iterate through translated instructions (as index), encode
    6. Mapping table comes from bitpack() and blocksize, low byte unknown
    7. Postprocess

# magic.bin          - dictionary length array of lengths indexed by translated instruction
# before_encoded.bin - ranged instructions (32-bit form) in dictionary indexed by
#                      translated instruction
#
# TODO
# - DoMagic13And70000 sorting based on BST?
# - bitpack() end bytes (0x02) and padding
#
#
'''


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

def bitpack(length, instr):
    print("in bitpack 0x%02x 0x%08x"%(length, instr))
    global buff, length_remain, ptr, count

    instr_part = instr & 0xff
    if length != 0:
        if length > 8:
            bitpack(length - 8, instr >> 8)
            length = 8

        length_part = length - length_remain - 1
        print("length_part: %d = %d - %d - 1"%(length_part, length, length_remain))

        if length_part < 0:
            # shift left
            print("shifting 0x%02x << %d = 0x%02x"%(instr_part, -length_part, (instr_part << -length_part) & 0xff))
            print("%d b %02x | %02x -> %02x"%(ptr, buff[ptr], (instr_part << -length_part) & 0xff, (buff[ptr] | (instr_part << -length_part) & 0xff) & 0xff))
            buff[ptr] |= (instr_part << -length_part) & 0xff
            print("length_remain: %d = %d - %d"%(length_remain - length, length_remain, length))
            length_remain -= length
        elif length_part == 0:
            # no shift
            print("no shift 0x%02x"%(instr_part))
            print("%d a %02x | %02x -> %02x"%(ptr, buff[ptr], instr_part, (buff[ptr] | instr_part) & 0xff))
            buff[ptr] |= instr_part
            ptr += 1
            buff.append(0x00)
            print("bitpack 1st buff.append")
            length_remain = 7
            print("length_remain: 7")
        elif length_part > 0:
            # shift right
            print("shifting 0x%02x >> %d = 0x%02x"%(instr_part, length_part, (instr_part >> length_part) & 0xff))
            print("%d c %02x | %02x -> %02x"%(ptr, buff[ptr], (instr_part >> length_part) & 0xff, (buff[ptr] | (instr_part >> length_part)) & 0xff))
            buff[ptr] |= (instr_part >> length_part) & 0xff
            ptr += 1
            buff.append(0x00)
            print("bitpack 2nd buff.append")
            # shift left into new byte
            print("shifting 0x%02x << %d = 0x%02x"%(instr_part, 8 - length_part, instr_part  << ((8 - length_part) & 0xff) & 0xff))
            print("%d d %02x | %02x -> %02x"%(ptr, buff[ptr], instr_part  << (8 - length_part & 0xff) & 0xff, (buff[ptr] | instr_part  << (8 - length_part & 0xff) & 0xff) & 0xff))
            buff[ptr] |= instr_part  << ((8 - length_part) & 0xff) & 0xff
            length_remain = 7 - length_part
            print("length_remain: %d = 7 - %d"%(length_remain, length_part))

# Read ALICE.bin

f = open(sys.argv[1], "rb")
buff = bytearray(f.read())
f.close()

# Translate BL and BLX instructions
ptr = 0
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
'''
hist=Counter(instrs)
shist=sorted(hist.items(), key=lambda x: (-x[1], x[0]))
shist_f=[freq for instr,freq in shist]
shist=[instr for instr,freq in shist]

# Generate magic vector, funked instructions dictionary (before_encode.bin)
range_regs = [0x0, 0x10, 0x50, 0xd0, 0x1d0, 0x3d0, 0xbd0, 0x1bd0]
#range_regs = [0x0, 0x02, 0x06, 0x0a, 0x0e, 0x12, 0x16, 0x1e]
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
'''

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
length_remain = 0x07
buff = bytearray([0x00])
count = 0
for instr in instrs:
    instr_idx = struct.unpack("<H", instr)[0]
    print("instr_idx %d 0x%04x total %d"%(instr_idx, instr_idx, len(fshist)))
    bitnum = magic[ instr_idx ]
    finstr = fshist [ instr_idx ]
    print("calling bitpack 0x%02x 0x%08x"%(bitnum, finstr))
    bitpack(bitnum, finstr)

    count += 1
    if count % 0x20 == 0:
        if count % 0x40 == 0:
            print("hit instruction blocksize 0x40 at ptr 0x%08x"%(ptr))
        if count > 0 and length_remain != 0x07:
            length_remain = 0x07
            ptr += 1
            buff.append(0x00)
            print("buff.append")
            # Do some stuff here...

# TODO Need to add some padding here

f=open("alice-py", "wb")
len = f.write(buff)
print("wrote alice-py %d bytes"%len)
f.close()
