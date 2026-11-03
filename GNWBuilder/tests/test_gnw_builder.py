"""Tests for the standalone GNWBuilder frontend."""

import contextlib
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gnw_builder as builder


class CatalogTests(unittest.TestCase):
    def test_default_folders_are_root_level(self):
        self.assertEqual(builder.DEFAULT_ROM_DIR, builder.WORKSPACE_ROOT / "roms")
        self.assertEqual(builder.DEFAULT_ARTWORK_DIR, builder.WORKSPACE_ROOT / "artwork")
        self.assertEqual(builder.DEFAULT_OUTPUT_DIR, builder.WORKSPACE_ROOT / "gnw")
        self.assertEqual(builder.DEFAULT_BUILD_DIR,
                         builder.WORKSPACE_ROOT / "build" / "gnw-builder" / "cache")
        self.assertEqual(builder.DEFAULT_PREVIEW_DIR,
                         builder.WORKSPACE_ROOT / "build" / "gnw-builder" / "preview")

    def test_bundled_titles_match_generator_filenames(self):
        for game in builder.engine.GAMES:
            with self.subTest(game=game):
                self.assertEqual(builder.output_filename(game),
                                 builder.engine.output_filename(game))

    def test_availability_requires_a_valid_nonmerged_set_and_artwork(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            roms = root / "roms"
            artwork = root / "artwork"
            roms.mkdir()
            artwork.mkdir()
            rom_name, artwork_name = builder._INPUT_NAMES["ball"]

            rows = {row[0]: row for row in builder.available_games(roms, artwork)}
            self.assertFalse(rows["ball"][2])
            self.assertIn("missing", rows["ball"][4].lower())

            # The file exists but is not a ZIP: it must not count as available.
            (roms / rom_name).write_bytes(b"not a zip")
            rows = {row[0]: row for row in builder.available_games(roms, artwork)}
            self.assertFalse(rows["ball"][2])
            self.assertIn("ZIP", rows["ball"][4])

            # A complete MAME NONMERGED set (program + SVG) is accepted.
            with zipfile.ZipFile(roms / rom_name, "w") as archive:
                archive.writestr("ac-01", b"\x00" * 4)
                archive.writestr("gnw_ball.svg", b"<svg/>")
            (artwork / artwork_name).write_bytes(b"art")
            rows = {row[0]: row for row in builder.available_games(roms, artwork)}
            self.assertEqual(rows["ball"][2:], (True, True, ""))


class ArgumentTests(unittest.TestCase):
    def test_folder_arguments_and_game_selection(self):
        parser, args = builder._parse_args([
            "--rom-dir", "R", "--artwork-dir", "A", "--output-dir", "O",
            "--force", "--only", "fire", "ball"])
        self.assertIsNotNone(parser)
        self.assertEqual(args.rom_dir, Path("R"))
        self.assertEqual(args.artwork_dir, Path("A"))
        self.assertEqual(args.output_dir, Path("O"))
        self.assertTrue(args.force)
        self.assertEqual(args.only, ["fire"])
        self.assertEqual(args.games, ["ball"])

    def test_bad_arguments_fail_before_any_build(self):
        for argv in (["--only"], ["--only="], ["fire", "does-not-exist"], ["--unknown"]):
            with self.subTest(argv=argv), contextlib.redirect_stderr(io.StringIO()) as stderr, \
                    patch.object(builder, "build_games") as build:
                with self.assertRaises(SystemExit) as error:
                    builder.main(argv)
                self.assertEqual(error.exception.code, 2)
                self.assertIn("error:", stderr.getvalue())
                build.assert_not_called()

    def test_incomplete_nonmerged_set_fails_before_building(self):
        rows = [("fire", "Fire", False, True,
                 "ROM set incomplete: missing fr-27")]
        with patch.object(builder, "available_games", return_value=rows), \
                patch.object(builder, "build_games") as build, \
                contextlib.redirect_stderr(io.StringIO()) as stderr:
            with self.assertRaises(SystemExit) as error:
                builder.main(["--only", "fire"])
        self.assertEqual(error.exception.code, 2)
        self.assertIn("incomplete", stderr.getvalue())
        self.assertIn("missing fr-27", stderr.getvalue())
        build.assert_not_called()

        rows = [("fire", "Fire", True, True, ""), ("ball", "Ball", True, True, "")]
        with patch.object(builder, "available_games", return_value=rows), \
                patch.object(builder, "build_games") as build, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(builder.main(
                ["--only=fire", "ball", "--force", "--only", "fire", "ball"]), 0)
        self.assertEqual(build.call_args.args[:2], (["fire", "ball"], True))

    def test_no_inputs_reports_selected_directories(self):
        with patch.object(builder, "available_games", return_value=[]), \
                patch.object(builder, "build_games") as build, \
                contextlib.redirect_stderr(io.StringIO()) as stderr:
            with self.assertRaises(SystemExit):
                builder.main(["--cli"])
        self.assertIn("no complete ROM/artwork pairs", stderr.getvalue())
        build.assert_not_called()

    def test_no_arguments_always_open_the_gui(self):
        with patch.object(builder, "_launched_from_explorer", return_value=False), \
                patch.object(builder, "run_gui", return_value=0) as run_gui:
            self.assertEqual(builder.main([]), 0)
        run_gui.assert_called_once()
        self.assertFalse(run_gui.call_args.kwargs["hide_console"])

    def test_explorer_launch_opens_gui_and_hides_console(self):
        with patch.object(builder, "_launched_from_explorer", return_value=True), \
                patch.object(builder, "run_gui", return_value=0) as run_gui:
            self.assertEqual(builder.main([]), 0)
        run_gui.assert_called_once()
        self.assertTrue(run_gui.call_args.kwargs["hide_console"])

    def test_cli_switch_builds_all_available_games(self):
        rows = [("fire", "Fire", True, True, ""), ("ball", "Ball", True, True, "")]
        with patch.object(builder, "available_games", return_value=rows), \
                patch.object(builder, "build_games") as build, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(builder.main(["--cli"]), 0)
        self.assertEqual(build.call_args.args[:2], (["fire", "ball"], False))

    def test_direct_explorer_parent_opens_gui(self):
        pid = os.getpid()
        tree = {pid: (10, "GNWBuilder.exe"), 10: (1, r"C:\Windows\explorer.exe")}
        with patch.object(builder.os, "name", "nt"), \
                patch.object(builder.sys, "argv", ["GNWBuilder.exe"]), \
                patch.object(builder, "_windows_process_tree", return_value=tree):
            self.assertTrue(builder._launched_from_explorer())

    def test_terminal_parent_stays_in_cli(self):
        pid = os.getpid()
        tree = {pid: (10, "GNWBuilder.exe"), 10: (1, "powershell.exe")}
        with patch.object(builder.os, "name", "nt"), \
                patch.object(builder.sys, "argv", ["GNWBuilder.exe"]), \
                patch.object(builder, "_windows_process_tree", return_value=tree):
            self.assertFalse(builder._launched_from_explorer())


class InkscapeTests(unittest.TestCase):
    def test_explicit_inkscape_override_wins(self):
        executable = r"C:\Tools\Inkscape\inkscape.com"
        with patch.dict(os.environ, {"INKSCAPE": executable}), \
                patch.object(builder.shutil, "which", return_value=executable):
            self.assertEqual(builder.discover_inkscape(), Path(executable))

    def test_invalid_override_is_actionable(self):
        with patch.dict(os.environ, {"INKSCAPE": r"C:\missing\inkscape.com"}), \
                patch.object(builder.shutil, "which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "INKSCAPE"):
                builder.discover_inkscape()

    def test_cancelled_build_does_not_launch_inkscape(self):
        event = builder.threading.Event()
        event.set()
        with patch.object(builder, "discover_inkscape") as discover:
            with self.assertRaises(builder.BuildCancelled):
                builder._run_inkscape_cancellable(["--version"], event)
        discover.assert_not_called()

    def test_cancelled_script_does_not_launch_inkscape(self):
        event = builder.threading.Event()
        event.set()
        with patch.object(builder, "discover_inkscape") as discover:
            with self.assertRaises(builder.BuildCancelled):
                builder._run_inkscape_script_cancellable("quit\n", event)
        discover.assert_not_called()


class LogOutputTests(unittest.TestCase):
    class FakeText:
        def __init__(self):
            self.content = ""

        def insert(self, index, text):
            self.assert_index(index, "end")
            self.content += text

        def delete(self, start, end):
            self.assert_index(start, "end-1c linestart")
            self.assert_index(end, "end-1c")
            line_start = self.content.rfind("\n") + 1
            self.content = self.content[:line_start]

        def assert_index(self, actual, expected):
            if actual != expected:
                raise AssertionError(f"expected index {expected!r}, got {actual!r}")

    def test_queue_writer_preserves_carriage_returns(self):
        events = builder.queue.Queue()
        writer = builder._QueueWriter(events)
        text = "\r  segments |=====-----| 50% 1.2.3"

        self.assertEqual(writer.write(text), len(text))
        writer.flush()

        self.assertEqual(events.get_nowait(), ("log", text))
        with self.assertRaises(builder.queue.Empty):
            events.get_nowait()

    def test_carriage_return_replaces_current_progress_line(self):
        widget = self.FakeText()

        builder._append_terminal_text(widget, "game header\n")
        builder._append_terminal_text(widget, "\rsegments 1%")
        builder._append_terminal_text(widget, "\rsegments 2%")
        builder._append_terminal_text(widget, "\rsegments 100%\nfinished\n")

        self.assertEqual(widget.content,
                         "game header\nsegments 100%\nfinished\n")


    def test_missing_streams_are_replaced(self):
        with patch.object(builder.sys, "stdout", None), \
                patch.object(builder.sys, "stderr", None), \
                patch.object(builder.os, "name", "posix"):
            builder._ensure_console_streams()
            self.assertIsNotNone(builder.sys.stdout)
            self.assertIsNotNone(builder.sys.stderr)
            builder.sys.stdout.close()
            builder.sys.stderr.close()


if __name__ == "__main__":
    unittest.main()
