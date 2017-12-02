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
 *  - Where do the BitNumbers come from?
 *  - Why are there 7s prepended to some instructions?
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

uint8_t buff[40];
int ptr = 0; // edi+10h
uint8_t edi12h = 0x07;
uint8_t edi1ch = 0;

void compress(uint8_t bitNum, uint32_t fInstr)
{
    printf("top of compress bitNum=0x%02x fInstr=0x%08x\n", bitNum, fInstr);
    uint8_t instrAndSeven0ch = (uint8_t)fInstr & 0xFF;

    if(bitNum != 0)
    {
        if(bitNum > 8)
        {
            bitNum -= 8;
            fInstr = fInstr >> 8;

            compress(bitNum, fInstr);
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
            printf("0x%02x | 0x%02x = 0x%02x\n", buff[ptr], var1, buff[ptr] | var1);
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
            printf("0x%02x | 0x%02x = 0x%02x\n", buff[ptr], var1, buff[ptr] | var1);
            buff[ptr] = buff[ptr] | var1;
            edi12h -= bitNum;
            edi1ch = 1;
            return;
        }
        else
        {
            // leftmost tree
            uint8_t var5 = var1 >> var2; // mov dl, bl; mov cl, al; shr dl, cl
            printf("0x%02x | 0x%02x = 0x%02x\n", buff[ptr], var5, buff[ptr] | var5);
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
            printf("0x%02x | 0x%02x = 0x%02x\n", buff[ptr], var1, buff[ptr] | var1);
            buff[ptr] = buff[ptr] | var1;
            var4 = var4 - var2;
            edi12h = var4;
            edi1ch = 1;
            return;
        }
    }
}

int main(int argc, char *argv[])
{
    memset(buff, 0, sizeof(buff));

// Uncomment to read buff size bytes from file
/*   FILE *f = fopen(argv[1], "rb");
    int count=sizeof(buff);
    uint16_t instr;
    while(count > 0)
    {
        fread(&instr, 2, 1, f);
        if(sizeof(buff) - count >= 4)
            compress(0x13, 0x00000 | instr);
        else
            compress(0x13, 0x70000 | instr);
        count -= 2;
    }
*/

    // Test compress incrementing instructions
    int start = 0x70000;
    for(int i=0; i<32; i++)
    {
        compress(0x13, start + (i*0x100));
    }

    // Test compress handwritten instructions
    /*compress(0x13, 0x70000);
    compress(0x13, 0x70100);
    compress(0x13, 0x70200);
    compress(0x13, 0x70300);
    compress(0x13, 0x70400);
    compress(0x13, 0x70500);
    compress(0x13, 0x70600);
    compress(0x13, 0x70700);
    compress(0x13, 0x70800);
    compress(0x13, 0x70900);
    compress(0x13, 0x70a00);
    */

    printf("buff:\n");
    for(int i=0; i<sizeof(buff); i++)
    {
        printf("0x%02x ", buff[i]);
    }
    printf("\n");
}
