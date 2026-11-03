# Building GameNWatchDS

Use BlocksDS and the Wonderful ARM toolchain. On Windows, run GNU Make in
an MSYS2 terminal. Run commands from the project root.

```sh
make -j2
make test
```

The normal console output is `GameNWatchDS.nds` in the project root.
Generated compilation and validation files stay under `build/`.
See the [technical reference](REFERENCE.md) for build options, asset requirements and packaging.

See the [repository conventions](PROJECT_LAYOUT.md) and [test index](../tests/README.md).
