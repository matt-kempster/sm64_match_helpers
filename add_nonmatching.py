#! /usr/bin/env python3
from pathlib import Path
import sys
import re
import fileinput
import os
import subprocess
import argparse
import random
from typing import Tuple


def replace_function(sm64_source: str, path_to_c_file: str, function: str):
    path_to_c_file = str(Path(sm64_source) / Path(path_to_c_file))

    with fileinput.input(files=[path_to_c_file], inplace=True) as fp:
        inside = False
        for line in fp:
            if inside and line == "}\n":
                print(line, end="")
                print("#endif")
                inside = False
                continue

            match = re.match(fr"(.*{function}.*) {{", line)
            if match is not None:
                inside = True
                print("#if defined(VERSION_EU) && !defined(NON_MATCHING)")
                print(match.group(1) + ";")
                print(f'GLOBAL_ASM("asm/non_matchings/{function}_eu.s")')
                print("#else")

            print(line, end="")


def write_asm(sm64_source: str, function: str, rom_offset: str) -> str:
    sm64_tools = os.environ.get("SM64_TOOLS")
    if not sm64_tools:
        raise EnvironmentError(
            "Env variable SM64_TOOLS should point to "
            "sm64tools checkout with mipsdisasm built"
        )
    asm = subprocess.run(
        [
            sm64_tools + "/mipsdisasm",
            "-p",
            f"{sm64_source}/baserom.eu.z64",
            f"0x80200000:{rom_offset}+0x1000",
        ],
        stdout=subprocess.PIPE,
    ).stdout.decode("utf-8")

    asm_filename = f"{sm64_source}/asm/non_matchings/{function}_eu.s"
    rand_seed = str(random.randint(0, 99)) + "_"
    with open(asm_filename, "w") as asm_file:
        should_break = False
        asm_file.write(f"glabel {function}\n")
        for lineno, line in enumerate(asm.split("\n")):
            if lineno < 4:
                continue
            line = line.replace("func_", "0x")
            line = line.replace("D_", "0x")
            line = line.replace(".L", ".L" + rand_seed)
            asm_file.write(line + "\n")
            print(line)
            if should_break:
                break
            if "jr    $ra" in line:
                # should_break = True
                should_break = input("done? ") != "n"

    return asm_filename


def get_next_nonmatching(sm64_source: str) -> Tuple[str, str, str]:
    os.chdir(sm64_source)
    first_diff_cmd = str(Path(sm64_source) / "first-diff.py")
    result = subprocess.run([first_diff_cmd], stdout=subprocess.PIPE)
    output = result.stdout.decode("utf-8")
    for line in output.split("\n"):
        match = re.match(
            # FOR THE OLD BEHAVIOR:
            # r"First instruction difference at ROM addr .*, in (.*) "
            # FOR THE NEW BEHAVIOR:
            r"First difference at ROM addr .*, in (.*) "
            r"\(ram .*, rom (.*), build/eu/(.*).o\)",
            line,
        )
        if match:
            function = match.group(1)
            rom_offset = match.group(2)
            path_to_c_file = match.group(3) + ".c"
            return (function, rom_offset, path_to_c_file)
    raise Exception("first-diff.py output didn't match expectations")


def make(sm64_source) -> bool:
    os.chdir(sm64_source)
    result = subprocess.run(["make", "VERSION=eu", "COMPARE=0"], stdout=subprocess.PIPE)
    if result.returncode != 0:
        print(result.stdout)
    return result.returncode == 0


def prompt(question_mark: bool = False) -> str:
    response = ""
    while response not in ["y", "n"] + (["?"] if question_mark else []):
        response = input(f"continue? y/n{'/?' if question_mark else ''}: ")
    return response


def main(sm64_source: str, no_replace: bool):
    print("first-diffing...")
    function, rom_offset, path_to_c_file = get_next_nonmatching(sm64_source)

    print(f"got function = {function}, offset = {rom_offset}, path = {path_to_c_file}")
    if "/" in function or "." in function:
        print("function looks wrong. bailing.")
        return

    response = prompt(question_mark=True)
    if response == "?":
        print("ok, you want to change the target c file to modify.")
        print("(this is for .inc.c-type files - behavior_actions in particular)")
        path_to_c_file = input("what's the actual c file path?")
    elif response == "n":
        print("bailing.")
        return

    print("overwriting asm file...")
    asm_filename = write_asm(sm64_source, function, rom_offset)

    response = prompt(question_mark=True)
    if response == "?":
        print(Path(asm_filename).read_text())
        response = prompt(question_mark=False)
    if response == "n":
        print(f"bailing. go delete that asm file ({asm_filename})")
        return

    if not no_replace:
        print("injecting c file contents...")
        replace_function(sm64_source, path_to_c_file, function)

    print("making...")
    result = make(sm64_source)
    if not result:
        print("something went wrong during make. bailing.")
        return

    print("first-diffing again...")
    function2, rom_offset2, _ = get_next_nonmatching(sm64_source)
    if function == function2 or rom_offset == rom_offset2:
        print(f"functions or rom offsets match ({function2}, {rom_offset2}).")
        print("you'll likely have to #define static to find the real next function.")
        return
    else:
        print("seems different enough.")

    print("done")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("sm64_source", help="Path to sm64_source")
    parser.add_argument(
        "--no-replace", help="Don't modify the C file", action="store_true"
    )
    args = parser.parse_args()
    main(args.sm64_source, args.no_replace)
