/*
 * viva-hdr - Print Mediatek VIVA image header
 *
 * Copyright 2017 Donn Morrison donn.morrison@gmail.com
 *
 * Compile: gcc viva-hdr.c -o viva-hdr
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
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>

struct gfh_file_info {
 uint8_t  id[12]; /* "FILE_INFO", zero-padded */
 uint32_t file_ver;
 uint16_t file_type;
 uint8_t  flash_dev;
 uint8_t  sig_type;
 uint32_t load_addr;
 uint32_t file_len;
 uint32_t max_size;
 uint32_t content_offset;
 uint32_t sig_len;
 uint32_t jump_offset;
 uint32_t attr;
} gfh_file_info;

int main(int argc, char* argv[]) {
    struct gfh_file_info fi;

    if(argc < 2)
    {
        printf("usage: %s <filename>\n", argv[0]);
        return 1;
    }

    int fd = open(argv[1],O_RDONLY);

    int l = read(fd, &fi, sizeof(gfh_file_info));

    printf("gfh header size: %d\n", sizeof(gfh_file_info));

    printf("id: %s\n", fi.id);
    printf("fil_ver: %d\n", fi.file_ver);
    printf("file_type: 0x%x\n", fi.file_type);
    printf("flash_dev: %d\n", fi.flash_dev);
    printf("sig_type: %d\n", fi.sig_type);
    printf("load_addr: 0x%x\n", fi.load_addr);
    printf("file_len: %d\n", fi.file_len);
    printf("max_size: %d\n", fi.max_size);
    printf("content_offset: 0x%x\n", fi.content_offset);
    printf("sig_len: %d\n", fi.sig_len);
    printf("jump_offset: 0x%x\n", fi.jump_offset);
    printf("attr: %d\n", fi.attr);

    close(fd);

    return 0;
}
