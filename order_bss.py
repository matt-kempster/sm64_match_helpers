#!/usr/bin/env python3.8
"""Forked from order_data.py."""
import argparse
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def get_baserom_asm_line(sm64_source: str, sm64tools: str, offset: str) -> str:
    return get_asm_line(
        sm64_source, sm64tools, offset, str(Path(sm64_source) / "baserom.eu.z64")
    )


def get_builtrom_asm_line(sm64_source: str, sm64tools: str, offset: str) -> str:
    return get_asm_line(
        sm64_source,
        sm64tools,
        offset,
        str(Path(sm64_source) / "build" / "eu" / "sm64.eu.z64"),
    )


def get_asm_line(sm64_source: str, sm64tools: str, offset: str, rom: str) -> str:
    output = (
        subprocess.run(
            [
                str(Path(sm64tools) / "mipsdisasm"),
                "-p",
                rom,
                f"0x80200000:{offset}+0x4",
            ],
            stdout=subprocess.PIPE,
        )
        .stdout.decode("utf-8")
        .strip()
    )
    return output.split("\n")[-1]


def get_real_ram_addrs(
    sm64_source: str, sm64tools: str, symbol: str, o_file: str, file_rom_start: str
) -> Optional[Tuple[str, str]]:
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
        # print(f"{symbol} is gone")
        return None
    elif not hi_offset or not lo_offset:
        raise Exception("wasn't able to find both hi and lo offsets")

    baserom_builtrom_ram_addrs: Tuple[str, str] = ("", "")
    for rom_func in (get_baserom_asm_line, get_builtrom_asm_line):
        hi_asm_line = hex(int(file_rom_start, 16) + int(hi_offset, 16))
        real_hi_offset = (
            "0x"
            + rom_func(sm64_source, sm64tools, hi_asm_line).split("0x")[-1].split()[0]
        )

        lo_asm_line = hex(int(file_rom_start, 16) + int(lo_offset, 16))
        thing = rom_func(sm64_source, sm64tools, lo_asm_line).split("0x")
        negate = False
        if thing[0][-1] == "-":
            negate = True
        real_lo_offset = (
            ("-" if negate else "") + "0x" + thing[-1].split()[0].split("(")[0]
        )

        real_ram_addr = hex(int(real_hi_offset + "0000", 16) + int(real_lo_offset, 16))

        if rom_func == get_baserom_asm_line:
            baserom_builtrom_ram_addrs = (real_ram_addr, baserom_builtrom_ram_addrs[1])
        else:
            baserom_builtrom_ram_addrs = (baserom_builtrom_ram_addrs[0], real_ram_addr)

    return baserom_builtrom_ram_addrs


def get_symbols(o_file: str, segment: str) -> List[str]:
    symbol_table = (
        subprocess.run(["mips-linux-gnu-objdump", "-t", o_file], stdout=subprocess.PIPE)
        .stdout.decode("utf-8")
        .split("\n")
    )
    return [
        line.split()[-1]
        for line in symbol_table
        if segment in line and not line.endswith(segment)
    ]


def get_o_files_and_offsets(sm64_source: str) -> List[Tuple[Path, str]]:
    o_files_and_offsets = []

    sm64_path = Path(sm64_source)
    map_file = sm64_path / "build" / "eu" / "sm64.eu.map"
    lines = map_file.read_text().split("\n")

    ram_to_rom = int("0x80240800", 16)
    # ram_to_rom = int("0x802B07F0", 16)
    # ram_to_rom = int("0x802A88B0", 16)
    # ram_to_rom = int("0x7FF6EF60", 16)
    # ram_to_rom = int("0x7FF6EF60", 16)  # goddard

    seen_main = False
    for idx, line in enumerate(lines):
        line = line.strip()

        if ".main" in line:
        # if ".engine" in line:
        # if ".goddard" in line:
            # if ".buffers.noload" in line:
            seen_main = True
        elif not seen_main:
            continue

        if ".engine" in line:
        # if ".menu" in line:
        # if ".buffers" in line:
        # if ".intro_segment_7" in line:
            # print("encountered engine - done parsing map")
            # print("encountered menu - done parsing map")
            # print("encountered buffers - done parsing map")
            print("done parsing map")
            break

        if "(.text)" not in line or "*.o" in line:
            continue

        line = line[: -len("(.text)")]

        filepath: Optional[Path] = None
        if "libultra.a" not in line and "libgoddard.a" not in line:
            filepath = sm64_path / line
        elif (maybe := sm64_path / line.replace("ultra.a:", "/src/")).is_file():
            filepath = maybe
        elif (maybe := sm64_path / line.replace("ultra.a:", "/asm/")).is_file():
            filepath = maybe
        elif (
            maybe := sm64_path / line.replace("libgoddard.a:", "src/goddard/")
        ).is_file():
            filepath = maybe
        else:
            print(f"can't figure out how to make this a real .o file: {line}")
            continue

        if not (offset_line := lines[idx + 1].strip()).startswith(".text"):
            offset_line = lines[idx + 2].strip()

        offset = hex(int(offset_line.split()[1], 16) - ram_to_rom)

        o_files_and_offsets.append((filepath, offset))

    return o_files_and_offsets


def print_symbol_position_diff(
    symbol: str, args, sm64tools, o_file, file_rom_start
) -> Optional[Tuple[str, str, str]]:
    ram_addrs = get_real_ram_addrs(
        args.sm64_source, sm64tools, symbol, o_file, file_rom_start
    )
    if ram_addrs:
        baserom, builtrom = ram_addrs
        diff = hex(int(baserom, 16) - int(builtrom, 16))
        return (baserom, builtrom, diff)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("sm64_source", help="Path to sm64_source")
    parser.add_argument("master_o_file", help="Path to o file to order bss in")
    args = parser.parse_args()

    o_files_and_offsets = get_o_files_and_offsets(args.sm64_source)

    sm64tools = os.environ.get("SM64_TOOLS")
    if not sm64tools:
        raise Exception("define SM64_TOOLS as an env var")

    symbol_positions: Dict[str, Tuple[str, str, str]] = {}
    bss_symbols = get_symbols(args.master_o_file, segment=".bss")
    for o_file, file_rom_start in o_files_and_offsets:
        if o_file.name == Path(args.master_o_file).name:
            for symbol in bss_symbols:
                pos = print_symbol_position_diff(
                    symbol, args, sm64tools, o_file, file_rom_start
                )
                if not pos:
                    continue
                if symbol in symbol_positions:
                    if symbol_positions[symbol] != pos:
                        print(
                            f"inconsistent position info for {symbol}: "
                            f"{symbol_positions[symbol]} vs {pos} in {o_file.name}"
                        )
                else:
                    symbol_positions[symbol] = pos
        else:
            for symbol in get_symbols(o_file, segment="*UND*"):
                if symbol in bss_symbols:
                    pos = print_symbol_position_diff(
                        symbol, args, sm64tools, o_file, file_rom_start
                    )
                    if not pos:
                        continue
                    if symbol in symbol_positions:
                        if symbol_positions[symbol] != pos:
                            print(
                                f"inconsistent position info for {symbol}: "
                                f"{symbol_positions[symbol]} vs {pos} in {o_file.name}"
                            )
                    else:
                        symbol_positions[symbol] = pos
    for symbol, (baserom, builtrom, diff) in sorted(
        symbol_positions.items(), key=lambda kv: int(kv[1][0], 16)
    ):
        print(f"{symbol}: {baserom=!s}, {builtrom=!s}... {diff=!s}")

