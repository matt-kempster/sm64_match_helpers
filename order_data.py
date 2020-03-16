#!/usr/bin/env python3.8
import argparse
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def get_baserom_asm_line(sm64_source: str, sm64tools: str, offset: str) -> str:
    output = (
        subprocess.run(
            [
                str(Path(sm64tools) / "mipsdisasm"),
                "-p",
                str(Path(sm64_source) / "baserom.eu.z64"),
                f"0x80200000:{offset}+0x4",
            ],
            stdout=subprocess.PIPE,
        )
        .stdout.decode("utf-8")
        .strip()
    )
    return output.split("\n")[-1]


def get_real_ram_addr(
    sm64_source: str, sm64tools: str, symbol: str, o_file: str, file_rom_start: str
) -> Optional[str]:
    objdump_output = (
        subprocess.run(
            ["mips-linux-gnu-objdump", "-rd", str(o_file)], stdout=subprocess.PIPE
        )
        .stdout.decode("utf-8")
        .split("\n")
    )

    hi_offset = ""
    lo_offset = ""
    for line in objdump_output:
        if symbol in line:
            if "R_MIPS_HI16" in line:
                hi_offset = line.split(":")[0].strip()
            elif "R_MIPS_LO16" in line:
                lo_offset = line.split(":")[0].strip()
            else:
                raise Exception(f"unsure why {symbol} in line: {line}")
    if not hi_offset and not lo_offset:
        print(f"{symbol} is gone")
        return None
    elif not hi_offset or not lo_offset:
        raise Exception("wasn't able to find both hi and lo offsets")

    hi_asm_line = hex(int(file_rom_start, 16) + int(hi_offset, 16))
    real_hi_offset = (
        "0x"
        + get_baserom_asm_line(sm64_source, sm64tools, hi_asm_line)
        .split("0x")[-1]
        .split()[0]
    )

    lo_asm_line = hex(int(file_rom_start, 16) + int(lo_offset, 16))
    thing = get_baserom_asm_line(sm64_source, sm64tools, lo_asm_line).split("0x")
    negate = False
    if thing[0][-1] == "-":
        negate = True
    real_lo_offset = ("-" if negate else "") + "0x" + thing[-1].split()[0].split("(")[0]

    real_ram_addr = hex(int(real_hi_offset + "0000", 16) + int(real_lo_offset, 16))
    return real_ram_addr


def get_symbols(o_file: str) -> List[str]:
    symbol_table = (
        subprocess.run(["mips-linux-gnu-objdump", "-t", o_file], stdout=subprocess.PIPE)
        .stdout.decode("utf-8")
        .split("\n")
    )
    return [
        line.split()[-1]
        for line in symbol_table
        if ".data" in line and not line.endswith(".data")
    ]


def get_o_files_and_offsets(sm64_source: str) -> List[Tuple[Path, str]]:
    o_files_and_offsets = []

    sm64_path = Path(sm64_source)
    map_file = sm64_path / "build" / "eu" / "sm64.eu.map"
    lines = map_file.read_text().split("\n")

    ram_to_rom = int("0x80240800", 16)

    seen_main = False
    for idx, line in enumerate(lines):
        line = line.strip()

        if ".main" in line:
            seen_main = True
        elif not seen_main:
            continue

        if ".engine" in line:
            print("encountered engine - done parsing map")
            break

        if "(.text)" not in line:
            continue

        line = line[: -len("(.text)")]

        filepath: Optional[Path] = None
        if "libultra.a" not in line:
            filepath = sm64_path / line
        elif (maybe := sm64_path / line.replace("ultra.a:", "/src/")).is_file():
            filepath = maybe
        elif (maybe := sm64_path / line.replace("ultra.a:", "/asm/")).is_file():
            filepath = maybe
        else:
            print(f"can't figure out how to make this a real .o file: {line}")
            continue

        if not (offset_line := lines[idx + 1].strip()).startswith(".text"):
            offset_line = lines[idx + 2].strip()
        offset = hex(int(offset_line.split()[1], 16) - ram_to_rom)

        o_files_and_offsets.append((filepath, offset))

    return o_files_and_offsets


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("sm64_source", help="Path to sm64_source")
    args = parser.parse_args()

    o_files_and_offsets = get_o_files_and_offsets(args.sm64_source)

    sm64tools = os.environ.get("SM64_TOOLS")
    if not sm64tools:
        raise Exception("define SM64_TOOLS as an env var")

    file_order: Dict[str, int] = {}
    for o_file, file_rom_start in o_files_and_offsets:
        min_symbol = float("inf")
        max_symbol = -1
        for symbol in get_symbols(o_file):
            try:
                ram_addr = get_real_ram_addr(
                    args.sm64_source, sm64tools, symbol, o_file, file_rom_start
                )
                if ram_addr:
                    print(f"{symbol}: {ram_addr}")
                    ram_addr_int = int(ram_addr, 16)
                    min_symbol = min(min_symbol, ram_addr_int)
                    max_symbol = max(max_symbol, ram_addr_int)
            except Exception:
                print("whatever...")
        if max_symbol != -1:
            file_order[o_file] = max_symbol
        else:
            print(f"no info about {o_file}")
    files = sorted(file_order.items(), key=lambda kv: kv[1])
    for fileinfo in files:
        print(fileinfo)
