#!/usr/bin/python3

'''
Alice decompress

Unpack Mediatek compressed ALICE firmware component

ALICE is range encoded (range registers contained in header) and then
bitpacked. Each packed instruction has a 3-bit prefix denoting the range from
which it comes and thus implicitly its length.

Sets of packed instructions are divided into blocks, the size of which is
contained in the header. When we encounter the end of a block, we must skip any
remaining bits in the current byte and move to the next start-of-byte.

As each range encoded instruction is unpacked, we look it up in the dictionary
appended to the end of ALICE to reveal the original instruction.

Requirements:
    python

Copyright 2018 Donn Morrison donn.morrison@gmail.com

TODO:
    - (done) EOF is now derived from the mapping table, see bitunpack()

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

import math
import os
import sys
import struct
import getopt

class BitBuf:
    """Bit view over bytes: MSB first inside each byte, same order as the
    BitArray slicing this replaces. len() is the number of bits."""

    def __init__(self, data):
        self.d = bytes(data)

    def __len__(self):
        return len(self.d) * 8

    def peek(self, pos, n):
        first = pos >> 3
        need = (pos & 7) + n
        chunk = self.d[first:first + (need + 7) // 8]
        if len(chunk) * 8 < need:
            chunk += b'\0' * ((need + 7) // 8 - len(chunk))
        v = int.from_bytes(chunk, 'big')
        return (v >> (len(chunk) * 8 - (pos & 7) - n)) & ((1 << n) - 1)


def bitunpack():
    global fout, instrdict, range_regs, bitbuff, mappings, alicebin, blocksize
    global total_blocks, mismatched
    bitptr = 0
    numblocks = 0
    byteswritten = 0
    lastblockbitptr = 0
    matchedblocks = 0
    lastblock = False
    lastinstr = None

    # Range register dependent vectors:
    #  starts 000, 001, ..., 111
    #  prefixes are starts shifted by respective range reg
    #  lengths are range encoded instruction lengths + starts
    #  range_regs_pow dictionary boundaries (ranges)
    starts = range(0,8) # each 3 bits long
    prefixes = [start << r for start,r in zip(starts, range_regs)]
    lengths = [r + 3 for r in range_regs]
    range_regs_pow = [0] + [int(math.pow(2, r)) for r in range_regs[0:-1]]
    lows = [sum(range_regs_pow[0:i+1]) for i in range(8)]

    while bitptr < ((mappings[-1])[0] + mappings[-1][1])*8 and bitptr < len(bitbuff): # mapping table addr + len
        # Check if we've done a block
        if blocksize != 0 and (byteswritten % blocksize) == 0:
#            print("--- hit a block at %d bytes written, compressed index 0x%08x, rem %d, %d"%(byteswritten, int(bitptr/8),bitptr%8, bitptr))
            sys.stdout.flush()
            # FFW to the next byte offset
            if bitptr%8 != 0:
                bitptr = bitptr + (8 - (bitptr%8))

            # Deterministic end of stream.
            # The mapping table records the byte offset of every even block, so
            # the number of blocks is exactly 2 * (number of real entries) and
            # the decompressed size is that times blocksize. No guessing needed.
            if numblocks >= total_blocks:
                print("--- reached block %d of %d, end of stream"%(numblocks, total_blocks))
                return

            # Check every even block against its own mapping table entry.
            # A direct index is both exact and O(1); the previous membership
            # test scanned every entry for every block.
            if numblocks%2 == 0:
                idx = int(numblocks/2)
                if idx < len(mappings):
                    want = mappings[idx][0]
                    got = int(bitptr/8)
                    if want == got:
                        matchedblocks += 1
                    else:
                        mismatched.append((numblocks, want, got))
#                    print("   --- bitptr in mapping table! matchedblocks = %d"%(matchedblocks))
#                else:
#                    print("   --- bitptr 0x%08x NOT in mapping table!"%(int(bitptr/8)))
#            print("--- ptr forwarded to next byte %d, numblocks = %d"%(bitptr, numblocks))
#            print("--- distance to start of previous block %d bits (%d bytes)"%(bitptr-lastblockbitptr,int((bitptr-lastblockbitptr)/8)))
            lastblockbitptr = bitptr
            numblocks += 1
            #if math.ceil(numblocks/2) == len(mappings) -1:
#            print("--- at pos %02f"%((numblocks/2) / float(len(mappings)-1)))

#        print("next 64 bits: %s"%(format(bitbuff[bitptr:bitptr+64].uint, '#066b')))
#        print("contains %d ones"%(bin(bitbuff[bitptr:bitptr+64].uint)[2:].count('1')))

        # The 3 bit prefix is the range index, so look the length up directly
        # instead of testing all eight candidates.
        s = bitbuff.peek(bitptr, 3)
        l = lengths[s]
        # Fetch the range encoded instruction
        instr = bitbuff.peek(bitptr, l)
#                print("%d (0x%x,%d): fetched instruction 0x%08x and prefix 0x%x, length %d"%(bitptr, int(bitptr/8), bitptr%8, instr, prefixes[starts.index(s)], l))

        # If encoded, look up in dictionary
        if s != 0x7:
            # Range base, precomputed rather than summed per instruction
            low = lows[s]
            # Subtract the instruction prefix
            instridx = instr - prefixes[s]
            # This is the index into the range_reg subrange
            originstr = instrdict[low + instridx]
        else:
            # Not encoded, simply extract the instruction
            originstr = instr & 0xffff
#                print("original instruction 0x%04x written at 0x%08x"%(originstr,byteswritten))
        lastinstr = originstr
        # Collect output, written out once at the end
        alicebin += struct.pack("<H", originstr)
        byteswritten += 2
        # Advance pointer
        bitptr += l
    print("--- stream exhausted at block %d of %d"%(numblocks, total_blocks))
    return

def untranslate_bl_blx():
    global buff
    ptr = 0 # ptr can be equiv to PC
    bl_count = 0
    blx_count = 0
    while ptr < len(buff)/2-1:
        if (ptr+1) % 32 == 0:
            ptr += 1
            continue

        instr = buff[ptr*2] | (buff[ptr*2+1] << 8)
        instr2 = buff[ptr*2+2] | (buff[ptr*2+3] << 8)

        if (instr & 0xf800) == 0xf000:
            if (instr2 & 0xf800) == 0xf800: # bit 12 = 1, BL instruction
                upbits = 0xf800
                bl_count += 1
            elif (instr2 & 0xf800) == 0xe800: # bit 12 = 0, BLX instruction
                upbits = 0xe800
                blx_count += 1
            else:
                ptr += 1
                continue

            if instr & 0x400: # if J2 bit is set
                # shift imm11 left 11 bits, add lower bits from imm10 + sign
                # multiply by two, subtract 0x7ffffffe?
                v10 = int((((instr & 0x7ff) << 0x0c) + ((instr2 & 0x7ff) << 1))/2) - (ptr-1) + 0x7ffffffe
            else:
                # shift imm11 left 11 bits, add lower bits from imm10 + sign
                # multiply by two, add 2
                v10 = int((((instr & 0x7ff) << 0x0c) + ((instr2 & 0x7ff) << 1))/2) - (ptr-1) - 0x00000002

#            print("-%d translated type 0x%04x from 0x%08x to 0x%08x"%(ptr, upbits, ((instr & 0x7ff) << 0x0c) + ((instr2 & 0x7ff) << 1), v10))
#            print("%d 0x%08x"%(ptr,v10))

            # reassemble branch target
            instr = (v10 >> 0x0b) & 0x7ff | 0xf000 # high bits
            instr2 = v10 & 0x7ff | upbits   # low bits

#            print("-translated 0x%04x to 0x%04x at 0x%x, diff = %d"%(buff[ptr*2] | buff[ptr*2+1] << 8, instr, ptr*2, (buff[ptr*2] | buff[ptr*2+1] << 8) - instr))
            buff[ptr*2] = instr & 0xff
            buff[ptr*2+1] = (instr >> 8) & 0xff
#            print("-translated 0x%04x to 0x%04x at 0x%x, diff = %d"%(buff[ptr*2+2] | buff[ptr*2+3] << 8, instr2, ptr*2+2, (buff[ptr*2+2] | buff[ptr*2+3] << 8) - instr2))
            buff[ptr*2+2] = instr2 & 0xff
            buff[ptr*2+3] = (instr2 >> 8) & 0xff

            ptr += 1
        ptr += 1

    print("translated %d bl and %d blx instructions"%(bl_count*2, blx_count*2))

# ALICE
# -t ALICE

notranslate = 0
if len(sys.argv) == 3 and sys.argv[1] == "-t":
    alicefile = sys.argv[2]
    notranslate = 1
elif len(sys.argv) == 2 and sys.argv[1] != "-t":
    alicefile = sys.argv[1]
elif len(sys.argv) < 2 or len(sys.argv) > 3:
    print("usage: unalice.py [-t] <ALICE>")
    print("       -t disable bl/blx addr translation (required for some images)")
    sys.exit()

f = open(alicefile, "rb")
magic = f.read(7)
if magic == b'ALICE_1':
    alice_version = 1
elif magic == b'ALICE_2':
    alice_version = 2
else:
    print("found %s, expected ALICE_2, quitting."%(magic))
    sys.exit(1)
print("found %s magic"%(magic))

header_size = 40 # ALICE_2 or ALICE_1 with full header
if alice_version == 1:
    f.seek(36) # Check ALICE_1
    endbytes = f.read(4)
    if endbytes != b'\x00\x00\xff\xff':
        header_size = 36 # ALICE_1 with short header

f.seek(8)
base, mapping_offset, dict_offset = struct.unpack("<LLL", f.read(12))
f.seek(0,2)
filesize = f.tell()
mapping_offset -= base - header_size
dict_offset -= base - header_size
compressed_offset = header_size

f.seek(20) # Range registers
reads = 0
range_regs = []
while reads < 7:
    #reg = int(math.pow(2, struct.unpack("<H", f.read(2))[0]))
    reg = struct.unpack("<H", f.read(2))[0]
    range_regs.append(reg)
    reads += 1
range_regs.append(16) # for infrequent instructions (0x70000 | instr) length 16+3=19

f.read(2)
blocksize = 0
if header_size == 40:
    blocksize = struct.unpack("<H", f.read(2))[0]
if blocksize == 0:
    blocksize = 64 # FIXME correct default for ALICE_1?

print("filesize %d bytes"%(filesize))
print("base 0x%08x"%(base))
print("header length %d"%(header_size))
print("blocksize %d bytes (%d instructions)"%(blocksize, blocksize/2))
print("compressed @ 0x%08x, len 0x%08x"%(compressed_offset, mapping_offset - compressed_offset))
print("maptable @ 0x%08x, len 0x%08x"%(mapping_offset, dict_offset - mapping_offset))
print("dictionary @ 0x%08x, len 0x%08x"%(dict_offset, filesize - dict_offset))
print("range registers (encoded lengths): %s"%(range_regs))
f.seek(compressed_offset) # size of ALICE header

buff = bytearray(f.read(mapping_offset - compressed_offset))

reads = 0
mappings = []
while reads < dict_offset - mapping_offset:
    mapping = struct.unpack("<L", f.read(4))[0]
    addr = (mapping - base) & 0x00ffffff
    length = mapping & 0xff000000
    if length != 0:
        length = (((mapping & 0xff000000)>>26) + (3*int(blocksize/2) >> 3)) + 1 # FIXME hardcoded 26
    print("mapping entry 0x%08x addr 0x%08x len %d"%(mapping, addr, length))
    mappings.append((addr, length))
    reads += 4

print("mappings length: %d"%(len(mappings)))

# Entries with a zero length field are sentinels, not blocks.
real_mappings = [m for m in mappings if m[1] != 0]
total_blocks = 2 * len(real_mappings)
mismatched = []
print("real mapping entries: %d, sentinels: %d"%(len(real_mappings), len(mappings) - len(real_mappings)))
print("expecting %d blocks = %d bytes decompressed"%(total_blocks, total_blocks * blocksize))

#mappingsbits = [a + (((b>>0x1a) + 3*(blocksize/2) >> 3) + 1) for a,b in mappings]
#print(mappingsbits)

print("last nonzero mapping: 0x%08x, len = %d"%(mappings[-2][0], mappings[-2][1]))

reads = 0
instrdict = []
while reads < filesize - dict_offset:
    instr = struct.unpack("<H", f.read(2))[0]
    instrdict.append(instr)
    reads += 2

print("read %d dictionary entries"%(len(instrdict)))
print("--- first %s"%(instrdict[0:4]))
print("--- last %s"%(instrdict[-1]))

f.close()

bitbuff = BitBuf(buff)

print("loaded compressed alice %d bytes"%(len(bitbuff)/8))

fout = open("alice-translated-py.bin", "wb")
alicebin = bytearray()

sys.stdout.flush()

print("unpacking alice...")
#try:
bitunpack()
print("done")
fout.write(alicebin)

print("block checkpoints: %d matched, %d mismatched"%(
    int(total_blocks/2) - len(mismatched), len(mismatched)))
if mismatched:
    print("first mismatch: block %d, mapping table says 0x%08x, decoder at 0x%08x"%mismatched[0])
print("decompressed %d bytes, expected %d (%s)"%(
    len(alicebin), total_blocks * blocksize,
    "match" if len(alicebin) == total_blocks * blocksize else "MISMATCH"))
#except:
#    pass 

fout.close()

buff = alicebin
if not notranslate:
    print("bl/blx address translation...")
    untranslate_bl_blx()
    print("done")
else:
    print("skipping bl/blx address translation")

print("writing alice-py.bin %d bytes"%(len(buff)))
falicebin = open("alice-py.bin", "wb")
falicebin.write(buff)
falicebin.close()

print("done")
