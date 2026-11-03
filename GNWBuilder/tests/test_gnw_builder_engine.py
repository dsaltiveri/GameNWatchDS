"""ROM-free generator regressions, with an optional real Inkscape smoke test."""
import contextlib
import io
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gnw_builder_engine as shrinker


def installed_inkscape():
    """Uses the generator's PATH, override and standard-Windows detection."""
    try:
        return shrinker.find_inkscape()
    except RuntimeError:
        return None


TEST_INKSCAPE = installed_inkscape()


class InkscapeTests(unittest.TestCase):
    def test_missing_python_dependency_is_actionable(self):
        missing = ModuleNotFoundError("No module named 'PIL'", name="PIL")
        with patch.object(shrinker, "_DEPENDENCY_IMPORT_ERROR", missing):
            with self.assertRaisesRegex(RuntimeError, "pip install Pillow numpy"):
                shrinker.ensure_dependencies()

    def test_explicit_executable_with_spaces(self):
        executable = "/custom tools/inkscape"
        with patch.dict(os.environ, {"INKSCAPE": executable}), \
                patch.object(shrinker.shutil, "which", return_value=executable) as which:
            self.assertEqual(shrinker.find_inkscape(), executable)
            which.assert_called_once_with(executable)

    def test_invalid_override_does_not_fall_back(self):
        with patch.dict(os.environ, {"INKSCAPE": "/missing/inkscape"}), \
                patch.object(shrinker.shutil, "which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "INKSCAPE"):
                shrinker.find_inkscape()

    def test_path_and_windows_fallback(self):
        for discovered, default_exists, expected in (
            (["/usr/bin/inkscape"], False, "/usr/bin/inkscape"),
            ([None, "C:/tools/inkscape.com"], False, "C:/tools/inkscape.com"),
            ([None, None], True, shrinker.INKSCAPE_WINDOWS),
        ):
            with self.subTest(expected=expected), \
                    patch.dict(os.environ, {"INKSCAPE": ""}), \
                    patch.object(shrinker.shutil, "which", side_effect=discovered), \
                    patch.object(shrinker.os.path, "isfile", return_value=default_exists):
                self.assertEqual(shrinker.find_inkscape(), expected)

    def test_missing_executable_is_actionable(self):
        with patch.dict(os.environ, {"INKSCAPE": ""}), \
                patch.object(shrinker.shutil, "which", return_value=None), \
                patch.object(shrinker.os.path, "isfile", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "PATH or set INKSCAPE"):
                shrinker.find_inkscape()

    def test_query_errors_and_launch_errors(self):
        with patch.object(shrinker, "find_inkscape", return_value="/tools/inkscape"):
            failed = subprocess.CompletedProcess([], 1, "partial output", "query failed")
            with patch.object(shrinker.subprocess, "run", return_value=failed):
                with self.assertRaisesRegex(RuntimeError, "query failed"):
                    shrinker.run_inkscape(["--query-all", "segments.svg"])
            with patch.object(shrinker.subprocess, "run", side_effect=OSError("unavailable")):
                with self.assertRaisesRegex(RuntimeError, "Could not run Inkscape"):
                    shrinker.run_inkscape(["--query-all", "segments.svg"])
            success = subprocess.CompletedProcess([], 0, "a,0,0,1,1", "")
            with patch.object(shrinker.subprocess, "run", return_value=success) as run:
                self.assertIs(shrinker.run_inkscape(["--query-all", "segments.svg"]), success)
                self.assertEqual(run.call_args.args[0],
                                 ["/tools/inkscape", "--query-all", "segments.svg"])
                self.assertEqual(run.call_args.kwargs["encoding"], "utf-8")
                self.assertEqual(run.call_args.kwargs["errors"], "replace")


class SegmentTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.svg = self.root / "source.svg"
        self.svg.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 4 3">'
            '<path id="a" d="M0 0h3v2h-3Z"><title>0.0.0</title></path></svg>')
        self.cache = self.root / "new" / "screen"
        self.query = "a,0,0,3,2\n"
        self.image = Image.new("RGB", (3, 2))
        self.image.putdata([(v, v, v) for v in (0, 64, 128, 192, 224, 255)])
        self.exports = []
        self.addCleanup(self.image.close)

    def fake_inkscape(self, args):
        if "-o" in args:
            destination = Path(args[args.index("-o") + 1])
            # Do not create directories here: exercise the production setup.
            self.assertTrue(destination.parent.is_dir())
            self.exports.append(destination)
            if destination.suffix == ".svg":
                shutil.copyfile(self.svg, destination)
            else:
                self.image.save(destination)
        return subprocess.CompletedProcess(args, 0, self.query, "")

    def fake_inkscape_script(self, script):
        for line in script.splitlines():
            if line.startswith("export-filename:"):
                self.fake_inkscape(["-o", line.split(":", 1)[1]])
        return subprocess.CompletedProcess([], 0, "", "")

    def render(self, inverted=False, force=False):
        with contextlib.redirect_stdout(io.StringIO()), \
                patch.object(shrinker, "run_inkscape", side_effect=self.fake_inkscape), \
                patch.object(shrinker, "run_inkscape_script",
                             side_effect=self.fake_inkscape_script):
            return shrinker.render_segments_shrinker(
                str(self.svg), str(self.cache), 4, 3, 4, 3, inverted, force)[0]

    def test_fresh_cache_and_repeat_build(self):
        self.assertFalse(self.cache.exists())
        first = self.render()
        self.assertEqual(first[0]["bbox"], (0, 0, 3, 2))
        self.assertEqual(first[0]["intensity"][0][:3], [0, 4, 8])
        exports = len(self.exports)
        self.assertEqual(self.render(), first)
        self.assertEqual(len(self.exports), exports)
        self.render(force=True)
        self.assertGreater(len(self.exports), exports)

    def test_lcd_mode_changes_reexport_cached_pngs(self):
        self.render()
        exports = len(self.exports)
        self.render(inverted=True)
        self.assertGreater(len(self.exports), exports)
        exports = len(self.exports)
        self.render(inverted=True)
        self.assertEqual(len(self.exports), exports)

    def test_missing_or_legacy_stamps_rebuild_cache(self):
        self.render()
        stamp = self.cache / "segments_iso.svg_md5"
        for old_stamp in (None, "old-svg-only-hash"):
            with self.subTest(stamp=old_stamp):
                if old_stamp is None:
                    stamp.unlink()
                else:
                    stamp.write_text(old_stamp)
                exports = len(self.exports)
                self.render()
                self.assertGreater(len(self.exports), exports)
        (self.cache / "segments_fix.svg.svg_md5").unlink()
        self.svg.write_text(self.svg.read_text().replace("h3", "h2"))
        self.render()
        self.assertEqual((self.cache / "segments_fix.svg").read_text(), self.svg.read_text())

    def test_incomplete_or_invalid_queries_reject_cached_segments(self):
        self.render()
        for query in ("", "other,0,0,3,2\n", "a,invalid,0,3,2\n", "a,nan,0,3,2\n"):
            with self.subTest(query=query):
                self.query = query
                with self.assertRaisesRegex(RuntimeError, "coordinates.*0.0.0"):
                    self.render()

    def test_missing_id_is_rejected(self):
        self.svg.write_text(self.svg.read_text().replace(' id="a"', ''))
        with self.assertRaisesRegex(RuntimeError, "no exportable id"):
            self.render()

    def test_crops_preserve_source_pixels_in_both_lcd_modes(self):
        for inverted in (False, True):
            for x, y, bbox, first in (
                (-1, 0, (0, 0, 2, 2), 4),
                (0, -1, (0, 0, 3, 1), 12),
                (-1, -1, (0, 0, 2, 1), 14),
                (-0.5, 0, (0, 0, 2, 2), 4),
                (0, -0.5, (0, 0, 3, 1), 12),
                (3, 2, (3, 2, 1, 1), 0),
                (1, 1, (1, 1, 3, 2), 0),
            ):
                with self.subTest(inverted=inverted, x=x, y=y):
                    self.query = f"a,{x},{y},3,2\n"
                    segment = self.render(inverted=inverted)[0]
                    self.assertEqual(segment["bbox"], bbox)
                    ox, oy, width, height = bbox
                    self.assertEqual(segment["intensity"][oy][ox], first)
                    for dy in range(height):
                        for dx in range(width):
                            value = self.image.getpixel((max(0, -math.floor(x)) + dx,
                                                         max(0, -math.floor(y)) + dy))[1] >> 4
                            self.assertEqual(segment["intensity"][oy + dy][ox + dx], value)
                            visible = value > 0 if inverted else value < 15
                            self.assertEqual(segment["mask"][oy + dy][ox + dx], visible)

    def test_fully_outside_segments_are_omitted(self):
        for x, y in ((-3, 0), (0, -2), (4, 0), (0, 3)):
            with self.subTest(x=x, y=y):
                self.query = f"a,{x},{y},3,2\n"
                self.assertEqual(self.render(), {})


class BackdropTests(unittest.TestCase):
    def test_dual_reflectors_use_the_lighter_plate_color(self):
        dark = Image.new("RGB", (4, 4), (112, 120, 128))
        light = Image.new("RGB", (4, 4), (176, 184, 192))
        self.addCleanup(dark.close)
        self.addCleanup(light.close)

        top, bottom = shrinker.flatten_dual_reflectors(dark, light)

        self.assertEqual(top.getpixel((0, 0)), (176, 184, 192))
        self.assertEqual(bottom.getpixel((0, 0)), (176, 184, 192))

    def test_dual_reflector_masks_preserve_each_screens_artwork(self):
        top = Image.new("RGB", (4, 4), (100, 110, 120))
        bottom = Image.new("RGB", (4, 4), (170, 180, 190))
        top.putpixel((0, 0), (255, 0, 0))
        bottom.putpixel((3, 3), (0, 0, 255))
        self.addCleanup(top.close)
        self.addCleanup(bottom.close)

        top, bottom = shrinker.flatten_dual_reflectors(top, bottom)

        self.assertEqual(top.getpixel((1, 1)), (170, 180, 190))
        self.assertEqual(bottom.getpixel((1, 1)), (170, 180, 190))
        self.assertEqual(top.getpixel((0, 0)), (255, 0, 0))
        self.assertEqual(bottom.getpixel((3, 3)), (0, 0, 255))


class RomSetValidationTests(unittest.TestCase):
    """NONMERGED=input validation: one self-contained ZIP per machine."""

    def make_zip(self, directory, entries, name="gnw_test.zip"):
        path = Path(directory) / name
        with zipfile.ZipFile(path, "w") as archive:
            for entry, data in entries.items():
                archive.writestr(entry, data)
        return str(path)

    def config(self, game, path):
        cfg = dict(shrinker.GAMES[game])
        cfg["rom_zip"] = path
        return cfg

    def test_valid_sm5a_set(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.make_zip(directory, {
                "ac-01": b"\x01" * 16, "gnw_ball.svg": b"<svg/>"})
            rom, melody, svgs = shrinker.read_rom_set(
                "ball", self.config("ball", path))
            self.assertEqual(rom, b"\x01" * 16)
            self.assertEqual(melody, b"")
            self.assertIn("gnw_ball.svg", svgs)
            self.assertIsNone(shrinker.rom_set_status(
                "ball", self.config("ball", path)))

    def test_invalid_zip_and_missing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            broken = Path(directory) / "gnw_test.zip"
            broken.write_bytes(b"not a zip")
            with self.assertRaises(shrinker.RomSetError) as error:
                shrinker.read_rom_set("ball", self.config("ball", str(broken)))
            self.assertEqual(error.exception.reason, "ROM ZIP is not a valid ZIP")
            missing = str(Path(directory) / "does-not-exist.zip")
            with self.assertRaises(shrinker.RomSetError) as error:
                shrinker.read_rom_set("ball", self.config("ball", missing))
            self.assertEqual(error.exception.reason, "ROM ZIP missing")

    def test_sm511_requires_its_melody(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.make_zip(directory, {
                "dr-802.program": b"\x01" * 16,
                "gnw_climber.svg": b"<svg/>"})
            with self.assertRaises(shrinker.RomSetError) as error:
                shrinker.read_rom_set("climber", self.config("climber", path))
            self.assertIn("dr-802.melody", error.exception.reason)

    def test_melody_must_be_256_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.make_zip(directory, {
                "dr-802.program": b"\x01" * 16,
                "dr-802.melody": b"\x00" * 10,
                "gnw_climber.svg": b"<svg/>"})
            with self.assertRaises(shrinker.RomSetError) as error:
                shrinker.read_rom_set("climber", self.config("climber", path))
            self.assertEqual(error.exception.reason, "melody missing or invalid")

    def test_merged_container_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.make_zip(directory, {
                "ac-01": b"\x01" * 16,
                "mc-25": b"\x02" * 16,
                "gnw_ball.svg": b"<svg/>"})
            with self.assertRaises(shrinker.RomSetError) as error:
                shrinker.read_rom_set("ball", self.config("ball", path))
            self.assertEqual(error.exception.reason, "ROM set is not NONMERGED")

    def test_program_size_and_missing_svg(self):
        with tempfile.TemporaryDirectory() as directory:
            huge = self.make_zip(directory, {
                "ac-01": b"\x00" * 4097, "gnw_ball.svg": b"<svg/>"})
            with self.assertRaises(shrinker.RomSetError) as error:
                shrinker.read_rom_set("ball", self.config("ball", huge))
            self.assertEqual(error.exception.reason, "invalid program size")
            no_svg = self.make_zip(directory, {"ac-01": b"\x00" * 16},
                                   name="gnw_no_svg.zip")
            with self.assertRaises(shrinker.RomSetError) as error:
                shrinker.read_rom_set("ball", self.config("ball", no_svg))
            self.assertIn("gnw_ball.svg", error.exception.reason)


@unittest.skipUnless(TEST_INKSCAPE, "Inkscape is not installed")
class RealInkscapeTests(unittest.TestCase):
    def test_mode_change_matches_a_forced_rebuild(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.dict(os.environ, {"INKSCAPE": TEST_INKSCAPE}), \
                contextlib.redirect_stdout(io.StringIO()):
            root = Path(directory)
            svg = root / "source.svg"
            svg.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="4" height="4" '
                'viewBox="0 0 4 4"><path id="a" d="M0 0H4L0 4Z" fill="#808080">'
                '<title>0.0.0</title></path></svg>')
            def render(inverted, force=False):
                return shrinker.render_segments_shrinker(
                    str(svg), str(root / "cache"), 4, 4, 4, 4, inverted, force)[0]
            render(False)
            cached = render(True)
            self.assertEqual(cached, render(True, True))
            self.assertEqual(cached[0]["intensity"][3][3], 0)
            (root / "cache/segments_fix.svg.svg_md5").unlink()
            svg.write_text(svg.read_text().replace("H4L0 4", "H2L0 2"))
            changed = render(True)
            self.assertEqual(changed[0]["bbox"], (0, 0, 2, 2))
            self.assertEqual(changed, render(True, True))

    def test_fractional_negative_export_is_cropped_at_the_lcd_edge(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.dict(os.environ, {"INKSCAPE": TEST_INKSCAPE}), \
                contextlib.redirect_stdout(io.StringIO()):
            root = Path(directory)
            svg = root / "source.svg"
            svg.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="4" height="3" '
                'viewBox="0 0 4 3"><path id="a" d="M-0.5 0h2v1h-2Z" fill="black">'
                '<title>0.0.0</title></path></svg>')
            segments, _ = shrinker.render_segments_shrinker(
                str(svg), str(root / "screen"), 4, 3, 4, 3, False, False)
            self.assertEqual(segments[0]["bbox"], (0, 0, 2, 1))
            self.assertEqual(segments[0]["intensity"][0][0], 0)
            self.assertGreater(segments[0]["intensity"][0][1], 0)
            self.assertLess(segments[0]["intensity"][0][1], 15)

    def test_shell_export_matches_individual_export(self):
        with tempfile.TemporaryDirectory() as directory, \
                contextlib.redirect_stdout(io.StringIO()):
            root = Path(directory) / "with space"
            root.mkdir()
            svg = root / "segments.svg"
            svg.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" '
                'viewBox="0 0 10 10">'
                '<rect id="a" x="1" y="1" width="3" height="2" fill="#000000">'
                '<title>0.0.1</title></rect>'
                '<rect id="b" x="5" y="4" width="4" height="3" fill="#000000">'
                '<title>0.0.2</title></rect></svg>')
            segments, titles = shrinker.find_segments(str(svg))
            shell_dir = root / "shell"
            shell_dir.mkdir()
            missing = shrinker.export_segments_shell(
                str(svg), str(shell_dir), titles, segments, "#FFFFFF")
            self.assertEqual(missing, [])

            reference_dir = root / "reference"
            reference_dir.mkdir()
            for title in titles:
                obj_id = shrinker._segment_obj_id(segments[title])
                shrinker.run_inkscape([
                    "-i", obj_id, "-j", "--export-area-snap",
                    "--export-background=#FFFFFF", "--export-type=png",
                    "-o", str(reference_dir / (title + ".png")), str(svg)])
            for title in titles:
                shell_img = Image.open(shell_dir / (title + ".png")).convert("RGBA")
                ref_img = Image.open(reference_dir / (title + ".png")).convert("RGBA")
                self.assertEqual(shell_img.size, ref_img.size)
                self.assertEqual(shell_img.tobytes(), ref_img.tobytes())

    def test_fresh_export_and_cached_geometry(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.dict(os.environ, {"INKSCAPE": TEST_INKSCAPE}), \
                contextlib.redirect_stdout(io.StringIO()):
            root = Path(directory)
            svg = root / "source.svg"
            svg.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="4" height="3" '
                'viewBox="0 0 4 3"><path id="a" d="M1 1h2v1h-2Z" fill="black">'
                '<title>0.0.0</title></path></svg>')
            cache = root / "new" / "screen"
            def render():
                return shrinker.render_segments_shrinker(
                    str(svg), str(cache), 4, 3, 4, 3, False, False)[0]
            first = render()
            self.assertEqual(first[0]["bbox"], (1, 1, 2, 1))
            self.assertEqual(first[0]["intensity"][1][1:3], [0, 0])
            self.assertEqual(render(), first)


if __name__ == "__main__":
    unittest.main()
