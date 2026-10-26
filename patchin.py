import builtins

def colored():
  """Patches in a dummy colored API."""

  class dummy:
    def fore_rgb(*_, *__): pass
    def back_rgb(*_, *__): pass

    class Style:
      RESET = ""
      BOLD = ""

  builtins.colored = dummy
