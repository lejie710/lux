"""The guest boot loader: build it, and make the changed copies experiments need.

The loader is a short assembly program (`guest/loader.s`) that stands in for
an operating system loader. Its unsigned build is byte-identical on every
machine with the same assembler and linker. Signing is not repeatable, so
the signed file is a fixed, committed artifact (see `keys`).

Changed copies differ from the signed loader in exactly one byte, and each
function proves from the file's own headers where that byte lies before it
returns anything.

A **second loader** exists for the boot order experiment in its "different"
form, where the two boot entries must lead to two different programs. It is
the same source with the letter A of the start message changed to B, signed
once with the same committed key, and committed as `guest/second-loader-signed.efi`.
Like the first signed loader it is a fixed artifact, pinned by hash here.
`verify_second_loader` proves what it is from the first loader: same
content except that one letter, and a signature area of its own.
"""
import hashlib
from dataclasses import dataclass
from pathlib import Path

from recorder import pe
from recorder.errors import FormatError, StagingRefused
from recorder.provenance import RunCommand

# The loader's first console line, stored as UTF-16. Its last letter is the
# byte the content-change experiments alter.
START_MESSAGE = "LUX-LOADER A"
CHANGED_LETTER = "B"

SECOND_LOADER_PATH = Path(__file__).parent / "guest" / "second-loader-signed.efi"
SECOND_LOADER_SHA256 = "948c330302d28389dfdc584a694fa19a9527cbd0fe8d3050785be02c14b1b06f"


@dataclass(frozen=True)
class ByteChange:
    """Where one byte was changed, and proof of which area it belongs to."""

    file_offset: int
    old_value: int
    new_value: int
    area: str            # for example "section .data" or "signature area"

    def as_document(self) -> dict[str, object]:
        """The change in the shape the recording stores."""
        return {"file_offset": self.file_offset, "old_value": self.old_value,
                "new_value": self.new_value, "area": self.area}


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
    try:
        part = pe.signature_part_at(signed_loader, offset_in_area)
    except FormatError as error:
        raise StagingRefused(f"the signature area cannot be read: {error}") from error
    changed = bytearray(signed_loader)
    changed[offset] ^= 0x01
    change = ByteChange(offset, signed_loader[offset], changed[offset],
                        f"signature area, {part.name}")
    return bytes(changed), change


def verify_second_loader(second_loader: bytes, signed_loader: bytes) -> None:
    """Check that the second loader is what it is said to be. Raises `StagingRefused`.

    Three facts are required: the file has the pinned hash; it carries a
    signature area; and its Authenticode digest equals that of the first
    loader with the one letter of its start message changed. The last fact
    means the two programs differ in that letter and in nothing else that
    the firmware measures.
    """
    if hashlib.sha256(second_loader).hexdigest() != SECOND_LOADER_SHA256:
        raise StagingRefused("the second loader differs from the committed, pinned file")
    if not pe.parse_pe(second_loader).is_signed:
        raise StagingRefused("the second loader has no signature area")
    one_letter_changed, _ = change_content_byte(signed_loader)
    if pe.authenticode_sha256(second_loader) != pe.authenticode_sha256(one_letter_changed):
        raise StagingRefused("the second loader is not the first loader with one letter changed")
