import subprocess
import signal
import typing
import msvcrt
import sys
import os

try:
    import colorama
    import colored
except:
    print("[!] Install 'colorama' and 'colored'? They're optional dependencies for Funcutter.", flush=True)

    while True:
        print("[!] (y/n) ", flush=True)

        resp = msvcrt.getwch()

        if resp == 'y':
            subprocess.run([sys.executable, "-m", "pip", "--no-version-check", "install", "colorama", "colored"])
        elif resp == 'n':
            break
        else:
            import patchin

            patchin.colored()

            continue

    print()
else:
    colorama.just_fix_windows_console()

from input import *

from modloaders.fabric import Fabric
from modloaders.legacy_fabric import LegacyFabric

from parsing.properties import *
from parsing.funcutter import *

from patching.writer import writePatches

#############
## READING ##
#############

def readFuncutter() -> Versions:
    with open("./build.funcutter", "r", encoding="utf-8") as f:
        funcutter = f.read()

    return parseFuncutter(funcutter)

def readProperties() -> tuple[Properties, str]:
    with open("./gradle.properties", "r", encoding="utf-8") as f:
        properties = f.read()

    return (
        parseProperties(properties),
        properties
    )

#############
## WRITING ##
#############

def writeProperties(properties: Properties) -> None:
    with open("./gradle.properties", "w", encoding="utf-8") as f:
        for key in properties:
            if key[0] == "\x00":
                f.write(properties[key] + "\n")
                continue

            f.write(key + "=" + properties[key] + "\n")

##############
## BUILDING ##
##############

def buildAll() -> None:
    ###=============###
    ### READ CONFIG ###
    ###=============###
    print("[Funcutter] > Configuring")

    funcutter = readFuncutter()

    ###======###
    ### DUMP ###
    ###======###
    if len(sys.argv) > 1 and sys.argv[1] == "!dump":
        print()

        for version in funcutter:
            if version['abstract']:
                sys.stderr.write("abstract ")

            sys.stderr.write("version %s {" % version['name'])

            inherits_started = False
            inherits_count = 0

            if version['extensions']:
                inherits_started = True

                sys.stderr.write("\n")
                sys.stderr.write("    inherits {\n")

                for obj in version['extensions']:
                    if isinstance(obj, typing.Callable):
                        sys.stderr.write("        patches from [dynamic] %s\n" % (obj.get()))
                    else:
                        sys.stderr.write("        patches from %s\n" % (obj))

            if version['properties']:
                for obj in version['properties']:
                    if isinstance(obj, typing.Callable):
                        if not inherits_started:
                            inherits_started = True
                            sys.stderr.write("    inherits {\n")

                        sys.stderr.write("        properties from [dynamic] %s\n" % (obj.get()))
                        inherits_count += 1

                if inherits_started:
                    sys.stderr.write("    }")

                if len(version['properties']) > inherits_count:
                    sys.stderr.write("\n")

                    props_started = False

                    for obj in version['properties']:
                        if isinstance(obj, tuple):
                            if not props_started:
                                props_started = True

                                if inherits_started:
                                    sys.stderr.write("\n")

                                sys.stderr.write("    properties {\n")

                            sys.stderr.write("        %s = %s\n" % obj)
                        elif isinstance(obj, str):
                            if not props_started:
                                props_started = True

                                if inherits_started:
                                    sys.stderr.write("\n")

                                sys.stderr.write("    properties {\n")

                            sys.stderr.write("        %s = %s\n" % (obj, version['properties'][obj]))

                    if props_started:
                        sys.stderr.write("    }")

                sys.stderr.write("\n")
            elif inherits_started:
                sys.stderr.write("    }")
                sys.stderr.write("\n")

            sys.stderr.write("}")
            sys.stderr.write("\n\n")

        sys.exit(0)

    ###=================###
    ### READ PROPERTIES ###
    ###=================###
    properties, propRaw = readProperties()

    jarName = properties.get('archives_base_name')

    ###=======###
    ### STASH ###
    ###=======###
    print("[Funcutter] > Storing")
    only_errors = {
      "stdout": subprocess.PIPE,
      "stderr": subprocess.STDOUT
    }

    subprocess.run(["git", "add", "."], **only_errors)
    subprocess.run(["git", "commit", "-m", "funcutter -- temporary", "--allow-empty"], **only_errors)

    ###===================###
    ### MAKE EACH VERSION ###
    ###===================###
    pendingReset = False
    recovery = []

    try:
      command = [".\\gradlew.bat"]

      for _ in range(1):
        if len(sys.argv) > 1:
          if sys.argv[1] == "!wait":
            def runner():
              print(old := "[Funcutter] Waiting. To continue, press any key.", end="")
              sys.stdout.flush()
              if msvcrt.getch() == b'\x03':
                print()
                raise KeyboardInterrupt()

              print("\r[Funcutter] Continuing." + " "*(len(old) - 23))

            break
          else:
            args = sys.argv[1:]

            if not args[0].startswith("-"):
              command.append(args.pop(0))
            else: command.append('build')

            skipNow = False

            for arg in args:
              if skipNow:
                skipNow = False
              elif arg in ('-v', '--version'):
                skipNow = True
              else:
                command.append(arg)
        else:
          command.append("build")

        runner = lambda: subprocess.run(command)

      expectingSpecific = None if len(sys.argv) < 3 else (
          sys.argv[sys.argv.index('-v')        + 1] if '-v'        in sys.argv else
          sys.argv[sys.argv.index('--version') + 1] if '--version' in sys.argv else
          None
      )

      for version in funcutter:
          if version['abstract']:
              continue

          if expectingSpecific:
              if expectingSpecific != version['name']:
                  continue

          print("[Funcutter] > Version " + version['name'])

          recovery.clear()
          pendingReset = True

          vproperties = {**properties, **version['properties']}

          if jarName != None:
              vproperties['archives_base_name'] = jarName + "+" + version['name']

          writeProperties(vproperties)

          for extension in version['extensions']:
              writePatches(extension, recovery)

          writePatches(version['name'], recovery)

          runner()

          for func in recovery:
            func()

          subprocess.run(["git", "reset", "--hard"])
          pendingReset = False

          if expectingSpecific:
              break
      else:
        if expectingSpecific:
          print("[Funcutter] [ERROR] Unable to find version '%s'" % sys.argv[2])
    except KeyboardInterrupt:
        print("[Funcutter] > Detected keyboard interrupt, cancelling")
        signal.signal(signal.SIGINT, lambda *_: None)

        if pendingReset:
          for func in recovery:
            func()

          subprocess.run(["git", "reset", "--hard"])

    ###===================###
    ### RESTORE OLD STATE ###
    ###===================###
    print("[Funcutter] > Restoring old state")

    with open("./gradle.properties", "w", encoding="utf-8") as f:
        f.write(propRaw)

    subprocess.run(["git", "reset", "--mixed", "HEAD~1"])

    ###==========###
    ### FINISHED ###
    ###==========###
    print("[Funcutter] > Finished")

#######################
## 'INIT' SUBCOMMAND ##
#######################

if len(sys.argv) > 1 and sys.argv[1] == "init":
  if os.path.isfile("build.funcutter"):
    print("ERROR: There's already a build.funcutter file in your directory")
    sys.exit(1)

  def logo():
    subprocess.run("cls" if os.name == "nt" else "clear", shell=True)

    print("|----------------------------|")
    print("| FunCutter :: Project Setup |")
    print("|----------------------------|")
    print()

  try:
    logo()
    modloader = listInput("Please select your modloader >", {
      "a": ("Fabric",        Fabric),
      "b": ("Legacy Fabric", LegacyFabric)
    })

    logo()

    print("Please input your Minecraft versions >")
    print("Leave empty to mark ready")
    print()

    mcvers = []
    while True:
      mcver = input("  ) ")
      if mcver == '':
        break

      mcvers.append(mcver)
  except KeyboardInterrupt:
    print("\nCancelling.")
    sys.exit(2)
  else:
    signal.signal(signal.SIGINT, lambda *_: None)

  funcutter = ""

  for mcver in mcvers:
    funcutter += "# %s\n" % mcver

    try:
      funcutter += modloader.properties(mcver)
    except Exception as e:
      if 'Fabric yarn' in str(e):
        print("[Missing Yarn] %s" % str(e))
        print("[Missing Yarn] Continue (y/n)? ", end="", flush=True)

        while True:
          key = msvcrt.getch()

          if key == b'\x03':
            raise KeyboardInterrupt()
          elif key == b'y':
            print("y", end="", flush=True)
            break
          elif key == b'n':
            print("n", flush=True)
            sys.exit(1)

        print()

        realYarnFetcher = modloader.getYarn
        modloader.getYarn = lambda *_: '<none>'
        funcutter += modloader.properties(mcver)
        modloader.getYarn = realYarnFetcher
      else:
        raise

    funcutter += "\n"

  with open("build.funcutter", "w", encoding="utf-8") as f:
    f.write(funcutter[:-1])

  sys.exit(0)

##########
## MAIN ##
##########

while True:
    if os.path.exists("./build.funcutter"):
        buildAll()
        break
    elif os.getcwd().count("/") <= 1:
        print("[Funcutter] [Main/ERROR] No 'build.funcutter' file could be found in your directory nor its ancestors")
        sys.exit(1)
    else:
        os.chdir("..")
