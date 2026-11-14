"""Read the headers of a PE/COFF image (the file format of UEFI programs).

The recorder needs three facts about the boot loader file:

* where its sections are (the parts that are loaded into memory),
* where its signature area is (the "certificate table" at the end of a
  signed file), and
* its Authenticode SHA-256, the digest that both the signature and the
  firmware's measurement are built on.

Only the 64-bit variant (PE32+) is supported, because that is what the
firmware in this project loads.

Method reference for the digest: Microsoft, "Windows Authenticode Portable
Executable Signature Format", section "Calculating the PE Image Hash".
"""
import hashlib
import struct
from dataclasses import dataclass

from recorder.errors import FormatError

_PE32_PLUS_MAGIC = 0x20B
_CERTIFICATE_DIRECTORY_INDEX = 4
_SECTION_HEADER_SIZE = 40


@dataclass(frozen=True)
class Section:
    """One section of the image as it lies in the file."""

    name: str
    file_offset: int
    file_size: int

    def contains(self, offset: int) -> bool:
        """True when the file offset lies inside this section."""
        return self.file_offset <= offset < self.file_offset + self.file_size


@dataclass(frozen=True)
class PeImage:
    """The header facts the recorder uses. All offsets are file offsets."""

    file_size: int
    header_size: int
    checksum_offset: int
    certificate_entry_offset: int
    signature_offset: int
    signature_size: int
    sections: tuple[Section, ...]

    @property
    def is_signed(self) -> bool:
        """True when the file carries a signature area."""
        return self.signature_offset != 0 and self.signature_size != 0


def parse_pe(data: bytes) -> PeImage:
    """Read the headers of a PE32+ file. Raises `FormatError` if it is not one."""
    if len(data) < 0x40 or data[:2] != b"MZ":
        raise FormatError("not a PE file: the first two bytes are not 'MZ'")
    (pe_offset,) = struct.unpack_from("<I", data, 0x3C)
    if data[pe_offset:pe_offset + 4] != b"PE\0\0":
        raise FormatError("not a PE file: the 'PE' signature is missing")
    (section_count,) = struct.unpack_from("<H", data, pe_offset + 6)
    (optional_size,) = struct.unpack_from("<H", data, pe_offset + 20)
    optional = pe_offset + 24
    (magic,) = struct.unpack_from("<H", data, optional)
    if magic != _PE32_PLUS_MAGIC:
        raise FormatError("not a 64-bit (PE32+) image")
    (header_size,) = struct.unpack_from("<I", data, optional + 60)
    certificate_entry = optional + 112 + 8 * _CERTIFICATE_DIRECTORY_INDEX
    signature_offset, signature_size = struct.unpack_from("<II", data, certificate_entry)
    return PeImage(
        file_size=len(data),
        header_size=header_size,
        checksum_offset=optional + 64,
        certificate_entry_offset=certificate_entry,
        signature_offset=signature_offset,
        signature_size=signature_size,
        sections=_read_sections(data, optional + optional_size, section_count),
    )


def _read_sections(data: bytes, table_offset: int, count: int) -> tuple[Section, ...]:
    """Read the section table that follows the optional header."""
    sections = []
    for index in range(count):
        entry = table_offset + _SECTION_HEADER_SIZE * index
        name = data[entry:entry + 8].rstrip(b"\0").decode("ascii", errors="replace")
        file_size, file_offset = struct.unpack_from("<II", data, entry + 16)
        sections.append(Section(name, file_offset, file_size))
    return tuple(sections)


def section_at(image: PeImage, offset: int) -> Section | None:
    """The section that holds a file offset, or None."""
    for section in image.sections:
        if section.contains(offset):
            return section
    return None


def in_signature_area(image: PeImage, offset: int) -> bool:
    """True when the file offset lies inside the signature area."""
    if not image.is_signed:
        return False
    return image.signature_offset <= offset < image.signature_offset + image.signature_size


def authenticode_sha256(data: bytes) -> str:
    """The Authenticode SHA-256 of a PE32+ file, as lowercase hex.

    The digest covers the whole file except three areas, so that adding a
    signature does not change it:

    1. the checksum field of the optional header,
    2. the header entry that points at the signature area,
    3. the signature area itself.

    Sections are hashed in file order. Bytes that follow the last section
    and come before the signature area are hashed too.
    """
    image = parse_pe(data)
    digest = hashlib.sha256()
    digest.update(data[:image.checksum_offset])
    digest.update(data[image.checksum_offset + 4:image.certificate_entry_offset])
    digest.update(data[image.certificate_entry_offset + 8:image.header_size])

    position = image.header_size
    for section in sorted(image.sections, key=lambda s: s.file_offset):
        if section.file_size == 0:
            continue
        digest.update(data[section.file_offset:section.file_offset + section.file_size])
        position = max(position, section.file_offset + section.file_size)

    end = len(data) - image.signature_size if image.is_signed else len(data)
    if end > position:
        digest.update(data[position:end])
    return digest.hexdigest()
