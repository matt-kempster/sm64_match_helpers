# run this from inside sm64_source
from pathlib import Path
import subprocess


def delete_if_unused(nonmatching: str):
    ret = subprocess.run(
        ["grep", "-r", nonmatching, "./src", "./lib"], stdout=subprocess.DEVNULL
    ).returncode
    if ret != 0:
        print(f"deleting {nonmatching}")
        Path(nonmatching).unlink()


files = Path("./asm/non_matchings").glob("*.s")
for nonmatching in [str(filename) for filename in files]:
    # delete_if_unused(nonmatching)
    if not (nonmatching.endswith("eu.s") or nonmatching.endswith("eu.inc.s")):
        continue

    dest = (
        Path(nonmatching).parent
        / "eu"
        / (Path(nonmatching).name.replace("_eu.s", ".s").replace("_eu.inc.s", ".inc.s"))
    )
    
    Path(nonmatching).replace(dest)
    found = False
    for src_file in Path("./src").rglob("*.c"):
        fulltext = src_file.read_text()
        if nonmatching in fulltext:
            print(f"replacing in {str(src_file)}")
            replacedtext = fulltext.replace(nonmatching, str(dest))
            src_file.write_text(replacedtext)
            break
    print(f"done with {str(dest)}")

