"""The two boot entries the boot order experiments use, written down as data.

The firmware keeps a list of boot options. Each option is a variable named
`Boot####` (four hexadecimal digits) that says what to start, and the
variable `BootOrder` lists the option numbers in the order they are tried.

The normal run has only the options the firmware makes for itself: its own
setup application (`Boot0000`, which is not part of a normal boot) and one
for the disk (`Boot0001`). A boot order experiment needs two options that
both lead to a loader, so that changing their order changes which one is
started first. This module defines those two:

* entry A, `Boot0002`, the file `\\EFI\\LUX\\A.EFI`;
* entry B, `Boot0003`, the file `\\EFI\\LUX\\B.EFI`.

Each option names its file by path only, with no disk in front. The firmware
then looks for that path on the disks it has; the virtual machine has one.

The entries and the order are written by the firmware's own `SetVariable`
service, in the same preparation boot that enrols the keys (see
`preparation`). `docs/DESIGN.md`, decision D6, says why.
"""
from dataclasses import dataclass

from recorder import varstore
from recorder.enrol import VariableWrite

# The directory on the boot disk that holds both loader files.
DISK_DIRECTORY: tuple[str, ...] = ("EFI", "LUX")
# The options the firmware creates for itself in the preparation boot. They
# stay in the list, after the two entries, in the order the firmware gave them.
FIRMWARE_OPTIONS: tuple[int, ...] = (0, 1)


@dataclass(frozen=True)
class BootEntry:
    """One boot option this project adds."""

    letter: str             # "A" or "B"
    number: int             # the #### of its Boot#### variable
    description: str        # the label the firmware prints when it tries the option
    file_name: str          # the loader file inside `DISK_DIRECTORY`

    @property
    def variable(self) -> str:
        """The name of the variable that holds this option."""
        return varstore.option_name(self.number)

    @property
    def firmware_path(self) -> str:
        """The file's path as the option stores it, with backslashes."""
        return "\\" + "\\".join((*DISK_DIRECTORY, self.file_name))


ENTRY_A = BootEntry("A", 2, "Lux entry A", "A.EFI")
ENTRY_B = BootEntry("B", 3, "Lux entry B", "B.EFI")
ENTRIES: tuple[BootEntry, ...] = (ENTRY_A, ENTRY_B)

ORDER_A_FIRST: tuple[int, ...] = (ENTRY_A.number, ENTRY_B.number, *FIRMWARE_OPTIONS)
ORDER_B_FIRST: tuple[int, ...] = (ENTRY_B.number, ENTRY_A.number, *FIRMWARE_OPTIONS)

# SHA-256 of the variable store template that holds both entries in the order
# A, B. Like the one-entry template's hash in the key manifest, it is a
# function of the committed keys, the packaged firmware and the values above:
# two independent preparation boots gave the same file.
TEMPLATE_SHA256 = "12f35963670eab15d8f0ae4210432c0036017f6b4411993df6b43cdaee200abf"


def option_names(order: tuple[int, ...]) -> list[str]:
    """An order as the variable names it lists, for example `Boot0002`."""
    return [varstore.option_name(number) for number in order]


def variable_writes(order: tuple[int, ...]) -> list[VariableWrite]:
    """The three `SetVariable` calls that create both entries and set the order.

    The two options first, then the list that refers to them, so the list
    never names an option that does not exist yet.
    """
    if sorted(order) != sorted(ORDER_A_FIRST):
        raise ValueError("a boot order lists entry A, entry B and the firmware's own options, each once")
    writes = [
        VariableWrite(entry.variable, varstore.GLOBAL_VARIABLE_GUID, varstore.BOOT_VARIABLE_ATTRIBUTES,
                      varstore.load_option(entry.description, entry.firmware_path))
        for entry in ENTRIES
    ]
    writes.append(VariableWrite("BootOrder", varstore.GLOBAL_VARIABLE_GUID,
                                varstore.BOOT_VARIABLE_ATTRIBUTES, varstore.boot_order_data(order)))
    return writes
