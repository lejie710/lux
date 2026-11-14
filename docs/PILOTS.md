# The pilots, as recorded

Four experiments were tried before any prediction existed. They are **pilots**: shown, never counted, with no prediction and no score. This note says what each recording shows when it is compared with `recordings/normal-1`. Every statement below is an observation of one firmware build in one virtual machine. None of it is a statement about what a specification requires.

All four start from the same variable store template as the normal run (`provenance.vars_template_sha256` is equal in every recording), with the same keys, firmware file and machine. Each was recorded with `python3 -m recorder record <name> --experiment <name>` and compared with `python3 -m recorder compare`. The numbers come from `recordings/comparisons/normal-1_vs_<name>.json`. Event type names are the names `tpm2_eventlog` prints.

## Summary

| Pilot | Change | Boot | First differing event | Registers that differ | Events |
|---|---|---|---|---|---|
| normal | none | loader ran | | | 28 |
| `e1` | one content byte of the loader, Secure Boot switched off | loader ran | 4: variable `SecureBoot`, register 7 | 4, 7 | 27 |
| `e2` | the same byte, Secure Boot on | refused, `Access Denied` | 25: `EV_EFI_VARIABLE_AUTHORITY`, register 7, absent | 4, 5, 7 | 26 |
| `e4` | Secure Boot switched off, nothing else | loader ran | 4: variable `SecureBoot`, register 7 | 7 | 27 |
| `e5` | the signed loader's hash added to `dbx` | refused, `Access Denied` | 8: variable `dbx`, register 7 | 4, 5, 7 | 27 |

The registers are the same in all four hash banks. All registers not listed are equal to the normal run.

## e1: one content byte changed, Secure Boot switched off

- **The boot continued.** The console shows `LUX-LOADER B: started, boot services active` (the changed byte turns the letter A into B), and the loader reached its last line after `ExitBootServices`.
- **First differing event: index 4**, the measurement of the variable `SecureBoot` into register 7. It differs before any loader is read.
- **Register 7** differs for two reasons: event 4, and the absence of the `EV_EFI_VARIABLE_AUTHORITY` event that the normal run logs at index 25. With checking off, this firmware logs no record of a key that allowed the loader.
- **Register 4** differs because the measured image digest is the changed loader's (`cef0a974...`), not the signed loader's (`00c5018d...`).
- **Register 5 is equal**: both `ExitBootServices` events are present, as in the normal run.

## e4: Secure Boot switched off, nothing else

- **The boot continued** with the unchanged, signed loader (`LUX-LOADER A`).
- **First differing event: index 4**, the same event with the same digest as in `e1`.
- **Only register 7 differs**, for the same two reasons as in `e1`. Register 4 is equal: the image digest measured is the signed loader's, exactly as in the normal run.
- The loader's own report differs although no register does: `MemoryMapSize` is `0x1860` where the normal run has `0x1950`, and `MapKey` differs. The same is seen in `e1`. This is a difference in the memory map the firmware hands over, visible only in the console and the loader report.

`e1` and `e4` together separate two things: `e4` differs from the normal run by the switch alone, and `e1` differs from `e4` by the loader byte alone (register 4).

## e5: the signed loader's hash on the forbidden list

- **The boot was refused.** The console shows `failed to load Boot0001 ... Access Denied`, then `No bootable option or device was found`. The loader printed nothing.
- **First differing event: index 8**, the measurement of the variable `dbx` into register 7. In the normal run that event carries 0 data bytes; here it carries 76, one signature list holding one SHA-256 hash. The hash in it is the signed loader's (`00c5018d...`).
- **Register 7** differs because of event 8 alone. The `EV_EFI_VARIABLE_AUTHORITY` event is present with the same digest as in the normal run, although the loader was refused. This is the visible difference from `e2`, where the changed loader matched no key and that event is absent.
- **Register 4** differs: no image digest is measured, and the firmware logs `Returning from EFI Application from Boot Option` and a second `Calling EFI Application from Boot Option`.
- **Register 5** differs: neither `ExitBootServices` event exists.

## What these recordings do not show

- **How the store was edited.** `e1` and `e4` set this firmware's own one-byte switch `SecureBootEnable` from 1 to 0 in the store file while the machine was off. `e5` writes a `dbx` record into the store file directly, with an all-zero timestamp, not through a signed update. The firmware read that record, measured it and enforced it. Whether the firmware would accept or reject a signed update of `dbx` is a different question, and these recordings do not answer it.
- **Any order of lookups.** `e5` shows that the forbidden list won. It does not show in which order the firmware consulted the two lists.
- **Repeatability beyond two runs.** Each of `e1`, `e4` and `e5` was booted twice (once into a scratch folder, once for the committed file). Registers, event log and console were equal both times. A fresh normal run was also equal to `normal-1` on every compared field.
