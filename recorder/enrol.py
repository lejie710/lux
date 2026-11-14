"""Build the small UEFI program that enrols the test keys.

Secure Boot keys are UEFI variables, and the firmware only accepts them
through its `SetVariable` service. So the keys are enrolled by booting a
tiny program once. For each variable it calls `SetVariable` with the bytes
of a signed update, prints ::

    LUX-SETVAR <name> status=<two hex digits>

(00 means success; the digits are the low byte of the status code), then
prints ``LUX-SETVAR done`` and powers the machine off.

No compiler is involved. The program is so small that its machine code is
written out here byte by byte, each line with the instruction it encodes,
and wrapped in a minimal PE32+ file (the executable format UEFI uses). The
output depends only on the input, so the same keys always give the same
program. Why this is Python and not a second assembly source, and what that
costs, is decision D5 in `docs/DESIGN.md`.

The file is put together in three steps, one function each: the code and
data are laid out (`_layout`), the headers are written for that layout
(`_headers`), and the pieces are joined (`build_enrol_program`).

Register use inside the program: `rsi` points at the data section, `rbx` at
the UEFI system table that the firmware passes in `rdx`.
"""
import struct
import uuid
from dataclasses import dataclass

DONE_LINE = "LUX-SETVAR done"

# ---- PE32+ constants. Names follow the Microsoft PE format description.
_FILE_ALIGNMENT = 0x200             # sections start on 512-byte boundaries in the file
_SECTION_ALIGNMENT = 0x1000         # and on 4096-byte boundaries in memory
_OPTIONAL_HEADER_SIZE = 240
_DOS_HEADER_SIZE = 0x40             # the PE signature follows directly
_MACHINE_X86_64 = 0x8664
_SECTION_COUNT = 3                  # .text, .data, .reloc
_FILE_IS_EXECUTABLE = 0x0002
_FILE_HANDLES_LARGE_ADDRESSES = 0x0020
_PE32_PLUS_MAGIC = 0x20B            # the 64-bit form of the optional header
_PREFERRED_IMAGE_BASE = 0x400000    # a hint only; the firmware loads the image where it likes
_SUBSYSTEM_EFI_APPLICATION = 10
_DLL_NX_COMPATIBLE = 0x0100         # the image does not run code from its data
_DIRECTORY_COUNT = 16
_DIRECTORY_BASE_RELOCATION = 5
_EMPTY_RELOCATION_BLOCK_SIZE = 12
# Section flags: what the section holds, and what may be done with it.
_SECTION_CODE = 0x00000020 | 0x20000000 | 0x40000000          # code, execute, read
_SECTION_DATA = 0x00000040 | 0x40000000 | 0x80000000          # data, read, write
_SECTION_RELOC = 0x00000040 | 0x02000000 | 0x40000000         # data, discardable, read


@dataclass(frozen=True)
class VariableWrite:
    """One `SetVariable` call the program makes."""

    name: str
    vendor_guid: str
    attributes: int
    payload: bytes


@dataclass(frozen=True)
class _Placed:
    """Offsets inside the data section of everything one call needs."""

    guid: int
    name: int
    message: int
    status_high_digit: int
    status_low_digit: int
    payload: int
    payload_size: int
    attributes: int


def _utf16(text: str) -> bytes:
    return text.encode("utf-16le")


def _align(value: int, boundary: int) -> int:
    return (value + boundary - 1) // boundary * boundary


def _rel32(value: int) -> bytes:
    return struct.pack("<i", value)


class _DataSection:
    """Collects the program's data; every item starts on an 8-byte boundary."""

    def __init__(self) -> None:
        self.bytes = bytearray()

    def put(self, item: bytes) -> int:
        """Append an item and return its offset."""
        while len(self.bytes) % 8:
            self.bytes.append(0)
        offset = len(self.bytes)
        self.bytes.extend(item)
        return offset


def _place_data(writes: list[VariableWrite]) -> tuple[_DataSection, int, list[_Placed], int]:
    """Lay out the data section: hex digits, per-variable items, the final line."""
    data = _DataSection()
    hex_digits = data.put(b"0123456789ABCDEF")
    placed: list[_Placed] = []
    for write in writes:
        guid = data.put(uuid.UUID(write.vendor_guid).bytes_le)
        name = data.put(_utf16(write.name + "\0"))
        text = f"LUX-SETVAR {write.name} status=??\r\n"
        message = data.put(_utf16(text + "\0"))
        high = message + 2 * text.index("?")
        payload = data.put(write.payload)
        placed.append(_Placed(guid, name, message, high, high + 2, payload,
                              len(write.payload), write.attributes))
    done = data.put(_utf16(DONE_LINE + "\r\n\0"))
    return data, hex_digits, placed, done


def _print_string(offset: int) -> bytes:
    """Machine code: print the UTF-16 string at data offset `offset`."""
    code = bytes([0x48, 0x8B, 0x4B, 0x40])                 # mov rcx, [rbx+0x40]   console output
    code += bytes([0x48, 0x8D, 0x96]) + _rel32(offset)     # lea rdx, [rsi+offset]
    code += bytes([0xFF, 0x51, 0x08])                      # call [rcx+8]          OutputString
    return code


def _set_variable(item: _Placed, hex_digits: int) -> bytes:
    """Machine code: one SetVariable call, then print its status line."""
    code = bytes([0x48, 0x8D, 0x8E]) + _rel32(item.name)              # lea rcx, [rsi+name]
    code += bytes([0x48, 0x8D, 0x96]) + _rel32(item.guid)             # lea rdx, [rsi+guid]
    code += bytes([0x41, 0xB8]) + struct.pack("<I", item.attributes)  # mov r8d, attributes
    code += bytes([0x41, 0xB9]) + struct.pack("<I", item.payload_size)  # mov r9d, size
    code += bytes([0x48, 0x8D, 0x86]) + _rel32(item.payload)          # lea rax, [rsi+payload]
    code += bytes([0x48, 0x89, 0x44, 0x24, 0x20])                     # mov [rsp+0x20], rax
    code += bytes([0x48, 0x8B, 0x43, 0x58])                           # mov rax, [rbx+0x58]  runtime services
    code += bytes([0xFF, 0x50, 0x58])                                 # call [rax+0x58]      SetVariable
    # Turn the low byte of the status into two hex digits inside the message.
    code += bytes([0x48, 0x89, 0xC2])                                 # mov rdx, rax
    code += bytes([0x48, 0xC1, 0xEA, 0x04])                           # shr rdx, 4
    code += bytes([0x83, 0xE2, 0x0F])                                 # and edx, 15
    code += bytes([0x8A, 0x94, 0x16]) + _rel32(hex_digits)            # mov dl, [rsi+rdx+digits]
    code += bytes([0x88, 0x96]) + _rel32(item.status_high_digit)      # mov [rsi+high], dl
    code += bytes([0x83, 0xE0, 0x0F])                                 # and eax, 15
    code += bytes([0x8A, 0x84, 0x06]) + _rel32(hex_digits)            # mov al, [rsi+rax+digits]
    code += bytes([0x88, 0x86]) + _rel32(item.status_low_digit)       # mov [rsi+low], al
    return code + _print_string(item.message)


def _power_off() -> bytes:
    """Machine code: ask the firmware to shut the machine down, then return."""
    code = bytes([0x48, 0x8B, 0x43, 0x58])     # mov rax, [rbx+0x58]   runtime services
    code += bytes([0xB9, 2, 0, 0, 0])          # mov ecx, 2            reset type: shutdown
    code += bytes([0x31, 0xD2])                # xor edx, edx
    code += bytes([0x45, 0x31, 0xC0])          # xor r8d, r8d
    code += bytes([0x45, 0x31, 0xC9])          # xor r9d, r9d
    code += bytes([0xFF, 0x50, 0x68])          # call [rax+0x68]       ResetSystem
    code += bytes([0x31, 0xC0])                # xor eax, eax
    code += bytes([0x48, 0x83, 0xC4, 0x30])    # add rsp, 0x30
    code += bytes([0x5F, 0x5E, 0x5B, 0xC3])    # pop rdi; pop rsi; pop rbx; ret
    return code


def _build_code(placed: list[_Placed], hex_digits: int, done: int) -> tuple[bytearray, int]:
    """The code section, and the position of the one address to fill in later."""
    code = bytearray()
    code += bytes([0x53, 0x56, 0x57])          # push rbx; push rsi; push rdi
    code += bytes([0x48, 0x83, 0xEC, 0x30])    # sub rsp, 0x30
    code += bytes([0x48, 0x89, 0xD3])          # mov rbx, rdx          system table
    code += bytes([0x48, 0x8D, 0x35])          # lea rsi, [rip+distance to data]
    fixup = len(code)
    code += bytes(4)
    for item in placed:
        code += _set_variable(item, hex_digits)
    code += _print_string(done)
    code += _power_off()
    return code, fixup


@dataclass(frozen=True)
class _Layout:
    """Where each of the three sections lies, in memory and in the file."""

    code: bytes
    data: bytes
    text_address: int       # addresses are relative to the start of the loaded image
    data_address: int
    reloc_address: int
    image_size: int
    text_raw: int           # "raw" sizes and offsets are positions in the file
    data_raw: int
    text_offset: int
    data_offset: int
    reloc_offset: int


def _layout(writes: list[VariableWrite]) -> _Layout:
    """Build code and data, decide where they go, and fill in the one address the code needs."""
    data, hex_digits, placed, done = _place_data(writes)
    code, fixup = _build_code(placed, hex_digits, done)

    text_address = _SECTION_ALIGNMENT
    data_address = text_address + _align(len(code), _SECTION_ALIGNMENT)
    reloc_address = data_address + _align(len(data.bytes), _SECTION_ALIGNMENT)
    # The code finds its data by distance from the instruction after the fixup.
    code[fixup:fixup + 4] = _rel32(data_address - (text_address + fixup + 4))

    text_raw = _align(len(code), _FILE_ALIGNMENT)
    data_raw = _align(len(data.bytes), _FILE_ALIGNMENT)
    text_offset = _FILE_ALIGNMENT
    data_offset = text_offset + text_raw
    return _Layout(
        code=bytes(code), data=bytes(data.bytes),
        text_address=text_address, data_address=data_address, reloc_address=reloc_address,
        image_size=reloc_address + _SECTION_ALIGNMENT,
        text_raw=text_raw, data_raw=data_raw,
        text_offset=text_offset, data_offset=data_offset, reloc_offset=data_offset + data_raw,
    )


def _optional_header(layout: _Layout) -> bytes:
    """The "optional" header: entry point, sizes, alignments and the directory table."""
    header = struct.pack("<HBBIIIII", _PE32_PLUS_MAGIC, 0, 0, layout.text_raw,
                         layout.data_raw + _FILE_ALIGNMENT, 0,
                         layout.text_address,      # entry point: the first byte of the code
                         layout.text_address)      # base of code
    header += struct.pack("<QII", _PREFERRED_IMAGE_BASE, _SECTION_ALIGNMENT, _FILE_ALIGNMENT)
    header += struct.pack("<HHHHHH", 0, 0, 0, 0, 0, 0)                 # version fields, unused
    header += struct.pack("<IIII", 0, layout.image_size, _FILE_ALIGNMENT, 0)   # headers fit one block
    header += struct.pack("<HH", _SUBSYSTEM_EFI_APPLICATION, _DLL_NX_COMPATIBLE)
    header += struct.pack("<QQQQ", 0, 0, 0, 0)                         # stack and heap sizes, unused
    header += struct.pack("<II", 0, _DIRECTORY_COUNT)
    directories = [(0, 0)] * _DIRECTORY_COUNT
    directories[_DIRECTORY_BASE_RELOCATION] = (layout.reloc_address, _EMPTY_RELOCATION_BLOCK_SIZE)
    for address, size in directories:
        header += struct.pack("<II", address, size)
    if len(header) != _OPTIONAL_HEADER_SIZE:
        raise AssertionError("optional header has the wrong size")
    return header


def _section_header(name: bytes, virtual_size: int, virtual_address: int,
                    raw_size: int, raw_offset: int, characteristics: int) -> bytes:
    return name.ljust(8, b"\0") + struct.pack(
        "<IIIIIIHHI", virtual_size, virtual_address, raw_size, raw_offset, 0, 0, 0, 0, characteristics)


def _section_table(layout: _Layout) -> bytes:
    """One 40-byte entry per section."""
    return (
        _section_header(b".text", len(layout.code), layout.text_address,
                        layout.text_raw, layout.text_offset, _SECTION_CODE)
        + _section_header(b".data", len(layout.data), layout.data_address,
                          layout.data_raw, layout.data_offset, _SECTION_DATA)
        + _section_header(b".reloc", _EMPTY_RELOCATION_BLOCK_SIZE, layout.reloc_address,
                          _FILE_ALIGNMENT, layout.reloc_offset, _SECTION_RELOC)
    )


def _headers(layout: _Layout) -> bytes:
    """Everything before the first section: DOS stub, PE signature, both headers, section table."""
    dos_header = bytearray(_DOS_HEADER_SIZE)
    dos_header[0:2] = b"MZ"
    struct.pack_into("<I", dos_header, 0x3C, _DOS_HEADER_SIZE)        # where the PE signature is
    coff_header = struct.pack("<HHIIIHH", _MACHINE_X86_64, _SECTION_COUNT, 0, 0, 0,
                              _OPTIONAL_HEADER_SIZE,
                              _FILE_IS_EXECUTABLE | _FILE_HANDLES_LARGE_ADDRESSES)
    return (bytes(dos_header) + b"PE\0\0" + coff_header
            + _optional_header(layout) + _section_table(layout))


def build_enrol_program(writes: list[VariableWrite]) -> bytes:
    """The complete PE32+ file of the enrolment program."""
    layout = _layout(writes)
    # An empty relocation block; the firmware expects the table to exist.
    relocations = struct.pack("<IIHH", 0, _EMPTY_RELOCATION_BLOCK_SIZE, 0, 0)
    return (
        _headers(layout).ljust(_FILE_ALIGNMENT, b"\0")
        + layout.code.ljust(layout.text_raw, b"\xCC")          # padding: breakpoint instructions
        + layout.data.ljust(layout.data_raw, b"\0")
        + relocations.ljust(_FILE_ALIGNMENT, b"\0")
    )
