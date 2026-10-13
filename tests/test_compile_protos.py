"""Tests for protobuf binding generation helpers."""

import importlib.util
import sys
from pathlib import Path

import pytest

from scripts.compile_protos import (
    compile_proto,
    find_protoc,
    fix_relative_imports,
    get_protoc_include,
    strip_valve_options,
    write_compile_sources,
)


def test_fix_relative_imports_rewrites_public_imports_at_each_depth(tmp_path: Path) -> None:
    """Public imports must resolve from generated modules inside ``gem.proto``."""
    top_level = tmp_path / "dota_shared_enums_pb2.py"
    top_level.write_text(
        "from events_pb2 import *\nfrom events_pb2 import EEvent as EEvent\n",
        encoding="utf-8",
    )

    subpackage = tmp_path / "nested"
    subpackage.mkdir()
    nested = subpackage / "consumer_pb2.pyi"
    nested.write_text(
        "from events_pb2 import *\nfrom events_pb2 import EEvent as EEvent\n",
        encoding="utf-8",
    )

    assert fix_relative_imports(tmp_path) == 2
    assert top_level.read_text(encoding="utf-8") == (
        "from .events_pb2 import *\nfrom .events_pb2 import EEvent as EEvent\n"
    )
    assert nested.read_text(encoding="utf-8") == (
        "from ..events_pb2 import *\nfrom ..events_pb2 import EEvent as EEvent\n"
    )

    assert fix_relative_imports(tmp_path) == 0


def test_shared_enums_reexports_moved_event_enum() -> None:
    """The upstream public import preserves the historical generated API path."""
    from gem.proto import dota_shared_enums_pb2, events_pb2

    assert dota_shared_enums_pb2.EEvent is events_pb2.EEvent
    assert (
        dota_shared_enums_pb2.EVENT_ID_INTERNATIONAL_2026 == events_pb2.EVENT_ID_INTERNATIONAL_2026
    )


# Since SteamTracking/Protobufs b2f2f32a the files use three options only Valve's
# descriptor.proto defines (HY-184). These are the shapes they take upstream.
@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ('option additional_includes = "entityhandle.h";\n', ""),
        (
            '\toptional uint32 a = 1 [boxed_type = "WorldGroupId_t"];\n',
            "\toptional uint32 a = 1;\n",
        ),
        (
            '\toptional uint32 a = 1 [default = 16777215, boxed_type = "CEHandleNetworkableInt", '
            'synthetic_default = "16777215"];\n',
            "\toptional uint32 a = 1 [default = 16777215];\n",
        ),
        (
            '\trepeated uint32 a = 1 [boxed_type = "X", (steamlearn_count) = 4];\n',
            "\trepeated uint32 a = 1 [(steamlearn_count) = 4];\n",
        ),
        (
            '\trepeated int32 a = 1 [packed = true, boxed_type = "X"];\n',
            "\trepeated int32 a = 1 [packed = true];\n",
        ),
        (
            '\toptional E a = 1 [default = K_None, boxed_type = "X", synthetic_default = "0", '
            "(key_field) = true];\n",
            "\toptional E a = 1 [default = K_None, (key_field) = true];\n",
        ),
    ],
)
def test_strip_valve_options_removes_only_valve_options(line: str, expected: str) -> None:
    text, removed = strip_valve_options(line)
    assert text == expected
    assert removed == line.count("boxed_type") + line.count("synthetic_default") + line.count(
        "additional_includes"
    )


def test_strip_valve_options_leaves_other_protos_unchanged() -> None:
    source = (
        'import "google/protobuf/descriptor.proto";\n'
        "option optimize_for = SPEED;\n"
        "option (msgpool_soft_limit) = 256;\n"
        "message M {\n"
        '\toptional string s = 1 [default = "a, [b]"];\n'
        "\toptional uint32 n = 2 [default = 7, deprecated = true];\n"
        "}\n"
    )
    assert strip_valve_options(source) == (source, 0)


def test_write_compile_sources_keeps_file_names(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.proto").write_text('option additional_includes = "x.h";\nmessage A {}\n')
    (src / "b.proto").write_text("message B {}\n")
    out = tmp_path / "out"
    out.mkdir()
    assert write_compile_sources(sorted(src.glob("*.proto")), out) == 1
    assert sorted(p.name for p in out.iterdir()) == ["a.proto", "b.proto"]
    assert (out / "a.proto").read_text() == "message A {}\n"


def test_protoc_compiles_the_stripped_copy(tmp_path: Path) -> None:
    """Upstream text fails as is; the stripped copy compiles and keeps its default."""
    pytest.importorskip("protoc")
    source = (
        'syntax = "proto2";\n'
        'option additional_includes = "entityhandle.h";\n'
        "message CMsgWithValveOptions {\n"
        '\toptional uint32 target = 1 [default = 16777215, boxed_type = "CEHandleNetworkableInt", '
        'synthetic_default = "16777215"];\n'
        "}\n"
    )
    raw = tmp_path / "raw"
    clean = tmp_path / "clean"
    out = tmp_path / "out"
    for directory in (raw, clean, out):
        directory.mkdir()
    (raw / "valve_options.proto").write_text(source)
    protoc_exe = find_protoc()
    include = get_protoc_include(protoc_exe)

    assert not compile_proto(raw / "valve_options.proto", raw, out, protoc_exe, include, False)

    write_compile_sources([raw / "valve_options.proto"], clean)
    assert compile_proto(clean / "valve_options.proto", clean, out, protoc_exe, include, False)

    spec = importlib.util.spec_from_file_location("valve_options_pb2", out / "valve_options_pb2.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
        assert module.CMsgWithValveOptions().target == 16777215
    finally:
        del sys.modules[spec.name]
