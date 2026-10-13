"""
Compile all .proto files in proto_definitions/dota2 into Python bindings.

Uses the protoc binary bundled with protoc-wheel-0 (installed via uv) so there
is no dependency on a system-level protoc installation.

Output layout:
    src/gem/proto/
        <name>_pb2.py          # generated message classes
        <name>_pb2.pyi         # type stubs (for IDE support)
        __init__.py

Usage:
    uv run python scripts/compile_protos.py
    uv run python scripts/compile_protos.py --force   # recompile even if up to date
    uv run python scripts/compile_protos.py --verbose # show each protoc invocation
"""

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# protoc emits sibling imports in three shapes that only resolve if the output
# dir is on sys.path. Since the generated modules live inside the `gem.proto`
# package, rewrite all three to package-relative imports:
#
#   1. flat:   `import netmessages_pb2 as netmessages__pb2`
#              -> `from . import netmessages_pb2 as netmessages__pb2`
#   2. dotted: `from steammessages_steamlearn import steamworkssdk_pb2 as ...`
#              (a dependency that lives in the subpackage steammessages_steamlearn/)
#              -> `from <dots>steammessages_steamlearn import steamworkssdk_pb2 as ...`
#   3. public: `from events_pb2 import *` or
#              `from events_pb2 import EEvent as EEvent`
#              -> `from .events_pb2 import ...`
#
# google.protobuf imports are left untouched (real installed package). The dotted
# rewrite's leading dots depend on the importing file's depth, so it is applied
# per file rather than via a single global substitution. Both rewrites anchor on
# the original (dot-less) form, so re-running on fixed files is a no-op.
_FLAT_IMPORT_RE = re.compile(r"^import (\w+_pb2) as (\w+)$", re.MULTILINE)
_DOTTED_IMPORT_RE = re.compile(r"^from (\w+) import (\w+_pb2) as (\w+)$", re.MULTILINE)
_PUBLIC_IMPORT_RE = re.compile(r"^from (\w+_pb2) import (.+)$", re.MULTILINE)

# Since SteamTracking/Protobufs b2f2f32a (2026-10-04) the protos use options that
# exist only in Valve's own copy of google/protobuf/descriptor.proto: FileOptions
# field 50 `additional_includes`, FieldOptions fields 20 `boxed_type` and 21
# `synthetic_default`. protoc's standard descriptor rejects them ("Option ...
# unknown"). They are C++ code-generation hints with no effect on the wire
# format, so the copies handed to protoc drop exactly these and keep every other
# option (`default`, `packed`, Valve's parenthesised extensions). Manta strips
# every field option instead, defaults included, which would change the values
# of absent fields; Valve's descriptor itself would clash with the protobuf
# runtime's. proto_definitions/ keeps the pristine upstream files.
_VALVE_FILE_OPTIONS = frozenset({"additional_includes"})
_VALVE_FIELD_OPTIONS = frozenset({"boxed_type", "synthetic_default"})
_FILE_OPTION_RE = re.compile(
    r"^[ \t]*option[ \t]+(\w+)[ \t]*=[^;\n]*;[ \t]*(?:\n|\Z)", re.MULTILINE
)
_FIELD_OPTIONS_RE = re.compile(r"[ \t]*\[([^\]\n]*)\]")
_OPTION_ENTRY_RE = re.compile(r'(?:[^,"]|"[^"]*")+')
_UNKNOWN_OPTION_RE = re.compile(r'Option "(\w+)" unknown')

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
PROTO_SRC_DIR = REPO_ROOT / "proto_definitions" / "dota2"
PROTO_OUT_DIR = REPO_ROOT / "src" / "gem" / "proto"


def find_protoc() -> Path:
    """Return the protoc binary from protoc-wheel-0 (preferred) or system PATH."""
    try:
        import protoc  # provided by protoc-wheel-0

        exe = Path(protoc.PROTOC_EXE)
        if exe.exists():
            return exe
    except ImportError:
        pass

    # Fall back to system protoc
    import shutil

    system_protoc = shutil.which("protoc")
    if system_protoc:
        print(
            "Warning: protoc-wheel-0 not found, falling back to system protoc.",
            file=sys.stderr,
        )
        return Path(system_protoc)

    print(
        "Error: protoc not found. Run `uv add protoc-wheel-0` or install protoc.",
        file=sys.stderr,
    )
    sys.exit(1)


def get_protoc_include(protoc_exe: Path) -> Path | None:
    """Return the bundled include dir if using protoc-wheel-0, else None."""
    try:
        import protoc

        include = Path(protoc.PROTOC_INCLUDE_DIR)
        return include if include.exists() else None
    except ImportError:
        return None


def is_up_to_date(proto_file: Path, out_dir: Path) -> bool:
    """Return True if the generated _pb2.py is newer than the .proto source."""
    pb2 = out_dir / (proto_file.stem + "_pb2.py")
    if not pb2.exists():
        return False
    return pb2.stat().st_mtime >= proto_file.stat().st_mtime


def strip_valve_options(text: str) -> tuple[str, int]:
    """Remove the options only Valve's ``descriptor.proto`` defines.

    Drops ``option additional_includes = "...";`` lines and the ``boxed_type`` /
    ``synthetic_default`` entries of field option lists, keeping every other
    entry; a list left empty is removed with its brackets.

    Args:
        text: The source of one ``.proto`` file.

    Returns:
        The cleaned source and the number of options removed.
    """
    removed = 0

    def drop_file_option(match: re.Match[str]) -> str:
        nonlocal removed
        if match.group(1) not in _VALVE_FILE_OPTIONS:
            return match.group(0)
        removed += 1
        return ""

    def drop_field_options(match: re.Match[str]) -> str:
        nonlocal removed
        entries = [entry.strip() for entry in _OPTION_ENTRY_RE.findall(match.group(1))]
        kept = [e for e in entries if e.split("=", 1)[0].strip() not in _VALVE_FIELD_OPTIONS]
        if len(kept) == len(entries):
            return match.group(0)
        removed += len(entries) - len(kept)
        return f" [{', '.join(kept)}]" if kept else ""

    text = _FILE_OPTION_RE.sub(drop_file_option, text)
    text = _FIELD_OPTIONS_RE.sub(drop_field_options, text)
    return text, removed


def write_compile_sources(proto_files: list[Path], dest_dir: Path) -> int:
    """Write the copies protoc compiles: each proto with Valve-only options removed.

    Args:
        proto_files: The upstream ``.proto`` files.
        dest_dir: An empty directory; each file keeps its name, so the generated
            descriptors are the same as compiling from ``proto_definitions/``.

    Returns:
        The number of options removed across all files.
    """
    removed = 0
    for proto_file in proto_files:
        text, count = strip_valve_options(proto_file.read_text())
        (dest_dir / proto_file.name).write_text(text)
        removed += count
    return removed


def ensure_init_files(out_dir: Path) -> None:
    """Create __init__.py in the output dir and its parent so it's importable."""
    for directory in (out_dir.parent, out_dir):
        init = directory / "__init__.py"
        if not init.exists():
            init.touch()
            print(f"  Created {init.relative_to(REPO_ROOT)}")


def compile_proto(
    proto_file: Path,
    proto_src_dir: Path,
    out_dir: Path,
    protoc_exe: Path,
    protoc_include: Path | None,
    verbose: bool,
) -> bool:
    """Compile a single .proto file. Returns True on success."""
    cmd = [
        str(protoc_exe),
        f"--proto_path={proto_src_dir}",
        f"--python_out={out_dir}",
        f"--pyi_out={out_dir}",
    ]
    if protoc_include:
        cmd.append(f"--proto_path={protoc_include}")
    cmd.append(str(proto_file))

    if verbose:
        print("  $", " ".join(cmd))

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  FAILED: {proto_file.name}", file=sys.stderr)
        print(result.stderr.strip(), file=sys.stderr)
        unknown = sorted(set(_UNKNOWN_OPTION_RE.findall(result.stderr)))
        if unknown:
            print(
                f"  Hint: option(s) {', '.join(unknown)} are not in protoc's descriptor.proto. "
                "If Valve's dota2/google/protobuf/descriptor.proto defines them, add them "
                "to _VALVE_FILE_OPTIONS / _VALVE_FIELD_OPTIONS in this script.",
                file=sys.stderr,
            )
        return False
    return True


def fix_relative_imports(out_dir: Path) -> int:
    """Rewrite sibling/subpackage ``_pb2`` imports to package-relative imports.

    protoc generates three cross-file import shapes that only resolve when
    ``out_dir`` is on ``sys.path``. All are rewritten to package-relative form
    so the generated modules import correctly as part of ``gem.proto``:

    - flat: ``import foo_pb2 as foo__pb2`` -> ``from . import foo_pb2 as ...``
    - dotted: ``from subpkg import bar_pb2 as ...`` (a dependency under the
      ``subpkg/`` subpackage) -> ``from <dots>subpkg import bar_pb2 as ...``
    - public: ``from foo_pb2 import *`` or a named import such as
      ``from foo_pb2 import Bar as Bar`` -> ``from <dots>foo_pb2 import ...``

    The leading-dot count for the dotted form depends on how deep the importing
    file sits below ``out_dir``: a top-level module needs one dot, a module one
    subpackage deep needs two. ``google.protobuf`` imports are not matched.
    Idempotent — files already in relative form are left unchanged.

    Args:
        out_dir: Root directory of the generated ``gem.proto`` package.

    Returns:
        The number of files that were modified.
    """
    fixed = 0
    generated_modules = list(out_dir.rglob("*_pb2.py")) + list(out_dir.rglob("*_pb2.pyi"))
    for generated_module in generated_modules:
        text = generated_module.read_text()
        new_text = _FLAT_IMPORT_RE.sub(r"from . import \1 as \2", text)

        # Depth below out_dir: top-level file -> 1 leading dot; one subpackage
        # deep -> 2 leading dots (up to out_dir, then into the sibling subpkg).
        depth = len(generated_module.relative_to(out_dir).parts) - 1
        dots = "." * (depth + 1)
        new_text = _DOTTED_IMPORT_RE.sub(rf"from {dots}\1 import \2 as \3", new_text)
        new_text = _PUBLIC_IMPORT_RE.sub(rf"from {dots}\1 import \2", new_text)

        if new_text != text:
            generated_module.write_text(new_text)
            fixed += 1
    return fixed


def ensure_subpackage_init_files(out_dir: Path) -> int:
    """Create ``__init__.py`` in every subdirectory that holds generated modules.

    protoc writes dependencies whose ``.proto`` name contains a directory part
    (e.g. ``steammessages_steamlearn.steamworkssdk.proto``) into a subdirectory.
    Those subdirectories need an ``__init__.py`` to be importable as packages so
    that package-relative imports like ``from .steammessages_steamlearn import``
    resolve.

    Args:
        out_dir: Root directory of the generated ``gem.proto`` package.

    Returns:
        The number of ``__init__.py`` files created.
    """
    created = 0
    for pb2 in out_dir.rglob("*_pb2.py"):
        pkg_dir = pb2.parent
        if pkg_dir == out_dir:
            continue
        init = pkg_dir / "__init__.py"
        if not init.exists():
            init.touch()
            created += 1
    return created


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile Dota 2 .proto files to Python.")
    parser.add_argument("--force", action="store_true", help="Recompile even if up to date.")
    parser.add_argument("--verbose", action="store_true", help="Print each protoc invocation.")
    args = parser.parse_args()

    if not PROTO_SRC_DIR.exists():
        print(
            f"Error: proto source directory not found: {PROTO_SRC_DIR}\n"
            "Run `bash scripts/download_protos.sh` first.",
            file=sys.stderr,
        )
        sys.exit(1)

    proto_files = sorted(PROTO_SRC_DIR.glob("*.proto"))
    if not proto_files:
        print(f"Error: no .proto files found in {PROTO_SRC_DIR}", file=sys.stderr)
        sys.exit(1)

    PROTO_OUT_DIR.mkdir(parents=True, exist_ok=True)
    ensure_init_files(PROTO_OUT_DIR)

    protoc_exe = find_protoc()
    protoc_include = get_protoc_include(protoc_exe)
    print(f"Using protoc: {protoc_exe}")
    print(f"Source:       {PROTO_SRC_DIR}  ({len(proto_files)} files)")
    print(f"Output:       {PROTO_OUT_DIR}")
    print()

    compiled = 0
    skipped = 0
    failed = 0

    with tempfile.TemporaryDirectory(prefix="gem-protos-") as tmp:
        compile_dir = Path(tmp)
        removed = write_compile_sources(proto_files, compile_dir)
        if removed:
            print(f"Removed {removed} Valve-only option(s) from the copies protoc compiles.")
            print()

        for proto_file in proto_files:
            if not args.force and is_up_to_date(proto_file, PROTO_OUT_DIR):
                if args.verbose:
                    print(f"  {proto_file.name} ... up to date")
                skipped += 1
                continue

            print(f"  {proto_file.name} ... ", end="", flush=True)
            if compile_proto(
                compile_dir / proto_file.name,
                compile_dir,
                PROTO_OUT_DIR,
                protoc_exe,
                protoc_include,
                args.verbose,
            ):
                print("ok")
                compiled += 1
            else:
                failed += 1

    print()
    print(f"Compiled: {compiled}  Skipped: {skipped}  Failed: {failed}")

    if failed:
        sys.exit(1)

    # protoc writes subpackage dependencies into subdirectories; give them an
    # __init__.py so they import as packages.
    inits = ensure_subpackage_init_files(PROTO_OUT_DIR)
    if inits:
        print(f"Created {inits} subpackage __init__.py file(s).")

    # protoc emits sibling/subpackage imports that break inside a package; rewrite
    # them to package-relative form so `from gem.proto import ...` works.
    fixed = fix_relative_imports(PROTO_OUT_DIR)
    if fixed:
        print(f"Patched relative imports in {fixed} file(s).")

    print()
    print("Next step:")
    print("  uv run python -c \"from gem.proto import demo_pb2; print('OK')\"")


if __name__ == "__main__":
    main()
