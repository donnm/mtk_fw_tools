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
    bitstring for python https://github.com/scott-griffiths/bitstring

Copyright 2018 Donn Morrison donn.morrison@gmail.com

TODO:
    - find correct EOF and stop decoding

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
from bitstring import BitArray

def bitunpack():
    global fout, instrdict, range_regs, bitbuff, mappings, alicebin, blocksize
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

    while bitptr < ((mappings[-1])[0] + mappings[-1][1])*8 and bitptr < len(bitbuff): # mapping table addr + len
        # Check if we've done a block
        if blocksize != 0 and (byteswritten % blocksize) == 0:
#            print("--- hit a block at %d bytes written, compressed index 0x%08x, rem %d, %d"%(byteswritten, int(bitptr/8),bitptr%8, bitptr))
            sys.stdout.flush()
            # FFW to the next byte offset
            if bitptr%8 != 0:
                bitptr = bitptr + (8 - (bitptr%8))

            # Check every even block against mapping table
            if numblocks%2 == 0:
#                print("--- corresponding maptable addr 0x%08x len %d"%(mappings[int(numblocks/2)][0], mappings[int(numblocks/2)][1]))
                if int(bitptr/8) in [m for m,l in mappings]:
                    matchedblocks += 1
#                    print("   --- bitptr in mapping table! matchedblocks = %d"%(matchedblocks))
#                else:
#                    print("   --- bitptr 0x%08x NOT in mapping table!"%(int(bitptr/8)))
#            print("--- ptr forwarded to next byte %d, numblocks = %d"%(bitptr, numblocks))
#            print("--- distance to start of previous block %d bits (%d bytes)"%(bitptr-lastblockbitptr,int((bitptr-lastblockbitptr)/8)))
            lastblockbitptr = bitptr
            numblocks += 1
            #if math.ceil(numblocks/2) == len(mappings) -1:
#            print("--- at pos %02f"%((numblocks/2) / float(len(mappings)-1)))

            # FIXME EOF detection is a hack based on observations.
            # We first check if we're near the end of the compressed region,
            # then lookahead for low 1 counts in the bit buffer, or observed
            # EOF instruction sequence (0xeaff, 0x0000)
            if (numblocks/2) / float(len(mappings)-1) > 0.999: # Somewhere near the end?
                # We've reached possibly the last complete block
                print("--- Possible last block, now scanning for EOF signature instructions")
                lastblock = True
#        print("next 64 bits: %s"%(format(bitbuff[bitptr:bitptr+64].uint, '#066b')))
#        print("contains %d ones"%(bin(bitbuff[bitptr:bitptr+64].uint)[2:].count('1')))

        # Look for instruction header
        for s,l in zip(starts,lengths):
            if bitbuff[bitptr:bitptr+3].uint == s:
                # Fetch the range encoded instruction
                instr = bitbuff[bitptr:bitptr+l].uint
#                print("%d (0x%x,%d): fetched instruction 0x%08x and prefix 0x%x, length %d"%(bitptr, int(bitptr/8), bitptr%8, instr, prefixes[starts.index(s)], l))

                # FIXME EOF detection is a hack based on observations.
                # We first check if we're near the end of the compressed region,
                # then lookahead for low 1 counts in the bit buffer, or observed
                # EOF instruction sequence (0xeaff, 0x0000)
                if (lastblock and bin(bitbuff[bitptr:bitptr+64].uint)[2:].count('1') < 2):
                    print("--- Last block, mostly zero bits left (< 2 of 64). Stopping.")
                    return
                if (lastblock and instr == 1 and s == 0 and lastinstr == 0xeaff): # If we're left with mostly zeros, probably at end
                    print("--- Last block, end instructions detected (0xeaff, 0x0000). Stopping.")
                    return
                # If encoded, look up in dictionary
                if s != 0x7:
                    # Find the range (have to sum previous ranges to get correct index)
                    low = sum(range_regs_pow[0:starts.index(s)+1])
                    # Subtract the instruction prefix
                    instridx = instr - prefixes[starts.index(s)]
                    # This is the index into the range_reg subrange
                    originstr = instrdict[low + instridx]
                else:
                    # Not encoded, simply extract the instruction
                    originstr = instr & 0xffff
#                print("original instruction 0x%04x written at 0x%08x"%(originstr,byteswritten))
                lastinstr = originstr
                decomp = struct.pack("<H", originstr)
                # Write decoded instruction to buffer/file
                fout.write(decomp)
                byteswritten += len(decomp)
                alicebin += bytearray(decomp)
                # Advance pointer
                bitptr += l
                break
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

bitbuff = BitArray(buff)

print("loaded compressed alice %d bytes"%(len(bitbuff)/8))

fout = open("alice-translated-py.bin", "wb")
alicebin = bytearray()

sys.stdout.flush()

print("unpacking alice...")
#try:
bitunpack()
print("done")
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
