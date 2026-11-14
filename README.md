# Lux

**When one thing in a PC's boot chain is changed, what does the specification require, what does it leave open, and what does this firmware actually do?**

Lux records one boot of open-source UEFI firmware in a virtual machine, from reset to the moment firmware hands the machine to the operating system. Then it changes one thing and boots again, and puts the normal run and the changed run side by side.

This repository holds three parts: **the recorder**, **the content**, and the first scene of **the site**. The recorder boots the machine, captures what the boot left behind, refuses any run whose readings disagree, and writes one JSON recording per boot. The content is the words of the site as data, each claim labelled with where it comes from and each evidence line copied from a recording. The site shows them as a scroll story; so far it has its opening and the first of seven stops.

## What exists so far

| Part | State |
|---|---|
| `recorder/` | A Python package (standard library only) that prepares keys, loader and variable store, records a named run, compares two recordings, and scores a comparison against a prediction into a result file |
| `recordings/normal-1`, `normal-2` | The normal run, recorded twice. The two are identical on every compared field |
| `recordings/e2` | A **pilot**: one content byte of the loader changed, Secure Boot on. The firmware refused it. It differs from the normal run in TPM registers 4, 5 and 7 and in no other register |
| `recordings/e1`, `e4`, `e5` | The three other **pilots**, described under "Pilots and counted experiments" and in `docs/PILOTS.md` |
| `recordings/comparisons/` | The five comparison files those statements come from: the two normal runs, and each pilot against `normal-1` |
| `content/` | The site's words as five JSON files in one shape: seven stops, the experiments section, the sources and the glossary. `content/README.md` describes the shape |
| `scripts/check_content.py` | Checks the content against the committed recordings and the rules in `content/README.md`. Standard library only |
| `site/` | The site: React, TypeScript and Vite, no other runtime package. Built so far: the navigation, the opening, the move inside the machine, stop 1 and its evidence panel. It reads its words from `content/` and writes none of its own. `site/ASSETS.md` says how each picture was made |
| `predictions/` | Empty. No prediction has been committed, so no counted experiment has been run |
| `docs/DESIGN.md` | Module boundaries, the four file formats (recording, comparison, prediction, score), the decisions and their costs |
| `docs/MUTATION_CHECKS.md` | Four rules broken on purpose, and the tests that failed |

There is no result yet for the question above. The numbers it asks for (specification-required behaviours met, open behaviours predicted correctly) come from counted experiments, and none has been run.

## The site

```
cd site
npm ci
npm run dev
```

The page opens at `http://127.0.0.1:5183/`. `npm test`, `npm run build` and `npm run format:check` are the three checks.

| Address | What it shows |
|---|---|
| `/` | The scene, pinned while the page scrolls through its steps |
| `/?static` | Every step as a still section, one under the other. A reader who prefers reduced motion gets this without asking |
| `/?step=N` | The scene frozen at step N (0, 1 or 2), with nothing to scroll. Add `&evidence` to open that step's evidence |
| `/#step-N` | The scrolled scene, landed on step N |

The site's tests render pages to HTML without a browser. They check the step-to-picture mapping, that every screen of the content has what a scene needs, the two address switches and the evidence panel's key and focus rules. They do not prove motion, layout or focus in a real window; those were checked by eye in one Chromium browser.

## How a run is trusted

Every run ends the same way, whether the loader was accepted or refused: the guest is paused, its memory is saved, and the virtual machine is killed while paused, so the software TPM is still alive to be read. Three readings of the same boot, taken by different routes, must then agree on all 24 registers in all four hash banks:

1. a replay of the firmware's event log, cut out of the saved guest memory;
2. a replay of the extend commands found in the software TPM's own log;
3. the register values read from the TPM itself.

The first reading is written by the firmware and does not pass through the TPM. The second and third both come from the one software TPM process, by two routes, and both replays use the same extend function, so the three are not fully independent of each other. `docs/DESIGN.md` section 4.3 says exactly how far.

If they disagree anywhere, the command exits with an error and writes nothing. The same holds when the end of the boot was not seen in time, and when a normal run was not accepted: a hung boot never becomes a recording of the normal run.

## Pilots and counted experiments

The measure of this project is a prediction committed **before** an experiment is run. Experiments that were tried during the early research, before any prediction existed, cannot meet that. They are declared as **pilots**: shown, never counted. There are four:

| Pilot | What it changes | What the recording shows | Registers that differ from the normal run |
|---|---|---|---|
| `e1` | One byte of the loader's content, Secure Boot switched off | The changed loader ran | 4, 7 |
| `e2` | The same byte, Secure Boot on | Refused, `Access Denied` | 4, 5, 7 |
| `e4` | Secure Boot switched off, nothing else | The signed loader ran | 7 |
| `e5` | The signed loader's hash added to the revocation list (`dbx`) | Refused, `Access Denied` | 4, 5, 7 |

All four were tried in the early research, with other tooling and a throwaway key set, and all four have since been recorded with this recorder, from the same variable store template as the normal run. They stay pilots: no prediction, no score. `docs/PILOTS.md` gives the first differing event of each, why each register differs, and what the recordings do not show.

A **counted** experiment (`boot-order`, `signature-byte`, `rebuilt-firmware`) is one that has never been run. The recorder refuses to run it unless all of this holds:

- `predictions/<experiment>.json` exists and is valid;
- it describes the same change as the experiment, and carries the values that decide what the experiment tests (which byte of the signature area, which rebuilt firmware file). Those values are read from the prediction and from nowhere else;
- it is committed, and the file on disk is byte for byte the committed one;
- two recordings of the normal run are on file and identical.

The recording stores the prediction's hash, commit and values, so a prediction edited after its run is detected. A counted recording is never overwritten.

## Limits

- **A virtual machine, not a real one.** QEMU under software emulation. Power sequencing, the first step of a real boot, does not exist here.
- **A software TPM** (swtpm), not a hardware chip.
- **Open-source firmware** (OVMF, built from EDK II, as packaged by Ubuntu). Nothing here shows what any vendor's firmware does on real hardware.
- **A release build of the firmware.** It prints no log of its early phases, so the recording begins with what the firmware measured, not with what it did internally.
- **One machine, one set of tool versions.** The recordings have been reproduced on the machine that made them. Another QEMU version, machine type or firmware package may give other register values; the recorder then says so instead of producing a recording that looks comparable.
- **Event type names are tool names.** They are the names `tpm2_eventlog` prints, not citations of a specification. The Trusted Computing Group document that defines the event log has not been read for this project yet.
- **The story stops assigned to events are this project's own mapping**, declared rule by rule in `recorder/storymap.py`.
- **The counted experiments can be staged but have never been booted**; `docs/DESIGN.md` section 11 lists what is unproven about them.
- **The pilots edit the variable store file while the machine is off.** `e5` writes the revocation record directly and not through a signed update, so it shows how this firmware treats a list that is there, not how it treats an update.
- **The test keys are public.** See `recorder/testkeys/README.md`. Never trust them anywhere.
- **The test certificates are not yet valid at the guest's fixed clock**, and this firmware accepts them all the same. That is observed behaviour, described in the same README.
- **Debian or Ubuntu only, as written.** Tool versions are read with `dpkg-query`.

## Setup on Linux or WSL

Tested on Ubuntu 24.04 inside WSL 2 only. The recorder needs these Ubuntu packages, and every recording stores their versions in its `provenance` block:

| Package | Used for |
|---|---|
| `qemu-system-x86` | the virtual machine |
| `ovmf` | the firmware and its empty variable store |
| `swtpm` | the software TPM |
| `binutils` | assembling and linking the guest loader |
| `python3` (3.12) | the recorder itself, standard library only |
| `git` | the prediction gate asks it whether a prediction is committed; needed for counted experiments only |
| `tpm2-tools` (optional) | decoding `eventlog.bin` yourself with `tpm2_eventlog` |

The first four are the ones whose versions a recording stores, read with `dpkg-query`, together with the Python version. `sbsigntool`, `efitools` and `openssl` were used once to create the committed key set and sign the loader. A clone of this repository does not need them, and their versions are recorded once, in `recorder/testkeys/MANIFEST.json`.

The recorder keeps its scratch files (run directories, sockets, the variable store template) in a work directory: `~/lux-work`, or the path in `LUX_WORK_DIR`. It must be on a Linux file system. On WSL that means not under `/mnt/`, because unix sockets do not work on a Windows drive. The repository itself may live anywhere.

All commands are run from the repository root.

### 1. Prepare (once per machine)

```
python3 -m recorder prepare
```

This verifies the committed test keys against their manifest, builds the guest loader and checks that it equals the committed signed one, checks that the packaged firmware file is the one the recordings were made with, and makes the variable store template with one enrolment boot (about ten seconds). Expected output:

```
firmware_sha256: 1286f2a3217d09b374d05951355d7a561c8bacecd74845c8a1fbb71a48c0de8d
keys: verified
loader_authenticode_sha256: 00c5018d3157edb92f96a08ba685a1c5913c5dd5fa2228b021dd9d4970eee50f
signed_loader_sha256: 0cb3ced82bf84f1a235c3b81f8029d055bd846a261cdfd71ad6f9f0437e18a78
vars_template_sha256: 57ec06981b573029dd48cd399a5546ad8e57dece61dac9cdeeb894e79e88cebf
prepared
```

If your tools build a different loader or a different template, or your firmware package is another version, the command says so and stops. It never generates new keys by itself.

### 2. Record a run

The names `normal-1`, `normal-2`, `e1`, `e2`, `e4` and `e5` are the committed recordings. They are evidence, and `record` refuses to write over an existing name. So use names of your own:

```
python3 -m recorder record my-normal --experiment normal
python3 -m recorder record my-e2 --experiment e2
```

Each takes about ten seconds and writes `recordings/<name>/recording.json` and `eventlog.bin`. Expected output for the normal run:

```
run my-normal: accepted, 28 events, agreement gate passed
written: recordings/my-normal/recording.json
```

and for the pilot: `run my-e2: refused, 26 events, agreement gate passed`.

To keep your runs out of the repository's `recordings/` folder altogether, add `--out some/other/folder`. To overwrite a recording on purpose, add `--replace`; the recording of a counted experiment is never replaced.

Exit codes of `record`: 0 for a recording; 1 for a refusal, with one sentence saying why, and nothing written; 3 when a changed run reached neither the loader's last line nor a refusal and was recorded as `timeout`.

A counted experiment is refused:

```
$ python3 -m recorder record blind --experiment signature-byte
refused: experiment 'signature-byte' is counted and must not run: no prediction file signature-byte.json exists
```

### 3. Compare

Compare your own run with the committed normal run. The baseline, named first, must be a recording of the normal run:

```
python3 -m recorder compare recordings/normal-1/recording.json recordings/my-e2/recording.json --out recordings/comparisons/normal-1_vs_my-e2.json
```

```
identical: false
registers differing (sha256): [4, 5, 7]
written: recordings/comparisons/normal-1_vs_my-e2.json
```

Comparing `recordings/normal-1/recording.json` with `recordings/my-normal/recording.json` prints `identical: true` when your machine reproduces the committed run.

`compare` refuses a recording with itself, with a renamed copy of itself, or with a recording whose agreement gate did not pass.

`scripts/record-pilots.sh` makes the six committed recordings and the five committed comparisons again (it passes `--replace` on purpose) and then checks that nothing is left running. The recording time is part of each file, so after it the committed files differ from the ones in git even when every compared field is equal.

### 4. Check against a prediction (for counted experiments, once they exist)

```
python3 -m recorder check COMPARISON.json --prediction predictions/ID.json --recording recordings/NAME/recording.json --baseline recordings/normal-1/recording.json --repeat recordings/comparisons/normal-1_vs_normal-2.json --out results/ID.json
```

What it prints, here for a prediction of four rows of which two did not hold:

```
specification-required rows met: 0 of 1
open rows predicted correctly: 2 of 3
mismatches: continues, pcr1
written: results/ID.json
```

**Exit code 0 means "scored", not "every row held".** A mismatch is a result and is listed by row; it is not an error. Exit code 1 means the score was refused: the comparison does not belong to that recording or baseline, the prediction was edited after the run, or the two normal runs are not identical. The file written with `--out` has the format `lux-score/1` (`docs/DESIGN.md` section 6.1) and is what a site would load for the two headline numbers.

## Tests

```
python3 -m unittest discover -s recorder/tests -t .
```

Expected last lines (the time varies):

```
Ran 285 tests in 15.465s

OK (skipped=5)
```

The unit tests need no virtual machine; they were also run with Python 3.12 on Windows. They do not change any file in the repository. Three of them build a temporary git repository to test the prediction gate against the real `git`. The five skipped tests are the integration test. To include it, on a prepared machine:

```
LUX_VM_TESTS=1 python3 -m unittest discover -s recorder/tests -t .
```

It boots the normal run twice (about twenty seconds in total), asserts that the agreement gate passed, that the two runs are equal on every compared field, that a fresh run equals the committed `normal-1`, and that no process is left running. Expected: `Ran 285 tests`, `OK`.

The content has its own check, which the unit tests also run:

```
python3 scripts/check_content.py
```

Expected last lines:

```
content check: 5 files, 28 screens, 322 claims, 81 claims uefi-required, 26 claims uefi-platform, 19 claims tcg-unread, 38 claims this-firmware, 143 claims recording, 15 claims general, 6 recordings, 59 glossary entries
content check: passed, no problems
```

It fails if a claim has no basis, a UEFI basis has no full citation, an evidence line is not found letter for letter in the recording it names, a statement has more than 14 words, wording such as "the specification says" sits on a claim about measured boot or about this firmware, or one of the seven stops is missing. `content/README.md` lists every rule.

## Reading a recording

`recording.json` holds, for one boot: what was changed, down to the one byte (`run.change_detail`); the provenance (tool versions, firmware hash, key fingerprints, full command lines); the outcome; the console lines, with the loader's long address dump kept apart in `loader_report`; every logged event with its register, type, digest, a one-line summary and its story stop; all register values in four banks; and the result of the agreement gate. Events are to be read in the order of their `index`: a story stop is a label, and in a refused boot the stops do not rise steadily. The field list `may_vary` names the only fields a comparison ignores. `docs/DESIGN.md` section 4 describes the format.

## Provenance of the committed recordings

QEMU 8.2.2 (`1:8.2.2+ds-0ubuntu1.18`), OVMF 2024.02 (`2024.02-2ubuntu0.10`, file `OVMF_CODE_4M.secboot.fd`, SHA-256 `1286f2a3217d09b374d05951355d7a561c8bacecd74845c8a1fbb71a48c0de8d`), swtpm 0.7.3, binutils 2.42, Python 3.12.3, on Ubuntu 24.04 under WSL 2. The key set and the signed loader were created once with OpenSSL 3.0.13, sbsigntool 0.9.4 and efitools 1.9.2. Machine type `pc-q35-8.2`, CPU model `qemu64`, 512 MiB, software emulation, clock fixed at 2026-01-01.

## Licence

No licence has been chosen for this repository yet. Until a licence file is added, the usual default applies: all rights are reserved, and this README's description of how to re-run the recorder is not a grant of any right. The firmware, virtual machine and TPM programs it drives are separate projects under their own licences.

## Sources

- UEFI Forum, *Unified Extensible Firmware Interface (UEFI) Specification*, version 2.11.
- Microsoft, *Windows Authenticode Portable Executable Signature Format* (the image digest).
- The source code and documentation of EDK II, QEMU, swtpm and tpm2-tools.
