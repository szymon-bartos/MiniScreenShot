"""Small entry point that can report startup failures without a working Tk."""
import ctypes
import importlib
import logging
import sys


def show_startup_error():
    message = (
        "Nie można uruchomić MiniScreenShot.\n\n"
        "Rozpakuj cały ZIP. Katalog _internal musi znajdować się obok EXE. "
        "Sprawdź dostęp do C:\\MiniScreenShot lub %LOCALAPPDATA%\\MiniScreenShot.\n\n"
        "Jeśli Windows zgłasza zagrożenie, pozostaw plik w kwarantannie i "
        "przekaż autorowi nazwę wykrycia. Nie wyłączaj ochrony ani nie dodawaj wyjątków.\n\n"
        "MiniScreenShot could not start. Extract the entire ZIP and keep _internal "
        "next to the EXE. Check access to the application data directory. "
        "If Windows reports a threat, keep the file quarantined and report the detection."
    )
    if sys.platform == "win32":
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        show = user32.MessageBoxW
        show.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
        show.restype = ctypes.c_int
        show(None, message, "MiniScreenShot", 0x10)
    elif sys.stderr is not None:
        print(message, file=sys.stderr)


def run_application():
    try:
        application = importlib.import_module("app_advanced")
        application.main()
        return 0
    except Exception:
        # Import errors, denied cache access and missing Tk resources can occur
        # before the main window exists. Preserve diagnostics when available.
        try:
            logging.getLogger(__name__).exception("Application startup failed")
        except Exception:
            pass
        try:
            show_startup_error()
        except Exception:
            # A failure to display the message must still produce a clean,
            # nonzero exit, including on a desktop that is shutting down.
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(run_application())
