# The counted experiments, before they are run

> **Since this note was written, each of the four has been booted once.** `docs/RESULTS.md` holds the result. Below this box the note stands as it was before the runs, so every "has not been booted" and "does not exist yet" describes that moment. One command differs from what was done: the scores were written to `recordings/scores/<experiment>.json`, not to `results/`.

Four counted experiments have a committed prediction: `boot-order-same`, `boot-order-different`, `signature-byte` and `signature-byte-off`. **None of them has been booted.** This note says how each is staged, what was booted to get that far, and how each is to be run, once. It was written together with the predictions and before any counted run. The decisions behind it are D6, D7 and D8 in `docs/DESIGN.md`.

## What was booted for this, and what was not

| Configuration | Booted | Why that is allowed |
|---|---|---|
| The packaged empty variable store with the enrolment program that also writes entries A and B and the order A, B | Yes, several times | A preparation boot. It makes the two-entry template; two independent boots gave the same file |
| The same, with the order A, B, `Boot0001`, `Boot0000` | Yes, once; the store was not made a template and was never booted | A preparation boot. Entry A stays before entry B. It tests the claim the staging check rests on (see "The stores") |
| Two boot entries, order A then B, same loader behind both (`normal-two-same`) | Yes, recorded twice for the repository | A normal run |
| Two boot entries, order A then B, second loader behind B (`normal-two-different`) | Yes, recorded twice for the repository | A normal run |
| The plain normal run and the pilots | Recordings unchanged; their comparison files were made again from them | Normal run and declared pilots |
| The enrolment program that writes the order B, A | **No** | It makes the changed configuration. `prepare --changed-boot-order` refuses to run it before a boot order prediction is committed |
| A store that lists B before A | **No. It does not exist yet** | The changed configuration of a counted experiment |
| A loader with the chosen signature byte changed | **No.** It has only been written into temporary folders by tests that boot nothing | The changed configuration of a counted experiment |

Everything known about the changed configurations comes from tests with a fake machine, which replays a normal boot whatever is staged. Those tests prove that each counted experiment can be staged from its committed prediction, recorded, compared and scored without an error. They say nothing about what the firmware will do.

## One earlier boot order change, declared

During the early research, before the recorder and before any prediction, a boot order was changed once on another configuration, and the test was repeated once to check it. It is not one of the counted experiments, and it is written down here because it bears on three of their rows.

| | The early test | The counted boot order experiments |
|---|---|---|
| Firmware file | The packaged build without Secure Boot | The packaged build with Secure Boot, keys enrolled |
| Boot options | The firmware's own three: its setup application, the disk, its built-in shell | Entries A and B, each a signed loader on the disk, and the firmware's own two |
| The change | The shell option moved to the front of `BootOrder`, with the shell's own command | Entry B listed before entry A, written by a preparation boot |
| What was read | The console lines and the variables `BootOrder` and `BootCurrent` | Console, loader report, event log, registers |
| Registers and event log | Not read | Read and compared |

What it showed: on the next boot this firmware tried the option now listed first, and `BootOrder` read back as it had been written. So the rows `continues`, `entry-b-first` and `order-measured-as-written` of the two boot order predictions were not written without any earlier observation of this firmware's handling of a changed order. It showed nothing about a path-only entry, a second loader, a register or an event, and every row on those rests on the normal runs and pilots named in the row.

## The two boot entries

| | Entry A | Entry B |
|---|---|---|
| Variable | `Boot0002` | `Boot0003` |
| Label the firmware prints | `Lux entry A` | `Lux entry B` |
| File the option names | `\EFI\LUX\A.EFI` | `\EFI\LUX\B.EFI` |
| Attributes | active, part of a normal boot | the same |
| How the file is named | by path only, with no disk in front | the same |
| Loader in the form "same" | the signed loader | the signed loader, the same bytes |
| Loader in the form "different" | the signed loader | the second signed loader (`recorder/guest/second-loader-signed.efi`) |

`BootOrder` in the normal runs: `Boot0002`, `Boot0003`, `Boot0000`, `Boot0001`. The last two are the options the firmware makes for itself in the preparation boot: its setup application, which is not part of a normal boot, and one for the disk. In the changed runs the first two are exchanged.

The disk of a two-entry run holds the two loader files and nothing else. There is no file at the default path `\EFI\BOOT\BOOTX64.EFI`.

## The stores

| Store | How it is made | SHA-256 |
|---|---|---|
| One-entry template | Enrolment boot that writes the keys | `57ec0698…cebf`, pinned in `recorder/testkeys/MANIFEST.json` |
| Two-entry template, order A, B | Enrolment boot that writes `Boot0002`, `Boot0003`, `BootOrder` and then the keys | `12f35963670eab15d8f0ae4210432c0036017f6b4411993df6b43cdaee200abf`, pinned in `recorder/bootentries.py` |
| Two-entry store, order B, A | The same boot with the other order. Not made yet | Not pinned. It is accepted only if it differs from the two-entry template in the value of `BootOrder` and in no other byte |

The check in the last row rests on a claim: when the firmware writes another order, the store file differs in the bytes of that value and nowhere else. The claim was tested without touching the order of A and B. A store the firmware wrote with the order A, B, `Boot0001`, `Boot0000` differs from the two-entry template in two bytes, both inside the value of `BootOrder`, and equals the template after an offline edit of those two bytes.

## What the two-entry normal runs show

These are observations of normal runs. The predictions use them as their baseline.

- **Entry A is started.** The console begins `BdsDxe: loading Boot0002 "Lux entry A" from \EFI\LUX\A.EFI`, and the loader runs to its last line. The firmware found the file from a path-only boot option.
- **30 events**, two more than the plain normal run: the measurements of `Boot0002` and `Boot0003`.
- **Event 14 measures `BootOrder`** into register 1, with eight data bytes. Its digest is the SHA-256 of those eight bytes as they were written. Events 15 to 18 measure `Boot0002`, `Boot0003`, `Boot0000`, `Boot0001`: the order the list gives, not the order of the numbers.
- **Only register 1 differs from the plain normal run.** Registers 0, 2 to 7 and 8 to 23 are equal in all four banks.
- **The two forms are equal** in console, loader report, events, registers and the store after the boot. They differ only in what the recording says lies behind entry B. Nothing else in a normal recording depends on that file.
- **The firmware did not change the order.** It measured the list exactly as the preparation boot had written it. UEFI 2.11 allows a firmware to add options and to remove invalid ones (chapter 3 Boot Manager, opening text, PDF page 152), so this is an observation about this firmware, not a rule.
- **Each form repeats.** `recordings/comparisons/normal-two-same-1_vs_normal-two-same-2.json` and `normal-two-different-1_vs_normal-two-different-2.json` both say `identical: true`.

## The signature byte

The signature area of the signed loader is 1624 bytes, from file offset 38680. Its parts, as `recorder/pe.py` reads them:

| Offset in the area | Bytes | Part |
|---|---|---|
| 0 | 8 | Entry header: length, revision, type |
| 8 | 133 | Structure |
| 141 | 32 | The image digest that was signed (`00c5018d…e50f`, the loader's Authenticode digest) |
| 173 | 4 | Structure |
| 177 | 835 | The signer's certificate (the db certificate) |
| 1012 | 99 | Structure |
| 1111 | 232 | The signed attributes, the record the signature is computed over |
| 1343 | 19 | Structure |
| 1362 | 256 | **The signature value** |
| 1618 | 6 | Padding |

"Structure" is the bytes that only hold the parts together: tags, lengths and identifiers.

**The chosen byte is offset 1490 in the area, file offset 40170: byte 128 of the 256 bytes of the signature value.** Its lowest bit is flipped, so `0xDA` becomes `0xDB`. No other byte of the file changes, and the file's Authenticode digest stays `00c5018d…e50f`, because that digest leaves the whole signature area out.

Two cases, each a counted experiment with its own prediction:

| Experiment | Secure Boot | Compared with | In one sentence, the prediction |
|---|---|---|---|
| `signature-byte` (primary) | on | `normal-1` | Refused like the pilot `e2`, although the file's digest is unchanged |
| `signature-byte-off` | switched off | `normal-1` | Runs, and the record equals the pilot `e4`: the changed byte adds nothing a recording can see |

`signature-byte-off` changes two things against the normal run, the switch and the byte, as the pilot `e1` does. Its prediction says so.

## The predictions

| File | Rows | Required by UEFI | Left to the platform by UEFI | Unread document | This firmware |
|---|---|---|---|---|---|
| `predictions/boot-order-same.json` | 20 | 2 | 1 | 2 | 15 |
| `predictions/boot-order-different.json` | 21 | 2 | 1 | 1 | 17 |
| `predictions/signature-byte.json` | 18 | 1 | 1 | 0 | 16 |
| `predictions/signature-byte-off.json` | 19 | 1 | 1 | 2 | 15 |

Each file opens with `wrong_if`: plain sentences saying what result would prove it wrong. Each names the baseline recording its rows were written against. Each lists under `not_scored` what it expects and cannot check; for the boot order that includes the value of `BootCurrent`, which the loader does not read.

How the rows got their labels:

- **Required by UEFI** only where the verified reading of UEFI 2.11 has a sentence for the behaviour: the boot continues with the stored order, the first element of `BootOrder` is tried first, an image whose signature is not found in `db` is not started, and with `SecureBoot` at 0 nothing is verified. Six rows in all.
- **Left to the platform** where UEFI 2.11 says so in words and the row predicts what this firmware will do with that freedom: the status text of a refusal, the switch that turns checking off with the keys kept, and whether the firmware leaves the written order alone.
- **Unread document** where the expectation goes beyond anything observed and the rule belongs to a document that has not been read: that the measured image digest does not cover the signature area or the file's path, and that the key record in register 7 is the same for two loaders signed with one key. These rows give the observation that makes the expectation plausible and claim nothing about the document.
- **This firmware** for everything that repeats an observation in a committed recording. Every register row is of this kind or the previous one. No row says that a specification assigns a register a purpose.

## How each one is run, once

On a prepared machine, from the repository root. Shown for `boot-order-same`; the three others differ in the names, in the normal run, and in the second line, which only the boot order experiments need.

```
python3 -m recorder prepare
python3 -m recorder prepare --changed-boot-order
python3 -m recorder record boot-order-same-1 --experiment boot-order-same --for-the-record
python3 -m recorder compare recordings/normal-two-same-1/recording.json recordings/boot-order-same-1/recording.json --out recordings/comparisons/normal-two-same-1_vs_boot-order-same-1.json
python3 -m recorder check recordings/comparisons/normal-two-same-1_vs_boot-order-same-1.json --prediction predictions/boot-order-same.json --recording recordings/boot-order-same-1/recording.json --baseline recordings/normal-two-same-1/recording.json --repeat recordings/comparisons/normal-two-same-1_vs_normal-two-same-2.json --out results/boot-order-same.json
```

| Experiment | Normal run to compare with | Repeat comparison |
|---|---|---|
| `boot-order-same` | `normal-two-same-1` | `normal-two-same-1_vs_normal-two-same-2.json` |
| `boot-order-different` | `normal-two-different-1` | `normal-two-different-1_vs_normal-two-different-2.json` |
| `signature-byte`, `signature-byte-off` | `normal-1` | `normal-1_vs_normal-2.json` |

`prepare --changed-boot-order` makes the store with the order B, A by one preparation boot and boots nothing else. It is needed once for both boot order experiments.

**The third line is the counted run.** Since the predictions are committed, the recorder no longer refuses these four experiments for want of one. `record` therefore asks for `--for-the-record`, and without it a counted experiment is refused before the prediction is looked at and before anything is staged. The words exist so that the one run is never made by a command typed to see what happens.

## The rule for the one run

1. A counted experiment is booted **once**, for the record, after its prediction is committed. There is no trial boot of the changed configuration, in whole or in part.
2. The prediction is **never edited** after the run. A row that did not hold is reported as a mismatch.
3. A run that fails for a **technical reason** (a timeout of the tooling, a failed agreement gate, a tool error) is reported as a failed run, and what it left in the work directory is kept. The tool may be repaired and the experiment run again **only if the failed run gave no information about any field the prediction names**. A refused agreement gate after a complete boot does give such information, because the console and the logs exist; a preparation boot that fails does not, because the changed configuration was never booted.
4. If a run is repeated, the fact and the reason are written down next to the result, and the new recording gets a new name. `record` refuses to write a second recording over a counted one.
5. A changed run that reaches neither the loader's last line nor a refusal is recorded as `timeout`. That is a result, not a technical failure, and it is scored.
