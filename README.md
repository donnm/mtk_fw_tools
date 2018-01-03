# mtk_fw_tools

Set of tools to unpack/repack Mediatek firmware. Work in progress.

The primary focus of developing these tools was to decompress the ALICE partition from Mediatek firmware blobs in order to inspect/reverse engineer the software on various devices (Smart watches, GSM trackers, cheap phones, etc.).

A typical firmware dump consists of:
    - Internal bootloader
    - External bootloader (EXT_BOOTLOADER)
    - Kernel (ROM)
    - User partition (VIVA header)
        - ZIMGE partition (ZIMAGE_ER - LZMA compressed resources)
        - BOOT_ZIMAGE partition (usually empty)
        - DCMCMP partition (LZMA compressed parts)
        - ALICE partition (ALICE_1/ALICE_2 - main firmware, compressed)

The main (non-kernel) firmware of the device seems to lie in the ALICE partition which is range encoded and bitpacked ARM instructions. Until now this encoding was not public.

Briefly, the encoder performs the following steps:

1. Read instructions from ALICE.bin (16-bits ARM Thumb)
2. Translate BL/BLX addresses
3. Add instructions, in order of appearance, to a binary tree
4. Generate dictionary (histogram)
5. Range encode instructions
6. Bitpack range encoded instructions
7. Generate mapping table (24-bit pointers to individual blocks), low byte unknown
8. Postprocess, prepend header, append mapping table and dictionary, etc

The decoder must do the reverse. In short, we read the compressed data as a bit string, looking up each instruction in the dictionary to retrieve the uncompressed version as we proceed. The mapping table tells us when we have reached a block of $blocksize (typically 64 bytes, 32 instructions), at which point we skip to the next start-of-byte and proceed. Presumably this lets the firmware decode segments of the code as needed, without loading the entire image into memory.

# Tools

    - alice.py - pack ALICE partition (not working 100% yet, use ALICE.exe instead)
    - unalice.py - unpack ALICE partition (working for ALICE_2 partition types except for some minor issues)

# Usage

## Requirements
    python3
    python3-bitstring

If you have the firmware of your device, open it in a hex editor and search for the ALICE_2 string.

<pre>
...
0017FEB0   DF 5A 8A AC  22 D7 FE 6F  01 6E 98 E8  79 36 7C 50  .Z.."..o.n..y6|P
0017FEC0   82 5E 25 DD  26 B9 20 A1  67 17 F9 2D  CD 54 EC 08  .^%.&. .g..-.T..
0017FED0   E0 A8 06 1D  A7 88 DB 9C  61 92 6E 75  1B 3D 1D 00  ........a.nu.=..
0017FEE0   41 4C 49 43  45 5F 32 00  08 FF 17 10  D0 92 2C 10  ALICE_2.......,.
0017FEF0   0C 6A 2D 10  04 00 06 00  07 00 08 00  0A 00 0B 00  .j-.............
0017FF00   0C 00 09 01  40 00 FF FF  E8 28 7D 15  2C 5B 2D 68  ....@....(}.,[-h
0017FF10   3F D5 F6 DF  E0 BB 8C CA  C2 D6 38 1E  05 33 9F CB  ?.........8..3..
0017FF20   04 96 CC 6D  35 7E F0 F4  20 3C B8 46  0E 79 0E 27  ...m5~.. <.F.y.'
0017FF30   9D 87 A6 4E  78 E2 03 B0  42 82 16 0C  CC 19 98 33  ...Nx...B......3
</pre>

Cut the section out using `dd` (0x17FEE0 == 1572576):

```
$ dd if=firmware.bin of=ALICE bs=1 skip=1572576
```

Run unalice on the resulting file:

```
$ python3 unalice.py ALICE
```

Load the resulting `alice-translated-py.bin` into your favourite disassembler!
