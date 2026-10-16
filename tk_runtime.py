"""Locate Tcl/Tk resources, including the archives shipped with Python 3.15."""

import os
import sys
import zipfile
from pathlib import Path
from app_storage import cache_session


def prepare_tk_runtime(cache_dir=None):
    # PyInstaller supplies its own resources and environment at runtime.
    if getattr(sys, "frozen", False):
        return

    source = Path(sys.base_prefix) / "tcl"
    cache = Path(cache_dir) if cache_dir else None
    for pattern, folder, entrypoint, variable in (
        ("libtcl*.zip", "tcl_library", "init.tcl", "TCL_LIBRARY"),
        ("libtk*.zip", "tk_library", "tk.tcl", "TK_LIBRARY"),
    ):
        if os.environ.get(variable):
            continue
        archives = sorted(source.glob(pattern))
        if not archives:
            continue
        if cache is None:
            cache = cache_session().path / "tk-runtime"
        archive = archives[-1]
        destination = cache / archive.stem
        library = destination / folder
        if not (library / entrypoint).is_file():
            with zipfile.ZipFile(archive) as bundle:
                bundle.extractall(destination)
        os.environ[variable] = str(library)
