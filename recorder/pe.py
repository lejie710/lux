"""Read the headers of a PE/COFF image (the file format of UEFI programs).

The recorder needs three facts about the boot loader file:

* where its sections are (the parts that are loaded into memory),
* where its signature area is (the "certificate table" at the end of a
  signed file), and
* its Authenticode SHA-256, the digest that both the signature and the
  firmware's measurement are built on.

It also reads what the signature area is made of (`signature_parts`), so that
an experiment that changes one byte there can say which thing it changed:
the signature value itself, the digest that was signed, the signer's
certificate, or padding.

Only the 64-bit variant (PE32+) is supported, because that is what the
firmware in this project loads.

Method reference for the digest: Microsoft, "Windows Authenticode Portable
Executable Signature Format", section "Calculating the PE Image Hash".

The signature area holds one entry: an 8-byte header, then a signed-data
structure in the DER encoding (each item is a tag byte, a length and a
body), then padding to a multiple of 8 bytes. Only the nesting this project's
signing tool writes is understood; anything else raises `FormatError`.
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


# ---------------------------------------------------------------- the signature area

PART_HEADER = "entry header"
PART_IMAGE_DIGEST = "signed image digest"
PART_CERTIFICATE = "signer certificate"
PART_SIGNED_ATTRIBUTES = "signed attributes"
PART_SIGNATURE_VALUE = "signature value"
PART_PADDING = "padding"
PART_STRUCTURE = "structure"

_ENTRY_HEADER_SIZE = 8              # length (4), revision (2), type (2)
_ENTRY_TYPE_SIGNED_DATA = 2         # the only entry type a UEFI image signature uses
_DER_SEQUENCE = 0x30
_DER_SET = 0x31
_DER_INTEGER = 0x02
_DER_OCTET_STRING = 0x04
_DER_CONTEXT_0 = 0xA0               # the item written as [0], with other items inside


@dataclass(frozen=True)
class SignaturePart:
    """One named run of bytes inside the signature area."""

    name: str
    offset_in_area: int      # counted from the first byte of the signature area
    size: int

    def contains(self, offset_in_area: int) -> bool:
        """True when the offset lies inside this part."""
        return self.offset_in_area <= offset_in_area < self.offset_in_area + self.size


@dataclass(frozen=True)
class _Item:
    """One DER item: where its header starts, and where its body starts and ends."""

    tag: int
    start: int
    body: int
    end: int


def _der_items(data: bytes, start: int, end: int) -> list[_Item]:
    """The DER items that lie side by side between two file offsets."""
    items: list[_Item] = []
    position = start
    while position < end:
        if position + 2 > end:
            raise FormatError("the signature area ends inside an item header")
        tag, length = data[position], data[position + 1]
        body = position + 2
        if length & 0x80:                       # long form: the low bits count the length bytes
            count = length & 0x7F
            if count == 0 or count > 4 or body + count > end:
                raise FormatError("the signature area holds a length this reader does not understand")
            length = int.from_bytes(data[body:body + count], "big")
            body += count
        if body + length > end:
            raise FormatError("an item of the signature area runs past its container")
        items.append(_Item(tag, position, body, body + length))
        position = body + length
    return items


def _expect(items: list[_Item], index: int, tag: int, what: str) -> _Item:
    """The item at a position, which must carry the given tag."""
    if index >= len(items) or items[index].tag != tag:
        raise FormatError(f"the signature area has no {what} where one is expected")
    return items[index]


def _inside(data: bytes, item: _Item) -> list[_Item]:
    return _der_items(data, item.body, item.end)


def _named_items(data: bytes, start: int, end: int) -> list[tuple[str, int, int]]:
    """Find the four named parts inside the signed-data entry, as (name, start, end)."""
    outer = _expect(_der_items(data, start, end), 0, _DER_SEQUENCE, "outer sequence")
    wrapped = _expect(_inside(data, outer), 1, _DER_CONTEXT_0, "signed-data wrapper")
    signed_data = _inside(data, _expect(_inside(data, wrapped), 0, _DER_SEQUENCE, "signed-data sequence"))
    # Signed data: version, digest algorithms, the signed content, certificates, signers.
    content = _expect(signed_data, 2, _DER_SEQUENCE, "signed content")
    certificates = _expect(signed_data, 3, _DER_CONTEXT_0, "certificate list")
    signers = _expect(signed_data, len(signed_data) - 1, _DER_SET, "signer list")

    # Signed content: an identifier, then a wrapper around
    # { what was hashed, { algorithm, digest } }.
    content_body = _expect(_inside(data, content), 1, _DER_CONTEXT_0, "content wrapper")
    indirect = _inside(data, _expect(_inside(data, content_body), 0, _DER_SEQUENCE, "content sequence"))
    digest_record = _inside(data, _expect(indirect, 1, _DER_SEQUENCE, "digest record"))
    image_digest = _expect(digest_record, 1, _DER_OCTET_STRING, "image digest")

    certificate_items = _inside(data, certificates)
    if len(certificate_items) != 1:
        raise FormatError("the signature area does not hold exactly one certificate")
    certificate = _expect(certificate_items, 0, _DER_SEQUENCE, "certificate")

    signer_items = _inside(data, signers)
    if len(signer_items) != 1:
        raise FormatError("the signature area does not hold exactly one signer")
    # Signer: version, who signed, digest algorithm, signed attributes,
    # signature algorithm, signature value.
    signer = _inside(data, _expect(signer_items, 0, _DER_SEQUENCE, "signer record"))
    _expect(signer, 0, _DER_INTEGER, "signer version")
    attributes = _expect(signer, 3, _DER_CONTEXT_0, "signed attributes")
    value = _expect(signer, 5, _DER_OCTET_STRING, "signature value")
    return [
        (PART_IMAGE_DIGEST, image_digest.body, image_digest.end),
        (PART_CERTIFICATE, certificate.start, certificate.end),
        (PART_SIGNED_ATTRIBUTES, attributes.start, attributes.end),
        (PART_SIGNATURE_VALUE, value.body, value.end),
    ]


def signature_parts(data: bytes) -> tuple[SignaturePart, ...]:
    """The named parts of a signed image's signature area, in file order.

    The parts do not overlap and together cover the whole area. Bytes that
    only hold the structure together (tags, lengths, identifiers) are
    reported as `structure`. Raises `FormatError` for an unsigned image or
    an area that is not laid out the way the signing tool lays it out.

    What each named part is:

    * `entry header`: the 8 bytes saying how long the entry is and of which type;
    * `signed image digest`: the image's Authenticode digest as the signer wrote it down;
    * `signer certificate`: the certificate that carries the signer's public key;
    * `signed attributes`: the small record the signature is computed over
      (it holds a digest of the part that contains the image digest);
    * `signature value`: the number made with the signer's private key;
    * `padding`: filler bytes after the entry.
    """
    image = parse_pe(data)
    if not image.is_signed:
        raise FormatError("the image has no signature area")
    area, area_end = image.signature_offset, image.signature_offset + image.signature_size
    if area_end > len(data) or image.signature_size < _ENTRY_HEADER_SIZE:
        raise FormatError("the signature area does not fit in the file")
    entry_length, _, entry_type = struct.unpack_from("<IHH", data, area)
    entry_end = area + entry_length
    if entry_type != _ENTRY_TYPE_SIGNED_DATA or not _ENTRY_HEADER_SIZE < entry_length <= image.signature_size:
        raise FormatError("the signature area does not hold one signed-data entry")
    if area_end - entry_end >= 8:
        raise FormatError("the signature area holds more than one entry")

    parts = [SignaturePart(PART_HEADER, 0, _ENTRY_HEADER_SIZE)]
    position = area + _ENTRY_HEADER_SIZE
    for name, start, end in _named_items(data, position, entry_end):
        if start < position:
            raise FormatError("the parts of the signature area are not in the expected order")
        if start > position:
            parts.append(SignaturePart(PART_STRUCTURE, position - area, start - position))
        parts.append(SignaturePart(name, start - area, end - start))
        position = end
    if entry_end > position:
        parts.append(SignaturePart(PART_STRUCTURE, position - area, entry_end - position))
    if area_end > entry_end:
        parts.append(SignaturePart(PART_PADDING, entry_end - area, area_end - entry_end))
    return tuple(parts)


def signature_part_at(data: bytes, offset_in_area: int) -> SignaturePart:
    """The part of the signature area that holds a byte. Raises `FormatError` if none does."""
    for part in signature_parts(data):
        if part.contains(offset_in_area):
            return part
    raise FormatError("the offset lies outside the signature area")
