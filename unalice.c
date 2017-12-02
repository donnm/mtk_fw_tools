/*
 * unalice - Mediatek firmware ALICE unpacker
 *
 * Copyright 2017 Donn Morrison donn.morrison@gmail.com
 *
 * Compile: gcc unalice.c -o unalice
 *
 * Unpack an ALICE firmware and translate BL/BLX addresses to their
 * relative equivalents. Work in progress.
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
#include <sys/stat.h>
#include <unistd.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
//#include "lzmadec.h"

struct aliceheader {
    char id [8]; // "ALICE_2\0"
    uint32_t CompressedStartAddress;
    uint32_t MappingTableStartAddress;
    uint32_t DictionaryAddress;
    uint16_t a1;
    uint16_t a2;
    uint16_t a3;
    uint16_t a4;
    uint16_t a5;
    uint16_t a6;
    uint16_t a7;
    uint8_t unknown; // 0x09
    uint8_t flag; // 0x01
    uint16_t blocksize;  // InstructionNumber?
    uint16_t eoh; // 0xff 0xff
};

int main(int argc, char* argv[])
{
    if(argc < 2)
    {
        printf("usage: %s ALICE\n", argv[0]);
        return 1;
    }

    FILE *f;
    struct aliceheader header;
    int len;

    f = fopen(argv[1], "rb");
    if(!f)
    {
        printf("Cannot open ALICE file %s\n", argv[1]);
        return 1;
    }

    struct stat st;
    stat(argv[1], &st);
    printf("ALICE file %s is %li bytes\n", argv[1], st.st_size);
    printf("reading ALICE header (40 bytes)\n");
    printf("----HEADER--------\n");
    len = fread(&header, 1, sizeof(header), f);
    printf("compressed base: 0x%08x\n", header.CompressedStartAddress);
    printf("mapping table offset: 0x%08x\n", header.MappingTableStartAddress);
    printf("dictionary offset: 0x%08x\n", header.DictionaryAddress);

    printf("unknown header fields: ");
    for(int i=0; i<7; i++)
    {
        printf("%04x ", ((uint16_t*)(void*)&header)[10+i]);
    }
    printf("\n");

    printf("flags: 0x%02x 0x%02x\n", header.unknown, header.flag);
    printf("block size: 0x%04x (%d bytes)\n", header.blocksize, header.blocksize);

    printf("----DICTIONARY----\n");
    int dictoffset = header.DictionaryAddress-header.CompressedStartAddress+40;
    printf("dic file pos: 0x%08x\n", dictoffset);
    // Create the dictionary
    int dictlen = st.st_size - dictoffset;
    printf("dictionary size (bytes): %d\n", dictlen);
    printf("dictionary size (entries): %d\n", dictlen/sizeof(uint16_t));

    uint16_t *dictionary = (uint16_t*)malloc(dictlen);
    if(dictionary == NULL)
    {
        printf("could not allocate memory for dictionary\n");
        return 1;
    }
    memset(dictionary, 0, dictlen);

    printf("Reading dictionary entries (%d total bytes)\n", dictlen);
    int pos = 0;
    fseek(f, dictoffset, SEEK_SET);
    len = fread(&dictionary[pos], 1, sizeof(uint16_t), f);
    while(len == sizeof(uint16_t))
    {
//        printf("pos %d (0x%04x): 0x%04x\n", pos, pos, (uint16_t)dictionary[pos]); 
        pos += len/sizeof(uint16_t);
        len = fread(&dictionary[pos], 1, sizeof(uint16_t), f);
    }

    printf("read %d entries\n", pos);
/*    for(int i=0; i<dictlen/sizeof(uint16_t); i++)
    {
        printf("pos %d (0x%04x): 0x%04x\n", i, i, (uint16_t)dictionary[i]);
    }
*/
    printf("----MAP TABLE-----\n");

    int mapoffset = header.MappingTableStartAddress-header.CompressedStartAddress+sizeof(header);
    printf("map table file pos: 0x%08x\n", mapoffset);

    int maplen = header.DictionaryAddress - header.MappingTableStartAddress;
    printf("map table size (bytes): %d\n", maplen);
    printf("map table size (entries): %d\n", maplen/sizeof(uint32_t));
    uint32_t *map = (uint32_t*)malloc(maplen);
    if(map == NULL)
    {
        printf("could not allocate memory for mapping table\n");
        return 1;
    }
    memset(map, 0, maplen);

    printf("Reading map table entries (%d total bytes)\n", maplen);
    pos = 0;
    fseek(f, mapoffset, SEEK_SET);
    while(pos*sizeof(uint32_t) < maplen)
    {
        len = fread(&map[pos], 1, sizeof(uint32_t), f);
//        printf("pos %d (0x%08x): 0x%08x\n", pos, pos, (uint32_t)map[pos]); 
        pos += len/sizeof(uint32_t);
    }

    printf("read %d entries\n", pos);

    for(int i=0; i<maplen/sizeof(uint32_t); i++)
    {
//        printf("pos %d (0x%04x): 0x%08x, translated: 0x%08x, code %d 0x%02x\n", i, i, 0x00FFFFFF & (uint32_t)map[i],0x00FFFFFF &  (uint32_t)map[i]-header.CompressedStartAddress, map[i] >> 24, map[i] >> 24);
    }

    
    printf("----ALICE---------\n");
    int alicelen = header.MappingTableStartAddress - header.CompressedStartAddress;
    uint16_t *alice = (uint16_t*)malloc(alicelen);
    //uint16_t *alice = (uint16_t*)malloc(alicelen + LZMA_PROPS_SIZE);
    if(map == NULL)
    {
        printf("could not allocate memory for alice\n");
        return 1;
    }
    memset(alice, 0, alicelen);

    alice[0] = 0x5d;
    alice[1] = 0x00;
    alice[2] = 0x00;
    alice[3] = 0x80;
    alice[4] = 0x00;
    int aliceoffset = sizeof(header);
    printf("alice file pos: 0x%08x\n", aliceoffset);

    printf("Reading alice %d total bytes\n", alicelen);
    pos = 5;
    fseek(f, aliceoffset, SEEK_SET);
    while(pos*sizeof(uint16_t) < alicelen)
    {
        len = fread(&alice[pos], 1, sizeof(uint16_t), f);
    //    printf("pos %d (0x%04x): 0x%04x\n", pos, pos, (uint16_t)alice[pos]);
        pos += len/sizeof(uint16_t);
    }

    printf("read %d 2-byte entries (%d bytes)\n", pos/sizeof(uint16_t), pos*2);

    for(int i=0; i<alicelen/sizeof(uint16_t); i++)
    {
  //      printf("pos %d (0x%04x): 0x%02x 0x%02x\n", i, i, alice[i] & 0x00FF , alice[i] >> 8);
    }


    // NOTE: below not working, compressed stream may not be LZMA
/*
 * printf("uncompressing ALICE\n");

    CLzmaDec state;
    ISzAlloc alloc = { malloc, free };
    ELzmaStatus status;
    SRes ret;

    LzmaDec_Construct(&state);
    ret = LzmaDec_AllocateProbs(&state, (uint8_t*)alice, LZMA_PROPS_SIZE, &alloc);
    if(SZ_OK != ret)
    {
        printf("allocateprobs failed ret = %d\n", ret);
        return 1;
    }

    state.dic = (uint8_t*)dictionary;
    state.dicBufSize = dictlen;

    printf("LzmaDec_Init\n");

    LzmaDec_Init(&state);

    uint8_t *dest = (uint8_t*)malloc(alicelen*2);
    uint32_t destlen;

    ret = LzmaDec_DecodeToBuf(&state, dest, &destlen, (uint8_t)alice, alicelen, LZMA_FINISH_ANY, &status);
    if(SZ_OK != ret)
    {
        printf("decode failed ret = %d\n", ret);
        return 1;
    }
    */

    free(alice);
    free(dictionary);
    free(map);
    fclose(f);
    return 0;
}
