#!/usr/bin/env python3
import re
from pathlib import Path


def chunks(l, n):
    for i in range(0, len(l), n):
        yield l[i : i + n]


def get_n_bytes(n, filename="./sm64_source/baserom.eu.z64", offset=0x002385DC):
    return Path(filename).read_bytes()[
        # 0x00237E30 : (0x00237E30 + n)  # file_select
        # offset : (offset + n)
        offset:
    ]


def parse(hexbytes):
    return [phrase.replace(b"\x00", b"") for phrase in hexbytes.split(b"\xff")]


def charmap(c):
    int_val = int.from_bytes(c, "big")
    current_winner = None

    for map_line in Path("./sm64_source/charmap.txt").read_text().split("\n"):
        if not map_line or map_line.startswith("#"):
            continue
        text, val = map_line.split(" = ")
        if val == f"0x{int_val:0>2X}":
            current_winner = text[1:-1]

    return current_winner or "@"


def translate(parsed):
    return [
        "".join(list(map(charmap, list(chunks(s, 1))))).replace("Õ", " ")
        for s in parsed
    ]


def print_triplet(triplet):
    en, fr, de = triplet
    name = "".join(
        list(filter(lambda c: c == "_" or c.isalnum(), en.replace(" ", "_")))
    )
    base = f"#define TEXT_{name}"
    print(f'{base}_FR _("{fr}")')
    print(f'{base}_DE _("{de}")')
    print()


def ezcopy(line):
    print("#ifndef VERSION_EU")
    print(line)
    print("#else")
    match = re.match(r"(.*\[\]) = \{ (.*) \};", line)
    triple = (
        "{ "
        + match.group(2)
        + " }, { "
        + match.group(2)
        + "_FR }, { "
        + match.group(2)
        + "_DE }"
    )
    print(match.group(1) + "[20] = {" + triple + "};")
    print("#endif")
    print()


if __name__ == "__main__":
    # texts = translate(parse(get_n_bytes(0x52F)))

    # for triplet in chunks(texts[:12], 3):
    #     print_triplet(triplet)

    # for triplet in chunks(texts[16:-20], 3):
    #     print_triplet(triplet)

    # for triplet in chunks(texts[-19:-10], 3):
    #     print_triplet(triplet)

    # texts = translate(parse(get_n_bytes(0x50)))
    # hexa = b'\x9E\x01\x9E\x0B\x18\x0B\x9F\x18\x16\x0B\x9E\x0B\x0A\x1D\x1D\x15\x0E\x0F\x12\x0E\x15\x0D\xFF\x00\x9E\x02\x9E\x20\x11\x18\x16\x19\x3E\x1C\x9E\x0F\x18\x1B\x1D\x1B\x0E\x1C\x1C\xFF\x9E\x03\x9E\x13\x18\x15\x15\x22\x9E\x1B\x18\x10\x0E\x1B\x9E\x0B\x0A\x22\xFF\x00\x9E\x04\x9E\x0C\x18\x18\x15\x6F\x9E\x0C\x18\x18\x15\x9E\x16\x18\x1E\x17\x1D\x0A\x12\x17\xFF\x00\x9E\x05\x9E\x0B\x12\x10\x9E\x0B\x18\x18\x3E\x1C\x9E\x11\x0A\x1E\x17\x1D\xFF\x00'
    # print(translate(parse(hexa)))
    # print(texts)
    # print()

    # print(
    #     translate(
    #         parse(get_n_bytes(0x400, "./sm64_source/mio0_menu_baserom.out", 0xFF50))
    #     )
    # )

    hexa = get_n_bytes(0x400, "./sm64_source/mio0_menu_baserom.out", 0xFF50)
    print("{\n")
    for i, c in enumerate(chunks(hexa, 1)):
        if i % 8 == 0:
            print("\n    ", end="")
        int_val = int.from_bytes(c, "big")
        print(f"0x{int_val:0>2X}, ", end="")
    print("\n}")

    # ezcopy("static unsigned char textNew[] = { TEXT_NEW };")

