# Repository layout

The Nintendo DS and DSi projects use the following repository conventions.
Run build and test commands from the project root.

| Path | Purpose |
| --- | --- |
| `README.md` | Project overview, installation and controls |
| `Makefile` | Main build entry point and `make test` |
| `Makefile.common` | Shared SDK and tool configuration |
| `Makefile.arm7`, `Makefile.arm9` | Processor-specific build rules |
| `arm7/source/`, `arm9/source/` | Maintained console code |
| `docs/README.md` | Documentation index |
| `docs/BUILDING.md` | Build entry points and requirements |
| `tests/README.md` | Host, emulator and hardware validation instructions |
| `tests/run_all_tests.py` | Default host validation entry point |
| `tests/fixtures/`, `tests/harness/`, `tests/stubs/` | Test data and native support, when needed |
| `tools/README.md` | Build, conversion, generation and analysis utilities |
| `experiments/README.md` | Historical research index or explicit statement that none is archived |
| `build/` | Generated objects, executables and test evidence; ignored by Git |
| `experiments/artifacts/` | Private research outputs; ignored by Git |

The root `.nds` is the documented emulator/player output. Additional packages
may be generated under `dist/`, which is ignored by Git. Source assets and
project-specific companion applications retain their own directories.

## Placement rules

Keep maintained test runners and their fixtures in `tests/`. Keep shared catalog,
conversion and build helpers in `tools/`; tests may reuse these helpers. Companion
applications can retain their own tests beside their sources, with the root test
index linking to them. The default host suite does not launch an emulator.

Keep current guides and production validation in `docs/`. Archive research in
`experiments/<topic>/` or `experiments/<category>/<study>/`, with a README,
provenance and an inventory where needed. Record historical Git revisions using
descriptive annotated tags. Preserve archived patches, numeric evidence and
inventoried source snapshots; do not rewrite them during routine reorganization.
Do not create empty study folders or tags for projects without archived research.

Legacy test paths under `tools/` forward to maintained implementations in `tests/`.
New commands and links should use `tests/`.

## Project-specific directories

GNWBuilder/ is a self-contained companion application, including its own unit tests. twilight/ supplies loader metadata. Local ROMs and generated game packages retain their documented locations.
