import json
import yaml

__all__ = ("scriptPatch",)
SCRIPTABLES = {
    "txt": (lambda text: text, lambda text: text),
    "json": (json.loads,     lambda obj: json.dumps    (obj, indent=2)),
    "yaml": (yaml.full_load, lambda obj: yaml.safe_dump(obj, indent=2))
}

def scriptPatch(patchPath: str, physicalPath: str) -> None:
    global SCRIPTABLES

    ext = physicalPath.rpartition(".")[2]
    if ext not in SCRIPTABLES:
        print("[FunCutter] [Patches/WARN] > Unrecognized extension '.%s', falling back to .txt" % ext)
        ext = "txt"

    with open(patchPath, "r", encoding="utf-8") as f:
        userscript = f.read()

    load, dump = SCRIPTABLES[ext]
    compiled = compile(userscript, patchPath, "exec")

    with open(physicalPath, "rb+") as f:
        encoding = "utf-8"
        physical = f.read().decode(encoding)

        f.seek(0)

        parsed = load(physical)
        options = {
            "this": parsed
        }

        exec(compiled, options, options)

        dumped = dump(options['this'])
        encoded = dumped.encode(encoding)

        f.write(encoded)
        f.truncate(len(encoded))
