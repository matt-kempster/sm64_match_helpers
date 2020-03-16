#! /usr/bin/env python3

import argparse
import subprocess
from pathlib import Path
from typing import List, Optional, Set


def get_unknown_symbols(bhv_path: str) -> Set[str]:
    out_list = subprocess.run(
        [
            "gcc",
            "-g",
            *("-nostdinc", "-std=gnu90"),
            *("-Wall", "-Wextra", "-Wno-format-security"),
            *("-DTARGET_N64", "-DNON_MATCHING", "-DAVOID_UB"),
            bhv_path,
        ],
        stderr=subprocess.PIPE,
    ).stderr.split(b"\n")
    lines = [line.decode("utf-8") for line in out_list if b"undeclared" in line]
    suffixes = [line[line.index("‘") + 1 :] for line in lines if "‘" in line]
    return set([prefix[: prefix.index("’")] for prefix in suffixes])


def get_unknown_functions(bhv_path) -> Set[str]:
    out_list = subprocess.run(
        [
            "gcc",
            "-g",
            *("-nostdinc", "-std=gnu90"),
            *("-Wall", "-Wextra", "-Wno-format-security"),
            *("-DTARGET_N64", "-DNON_MATCHING", "-DAVOID_UB"),
            bhv_path,
        ],
        stderr=subprocess.PIPE,
    ).stderr.split(b"\n")
    lines = [
        line.decode("utf-8")
        for line in out_list
        if b"implicit declaration of function" in line
    ]
    suffixes = [line[line.index("‘") + 1 :] for line in lines if "‘" in line]
    return set([prefix[: prefix.index("’")] for prefix in suffixes])


def find_symbol(symbol: str) -> Optional[str]:
    if symbol.startswith("DIALOG"):
        return "include/dialog_ids.h"
    elif symbol.startswith("COURSE_"):
        return "include/course_table.h"
    elif symbol.startswith("SEQ_"):
        return "include/seq_ids.h"
    elif "_seg7_collision" in symbol:
        return "levels/" + symbol[: symbol.index("_seg7_collision")] + "/header.h"

    comments = r"\/\*(\*(?!\/)|[^*])*\*\/"
    defines = fr"^(\s|{comments})*#define\s({comments})*\s*{symbol}\s"
    typedefs = fr"typedef.*\s{symbol};"
    declarations = fr"[^=]+\s[\*]*{symbol}(\[.*\])*;"
    for pattern in [defines, typedefs, declarations]:
        results = subprocess.run(
            ["grep", "-r", "-P", pattern, "src", "include",], stdout=subprocess.PIPE,
        ).stdout.split(b"\n")
        nontrivial_files = [result for result in results if result != b""]
        true_h_files = [
            filename[: filename.index(b":")]
            for filename in nontrivial_files
            if b".h" in filename
        ]
        if true_h_files:
            break

    if len(true_h_files) == 0:
        print(f"{symbol} not found")
        return None

    almost_there = true_h_files[0].decode("utf-8")
    if almost_there == "include/PR/mbi.h":
        return "include/PR/ultratypes.h"
    else:
        return almost_there


def find_function(func: str) -> Optional[str]:
    if func in ["sins", "coss"]:
        return "src/engine/math_util.h"
    pattern = fr"^[\w\s\*]*\w[\w\s\*]*[\s\*]+{func}\([^\(\)]*\);"
    # print(pattern)
    results = subprocess.run(
        ["grep", "-r", "-P", pattern, "src", "include",], stdout=subprocess.PIPE,
    ).stdout.split(b"\n")
    nontrivial_files = [result for result in results if result != b""]
    true_h_files = [
        filename[: filename.index(b":")]
        for filename in nontrivial_files
        if b".h" in filename
    ]

    if len(true_h_files) == 0:
        print(f"{func} not found")
        return None

    file = true_h_files[0].decode("utf-8")
    # print(file)
    return file


def get_print_includes(files) -> List[str]:
    lst_files = []
    for file in files:
        lst_files.append(f'#include "{file}"')
    return lst_files


if __name__ == "__main__":
    for bhv_file in (Path("./src") / "game" / "behaviors").iterdir():
        files: Set[str] = set(["include/object_fields.h"])
        symbols = get_unknown_symbols(bhv_file)
        for symbol in symbols:
            if file := find_symbol(symbol):
                files.add(file)  # type: ignore

        functions = get_unknown_functions(bhv_file)
        for func in functions:
            # print(func)
            if file := find_function(func):
                files.add(file)  # type: ignore

        includes = get_print_includes(files)
        print(bhv_file)
        print("\n".join(sorted(includes)))

        lines = bhv_file.read_text().split("\n")
        lines = list(sorted(includes)) + lines
        bhv_file.write_text("\n".join(lines))
