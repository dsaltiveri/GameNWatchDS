#!/usr/bin/env python3
"""Graphical and command-line frontend for the GameNWatchDS .gnw generator."""

from __future__ import annotations

import argparse
import contextlib
import ctypes
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import gnw_builder_engine as engine


APP_NAME = "GNWBuilder"
APP_VERSION = "1.0.0"
RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
WORKSPACE_ROOT = (Path(sys.executable).resolve().parent
                  if getattr(sys, "frozen", False)
                  else Path(__file__).resolve().parents[1])
DEFAULT_ROM_DIR = WORKSPACE_ROOT / "roms"
DEFAULT_ARTWORK_DIR = WORKSPACE_ROOT / "artwork"
DEFAULT_OUTPUT_DIR = WORKSPACE_ROOT / "gnw"
BUILDER_WORK_DIR = WORKSPACE_ROOT / "build" / "gnw-builder"
DEFAULT_BUILD_DIR = BUILDER_WORK_DIR / "cache"
DEFAULT_PREVIEW_DIR = BUILDER_WORK_DIR / "preview"

_INPUT_NAMES = {
    game: (Path(cfg["rom_zip"]).name, Path(cfg["art_zip"]).name)
    for game, cfg in engine.GAMES.items()
}
_PROCESS_LOCK = threading.Lock()
_ACTIVE_PROCESS: subprocess.Popen[str] | None = None


class BuildCancelled(RuntimeError):
    """Raised when the graphical build is cancelled by the user."""


def _descriptor_path(game: str) -> Path:
    return RESOURCE_ROOT / "arm9" / "source" / "games" / f"game_{game}.c"


def game_title(game: str) -> str:
    """Return the visible menu title bundled from the C descriptor."""
    source = _descriptor_path(game).read_text(encoding="utf-8")
    match = re.search(r'\.name\s*=\s*"([^"]+)"', source)
    if not match:
        raise ValueError(f"Missing menu title in {_descriptor_path(game)}")
    return match.group(1)


def output_filename(game: str) -> str:
    title = game_title(game)
    if any(char in title for char in '<>:"/\\|?*'):
        raise ValueError(f"Menu title is not a FAT-compatible filename: {title}")
    return title.rstrip(". ") + ".gnw"


def available_games(rom_dir: Path, artwork_dir: Path):
    """Return display, availability and validation details for every game.

    ``has_rom`` is true only when the ZIP is a complete MAME NONMERGED set
    (one self-contained ZIP per machine), not merely when the file exists.
    ``reason`` explains a missing or invalid ROM ZIP for the GUI and CLI.
    """
    rows = []
    for game in sorted(engine.GAMES, key=lambda value: game_title(value).casefold()):
        rom_name, artwork_name = _INPUT_NAMES[game]
        rom_path = rom_dir / rom_name
        has_rom = rom_path.is_file()
        reason = ""
        if has_rom:
            cfg = dict(engine.GAMES[game])
            cfg["rom_zip"] = str(rom_path.resolve())
            reason = engine.rom_set_status(game, cfg) or ""
            has_rom = not reason
        else:
            reason = f"ROM ZIP missing ({rom_name})"
        has_artwork = (artwork_dir / artwork_name).is_file()
        rows.append((game, game_title(game), has_rom, has_artwork, reason))
    return rows


def _registry_inkscape_candidates():
    if os.name != "nt":
        return []
    try:
        import winreg
    except ImportError:
        return []
    candidates = []
    locations = (
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\inkscape.exe"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\inkscape.exe"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\inkscape.exe"),
    )
    for hive, key_name in locations:
        try:
            with winreg.OpenKey(hive, key_name) as key:
                value, _ = winreg.QueryValueEx(key, None)
        except OSError:
            continue
        path = Path(value)
        candidates.extend((path.with_name("inkscape.com"), path))
    return candidates


def discover_inkscape() -> Path:
    """Find Inkscape without weakening an explicit INKSCAPE override."""
    configured = os.environ.get("INKSCAPE")
    if configured:
        resolved = shutil.which(configured)
        if not resolved:
            raise RuntimeError(f"Inkscape not found: {configured} (INKSCAPE)")
        return Path(resolved)

    for name in ("inkscape.com", "inkscape"):
        resolved = shutil.which(name)
        if resolved:
            return Path(resolved)

    candidates = list(_registry_inkscape_candidates())
    for variable in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(variable)
        if base:
            candidates.extend((Path(base) / "Inkscape" / "bin" / "inkscape.com",
                               Path(base) / "Inkscape" / "bin" / "inkscape.exe"))
    candidates.extend((Path(r"C:\Program Files\Inkscape\bin\inkscape.com"),
                       Path(r"C:\Program Files\Inkscape\bin\inkscape.exe")))
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise RuntimeError(
        "Inkscape is not installed or could not be found. Install Inkscape for "
        "Windows, add it to PATH, or set INKSCAPE to inkscape.com."
    )


def inkscape_version(executable: Path) -> str:
    result = subprocess.run([str(executable), "--version"], capture_output=True,
                            text=True, encoding="utf-8", errors="replace",
                            timeout=15)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Inkscape --version failed")
    return result.stdout.strip()


def _configure_engine(rom_dir: Path, artwork_dir: Path, output_dir: Path) -> None:
    engine.ROOT = str(WORKSPACE_ROOT)
    engine.GNW_DIR = str(output_dir.resolve())
    engine.SRC_DIR = str(DEFAULT_BUILD_DIR.resolve())
    engine.PREVIEW_DIR = str(DEFAULT_PREVIEW_DIR.resolve())
    engine.output_filename = output_filename
    for game, cfg in engine.GAMES.items():
        rom_name, artwork_name = _INPUT_NAMES[game]
        cfg["rom_zip"] = str((rom_dir / rom_name).resolve())
        cfg["art_zip"] = str((artwork_dir / artwork_name).resolve())


def _run_inkscape_cancellable(args, cancel_event: threading.Event):
    if cancel_event.is_set():
        raise BuildCancelled("Build cancelled")
    executable = discover_inkscape()
    creationflags = 0
    if os.name == "nt":
        creationflags = (getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) |
                         getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        process = subprocess.Popen(
            [str(executable)] + list(args), stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8",
            errors="replace", creationflags=creationflags)
    except OSError as exc:
        raise RuntimeError(f"Could not run Inkscape: {exc}") from exc

    global _ACTIVE_PROCESS
    with _PROCESS_LOCK:
        _ACTIVE_PROCESS = process
    try:
        while True:
            try:
                stdout, stderr = process.communicate(timeout=0.10)
                break
            except subprocess.TimeoutExpired:
                if cancel_event.is_set():
                    process.terminate()
                    try:
                        process.communicate(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.communicate()
                    raise BuildCancelled("Build cancelled")
    finally:
        with _PROCESS_LOCK:
            if _ACTIVE_PROCESS is process:
                _ACTIVE_PROCESS = None
    if cancel_event.is_set():
        raise BuildCancelled("Build cancelled")
    if process.returncode != 0:
        raise RuntimeError("Inkscape failed [rc=%d, %s]: %s" % (
            process.returncode, " ".join(str(arg) for arg in args)[:160],
            stderr[-400:]))
    return subprocess.CompletedProcess(process.args, process.returncode,
                                       stdout, stderr)


def _run_inkscape_script_cancellable(script, cancel_event: threading.Event):
    """Runs one ``inkscape --shell`` batch and keeps it cancellable.

    Progress output is discarded (the engine already reports it); stderr is
    captured through a temporary file to avoid pipe deadlocks while the
    script is fed to the process.
    """
    if cancel_event.is_set():
        raise BuildCancelled("Build cancelled")
    executable = discover_inkscape()
    creationflags = 0
    if os.name == "nt":
        creationflags = (getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) |
                         getattr(subprocess, "CREATE_NO_WINDOW", 0))
    stderr = ""
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8",
                                errors="replace") as err:
        try:
            process = subprocess.Popen(
                [str(executable), "--shell"], stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL, stderr=err, text=True,
                encoding="utf-8", errors="replace",
                creationflags=creationflags)
        except OSError as exc:
            raise RuntimeError(f"Could not run Inkscape: {exc}") from exc

        global _ACTIVE_PROCESS
        with _PROCESS_LOCK:
            _ACTIVE_PROCESS = process
        try:
            try:
                process.stdin.write(script)
                process.stdin.close()
            except OSError:
                pass
            while process.poll() is None:
                if cancel_event.is_set():
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                    raise BuildCancelled("Build cancelled")
                time.sleep(0.10)
            err.seek(0)
            stderr = err.read()
        finally:
            with _PROCESS_LOCK:
                if _ACTIVE_PROCESS is process:
                    _ACTIVE_PROCESS = None
    if cancel_event.is_set():
        raise BuildCancelled("Build cancelled")
    if process.returncode != 0:
        raise RuntimeError("Inkscape shell failed [rc=%d]: %s" % (
            process.returncode, (stderr or "")[-400:]))
    return subprocess.CompletedProcess(process.args, process.returncode,
                                       "", stderr)


def cancel_active_process() -> None:
    with _PROCESS_LOCK:
        process = _ACTIVE_PROCESS
    if process is not None and process.poll() is None:
        try:
            process.terminate()
        except OSError:
            pass


def build_games(games, force: bool, rom_dir: Path, artwork_dir: Path,
                output_dir: Path, cancel_event: threading.Event | None = None,
                progress=None) -> None:
    engine.ensure_dependencies()
    cancel_event = cancel_event or threading.Event()
    rom_dir = Path(rom_dir)
    artwork_dir = Path(artwork_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    DEFAULT_BUILD_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULT_PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

    rows = {row[0]: row for row in available_games(rom_dir, artwork_dir)}
    problems = []
    for game in games:
        row = rows.get(game)
        if row is None:
            problems.append(f"{game}: unknown game")
        elif not row[2]:
            problems.append(f"{game}: {row[4] or 'ROM ZIP invalid'}")
        elif not row[3]:
            problems.append(f"{game}: artwork ZIP missing")
    if problems:
        raise RuntimeError("Incomplete inputs: " + "; ".join(problems))

    executable = discover_inkscape()
    os.environ["INKSCAPE"] = str(executable)
    _configure_engine(rom_dir, artwork_dir, output_dir)
    original_run_inkscape = engine.run_inkscape
    original_run_inkscape_script = engine.run_inkscape_script
    engine.run_inkscape = lambda args: _run_inkscape_cancellable(args, cancel_event)
    engine.run_inkscape_script = (
        lambda script: _run_inkscape_script_cancellable(script, cancel_event))
    try:
        total = len(games)
        for index, game in enumerate(games):
            if cancel_event.is_set():
                raise BuildCancelled("Build cancelled")
            if progress:
                progress(index, total, game)
            engine.build_gw(game, force, index, total)
        if progress:
            progress(total, total, None)
    finally:
        engine.run_inkscape = original_run_inkscape
        engine.run_inkscape_script = original_run_inkscape_script


def _parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--gui", action="store_true", help="Open the graphical interface")
    mode.add_argument("--cli", action="store_true",
                      help="Use command-line mode (with no games, build all available games)")
    parser.add_argument("--version", action="store_true", help="Print the builder version")
    parser.add_argument("--force", action="store_true", help="Re-render selected segments")
    parser.add_argument("--only", action="append", default=[], metavar="GAME",
                        help="Select a game (may be repeated)")
    parser.add_argument("--rom-dir", type=Path, default=DEFAULT_ROM_DIR)
    parser.add_argument("--artwork-dir", type=Path, default=DEFAULT_ARTWORK_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("games", nargs="*", metavar="GAME")
    return parser, parser.parse_intermixed_args(argv)


def _run_cli(args, parser) -> int:
    if args.version:
        print(f"{APP_NAME} {APP_VERSION}")
        return 0
    targets = args.only + args.games
    unknown = sorted(set(targets) - engine.GAMES.keys())
    if unknown:
        parser.error("unknown game(s): %s (valid: %s)" %
                     (", ".join(unknown), ", ".join(sorted(engine.GAMES))))
    rows = {row[0]: row for row in available_games(args.rom_dir, args.artwork_dir)}
    if targets:
        problems = []
        for game in dict.fromkeys(targets):
            row = rows.get(game)
            if row is None:
                problems.append(f"{game}: unknown game")
            elif not row[2]:
                problems.append(f"{game}: {row[4] or 'ROM ZIP invalid'}")
            elif not row[3]:
                problems.append(f"{game}: artwork ZIP missing")
        if problems:
            parser.error("incomplete inputs: " + "; ".join(problems))
        games = list(dict.fromkeys(targets))
    else:
        games = [game for game, row in rows.items() if row[2] and row[3]]
    if not games:
        parser.error("no complete ROM/artwork pairs found in the selected "
                     "directories (MAME NONMERGED ZIPs required)")
    build_games(games, args.force, args.rom_dir, args.artwork_dir,
                args.output_dir)
    print("\nOK")
    return 0


def _windows_process_tree():
    """Return {pid: (parent_pid, executable)} using only the Windows API."""
    if os.name != "nt":
        return {}
    try:
        from ctypes import wintypes

        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD),
                ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t),
                ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", wintypes.LONG),
                ("dwFlags", wintypes.DWORD),
                ("szExeFile", wintypes.WCHAR * 260),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        create_snapshot = kernel32.CreateToolhelp32Snapshot
        create_snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
        create_snapshot.restype = wintypes.HANDLE
        process_first = kernel32.Process32FirstW
        process_first.argtypes = (wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W))
        process_first.restype = wintypes.BOOL
        process_next = kernel32.Process32NextW
        process_next.argtypes = (wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W))
        process_next.restype = wintypes.BOOL
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = (wintypes.HANDLE,)
        close_handle.restype = wintypes.BOOL

        snapshot = create_snapshot(0x00000002, 0)
        if snapshot == wintypes.HANDLE(-1).value:
            return {}
        try:
            entry = PROCESSENTRY32W()
            entry.dwSize = ctypes.sizeof(entry)
            tree = {}
            if process_first(snapshot, ctypes.byref(entry)):
                while True:
                    tree[int(entry.th32ProcessID)] = (
                        int(entry.th32ParentProcessID), entry.szExeFile)
                    if not process_next(snapshot, ctypes.byref(entry)):
                        break
            return tree
        finally:
            close_handle(snapshot)
    except (AttributeError, OSError):
        return {}


def _launched_from_explorer() -> bool:
    if os.name != "nt" or sys.argv[1:]:
        return False
    tree = _windows_process_tree()
    parent = tree.get(os.getpid(), (0, ""))[0]
    return Path(tree.get(parent, (0, ""))[1]).name.casefold() == "explorer.exe"


def _hide_console() -> None:
    if os.name != "nt":
        return
    try:
        window = ctypes.windll.kernel32.GetConsoleWindow()
        if window:
            ctypes.windll.user32.ShowWindow(window, 0)
    except (AttributeError, OSError):
        pass


def _ensure_console_streams() -> None:
    """Gives stdout/stderr a destination in the --windowed Windows build.

    PyInstaller leaves both as ``None`` in windowed mode, so the documented
    command-line mode crashed on its first ``print``. Reattach to the parent
    terminal when the EXE was started from one; otherwise use the null device
    so a GUI/double-click launch never crashes on progress output.
    """
    if sys.stdout is not None and sys.stderr is not None:
        return
    if os.name == "nt":
        try:
            if ctypes.windll.kernel32.AttachConsole(-1):
                sys.stdout = open("CONOUT$", "w", encoding="utf-8", buffering=1)
                sys.stderr = open("CONOUT$", "w", encoding="utf-8", buffering=1)
                return
        except (AttributeError, OSError):
            pass
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
    sys.stderr = open(os.devnull, "w", encoding="utf-8")


def _enable_high_dpi() -> None:
    if os.name != "nt":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


class _QueueWriter:
    def __init__(self, events):
        self.events = events

    def write(self, text):
        if text:
            self.events.put(("log", text))
        return len(text)

    def flush(self):
        pass


def _append_terminal_text(widget, text):
    """Append console output, treating carriage returns as line replacement."""
    for chunk in re.split(r"(\r\n|\r|\n)", text):
        if chunk == "\r":
            widget.delete("end-1c linestart", "end-1c")
        elif chunk in ("\r\n", "\n"):
            widget.insert("end", "\n")
        elif chunk:
            widget.insert("end", chunk)


class BuilderGUI:
    def __init__(self, root, initial_args):
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk

        self.tk = tk
        self.ttk = ttk
        self.filedialog = filedialog
        self.messagebox = messagebox
        self.root = root
        self.events = queue.Queue()
        self.cancel_event = threading.Event()
        self.worker = None
        self.game_vars = {}
        self.game_available = {}
        self.closing = False

        root.title(f"{APP_NAME} {APP_VERSION}")
        root.geometry("900x720")
        root.minsize(760, 580)
        try:
            root.iconphoto(True, tk.PhotoImage(file=str(RESOURCE_ROOT / "icon.gif")))
        except tk.TclError:
            pass
        root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.rom_var = tk.StringVar(value=str(initial_args.rom_dir))
        self.artwork_var = tk.StringVar(value=str(initial_args.artwork_dir))
        self.output_var = tk.StringVar(value=str(initial_args.output_dir))
        self.force_var = tk.BooleanVar(value=initial_args.force)
        self.status_var = tk.StringVar(value="Checking Inkscape...")
        self.current_var = tk.StringVar(value="Ready")

        outer = ttk.Frame(root, padding=12)
        outer.pack(fill="both", expand=True)
        paths = ttk.LabelFrame(outer, text="Folders", padding=8)
        paths.pack(fill="x")
        self._path_row(paths, 0, "ROM ZIPs", self.rom_var)
        self._path_row(paths, 1, "Artwork ZIPs", self.artwork_var)
        self._path_row(paths, 2, ".gnw output", self.output_var, output=True)

        status = ttk.Frame(outer)
        status.pack(fill="x", pady=(8, 4))
        ttk.Label(status, textvariable=self.status_var).pack(side="left")
        ttk.Button(status, text="Refresh", command=self.refresh).pack(side="right")

        games_box = ttk.LabelFrame(outer, text="Games", padding=0)
        games_box.pack(fill="both", expand=True, pady=4)
        games_body = tk.Frame(games_box, background="white",
                              borderwidth=0, highlightthickness=0)
        games_body.pack(fill="both", expand=True)
        canvas = tk.Canvas(games_body, highlightthickness=0, borderwidth=0,
                           background="white", yscrollincrement=16)
        scrollbar = ttk.Scrollbar(games_body, orient="vertical", command=canvas.yview)
        self.games_frame = tk.Frame(canvas, background="white", borderwidth=0)
        self.games_frame.bind("<Configure>",
                              lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        window = canvas.create_window((0, 0), window=self.games_frame, anchor="nw")
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, width=event.width))
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        controls = ttk.Frame(outer)
        controls.pack(fill="x", pady=4)
        ttk.Button(controls, text="Select all", command=lambda: self._select(True)).pack(side="left")
        ttk.Button(controls, text="None", command=lambda: self._select(False)).pack(side="left", padx=4)
        ttk.Checkbutton(controls, text="Force regeneration", variable=self.force_var).pack(side="left", padx=12)
        self.open_button = ttk.Button(controls, text="Open output", command=self._open_output)
        self.open_button.pack(side="right")
        self.cancel_button = ttk.Button(controls, text="Cancel", command=self.cancel, state="disabled")
        self.cancel_button.pack(side="right", padx=4)
        self.build_button = ttk.Button(controls, text="Generate", command=self.start)
        self.build_button.pack(side="right")

        ttk.Label(outer, textvariable=self.current_var).pack(anchor="w", pady=(4, 0))
        self.progress = ttk.Progressbar(outer, mode="determinate")
        self.progress.pack(fill="x", pady=(2, 6))
        self.log = tk.Text(outer, height=9, wrap="word", state="disabled")
        self.log.pack(fill="both", expand=False)

        self.refresh()
        root.after(100, self._drain_events)

    def _path_row(self, parent, row, label, variable, output=False):
        self.ttk.Label(parent, text=label, width=14).grid(row=row, column=0, sticky="w", pady=2)
        entry = self.ttk.Entry(parent, textvariable=variable)
        entry.grid(row=row, column=1, sticky="ew", padx=6, pady=2)
        entry.bind("<FocusOut>", lambda _event: self.refresh())
        self.ttk.Button(parent, text="Browse...",
                        command=lambda: self._browse(variable, output)).grid(row=row, column=2)
        parent.columnconfigure(1, weight=1)

    def _browse(self, variable, output):
        initial = Path(variable.get())
        if not initial.is_dir():
            initial = initial.parent
        selected = self.filedialog.askdirectory(
            title="Select output folder" if output else "Select input folder",
            initialdir=str(initial) if initial.is_dir() else str(WORKSPACE_ROOT),
            mustexist=not output)
        if selected:
            variable.set(os.path.normpath(selected))
            self.refresh()

    def refresh(self):
        previous = {game: var.get() for game, var in self.game_vars.items()}
        for child in self.games_frame.winfo_children():
            child.destroy()
        self.game_vars = {}
        self.game_available = {}
        rows = available_games(Path(self.rom_var.get()), Path(self.artwork_var.get()))
        for row, (game, title, has_rom, has_artwork, reason) in enumerate(rows):
            complete = has_rom and has_artwork
            variable = self.tk.BooleanVar(value=previous.get(game, complete))
            self.game_vars[game] = variable
            self.game_available[game] = complete
            rom_status = "OK" if has_rom else (reason or "invalid")
            text = (f"{title}    ROM {rom_status} | "
                    f"Artwork {'OK' if has_artwork else 'missing'}")
            check = self.tk.Checkbutton(
                self.games_frame, text=text, variable=variable,
                background="white", activebackground="white",
                selectcolor="white", highlightthickness=0,
                anchor="w", justify="left")
            if not complete:
                check.configure(state="disabled")
                variable.set(False)
            check.grid(row=row, column=0, sticky="w", padx=6, pady=2)
        try:
            executable = discover_inkscape()
            version = inkscape_version(executable)
            warning = "" if " 1.4.4 " in f" {version} " else " (unvalidated version)"
            self.status_var.set(f"{version}{warning} — {executable}")
            self.build_button.state(["!disabled"])
        except Exception as exc:
            self.status_var.set(str(exc))
            self.build_button.state(["disabled"])

    def _select(self, value):
        for game, variable in self.game_vars.items():
            try:
                variable.set(value and self.game_available.get(game, False))
            except self.tk.TclError:
                pass

    def _append_log(self, text):
        self.log.configure(state="normal")
        _append_terminal_text(self.log, text)
        self.log.see("end")
        self.log.configure(state="disabled")

    def start(self):
        selected = [game for game, variable in self.game_vars.items() if variable.get()]
        if not selected:
            self.messagebox.showwarning(APP_NAME, "Select at least one complete game.")
            return
        output = Path(self.output_var.get())
        rom_dir = Path(self.rom_var.get())
        artwork_dir = Path(self.artwork_var.get())
        force = self.force_var.get()
        try:
            output.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.messagebox.showerror(APP_NAME, f"Could not create the output folder:\n{exc}")
            return
        self.cancel_event.clear()
        self.progress.configure(maximum=len(selected), value=0)
        self.build_button.state(["disabled"])
        self.cancel_button.state(["!disabled"])
        self.current_var.set("Starting...")
        self._append_log("\n=== GNWBuilder started ===\n")

        def progress(index, total, game):
            self.events.put(("progress", index, total, game))

        def worker():
            writer = _QueueWriter(self.events)
            try:
                with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
                    build_games(selected, force, rom_dir, artwork_dir, output,
                                self.cancel_event, progress)
                self.events.put(("done", len(selected)))
            except BuildCancelled:
                self.events.put(("cancelled",))
            except Exception:
                self.events.put(("error", traceback.format_exc()))
            finally:
                writer.flush()

        self.worker = threading.Thread(target=worker, name="GNWBuilder worker", daemon=True)
        self.worker.start()

    def cancel(self):
        if self.worker and self.worker.is_alive():
            self.cancel_event.set()
            cancel_active_process()
            self.current_var.set("Cancelling...")
            self.cancel_button.state(["disabled"])

    def _drain_events(self):
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == "log":
                    self._append_log(event[1])
                elif event[0] == "progress":
                    _, index, total, game = event
                    self.progress.configure(maximum=total, value=index)
                    self.current_var.set("Complete" if game is None else
                                         f"Generating {game} ({index + 1}/{total})")
                elif event[0] == "done":
                    self._finish(f"Completed: {event[1]} game(s)")
                    self.messagebox.showinfo(APP_NAME, "Generation completed successfully.")
                elif event[0] == "cancelled":
                    self._finish("Cancelled")
                elif event[0] == "error":
                    self._append_log(event[1])
                    self._finish("Failed")
                    self.messagebox.showerror(APP_NAME, "Generation failed. See the log for details.")
        except queue.Empty:
            pass
        if self.closing and not (self.worker and self.worker.is_alive()):
            self.root.destroy()
            return
        self.root.after(100, self._drain_events)

    def _finish(self, status):
        self.current_var.set(status)
        self.build_button.state(["!disabled"])
        self.cancel_button.state(["disabled"])
        self.worker = None

    def _open_output(self):
        path = Path(self.output_var.get())
        path.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(path)

    def _on_close(self):
        if self.worker and self.worker.is_alive():
            if not self.messagebox.askyesno(APP_NAME, "A build is running. Cancel it and close?"):
                return
            self.closing = True
            self.cancel()
            return
        self.root.destroy()


def run_gui(args, hide_console=False) -> int:
    _enable_high_dpi()
    if hide_console:
        _hide_console()
    import tkinter as tk
    root = tk.Tk()
    BuilderGUI(root, args)
    root.mainloop()
    return 0


def main(argv=None) -> int:
    _ensure_console_streams()
    argv = list(sys.argv[1:] if argv is None else argv)
    parser, args = _parse_args(argv)
    from_explorer = not argv and _launched_from_explorer()
    # No arguments always means GUI. Explorer detection is retained only to
    # hide the console window; GUI startup must not depend on parent-process
    # inspection, which can vary between Windows shells and launchers.
    if args.gui or (not argv and not args.cli):
        return run_gui(args, hide_console=from_explorer)
    return _run_cli(args, parser)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        raise SystemExit(130)
    except SystemExit:
        raise
    except Exception:
        # The Windows build is a --windowed EXE: an unhandled exception would
        # otherwise exit silently. Keep the traceback for bug reports.
        log_path = Path(tempfile.gettempdir()) / "GNWBuilder-error.log"
        try:
            log_path.write_text(traceback.format_exc(), encoding="utf-8")
        except OSError:
            pass
        raise
