import os
import colored
import subprocess

from .kind.file_patch import writePatch
from .kind.script_patch import scriptPatch

__all__ = ("writePatches",)

def noext(fn):
    left, middle, ext = fn.rpartition(".")

    if ext.startswith(("fp-", "fd-", "fs-")):
        return left + middle + ext[3:]

    return fn

def writePatches(versionName: str, recovery: list, *, sub: str = "", recoveryLate: list|None = None) -> None:
    if recoveryLate is None:
        recoveryLate = []
        newLate = True
    else:
        newLate = False

    try:
        path = "versions/" + versionName + sub
        files = os.listdir(path)
    except FileNotFoundError as e:
        if sub != "":
            raise e

        return

    srcs = os.listdir("src")
    if os.path.isfile(skipSources := ("versions/" + versionName + "/.skip-sources")):
        with open(skipSources, "r", encoding='utf-8') as f:
            data = f.read().splitlines()

        for line in data:
            if line and not line.startswith(";"):
                srcs.remove(line)

    overrides = {}

    if os.path.isfile(overridesF := ("versions/" + versionName + "/.overrides")):
        with open(overridesF, "r", encoding='utf-8') as f:
            data = f.read().splitlines()

        for line in data:
            if line and not line.startswith(";"):
                pkg, _, modu = line.partition(" == ")
                overrides["/" + pkg] = modu

    for fn in files:
        fnSlashed = "/" + fn

        subN = sub + fnSlashed
        pathN = path + fnSlashed

        for ovr in overrides:
            if subN.startswith(ovr):
                physP = "src/" + overrides[ovr]
                physN = physP + subN

                break
        else:
            order = []
            subNS = subN.split("/")

            for srcName in srcs:
                physP = "src/" + srcName
                physN = physP + subN

                if os.path.exists(noext(physN)):
                    break

                for i in range(1, len(subNS)):
                    if os.path.exists(physP + "/".join(subNS[:-i])):
                       order.append((i, physP, physN))
                       break
            else:
                if len(order) > 2:
                    last = order[0][0]
                    same = True

                    for key in order[1:]:
                        if key[0] != last:
                           same = False
                           break

                    if same:
                       #print('clearing ' + repr(order))
                       order.clear()

                if order:
                    order = sorted(order, key=lambda tuple: tuple[0])
                    _, physP, physN = order[0]
                    #print("using " + physN + " (" + str(_) + ") <- " + repr(order))
                else:
                    #print("at " + physN + " <- " + repr(order))
                    physP = "src/main"
                    physN = physP + subN

        if os.path.isdir(pathN) != os.path.isdir(physN):
            if os.path.exists(physN):
                raise Exception("Incorrect filetype")
            else:
                os.mkdir(physN)
                print("[Funcutter] [Patches] > Creating directory " + pathN)
                recoveryLate.append(rmdir_proxy(physN))

        if os.path.isdir(pathN):
            writePatches(versionName, recovery, sub=subN, recoveryLate=recoveryLate)
        elif (dotSplit := fn.rpartition("."))[2].startswith("fp-"):
            print(colored.fore_rgb(80, 80, 80) + "[Funcutter] [Patches] " + colored.fore_rgb(120, 80, 120) + "> Applying " + colored.Style.BOLD + pathN + colored.Style.RESET)

            physN = physP + sub + "/" + dotSplit[0] + "." + dotSplit[2][3:]

            if not os.path.isfile(physN):
                input(colored.fore_rgb(140, 80, 80) + "\a[Funcutter] [Patches] [ERROR] > Failed to apply: " + pathN + " [%s]  " % ("not a file" if os.path.exists(physN) else "doesn't exist") + colored.Style.RESET)
                continue

            writePatch(pathN, physN)
        elif (dotSplit := fn.rpartition("."))[2].startswith("fs-"):
            print(colored.fore_rgb(80, 80, 80) + "[Funcutter] [Patches] " + colored.fore_rgb(80, 120, 120) + "> Running " + colored.Style.BOLD + pathN + colored.Style.RESET)

            physN = physP + sub + "/" + dotSplit[0] + "." + dotSplit[2][3:]

            if not os.path.isfile(physN):
                input(colored.fore_rgb(140, 80, 80) + "\a[Funcutter] [Patches] [ERROR] > Failed to run: " + pathN + " [%s]  " % ("not a file" if os.path.exists(physN) else "doesn't exist") + colored.Style.RESET)
                continue

            scriptPatch(pathN, physN)
        elif (dotSplit := fn.rpartition("."))[2].startswith("fd-"):
            print(colored.fore_rgb(80, 80, 80) + "[Funcutter] [Patches] " + colored.fore_rgb(120, 80, 80) + "> Deleting " + colored.Style.BOLD + pathN + colored.Style.RESET)

            realP = physP + sub + "/" + dotSplit[0] + "." + dotSplit[2][3:]
            optional = False

            with open(pathN, "r", encoding='utf-8', errors='ignore') as infofile:
                if infofile.read().strip() == '[optional]':
                    optional = True

            if not os.path.isfile(realP):
                input(colored.fore_rgb(140, 80, 80) + "\a[Funcutter] [Patches] [ERROR] > Failed to delete: " + pathN + " [%s]  " % ("not a file" if os.path.exists(physN) else "doesn't exist") + colored.Style.RESET)
                continue

            try:
                os.unlink(realP)
            except:
                if not optional:
                    raise

            recovery.append(runner(["git", "restore", realP]))
        else:
            print(colored.fore_rgb(80, 80, 80) + "[Funcutter] [Patches] " + colored.fore_rgb(80, 120, 80) + "> Creating " + colored.Style.BOLD + pathN + colored.Style.RESET)

            with open(pathN, "rb") as src:
                with open(physN, "wb") as dest:
                    dest.write(src.read())

            recovery.append(deleter(physN))

    if newLate:
        recovery.extend(recoveryLate)

def rmdir_proxy(path: str):
    return lambda: os.rmdir(path)

def runner(args: list[str]):
    return lambda: subprocess.run(args)

def deleter(path: str):
    return lambda: os.unlink(path) if os.path.exists(path) else None
