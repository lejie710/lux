# Lux

**When one thing in a PC's boot chain is changed, what does the specification require, what does it leave open, and what does this firmware actually do?**

Lux records one boot of open-source UEFI firmware in a virtual machine, from reset to the moment firmware hands the machine to the operating system. Then it changes one thing and boots again, and puts the normal run and the changed run side by side.

This repository is at its first stage: **the recorder**. It boots the machine, captures what the boot left behind, refuses any run whose readings disagree, and writes one JSON recording per boot. The site that will tell the story from these recordings does not exist yet.

## What exists so far

| Part | State |
|---|---|
| `recorder/` | A Python package (standard library only) that prepares keys, loader and variable store, records a named run, compares two recordings, and scores a comparison against a prediction |
| `recordings/normal-1`, `normal-2` | The normal run, recorded twice. The two are identical on every compared field |
| `recordings/e2` | A **pilot**: one content byte of the loader changed, Secure Boot on. The firmware refused it. It differs from the normal run in TPM registers 4, 5 and 7 and in no other register |
| `recordings/comparisons/` | The two comparison files those statements come from |
| `predictions/` | Empty. No prediction has been committed, so no counted experiment has been run |
| `docs/DESIGN.md` | Module boundaries, the three file formats, the decisions and their costs |
| `docs/MUTATION_CHECKS.md` | Three rules broken on purpose, and the tests that failed |

There is no result yet for the question above. The numbers it asks for (specification-required behaviours met, open behaviours predicted correctly) come from counted experiments, and none has been run.

## How a run is trusted

Every run ends the same way, whether the loader was accepted or refused: the guest is paused, its memory is saved, and the virtual machine is killed while paused, so the software TPM is still alive to be read. Three independent readings of the same boot must then agree on all 24 registers in all four hash banks:

1. a replay of the firmware's event log, cut out of the saved guest memory;
2. a replay of the extend commands found in the software TPM's own log;
3. the register values read from the TPM itself.

If they disagree anywhere, the command exits with an error and writes nothing.

## Pilots and counted experiments

The measure of this project is a prediction committed **before** an experiment is run. Experiments that were tried during the early research, before any prediction existed, cannot meet that. They are declared as **pilots**: shown, never counted. `e2` is one of them.

A **counted** experiment (`boot-order`, `signature-byte`, `rebuilt-firmware`) is one that has never been run. The recorder refuses to run it unless `predictions/<experiment>.json` exists, is valid, and is committed without later changes. The recording stores the prediction's hash and commit, so a prediction edited after its run is detected.

## Limits

- **A virtual machine, not a real one.** QEMU under software emulation. Power sequencing, the first step of a real boot, does not exist here.
- **A software TPM** (swtpm), not a hardware chip.
- **Open-source firmware** (OVMF, built from EDK II, as packaged by Ubuntu). Nothing here shows what any vendor's firmware does on real hardware.
- **A release build of the firmware.** It prints no log of its early phases, so the recording begins with what the firmware measured, not with what it did internally.
- **One machine, one set of tool versions.** The recordings have been reproduced on the machine that made them. Another QEMU version, machine type or firmware package may give other register values; the recorder then says so instead of producing a recording that looks comparable.
- **Event type names are tool names.** They are the names `tpm2_eventlog` prints, not citations of a specification. The Trusted Computing Group document that defines the event log has not been read for this project yet.
- **The story stops assigned to events are this project's own mapping**, declared rule by rule in `recorder/storymap.py`.
- **Several experiments can be staged but have never been booted**; `docs/DESIGN.md` section 11 lists what is unproven about them.
- **The test keys are public.** See `recorder/testkeys/README.md`. Never trust them anywhere.

## Setup on Linux or WSL

Tested on Ubuntu 24.04 inside WSL 2 only. The recorder needs these Ubuntu packages, and every recording stores their versions in its `provenance` block:

| Package | Used for |
|---|---|
| `qemu-system-x86` | the virtual machine |
| `ovmf` | the firmware and its empty variable store |
| `swtpm` | the software TPM |
| `binutils` | assembling and linking the guest loader |
| `python3` (3.12) | the recorder itself, standard library only |
| `tpm2-tools` (optional) | decoding `eventlog.bin` yourself with `tpm2_eventlog` |

`sbsigntool`, `efitools` and `openssl` were used once to create the committed key set and sign the loader. A clone of this repository does not need them.

The recorder keeps its scratch files (run directories, sockets, the variable store template) in a work directory: `~/lux-work`, or the path in `LUX_WORK_DIR`. It must be on a Linux file system. On WSL that means not under `/mnt/`, because unix sockets do not work on a Windows drive. The repository itself may live anywhere.

All commands are run from the repository root.

### 1. Prepare (once per machine)

```
python3 -m recorder prepare
```

This verifies the committed test keys against their manifest, builds the guest loader and checks that it equals the committed signed one, and makes the variable store template with one enrolment boot (about ten seconds). Expected output:

```
keys: verified
loader_authenticode_sha256: 00c5018d3157edb92f96a08ba685a1c5913c5dd5fa2228b021dd9d4970eee50f
signed_loader_sha256: 0cb3ced82bf84f1a235c3b81f8029d055bd846a261cdfd71ad6f9f0437e18a78
vars_template_sha256: 57ec06981b573029dd48cd399a5546ad8e57dece61dac9cdeeb894e79e88cebf
prepared
```

If your tools build a different loader or a different template, the command says so and stops. It never generates new keys by itself.

### 2. Record a run

```
python3 -m recorder record normal-1 --experiment normal
python3 -m recorder record e2 --experiment e2
```

Each takes about ten seconds and writes `recordings/<name>/recording.json` and `eventlog.bin`. Expected output for the normal run:

```
run normal-1: accepted, 28 events, agreement gate passed
written: recordings/normal-1/recording.json
```

and for the pilot: `run e2: refused, 26 events, agreement gate passed`.

A counted experiment is refused:

```
$ python3 -m recorder record blind --experiment signature-byte
refused: experiment 'signature-byte' is counted and must not run: no prediction file signature-byte.json exists
```

### 3. Compare

```
python3 -m recorder compare recordings/normal-1/recording.json recordings/e2/recording.json --out recordings/comparisons/normal-1_vs_e2.json
```

```
identical: false
registers differing (sha256): [4, 5, 7]
```

`scripts/record-pilots.sh` runs steps 2 and 3 for `normal-1`, `normal-2` and `e2` and then checks that nothing is left running.

### 4. Check against a prediction (for counted experiments, once they exist)

```
python3 -m recorder check COMPARISON.json --prediction predictions/ID.json --recording recordings/NAME/recording.json
```

## Tests

```
python3 -m unittest discover -s recorder/tests -t .
```

Expected last lines (the time varies):

```
Ran 168 tests in 4.143s

OK (skipped=4)
```

The unit tests need no virtual machine; they were also run with Python 3.12 on Windows. The four skipped tests are the integration test. To include it, on a prepared machine:

```
LUX_VM_TESTS=1 python3 -m unittest discover -s recorder/tests -t .
```

It boots the normal run twice (about twenty seconds in total), asserts that the agreement gate passed, that the two runs are equal on every compared field, and that a fresh run equals the committed `normal-1`. Expected: `Ran 168 tests`, `OK`.

## Reading a recording

`recording.json` holds, for one boot: the provenance (tool versions, firmware hash, key fingerprints, full command lines), the outcome, the console lines, every logged event with its register, type, digest, a one-line summary and its story stop, all register values in four banks, and the result of the agreement gate. The field list `may_vary` names the only fields a comparison ignores. `docs/DESIGN.md` section 4 describes the format.

## Provenance of the committed recordings

QEMU 8.2.2 (`1:8.2.2+ds-0ubuntu1.18`), OVMF 2024.02 (`2024.02-2ubuntu0.10`, file `OVMF_CODE_4M.secboot.fd`, SHA-256 `1286f2a3217d09b374d05951355d7a561c8bacecd74845c8a1fbb71a48c0de8d`), swtpm 0.7.3, tpm2-tools 5.6, sbsigntool 0.9.4, efitools 1.9.2, binutils 2.42, Python 3.12.3, on Ubuntu 24.04 under WSL 2. Machine type `pc-q35-8.2`, CPU model `qemu64`, 512 MiB, software emulation, clock fixed at 2026-01-01.

## Sources

- UEFI Forum, *Unified Extensible Firmware Interface (UEFI) Specification*, version 2.11.
- Microsoft, *Windows Authenticode Portable Executable Signature Format* (the image digest).
- The source code and documentation of EDK II, QEMU, swtpm and tpm2-tools.
