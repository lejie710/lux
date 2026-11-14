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
and wrapped in a minimal PE32+ file. The output depends only on the input,
so the same keys always give the same program.

Register use inside the program: `rsi` points at the data section, `rbx` at
the UEFI system table that the firmware passes in `rdx`.
"""
import struct
import uuid
from dataclasses import dataclass

DONE_LINE = "LUX-SETVAR done"
_FILE_ALIGNMENT = 0x200
_SECTION_ALIGNMENT = 0x1000
_OPTIONAL_HEADER_SIZE = 240


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


def _section_header(name: bytes, virtual_size: int, virtual_address: int,
                    raw_size: int, raw_offset: int, characteristics: int) -> bytes:
    return name.ljust(8, b"\0") + struct.pack(
        "<IIIIIIHHI", virtual_size, virtual_address, raw_size, raw_offset, 0, 0, 0, 0, characteristics)


def build_enrol_program(writes: list[VariableWrite]) -> bytes:
    """The complete PE32+ file of the enrolment program."""
    data, hex_digits, placed, done = _place_data(writes)
    code, fixup = _build_code(placed, hex_digits, done)

    text_address = _SECTION_ALIGNMENT
    data_address = text_address + _align(len(code), _SECTION_ALIGNMENT)
    reloc_address = data_address + _align(len(data.bytes), _SECTION_ALIGNMENT)
    image_size = reloc_address + _SECTION_ALIGNMENT
    code[fixup:fixup + 4] = _rel32(data_address - (text_address + fixup + 4))

    text_raw = _align(len(code), _FILE_ALIGNMENT)
    data_raw = _align(len(data.bytes), _FILE_ALIGNMENT)
    text_offset = _FILE_ALIGNMENT
    data_offset = text_offset + text_raw
    reloc_offset = data_offset + data_raw
    # An empty relocation block; the firmware expects the table to exist.
    relocations = struct.pack("<IIHH", 0, 12, 0, 0).ljust(_FILE_ALIGNMENT, b"\0")

    dos_header = bytearray(0x40)
    dos_header[0:2] = b"MZ"
    struct.pack_into("<I", dos_header, 0x3C, 0x40)
    coff_header = struct.pack("<HHIIIHH", 0x8664, 3, 0, 0, 0, _OPTIONAL_HEADER_SIZE, 0x0022)
    optional = struct.pack("<HBBIIIII", 0x20B, 0, 0, text_raw, data_raw + _FILE_ALIGNMENT,
                           0, text_address, text_address)
    optional += struct.pack("<QII", 0x400000, _SECTION_ALIGNMENT, _FILE_ALIGNMENT)
    optional += struct.pack("<HHHHHH", 0, 0, 0, 0, 0, 0)
    optional += struct.pack("<IIII", 0, image_size, _FILE_ALIGNMENT, 0)
    optional += struct.pack("<HH", 10, 0x0100)            # subsystem 10: UEFI application
    optional += struct.pack("<QQQQ", 0, 0, 0, 0)
    optional += struct.pack("<II", 0, 16)
    directories = [(0, 0)] * 16
    directories[5] = (reloc_address, 12)                   # base relocation table
    for address, size in directories:
        optional += struct.pack("<II", address, size)
    if len(optional) != _OPTIONAL_HEADER_SIZE:
        raise AssertionError("optional header has the wrong size")

    sections = _section_header(b".text", len(code), text_address, text_raw, text_offset, 0x60000020)
    sections += _section_header(b".data", len(data.bytes), data_address, data_raw, data_offset, 0xC0000040)
    sections += _section_header(b".reloc", 12, reloc_address, _FILE_ALIGNMENT, reloc_offset, 0x42000040)
    headers = bytes(dos_header) + b"PE\0\0" + coff_header + optional + sections
    return (headers.ljust(_FILE_ALIGNMENT, b"\0") + bytes(code).ljust(text_raw, b"\xCC")
            + bytes(data.bytes).ljust(data_raw, b"\0") + relocations)
