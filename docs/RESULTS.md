# Results of the counted experiments

Four counted experiments were each booted **once**, after their prediction was committed, and scored against it. This note gives the two numbers the project's question asks for, every row behind them, and what the numbers do not show. The tables are made from the committed files; the commands at the end make the scores again.

## The two numbers

| | Result |
|---|---|
| Specification-required behaviours met | **6 of 6** |
| Open behaviours predicted correctly | **72 of 72** |
| Mismatches | **none** |

"Specification-required" counts the rows labelled as required by UEFI 2.11, each with a section title and a PDF page. "Open" counts the rows with one of the three other labels:

| Label of an open row | Held |
|---|---|
| Left to the platform by UEFI 2.11 (cited) | 4 of 4 |
| Rule belongs to a document that has not been read | 5 of 5 |
| This firmware's own behaviour, from an earlier recording | 63 of 63 |

| Experiment | Specification-required rows met | Open rows predicted correctly | Mismatches |
|---|---|---|---|
| `signature-byte` | 1 of 1 | 17 of 17 | none |
| `signature-byte-off` | 1 of 1 | 18 of 18 | none |
| `boot-order-same` | 2 of 2 | 18 of 18 | none |
| `boot-order-different` | 2 of 2 | 19 of 19 | none |

No row failed, so there is no mismatch to state. **Read the numbers with the five points below; without them they say more than was shown.**

1. **The rows are not independent, so the row counts are larger than the number of separate predictions.** `first-event-stop` cannot fail when `first-event` holds. `first-console-line` implies `entry-b-first`. `image-digest-absent` and `second-loader-measured` are parts of the rows that list the unpaired events. Most register rows follow from the event rows. Each row could have failed, and none is a separate experiment.
2. **The six specification-required rows cover four behaviours.** "The boot continues with the stored order" and "the first element of `BootOrder` is tried first" are each counted in both forms of the boot order experiment. The other two are "an image whose signature is not found in `db` is not started" and "with `SecureBoot` at 0 nothing is verified".
3. **Most open rows predicted that this firmware would repeat what a pilot or a normal run had already shown.** `signature-byte` predicted a record equal to the pilot `e2` and `signature-byte-off` one equal to the pilot `e4`, row by row. What was not known before the runs was whether a changed signature value would behave like changed content (refused, same events) and whether the measured image digest would ignore the signature area. Both turned out as predicted.
4. **`signature-byte-off` is secondary.** Against its normal run it changes two things, the switch and the byte, so it is not a one-change experiment against `normal-1`. It changes one thing against the pilot `e4`, and `e4` was recorded once for the repository. Its prediction said so before the run. Without it the numbers are 5 of 5 and 54 of 54.
5. **The boot order rows `continues`, `entry-b-first` and `order-measured-as-written` were not written without any earlier observation.** During the early research a boot order was changed once on another configuration (the packaged firmware without Secure Boot, the firmware's own three options, console lines and two variables read, no register or event read), and the test was repeated once. It showed that this firmware tries the option now listed first and leaves the written order as written. `docs/COUNTED.md` declares it. The counted configuration itself, entry B before entry A with Secure Boot on, was booted here for the first time.

## How the runs were made

- **Order of events:** the predictions were committed (`76ce581`, notes reworded in `b6270c1` before any run); an independent audit found no trace of any changed configuration in the repository or the work directory; then each experiment was recorded once with `python3 -m recorder record <experiment>-1 --experiment <experiment> --for-the-record`.
- **The dates, on one clock.** A recording carries its time in UTC. The `written` date in a prediction file is the calendar date at the place of writing, eight hours ahead of UTC. So a prediction that says `written: 2026-11-15` stands beside a run recorded on `2026-11-14`, and that reads as if the run came first. It did not. In UTC the predictions were committed at 2026-11-14T16:13:51Z (`76ce581`) and their notes reworded at 16:41:25Z (`b6270c1`); the four runs were recorded at 16:52:02Z, 16:53:32Z, 16:55:26Z and 16:56:19Z.
- **Each was booted exactly once.** No run failed, none was repeated, none ended as `timeout`. The agreement gate passed in all four.
- **The changed boot order store** was made by one preparation boot (`python3 -m recorder prepare --changed-boot-order`) after the boot order predictions were committed. That boot runs the enrolment program on the empty store; it does not boot the changed order. The store has SHA-256 `6bce1b1d7fcd7e037096fbc574f270946c6491909eaa605eb90a86192eff09c7` and differs from the pinned two-entry template in the value of `BootOrder` only.
- **Before the counted runs, on the same machine,** a fresh plain normal run and a fresh run of each two-entry normal run were equal to the committed ones on every compared field, and a fresh run of the pilot `e2` gave the committed comparison. Those are normal runs and a declared pilot.
- **The recording, not the score, proves that the change was made.** For the two signature experiments every scored row would look the same if the loader had been the pilot's. So each section below quotes `run.change_detail` and the hashes of what was booted.

## `signature-byte`

**Change:** one byte changed inside the loader's signature area, Secure Boot on.

| | |
|---|---|
| Prediction | `predictions/signature-byte.json`, SHA-256 `37eda582ea91f69fde363d22fbc1bba3f208dca99dcc905280aecb7742abbc8a`, last changed in commit `76ce581` |
| Run | `signature-byte-1`, recorded 2026-11-14T16:52:02Z, in commit `8be0f6f`. Recording SHA-256 `d348f1bf959d4a7912709efa31d6349768ccd0e6893ae17ed1db50ddff55965b` |
| Compared with | `normal-1` (`recordings/comparisons/normal-1_vs_signature-byte-1.json`) |
| Score file | `recordings/scores/signature-byte.json` |
| Outcome | `refused`, 26 events, agreement gate passed |
| Proof of the change | `run.change_detail.loader_byte`: file offset 40170, `0xDA` to `0xDB`, signature area, signature value. The loader file booted has SHA-256 `f9a028b6...9496` (the signed loader has `0cb3ced8...8a78`) and Authenticode digest `00c5018d...e50f`, the signed loader's |
| Specification-required rows met | **1 of 1** |
| Open rows predicted correctly | **17 of 17** |
| Mismatches | none |

| Row | Expected | Observed | Basis | Held |
|---|---|---|---|---|
| `refused` | `refused` | `refused` | required by UEFI 2.11 (32.5.1 Overview (under 32.5 UEFI Image Validation), PDF page 1633) | yes |
| `refusal-text` | `BdsDxe: failed to load Boot0001 "UEFI QEMU HARDDISK QM00001 " from PciRoot(0x0)/Pci(0x1F,0x2)/Sata(0x0,0xFFFF,0x0): Access Denied` | `BdsDxe: failed to load Boot0001 "UEFI QEMU HARDDISK QM00001 " from PciRoot(0x0)/Pci(0x1F,0x2)/Sata(0x0,0xFFFF,0x0): Access Denied` | left to the platform by UEFI 2.11 (7.4.1 EFI_BOOT_SERVICES.LoadImage(), PDF page 283) | yes |
| `first-event` | `25` | `25` | this firmware | yes |
| `first-event-stop` | `6` | `6` | this firmware | yes |
| `first-event-in-changed-run` | register 4, `EV_EFI_ACTION`, digest `7044f063...28a6` | register 4, `EV_EFI_ACTION`, digest `7044f063...28a6` | this firmware | yes |
| `pcr0-same` | differing registers do not include 0 | differing: 4, 5, 7 | this firmware | yes |
| `pcr1-same` | differing registers do not include 1 | differing: 4, 5, 7 | this firmware | yes |
| `pcr2-same` | differing registers do not include 2 | differing: 4, 5, 7 | this firmware | yes |
| `pcr3-same` | differing registers do not include 3 | differing: 4, 5, 7 | this firmware | yes |
| `pcr4-differs` | differing registers include 4 | differing: 4, 5, 7 | this firmware | yes |
| `pcr5-differs` | differing registers include 5 | differing: 4, 5, 7 | this firmware | yes |
| `pcr6-same` | differing registers do not include 6 | differing: 4, 5, 7 | this firmware | yes |
| `pcr7-differs` | differing registers include 7 | differing: 4, 5, 7 | this firmware | yes |
| `events-only-in-normal-run` | event 25, register 7, `EV_EFI_VARIABLE_AUTHORITY`, digest `3af94976...9ece`<br>event 26, register 4, `EV_EFI_BOOT_SERVICES_APPLICATION`, digest `00c5018d...e50f`<br>event 27, register 5, `EV_EFI_ACTION`, digest `d8043d6b...b41b`<br>event 28, register 5, `EV_EFI_ACTION`, digest `b54f7542...eba0` | event 25, register 7, `EV_EFI_VARIABLE_AUTHORITY`, digest `3af94976...9ece`<br>event 26, register 4, `EV_EFI_BOOT_SERVICES_APPLICATION`, digest `00c5018d...e50f`<br>event 27, register 5, `EV_EFI_ACTION`, digest `d8043d6b...b41b`<br>event 28, register 5, `EV_EFI_ACTION`, digest `b54f7542...eba0` | this firmware | yes |
| `events-only-in-changed-run` | event 25, register 4, `EV_EFI_ACTION`, digest `7044f063...28a6`<br>event 26, register 4, `EV_EFI_ACTION`, digest `3d6772b4...33ba` | event 25, register 4, `EV_EFI_ACTION`, digest `7044f063...28a6`<br>event 26, register 4, `EV_EFI_ACTION`, digest `3d6772b4...33ba` | this firmware | yes |
| `image-digest-absent` | list includes event 26, register 4, `EV_EFI_BOOT_SERVICES_APPLICATION`, digest `00c5018d...e50f` | event 25, register 7, `EV_EFI_VARIABLE_AUTHORITY`, digest `3af94976...9ece`<br>event 26, register 4, `EV_EFI_BOOT_SERVICES_APPLICATION`, digest `00c5018d...e50f`<br>event 27, register 5, `EV_EFI_ACTION`, digest `d8043d6b...b41b`<br>event 28, register 5, `EV_EFI_ACTION`, digest `b54f7542...eba0` | this firmware | yes |
| `console-first-difference` | `2` | `2` | this firmware | yes |
| `loader-report-empty` | `1` | `1` | this firmware | yes |

The label of the row `refused` needs one sentence. UEFI 2.11 says that an image whose signature is not found in the authorised database is not started; its own words are that the image is "deferred" and the next boot option is selected. That a signature value with one bit changed cannot be found there is a property of the signature scheme, which UEFI does not describe. The row held, so the question of how to report the other outcome did not arise.

Beyond the rows: `signature-byte-1` equals the pilot `e2` in console, loader report, every event, every register in all four banks and the store after the boot. The two runs booted different files: `e2` has a changed content byte and another Authenticode digest, this run has the signed loader's digest and a changed signature value. This firmware treated both the same way and logged no image digest for either.

## `signature-byte-off`

**Change:** one byte changed inside the loader's signature area, Secure Boot switched off.

| | |
|---|---|
| Prediction | `predictions/signature-byte-off.json`, SHA-256 `26b58fc8da7a69ba61323ed2ae555b6289352755cb9c2f0cbcc5b60faf11412d`, last changed in commit `b6270c1` |
| Run | `signature-byte-off-1`, recorded 2026-11-14T16:53:32Z, in commit `0347a16`. Recording SHA-256 `0925a7a63ccba34e0eb4cfa09cf601701110b1de990ef298a02f7d3a14226087` |
| Compared with | `normal-1` (`recordings/comparisons/normal-1_vs_signature-byte-off-1.json`) |
| Score file | `recordings/scores/signature-byte-off.json` |
| Outcome | `accepted`, 27 events, agreement gate passed |
| Proof of the change | `run.change_detail.loader_byte`: file offset 40170, `0xDA` to `0xDB`, signature area, signature value. The loader file booted has SHA-256 `f9a028b6...9496` (the signed loader has `0cb3ced8...8a78`) and Authenticode digest `00c5018d...e50f`, the signed loader's; `run.change_detail.store_edits`: `secure-boot-off` |
| Specification-required rows met | **1 of 1** |
| Open rows predicted correctly | **18 of 18** |
| Mismatches | none |

| Row | Expected | Observed | Basis | Held |
|---|---|---|---|---|
| `accepted` | `accepted` | `accepted` | required by UEFI 2.11 (3.3 Globally Defined Variables, PDF page 166) | yes |
| `no-refusal` | none | none | this firmware | yes |
| `switch-reported-off` | register 7, `EV_EFI_VARIABLE_DRIVER_CONFIG`, digest `115aa827...02d8` | register 7, `EV_EFI_VARIABLE_DRIVER_CONFIG`, digest `115aa827...02d8` | left to the platform by UEFI 2.11 (3.3 Globally Defined Variables, PDF page 166) | yes |
| `first-event` | `4` | `4` | this firmware | yes |
| `first-event-stop` | `4` | `4` | this firmware | yes |
| `pcr0-same` | differing registers do not include 0 | differing: 7 | this firmware | yes |
| `pcr1-same` | differing registers do not include 1 | differing: 7 | this firmware | yes |
| `pcr2-same` | differing registers do not include 2 | differing: 7 | this firmware | yes |
| `pcr3-same` | differing registers do not include 3 | differing: 7 | this firmware | yes |
| `pcr4-same` | differing registers do not include 4 | differing: 7 | unread document | yes |
| `pcr5-same` | differing registers do not include 5 | differing: 7 | this firmware | yes |
| `pcr6-same` | differing registers do not include 6 | differing: 7 | this firmware | yes |
| `pcr7-differs` | differing registers include 7 | differing: 7 | this firmware | yes |
| `events-only-in-normal-run` | event 4, register 7, `EV_EFI_VARIABLE_DRIVER_CONFIG`, digest `ccfc4bb3...a40e`<br>event 25, register 7, `EV_EFI_VARIABLE_AUTHORITY`, digest `3af94976...9ece` | event 4, register 7, `EV_EFI_VARIABLE_DRIVER_CONFIG`, digest `ccfc4bb3...a40e`<br>event 25, register 7, `EV_EFI_VARIABLE_AUTHORITY`, digest `3af94976...9ece` | this firmware | yes |
| `events-only-in-changed-run` | event 4, register 7, `EV_EFI_VARIABLE_DRIVER_CONFIG`, digest `115aa827...02d8` | event 4, register 7, `EV_EFI_VARIABLE_DRIVER_CONFIG`, digest `115aa827...02d8` | this firmware | yes |
| `image-digest-present` | list does not include event 26, register 4, `EV_EFI_BOOT_SERVICES_APPLICATION`, digest `00c5018d...e50f` | event 4, register 7, `EV_EFI_VARIABLE_DRIVER_CONFIG`, digest `ccfc4bb3...a40e`<br>event 25, register 7, `EV_EFI_VARIABLE_AUTHORITY`, digest `3af94976...9ece` | unread document | yes |
| `console-first-difference` | `6` | `6` | this firmware | yes |
| `console-first-difference-text` | `LUX MemoryMapSize=0000000000001860` | `LUX MemoryMapSize=0000000000001860` | this firmware | yes |
| `loader-report-first-difference` | `28` | `28` | this firmware | yes |

Beyond the rows: `signature-byte-off-1` equals the pilot `e4` in console, loader report, every event, every register in all four banks and the store after the boot. Register 4 holds the same image digest as in the normal run, although the file's SHA-256 differs: the digest this firmware measured does not cover the changed byte. That is an observation of this firmware. Which bytes a measurement must cover is defined in documents that have not been read for this project.

## `boot-order-same`

**Change:** BootOrder lists entry B before entry A, written in a preparation boot; both entries hold the same signed loader.

| | |
|---|---|
| Prediction | `predictions/boot-order-same.json`, SHA-256 `7ef1d8cd8f5260aa5b92bfb4cc93fee9dfc87c2624345555e19aea5c6423a80f`, last changed in commit `b6270c1` |
| Run | `boot-order-same-1`, recorded 2026-11-14T16:55:26Z, in commit `4aebe41`. Recording SHA-256 `6b4ffac17532c11a106a34d59af0c1c8e048e15e1bffbd358e328582d1fa4573` |
| Compared with | `normal-two-same-1` (`recordings/comparisons/normal-two-same-1_vs_boot-order-same-1.json`) |
| Score file | `recordings/scores/boot-order-same.json` |
| Outcome | `accepted`, 30 events, agreement gate passed |
| Proof of the change | `run.change_detail.boot_order`: `Boot0003`, `Boot0002`, `Boot0000`, `Boot0001`. The store booted has SHA-256 `6bce1b1d...09c7` (the two-entry template has `12f35963...0abf`); staging accepted it because it differs from that template in the value of `BootOrder` and in no other byte |
| Specification-required rows met | **2 of 2** |
| Open rows predicted correctly | **18 of 18** |
| Mismatches | none |

| Row | Expected | Observed | Basis | Held |
|---|---|---|---|---|
| `continues` | `accepted` | `accepted` | required by UEFI 2.11 (3 Boot Manager (opening text), PDF page 152) | yes |
| `entry-b-first` | text contains `Boot0003` | `BdsDxe: loading Boot0003 "Lux entry B" from \EFI\LUX\B.EFI` | required by UEFI 2.11 (3.3 Globally Defined Variables (Table 3.3 Global Variables), PDF page 165) | yes |
| `first-console-line` | `BdsDxe: loading Boot0003 "Lux entry B" from \EFI\LUX\B.EFI` | `BdsDxe: loading Boot0003 "Lux entry B" from \EFI\LUX\B.EFI` | this firmware | yes |
| `console-first-difference` | `1` | `1` | this firmware | yes |
| `no-refusal` | none | none | this firmware | yes |
| `order-measured-as-written` | register 1, `EV_EFI_VARIABLE_BOOT`, digest `af165fc3...651d` | register 1, `EV_EFI_VARIABLE_BOOT`, digest `af165fc3...651d` | left to the platform by UEFI 2.11 (3 Boot Manager (opening text), PDF page 152) | yes |
| `first-event` | `14` | `14` | this firmware | yes |
| `first-event-stop` | `5` | `5` | this firmware | yes |
| `pcr0-same` | differing registers do not include 0 | differing: 1 | this firmware | yes |
| `pcr1-differs` | differing registers include 1 | differing: 1 | this firmware | yes |
| `pcr2-same` | differing registers do not include 2 | differing: 1 | this firmware | yes |
| `pcr3-same` | differing registers do not include 3 | differing: 1 | this firmware | yes |
| `pcr4-same` | differing registers do not include 4 | differing: 1 | unread document | yes |
| `pcr5-same` | differing registers do not include 5 | differing: 1 | this firmware | yes |
| `pcr6-same` | differing registers do not include 6 | differing: 1 | this firmware | yes |
| `pcr7-same` | differing registers do not include 7 | differing: 1 | unread document | yes |
| `events-only-in-normal-run` | event 14, register 1, `EV_EFI_VARIABLE_BOOT`, digest `6fefab5c...fe30` | event 14, register 1, `EV_EFI_VARIABLE_BOOT`, digest `6fefab5c...fe30` | this firmware | yes |
| `events-only-in-changed-run` | event 14, register 1, `EV_EFI_VARIABLE_BOOT`, digest `af165fc3...651d` | event 14, register 1, `EV_EFI_VARIABLE_BOOT`, digest `af165fc3...651d` | this firmware | yes |
| `loader-report-equal` | no difference | no difference | this firmware | yes |
| `nothing-else-differs` | `event_log.sha256`<br>`provenance.boot_order`<br>`provenance.vars_template_sha256`<br>`vars_after_sha256` | `event_log.sha256`<br>`provenance.boot_order`<br>`provenance.vars_template_sha256`<br>`vars_after_sha256` | this firmware | yes |

## `boot-order-different`

**Change:** BootOrder lists entry B before entry A, written in a preparation boot; entry B holds a second signed loader.

| | |
|---|---|
| Prediction | `predictions/boot-order-different.json`, SHA-256 `8356de599a86a9d25d64bef1d2b66eeec7f51e5ae50b6eca5e4a489a89de242d`, last changed in commit `b6270c1` |
| Run | `boot-order-different-1`, recorded 2026-11-14T16:56:19Z, in commit `583d15f`. Recording SHA-256 `c72bdfacc169f4e201819a2c45dc8abdc1829561e8456f7ea9ffc337f2b1ffa6` |
| Compared with | `normal-two-different-1` (`recordings/comparisons/normal-two-different-1_vs_boot-order-different-1.json`) |
| Score file | `recordings/scores/boot-order-different.json` |
| Outcome | `accepted`, 30 events, agreement gate passed |
| Proof of the change | `run.change_detail.boot_order`: `Boot0003`, `Boot0002`, `Boot0000`, `Boot0001`. The store booted has SHA-256 `6bce1b1d...09c7` (the two-entry template has `12f35963...0abf`); staging accepted it because it differs from that template in the value of `BootOrder` and in no other byte |
| Specification-required rows met | **2 of 2** |
| Open rows predicted correctly | **19 of 19** |
| Mismatches | none |

| Row | Expected | Observed | Basis | Held |
|---|---|---|---|---|
| `continues` | `accepted` | `accepted` | required by UEFI 2.11 (3 Boot Manager (opening text), PDF page 152) | yes |
| `entry-b-first` | text contains `Boot0003` | `BdsDxe: loading Boot0003 "Lux entry B" from \EFI\LUX\B.EFI` | required by UEFI 2.11 (3.3 Globally Defined Variables (Table 3.3 Global Variables), PDF page 165) | yes |
| `first-console-line` | `BdsDxe: loading Boot0003 "Lux entry B" from \EFI\LUX\B.EFI` | `BdsDxe: loading Boot0003 "Lux entry B" from \EFI\LUX\B.EFI` | this firmware | yes |
| `console-first-difference` | `1` | `1` | this firmware | yes |
| `no-refusal` | none | none | this firmware | yes |
| `order-measured-as-written` | register 1, `EV_EFI_VARIABLE_BOOT`, digest `af165fc3...651d` | register 1, `EV_EFI_VARIABLE_BOOT`, digest `af165fc3...651d` | left to the platform by UEFI 2.11 (3 Boot Manager (opening text), PDF page 152) | yes |
| `first-event` | `14` | `14` | this firmware | yes |
| `first-event-stop` | `5` | `5` | this firmware | yes |
| `pcr0-same` | differing registers do not include 0 | differing: 1, 4 | this firmware | yes |
| `pcr1-differs` | differing registers include 1 | differing: 1, 4 | this firmware | yes |
| `pcr2-same` | differing registers do not include 2 | differing: 1, 4 | this firmware | yes |
| `pcr3-same` | differing registers do not include 3 | differing: 1, 4 | this firmware | yes |
| `pcr4-differs` | differing registers include 4 | differing: 1, 4 | this firmware | yes |
| `pcr5-same` | differing registers do not include 5 | differing: 1, 4 | this firmware | yes |
| `pcr6-same` | differing registers do not include 6 | differing: 1, 4 | this firmware | yes |
| `pcr7-same` | differing registers do not include 7 | differing: 1, 4 | unread document | yes |
| `events-only-in-normal-run` | event 14, register 1, `EV_EFI_VARIABLE_BOOT`, digest `6fefab5c...fe30`<br>event 28, register 4, `EV_EFI_BOOT_SERVICES_APPLICATION`, digest `00c5018d...e50f` | event 14, register 1, `EV_EFI_VARIABLE_BOOT`, digest `6fefab5c...fe30`<br>event 28, register 4, `EV_EFI_BOOT_SERVICES_APPLICATION`, digest `00c5018d...e50f` | this firmware | yes |
| `events-only-in-changed-run` | event 14, register 1, `EV_EFI_VARIABLE_BOOT`, digest `af165fc3...651d`<br>event 28, register 4, `EV_EFI_BOOT_SERVICES_APPLICATION`, digest `cef0a974...1432` | event 14, register 1, `EV_EFI_VARIABLE_BOOT`, digest `af165fc3...651d`<br>event 28, register 4, `EV_EFI_BOOT_SERVICES_APPLICATION`, digest `cef0a974...1432` | this firmware | yes |
| `second-loader-measured` | list includes event 28, register 4, `EV_EFI_BOOT_SERVICES_APPLICATION`, digest `cef0a974...1432` | event 14, register 1, `EV_EFI_VARIABLE_BOOT`, digest `af165fc3...651d`<br>event 28, register 4, `EV_EFI_BOOT_SERVICES_APPLICATION`, digest `cef0a974...1432` | this firmware | yes |
| `loader-report-equal` | no difference | no difference | this firmware | yes |
| `nothing-else-differs` | `event_log.sha256`<br>`provenance.boot_order`<br>`provenance.vars_template_sha256`<br>`vars_after_sha256` | `event_log.sha256`<br>`provenance.boot_order`<br>`provenance.vars_template_sha256`<br>`vars_after_sha256` | this firmware | yes |

Beyond the rows of the two boot order runs, read from the recordings:

- **The measurements of the two entries exchanged places.** In the normal runs events 15 and 16 measure `Boot0002` and then `Boot0003`; in both changed runs they measure `Boot0003` and then `Boot0002`. The predictions expected this under `not_scored`, because a comparison pairs events wherever they stand.
- **Entry A was not tried.** Neither changed run has a refusal line or an event of a second attempt.
- **The digest of event 14** is `af165fc3...651d`, the SHA-256 of the eight bytes `03 00 02 00 00 00 01 00`, the order as the preparation boot wrote it.
- **The store after the boot** is the same file in both forms.
- **`BootCurrent` was not read.** UEFI 2.11 says what it should hold; no recording shows it.

## The pilots, not counted

Four experiments were tried during the early research, before any prediction existed. They have no prediction and no score, and they are in none of the numbers above. `docs/PILOTS.md` describes each.

| Pilot | What it changes | What the recording shows | Registers that differ from the normal run |
|---|---|---|---|
| `e1` | One byte of the loader's content, Secure Boot switched off | The changed loader ran | 4, 7 |
| `e2` | The same byte, Secure Boot on | Refused, `Access Denied` | 4, 5, 7 |
| `e4` | Secure Boot switched off, nothing else | The signed loader ran | 7 |
| `e5` | The signed loader's hash added to the revocation list (`dbx`) | Refused, `Access Denied` | 4, 5, 7 |

One counted experiment has not been run: `rebuilt-firmware`. No such firmware has been built, it has no prediction, and the recorder refuses it.

## Limits

- **One run each.** A counted experiment is booted once by rule, so nothing here says how often a changed run repeats. The normal runs they are compared with were each recorded twice and are identical.
- **One firmware build in one virtual machine**, with a software TPM, under software emulation: OVMF 2024.02 as packaged by Ubuntu, QEMU 8.2.2, swtpm 0.7.3. Nothing here shows what another build or any vendor's firmware on real hardware does.
- **"Required by UEFI 2.11" means: the cited sentence was found in a reading of that document, by section title and PDF page.** It is this project's reading, not a conformance test. Four behaviours were checked, out of a specification of many hundred pages.
- **No row says what a Trusted Computing Group document requires.** The document that defines the event log and the use of the registers has not been read. Every register and event row is an observation of this firmware, and event type names are the names a tool prints.
- **The blindness of the runs rests on the repository's history and one audit**, not on a mechanism that could not have been bypassed. The recorder refuses a counted experiment without a committed prediction; it cannot prove that nobody booted the configuration with other tools. The audit read every variable store and loader file in the work directory before the runs and found none of a changed configuration.
- **The prediction notes were reworded once after the first commit and before any run** (`b6270c1`): three files, notes on what a citation covers, no expected value. `signature-byte.json` is unchanged since `76ce581`. Each recording stores the hash and commit of the prediction it ran under.
- **The predictions were written with the pilots and the normal runs in sight.** That is what "this firmware" as a basis means. A high count of open rows therefore shows that the firmware is consistent with itself across these changes more than it shows foresight.
- **What a recording cannot see was not scored:** the value of `BootCurrent`, and the table in which UEFI says a refused image is recorded.
- **The changed boot order was written by a preparation boot and the machine was switched off before the recorded boot.** A change of the order while the machine runs, or by an operating system, was not tested.
- **The test certificates are not yet valid at the guest's fixed clock**, and this firmware accepts them all the same, in the normal runs as in these.

## Checked a second time

After the runs, a second check was made by someone who ran none of them, with a script that shares no code with the recorder. Nothing was booted for it. It found no difference from this note.

| What was checked | Result |
|---|---|
| The four scores, made again from the recordings and the prediction files: the comparison fields recomputed from the two recordings, then every row judged | 6 of 6 and 72 of 72, no mismatch. Every row verdict equals the committed score file, and every recomputed comparison field equals the committed comparison |
| The registers of all 14 committed recordings, replayed from `eventlog.bin` with a separate parser, in all four hash banks | 96 of 96 values equal in each recording. Every digest that is defined by its event's own data was recomputed and is equal |
| The gate block of each recording | `passed`, and all seven checks true, in all 14 |
| Each prediction: the file on disk, the hash stored in the recording, the file read out of the commit the recording names, and the file at the head of the history | The same SHA-256 in all four places, for all four predictions |
| Order in the history | Both prediction commits are ancestors of every commit that adds a counted recording |
| The run directories left on the machine | One directory and one attempt marker per counted run. Each TPM log holds one start-up command, and each console log one boot |
| Every variable store and loader file on the machine | The only stores that list entry B first, and the only loader files with the changed signature byte, were written after the prediction commits: by the preparation boot and by the four runs |
| The changed loader, made again from the committed signed loader by flipping the lowest bit of the byte at file offset 40170 | SHA-256 `f9a028b6f2544a7e03f007b6058c3b45ebc930e094e0a92de0d902938e0b9496`, as recorded. The byte lies in the 256 bytes of the signature value |
| The store with the changed order against the two-entry template | Two bytes differ, both inside the value of `BootOrder` |

What this check cannot show: file times and commit times can be set by hand, and it was made on the same machine as the runs. It shows that the files agree with each other and with this note, not that no other boot was ever made.

## Checking the scores

From the repository root. Nothing is booted.

```
python3 -m recorder compare recordings/normal-1/recording.json recordings/signature-byte-1/recording.json --out /tmp/c.json
python3 -m recorder check /tmp/c.json --prediction predictions/signature-byte.json --recording recordings/signature-byte-1/recording.json --baseline recordings/normal-1/recording.json --repeat recordings/comparisons/normal-1_vs_normal-2.json
```

```
specification-required rows met: 1 of 1
open rows predicted correctly: 17 of 17
mismatches: none
```

The other three are checked the same way, with the normal run and the repeat comparison that `docs/COUNTED.md` lists for each. `check` refuses when the prediction file is not the one the run was recorded under, so an edited prediction cannot be scored.
