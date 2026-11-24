"""Make stdout/stderr UTF-8 on Windows consoles.

DeepFace prints emoji (e.g. a warning sign) while downloading model weights. On a
Windows cmd window (cp1252) that print raises UnicodeEncodeError inside the face
engine, which used to surface as "no face detected". Re-encoding the console as
UTF-8 with errors="replace" makes such prints harmless.
"""

import sys


def force_utf8_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass
