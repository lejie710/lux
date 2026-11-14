"""The guest boot loader: build it, and make the changed copies experiments need.

The loader is a short assembly program (`guest/loader.s`) that stands in for
an operating system loader. Its unsigned build is byte-identical on every
machine with the same assembler and linker. Signing is not repeatable, so
the signed file is a fixed, committed artifact (see `keys`).

Changed copies differ from the signed loader in exactly one byte, and each
function proves from the file's own headers where that byte lies before it
returns anything.
"""
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from recorder import pe
from recorder.errors import StagingRefused

# The loader's first console line, stored as UTF-16. Its last letter is the
# byte the content-change experiments alter.
START_MESSAGE = "LUX-LOADER A"
CHANGED_LETTER = "B"

# Runs a command and returns its output; raises `ToolMissing` if it fails.
RunCommand = Callable[[list[str]], str]


@dataclass(frozen=True)
class ByteChange:
    """Where one byte was changed, and proof of which area it belongs to."""

    file_offset: int
    old_value: int
    new_value: int
    area: str            # for example "section .data" or "signature area"


def build_commands(source: Path, build_directory: Path) -> list[list[str]]:
    """The assembler and linker command lines for the unsigned loader.

    `--no-insert-timestamp` keeps the build time out of the file, which is
    what makes the build repeatable. Subsystem 10 marks a UEFI application.
    """
    object_file = build_directory / "loader.o"
    return [
        ["as", "-o", str(object_file), str(source)],
        ["ld", "-m", "i386pep", "--subsystem", "10", "-e", "efi_main",
         "--no-insert-timestamp", "-o", str(build_directory / "loader.efi"), str(object_file)],
    ]


def build_loader(source: Path, build_directory: Path, run: RunCommand) -> Path:
    """Assemble and link the unsigned loader; return the path of the result."""
    build_directory.mkdir(parents=True, exist_ok=True)
    for command in build_commands(source, build_directory):
        run(command)
    return build_directory / "loader.efi"


def change_content_byte(signed_loader: bytes) -> tuple[bytes, ByteChange]:
    """A copy of the loader with one letter of its start message changed.

    Refused unless the byte lies inside a section of the image and outside
    the signature area, so the change is a change of the loader's content.
    """
    needle = START_MESSAGE.encode("utf-16le")
    if signed_loader.count(needle) != 1:
        raise StagingRefused("the loader's start message was not found exactly once")
    offset = signed_loader.index(needle) + len(needle) - 2
    image = pe.parse_pe(signed_loader)
    section = pe.section_at(image, offset)
    if section is None or not image.is_signed or pe.in_signature_area(image, offset):
        raise StagingRefused("the byte to change is not inside a section of a signed image")
    changed = bytearray(signed_loader)
    changed[offset] = ord(CHANGED_LETTER)
    change = ByteChange(offset, signed_loader[offset], changed[offset], f"section {section.name}")
    return bytes(changed), change


def change_signature_byte(signed_loader: bytes, offset_in_area: int) -> tuple[bytes, ByteChange]:
    """A copy of the loader with one bit flipped in one byte of its signature area.

    `offset_in_area` counts from the start of the signature area. Refused
    when the file has no signature area or the offset falls outside it.
    """
    image = pe.parse_pe(signed_loader)
    if not image.is_signed:
        raise StagingRefused("the loader has no signature area")
    offset = image.signature_offset + offset_in_area
    if offset_in_area < 0 or offset >= len(signed_loader) or not pe.in_signature_area(image, offset):
        raise StagingRefused("the byte to change is not inside the signature area")
    if pe.section_at(image, offset) is not None:
        raise StagingRefused("the signature area overlaps a section; the location is ambiguous")
    changed = bytearray(signed_loader)
    changed[offset] ^= 0x01
    change = ByteChange(offset, signed_loader[offset], changed[offset], "signature area")
    return bytes(changed), change
