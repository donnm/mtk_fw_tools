/*
 * Alice compress
 *
 * Attempt to pack 16-bit instructions using ALICE.exe compression.
 * Use a sliding window over instructions and bit shifting and OR to 
 * pack bits according to a dictionary.
 *
 * Copyright 2017 Donn Morrison donn.morrison@gmail.com
 *
 * Compile: gcc alice.c -o alice
 * 
 * TODO
 * Dictionary maker:
 *  - Where do the BitNumbers come from? --- Range registers
 *  - Why are there 7s prepended to some instructions? --- dunno, but correspond to bitNumber 13h
 *
 * Начало тела - body start
 * СжаТЬгй файл - combined file
 * таблица отображения - mapping table
 * словара - dictionary
 * до конца - to end
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

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

//uint16_t buff[512];
int ptr = 0; // edi+10h
uint8_t edi12h = 0x07;
uint8_t edi1ch = 0;

void compress(uint8_t *buff, uint8_t bitNum, uint32_t fInstr)
{
//    printf("top of compress bitNum=0x%02x fInstr=0x%08x ptr=%d\n", bitNum, fInstr, ptr);
    uint8_t instrAndSeven0ch = (uint8_t)fInstr & 0xFF;

    if(bitNum != 0)
    {
        if(bitNum > 8)
        {
            bitNum -= 8;
            fInstr = fInstr >> 8;

            compress(buff, bitNum, fInstr);
            bitNum = 8;
        }

        uint8_t var1 = 1 << bitNum;
        uint8_t var2 = bitNum - edi12h;
        var1--;
        var1 = var1 & instrAndSeven0ch;
        var2--;
        instrAndSeven0ch = var2;

        if(var2 == 0)
        {
            // Rightmost tree
//            printf("0x%02x | 0x%02x = 0x%02x\n", buff[ptr], var1, buff[ptr] | var1);
            buff[ptr] = buff[ptr] | var1;
            ptr++;
            if(ptr == 0x100)
            {
                // call sub_190600 to reallocate
            }
            edi12h = 7;
            edi1ch = 1;
            return;

        }
        else if(var2 >> 7)
        {
            // Middle tree
            uint32_t var3 = var2;
            if(var2 >> 7)
                var3 = var2 | 0xFFFFFF00;
            var3 = -var3;
            var1 = var1 << var3;
//            printf("0x%02x | 0x%02x = 0x%02x\n", buff[ptr], var1, buff[ptr] | var1);
            buff[ptr] = buff[ptr] | var1;
            edi12h -= bitNum;
            edi1ch = 1;
            return;
        }
        else
        {
            // leftmost tree
            uint8_t var5 = var1 >> var2; // mov dl, bl; mov cl, al; shr dl, cl
//            printf("0x%02x | 0x%02x = 0x%02x\n", buff[ptr], var5, buff[ptr] | var5);
            buff[ptr] = buff[ptr] | var5; 
            ptr++;
            if(ptr == 0x100)
            {
                var2 = instrAndSeven0ch; // al
            }
            
            uint32_t var3 = var2; // esi
            if(var2 >> 7)
                var3 = var2 | 0xFFFFFF00;

            uint32_t var4 = 8 - var3;
            var1 = var1 << (uint8_t)(var4 & 0xFF);
            var4 = 0x07; // var4 = cl
//            printf("0x%02x | 0x%02x = 0x%02x\n", buff[ptr], var1, buff[ptr] | var1);
            buff[ptr] = buff[ptr] | var1;
            var4 = var4 - var2;
            edi12h = var4;
            edi1ch = 1;
            return;
        }
    }
}

void translate_bl_blx(uint16_t *buff, int count)
{
    // Careful, might be possible to overrun the buffer because
    // we increment i inside the loop at different stages
    int bl_count;
    int blx_count;
    for(int i=0; i<count; i++)
    {
        if((i+1) % 32 == 0) // Block size
        {
//            printf("skipping scan at %d\n", i+1);
            continue;
        }

        uint32_t instr, instr2, edi, esi;
        instr = buff[i]; // eax
//        printf("checking instruction 0x%02x\n", instr);
        edi = instr & 0xf800;

        if(edi == 0xf000)
        {
            instr2 = buff[i+1]; // edx
//            printf("found one! now checking next instruction 0x%02x\n", instr2);
            esi = instr2 & 0xf800;

            if(esi == 0xf800)
            {
                // BL instruction, translate
                instr2 &= 0x7ff;
                if(instr & 0x400)
                {
                    instr &= 0x7ff;
                    instr = instr << 0x0b;
                    instr += i;
                    instr2 += instr;
                    instr = instr2*2-0x7ffffe; // FIXME
                }
                else
                {
                    instr &= 0x7ff;
                    instr = instr << 0x0b;
                    instr += i;
                    instr2 += instr;
                    instr = instr2*2+2;
                }
                bl_count++;
                instr2 = instr >> 0x0c;
                instr = instr >> 1;
                instr &= 0x7ff;
                instr2 &= 0x7ff;

                instr |= esi;
                instr2 |= edi;

                printf("Translated 0x%04x to 0x%04x at %d\n", buff[i], instr2, i*2);
                printf("Translated 0x%04x to 0x%04x at %d\n", buff[i+1], instr, (i+1)*2);

                buff[i] = instr2;
                buff[i+1] = instr;

                i++; // increment i because we check for BLX below
            }
        }

        instr = buff[i]; // eax
//        printf("checking instruction 0x%02x\n", instr);
        edi = instr & 0xf800;

        if(edi == 0xf000)
        {
            instr2 = buff[i+1]; // edx
//            printf("found one! now checking next instruction 0x%02x\n", instr2);
            esi = instr2 & 0xf800;

            if(esi == 0xe800)
            {
                // BLX instruction, translate
                instr2 &= 0x7ff;
                if(instr & 0x400)
                {
                    instr &= 0x7ff;
                    instr = instr << 0x0b;
                    instr += i;
                    instr2 += instr;
                    instr = instr2*2-0x7ffffe; // FIXME
                }
                else
                {
                    instr &= 0x7ff;
                    instr = instr << 0x0b;
                    instr += i;
                    instr2 += instr;
                    instr = instr2*2+2;
                }
                blx_count++;
                instr2 = instr >> 0x0c;
                instr = instr >> 1;
                instr &= 0x7ff;
                instr2 &= 0x7ff;

                instr |= esi;
                instr2 |= edi;

                printf("Translated 0x%04x to 0x%04x at %d\n", buff[i], instr2, i*2);
                printf("Translated 0x%04x to 0x%04x at %d\n", buff[i+1], instr, (i+1)*2);

                buff[i] = instr2;
                buff[i+1] = instr;

                i++; // increment i because we check for BLX below
            }
        }
    }
}

int main(int argc, char *argv[])
{
    if(argc < 3)
    {
        printf("usage: alice <ALICE.bin> <magic.bin>\n");
        return 1;
    }

    struct stat st;
    stat(argv[1], &st);
    uint16_t *buff;
    uint8_t *encbuff;
    uint16_t *histcounts;
    uint8_t *magic;

    buff = malloc(st.st_size);
    if(!buff)
    {
        printf("malloc buff failed\n");
        return 1;
    }
    encbuff = malloc(st.st_size * 2);
    if(!encbuff)
    {
        printf("malloc encbuff failed\n");
        return 1;
    }
    histcounts = malloc(sizeof(uint16_t)*0xffff);
    if(!histcounts)
    {
        printf("malloc histcounts failed\n");
        return 1;
    }
    magic = malloc(0x10000*sizeof(uint8_t));
    if(!magic)
    {
        printf("malloc magic failed\n");
        return 1;
    }

    memset(buff, 0, st.st_size);
    memset(encbuff, 0, st.st_size*2);
    memset(histcounts, 0, sizeof(uint16_t)*0xffff);
    memset(magic, 0, sizeof(uint8_t)*0x10000);

    // 1. Read ALICE.bin bytes
    // 2. Translate BL/BLX
    // 3. Insert each instruction into binary search tree dictionary (self balancing?)
    // 4. Some kind of memory location copying loop
    // 5. Accumulator & shortest path
    // 6. Histogram
    // 7. Encode
    // 8. Write output

// Uncomment to read buff size bytes from file
    FILE *f = fopen(argv[1], "rb");
    int count=st.st_size/2;
    uint16_t instr;
    for(int j=0; j<st.st_size; j++)
    {
        fread(&buff[j], sizeof(uint16_t), 1, f);
    }

    printf("translating bl/blx instructions...\n");
    translate_bl_blx(buff, count);

    printf("buff:\n");
    for(int i=0; i<count; i++)
    {
        if(i%8 == 0 && i != 0)
            printf(" ");
        if(i%16 == 0 && i != 0)
            printf("\n");
        printf("0x%04x ", buff[i]);
    }
    printf("\n");

    FILE *fbuff = fopen("translated.bin", "wb");
    fwrite(buff, sizeof(uint16_t), count, fbuff);
    fclose(fbuff);

    printf("counting occurrences...\n");
    for(int i=0; i<count; i++)
    {
//        printf("%i found 0x%04x, %d -> %d\n", i, buff[i], histcounts[ buff[i] ],histcounts[ buff[i] ]+1);
        histcounts[ buff[i] ]++;
    }
    for(int i=0; i<0xFFFF; i++)
    {
        if(histcounts[ i ] != 0)
            printf("instr 0x%04x %d\n", i, histcounts[ i ]);
    }

    FILE *fmagic = fopen(argv[2], "rb");
    fread(magic, sizeof(uint8_t), 0x10000, fmagic);
    fclose(fmagic);

    printf("encoding instructions...\n");
    int start = 0x70000;
    for(int i=0; i<count; i++)
    {
        if(magic[ buff[i] ] == 0x13)
            compress(encbuff, 0x13, start + buff[i]);
        else
            compress(encbuff, magic[ buff[i] ], buff[i]);
    }

    printf("encbuff:\n");
    for(int i=0; i<st.st_size; i++)
    {
        if(i%8 == 0 && i != 0)
            printf(" ");
        if(i%16 == 0 && i != 0)
            printf("\n");
        printf("0x%02x ", encbuff[i]);
    }
    printf("\n");

    FILE *ebuff = fopen("translated_encoded.bin", "wb");
    fwrite(encbuff, sizeof(uint8_t), ptr, ebuff);
    fclose(ebuff);

    free(buff);
    free(encbuff);
    free(histcounts);
}
