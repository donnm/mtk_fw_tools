/*
 * dicreader - Mediatek firmware ALICE dictionary reader
 *
 * Copyright 2017 Donn Morrison donn.morrison@gmail.com
 *
 * Compile: gcc dicreader.c -o dicreader
 *
 * This was quickly written to dump dictionary information in
 * a readable format while trying to reverse the Mediatek ALICE
 * firmware compression. May contain bugs.
 *
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 * 
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 * 
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 */

#include <stdio.h>
#include <sys/types.h>
#include <stdint.h>
#include <string.h>

struct dictheader {
    uint32_t headerlen;
    uint32_t diclen; // (filesize - 40 (headerlength))
    uint32_t rangereg_0;
    uint32_t rangereg_1;
    uint32_t rangereg_2;
    uint32_t rangereg_3;
    uint32_t rangereg_4;
    uint32_t rangereg_5;
    uint32_t rangereg_6;
    uint32_t rangereg_7;
};

int main(int argc, char* argv[])
{
    if(argc < 2 || ((argc == 3) && (strcmp(argv[1], "-h") != 0) && (strcmp(argv[1], "-a") != 0)))
    {
        printf("usage: %s [-h or -a] dicfile\n", argv[0]);
        printf("       -h - headerless dictionary (~M2.tmp)\n");
        printf("       -a - ALICE dictionary (ALICE)\n");
        return 1;
    }

    FILE *f;
    struct dictheader header;
    int len;
    uint16_t dicentry;

    if (argc == 3 && (strcmp(argv[1], "-h") == 0))
    {
        f = fopen(argv[2], "rb");
        if(!f)
            return 1;
    }
    else if (argc == 3 && (strcmp(argv[1], "-a") == 0))
    {
        f = fopen(argv[2], "rb");
        if(!f)
            return 1;

        printf("reading ALICE header\n");
        printf("-----------------\n");
        long base;
        long offset;
        fseek(f, 8, SEEK_SET);
        fread(&base, 1, 4, f);
        printf("compressed base: 0x%08x\n", base);
        fseek(f, 8+4+4, SEEK_SET); // Seek to dictionary address location in alice header
        len = fread(&offset, 1, 4, f); // read location
        printf("dictionary offset: 0x%08x\n", offset);
        printf("dic file pos: 0x%08x\n", offset-base+40);
        fseek(f, (long)(offset-base+40), SEEK_SET);
    }
    else
    {
        f = fopen(argv[1], "rb");
        if(!f)
            return 1;
        len = fread(&header, 1, sizeof(header), f);

        printf("header %d bytes\n", len);

        printf("-----------------\n");
        printf("header length: %d bytes\n", header.headerlen);
        printf("dict length: %d bytes\n", header.diclen);
        printf("num entries: %d\n", header.diclen/2);
        printf("range registers: %d, %d, %d, %d, %d, %d, %d, %d\n", header.rangereg_0,header.rangereg_1,header.rangereg_2,header.rangereg_3,header.rangereg_4,header.rangereg_5,header.rangereg_6,header.rangereg_7);
    }

    printf("entries:\n");
    len = fread(&dicentry, 1, sizeof(uint16_t), f);
    int pos = 0;
    while(len == sizeof(uint16_t))
    {
        printf("pos %d (0x%04x): 0x%04x\n", pos, pos, dicentry); 
        len = fread(&dicentry, 1, sizeof(uint16_t), f);
        pos += len;
    }
    fclose(f);
    return 0;
}
