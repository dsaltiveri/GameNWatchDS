# Tests and validation

Run the default host suites from the project root:

```sh
python tests/run_all_tests.py
# or, in the build environment:
make test
```

A host GCC is required for native harnesses. Generated outputs belong under
`build/`; transient harnesses may use the operating system temporary directory.

Use `python tests/run_all_tests.py --list` to list the default suites.

The default suite runs ROM-free catalog and renderer/audio regressions plus
[GNWBuilder unit tests](../GNWBuilder/tests/). Core and launcher acceptance
against local game packages remain explicit commands.

## Available runners

- `check_mame_inputs.py`
- `run_catalog_io_tests.py`
- `run_core_tests.py`
- `run_headless_tests.py`
- `run_launcher_tests.py`
- `run_regression_tests.py`

Emulator and hardware checks are separate from host validation. See the
[project README](../README.md), [build guide](../docs/BUILDING.md) and
[repository layout](../docs/PROJECT_LAYOUT.md) for requirements and locations.
