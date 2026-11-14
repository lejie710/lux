"""PCR arithmetic shared by every module that touches TPM register values.

A PCR (platform configuration register) is a register inside the TPM that can
only be changed by "extending" it: new value = hash(old value + digest). The
TPM keeps one set of 24 registers per hash algorithm; each set is a "bank".
"""
import hashlib

# TPM algorithm identifier -> (hashlib name, digest size in bytes).
ALGORITHMS: dict[int, tuple[str, int]] = {
    0x0004: ("sha1", 20),
    0x000B: ("sha256", 32),
    0x000C: ("sha384", 48),
    0x000D: ("sha512", 64),
}
BANK_NAMES: tuple[str, ...] = tuple(name for name, _ in ALGORITHMS.values())
DIGEST_SIZES: dict[str, int] = {name: size for name, size in ALGORITHMS.values()}
PCR_COUNT = 24

# bank name -> the 24 register values of that bank
PcrBanks = dict[str, list[bytes]]


def start_value(pcr_index: int, size: int) -> bytes:
    """Value of one register right after the TPM starts.

    Observed on this software TPM: registers 17 to 22 start as all one bits,
    every other register starts as all zero bits.
    """
    fill = b"\xff" if 17 <= pcr_index <= 22 else b"\x00"
    return fill * size


def start_banks() -> PcrBanks:
    """All four banks in their start state."""
    return {
        name: [start_value(index, size) for index in range(PCR_COUNT)]
        for name, size in DIGEST_SIZES.items()
    }


def extend(bank: str, old_value: bytes, digest: bytes) -> bytes:
    """The extend rule: hash the old register value followed by the digest.

    The order matters. Hashing the digest first would give a different value,
    and a replay would no longer match what the TPM holds.
    """
    return hashlib.new(bank, old_value + digest).digest()


def banks_to_hex(banks: PcrBanks) -> dict[str, dict[str, str]]:
    """Register values as lowercase hex text, keyed by bank and index."""
    return {
        bank: {str(index): value.hex() for index, value in enumerate(values)}
        for bank, values in banks.items()
    }


def banks_from_hex(document: dict[str, dict[str, str]]) -> PcrBanks:
    """The reverse of `banks_to_hex`."""
    return {
        bank: [bytes.fromhex(values[str(index)]) for index in range(PCR_COUNT)]
        for bank, values in document.items()
    }
