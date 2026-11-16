# Lux

_What your laptop does before it wakes: one boot of open-source UEFI firmware, told from reset to the moment firmware hands the machine over and recorded from the firmware's first measurement on, and what happens when one thing in that chain is changed._

![Lux. Before light. What your laptop does before it wakes. An open laptop with a dark screen, in front of the first line of light on the horizon before sunrise.](docs/cover.webp)

**Live site:** https://lejie710.github.io/lux/

## The question

**When one thing in a PC's boot chain is changed, what does the specification require, what does it leave open, and what does this firmware actually do?**

Lux records one boot of open-source UEFI firmware in a virtual machine, up to the moment firmware hands the machine to the operating system. The recording begins at the firmware's first measurement; the steps before it are described, not recorded. Then it changes one thing and boots again, and puts the normal run and the changed run side by side. Before each counted experiment, a prediction was committed, and every row of it says where it comes from: required by the UEFI specification, left to the platform by that specification, belonging to a Trusted Computing Group document that was not read, or this firmware's own behaviour.

## What the evidence shows

**In four counted experiments, each booted once after its prediction was committed, this firmware met 6 of 6 specification-required rows and 72 of 72 open rows were predicted correctly, with no mismatch. Those are counts of rows, not of independent findings: the 6 required rows cover 4 behaviours, and most of the 72 open rows predicted that this firmware would repeat what a normal run or a pilot had already shown.** So the larger number shows that this firmware is consistent with itself across these changes more than it shows foresight.

Read the numbers with these beside them:

- **Four further experiments are pilots.** They were tried before any prediction existed, so they are shown and never counted: they have no prediction and no score, and they are in none of the numbers.
- **One of the four counted experiments is secondary.** `signature-byte-off` changes two things against its normal run. Without it the numbers are 5 of 5 and 54 of 54.
- **Three boot order rows were not written without any earlier observation.** An early test on another configuration had already shown this firmware trying the option listed first.
- **One firmware build, one virtual machine, a software TPM, one run each.** Nothing here shows what any vendor's firmware does on real hardware, or how often a changed run repeats.
- **"Required" means a sentence found in a reading of UEFI 2.11**, cited by section title and PDF page. It is this project's reading of four behaviours, not a conformance test. The chapters the story needs were read page by page and the rest was searched by keyword; some chapters were not read.
- **No row says what a Trusted Computing Group document requires, and no stop says what the Platform Initialization specification requires.** Neither was read. Every statement about a TPM register or a logged event is an observation of this firmware, and the phase names SEC, PEI, DXE and BDS are taken from the firmware's own source, read at the EDK II project's master branch and not at the tag the packaged build was made from.

| Counted experiment | The one thing changed | Specification-required rows met | Open rows predicted correctly |
|---|---|---|---|
| `signature-byte` | One byte inside the signature value of the loader, Secure Boot on | 1 of 1 | 17 of 17 |
| `signature-byte-off` (secondary) | The same byte, Secure Boot switched off | 1 of 1 | 18 of 18 |
| `boot-order-same` | `BootOrder` lists entry B before entry A; both hold the same signed loader | 2 of 2 | 18 of 18 |
| `boot-order-different` | The same change; entry B holds a second signed loader | 2 of 2 | 19 of 19 |

| Claim | Evidence | Where |
|---|---|---|
| The two numbers are what the files say | One score file per counted run, with a verdict for every row. A test makes each score again from the committed recording, comparison and prediction, and pins the totals | `recordings/scores/`, `docs/RESULTS.md`, `recorder/tests/test_committed_recordings.py` |
| Each prediction came before its run | Each counted recording stores the path, hash and commit of the prediction it ran under, and the recorder refuses a counted run whose prediction file is not byte for byte the committed one. The prediction commits are ancestors of the recording commits | `recordings/<run>/recording.json` field `provenance.prediction`, `docs/RESULTS.md` "How the runs were made" |
| The normal run repeats | Each of the three normal runs was recorded twice, and each pair is identical on every compared field | `recordings/comparisons/*-1_vs_*-2.json` |
| A recording follows from its boot | Three readings of each boot (the firmware's event log, the TPM's own log, the registers read from the TPM) agree on all 24 registers in four hash banks, in all 14 recordings. A test replays every committed event log | field `gate` of each recording, `eventlog.bin` beside it |
| Every line the site quotes is in a recording | A check compares each evidence line with the field it names, letter for letter, and fails if a claim has no basis or a UEFI basis has no full citation | `scripts/check_content.py`: 357 claims, 28 screens |
| Every byte value the story states is in the raw event log | The story states a few values that `recording.json` does not hold (it keeps each record's size and digest): the Secure Boot switch, the stored boot order, the first bytes and the names of the two boot options, and that the 851 bytes of the key record are the end of the 879 bytes of the allowed list. A test reads each from the committed `eventlog.bin` and compares it with the sentence in the content | `recorder/tests/test_recorded_bytes.py`, `recordings/normal-1/eventlog.bin` |
| The pilots are what they are said to be | Four recordings and their comparisons with the normal run, described one by one | `docs/PILOTS.md` |

What one changed byte looks like on the site. This run is a pilot:

![The experiments page: two laptops side by side. On the left, screen lit: "Untouched, the loader is started." On the right, screen dark: "With one byte changed, the loader is never started", with the console line that ends in "Access Denied". A label says the run is a pilot, shown and not counted.](docs/images/experiment.png)

## Limits

What this project does not show, stated so that nobody has to find out.

- **A virtual machine, not a real one.** QEMU under software emulation. Power sequencing, the first step of a real boot, does not exist there, so the first stop is described from documents and says so.
- **A software TPM** (swtpm), not a hardware chip.
- **One build of open-source firmware** (OVMF, built from EDK II, as packaged by Ubuntu). Another firmware may make every platform choice differently.
- **A release build.** It prints no log of its early phases, so the recording begins with what the firmware measured, not with what it did internally. Stop 2 shows nothing recorded, and says so.
- **Two documents were not read.** The Trusted Computing Group document that defines the event log and the use of the registers could not be obtained. The Platform Initialization specification, where the phase names come from, was not read. Event type names are the names the tool `tpm2_eventlog` prints, and the assignment of an event to a story stop is this project's own, declared rule by rule in `recorder/storymap.py`.
- **The paraphrases of UEFI 2.11 were checked by reading, not by a test.** The content check proves that a citation is complete and that a quoted line is in a recording. It cannot prove that a sentence about the specification is right.
- **Each counted experiment was booted once.** A single run says nothing about how often a changed run repeats.
- **The predictions were written with the pilots and the normal runs in sight.** That is what "this firmware" as a basis means.
- **The blindness of the counted runs rests on the repository's history and one audit**, not on a mechanism that could not have been bypassed. The recorder refuses a counted run without a committed prediction; it cannot prove that nobody booted that configuration with other tools. The audit's script and its output are not in the repository; `docs/RESULTS.md`, "Checked a second time", says which of its rows a reader can repeat from the committed files.
- **One machine, one set of tool versions.** Another QEMU version, machine type or firmware package may give other register values; the recorder then says so instead of producing a recording that looks comparable. The recordings were made and repeated on one machine only, Ubuntu 24.04 under WSL 2. `prepare` refuses any firmware file but the one from the Ubuntu package `ovmf` `2024.02-2ubuntu0.10`, and any assembler or linker that builds other loader bytes, so another distribution or release has never passed and may be refused.
- **The pilots edit the variable store file while the machine is off.** `e5` writes the revocation record directly and not through a signed update, so it shows how this firmware treats a list that is there, not how it treats an update.
- **The loader does not read `BootCurrent`**, so no recording can show it.
- **The test keys are public**, private halves included, so that the recordings can be reproduced. Never trust them anywhere. See `recorder/testkeys/README.md`.
- **The test certificates are not yet valid at the guest's fixed clock**, and this firmware accepts them all the same. That is observed behaviour.
- **The pictures are illustrations** of a fictional laptop and board. They show where the story is and prove nothing.

Not tested, and carried here from `docs/VERIFICATION.md`:

- **No automated test opens a browser.** The site's tests render pages to HTML. Motion, layout and focus were checked by eye and by a scripted drive in one Chromium-based browser at 1440 x 900, 430 x 932, 390 x 844 and 375 x 812; the three screens that show the whole laptop were also read at thirteen window sizes between 800 and 1440 px across. Firefox, a phone held sideways, a window under 600 px tall and a screen reader have not been tested. Motion was judged by the timing a script read and by the author's own scrolling, not by a second person.
- **One phone was tried, and the story failed on it.** On an iPhone, in its own browser, the published build of commit `3a2767e` ended the page after a little scrolling of the story; the still page and a frozen step stayed up. The board is now drawn in another way, so that the memory its picture takes no longer grows with the screen's density (`docs/VERIFICATION.md` section 13). That was measured only in a desktop Chromium-based browser made to look like a phone, at device pixel ratios of 1, 2 and 3. It is not known that it ends the fault until the new build has been opened on that phone.
- **The hosted runner boots nothing.** `.github/workflows/check.yml` passed on a hosted runner at commits `6dab704` and `0fa1d15`, and `.github/workflows/deploy.yml` at `0fa1d15`. That shows the offline commands pass on one runner image at those commits. The six tests that boot a virtual machine are skipped there, and no recording was ever made by a runner.
- **The live site was walked once, in one browser.** After the first deployment the public address was opened in a new, empty profile of one Chromium-based desktop browser, at 1440 x 900 and in an emulated 390 x 844 window (`docs/VERIFICATION.md` section 12). The preview of a pasted link was read from the tags as served; no preview service was asked to fetch the page. The 13 links that lead to other sites were not requested in that walk.
- **Process cleanup when the virtual machine is killed from outside** is covered by the integration test and a script, not by a unit test.

## Non-goals

| Not in this project | Why |
|---|---|
| A recording of a real laptop or board | Real firmware is a vendor's code and not a public source. Every step here is meant to be repeatable on Ubuntu 24.04 with the pinned package versions; it has been repeated on one machine only. This is the project's largest limit |
| Vendor-specific firmware behaviour | The project is vendor-neutral |
| Hardware error handling | Out of scope |
| Anything after the handoff: kernel start-up, an operating system's own boot manager | The story ends when firmware steps back |
| An attack tutorial: no bypass of Secure Boot, no reproduction of a known vulnerability | Each experiment changes one thing on the project's own virtual machine to see how the protection reacts. That is validation |
| A live virtual machine in the browser | Readers see recorded evidence |
| A course with quizzes, progress or accounts; other languages; a polished phone version | It is an explainer for a wide screen, readable on a phone, in English |
| A measure of whether readers understand it | No reader study was run |

## What the site shows

![The opening screen of the site: a laptop before power, dark, with the words "Lux. Before light. What your laptop does before it wakes." and an invitation to scroll that names the author: "An explainer of the UEFI boot by Le Jie Tan, from public specifications and one recorded boot".](docs/images/opening.png)

![Stop 6 of 7, "Load and verify": the statement "Before the loader runs, firmware checks who signed it", a circuit board whose lit parts rest at half their light, one line from the recording (PCR 7, EV_EFI_VARIABLE_AUTHORITY, "variable db, 851 data bytes") and the control "Open the evidence".](docs/images/stop-6.png)

- **The story**: the opening, the way inside the machine, and seven stops from power and reset to the handoff, in 22 steps. A screen holds one statement, one line copied from a recording, a citation marker and "Open the evidence". Behind that control are the console lines, the log records with their digests, the register values, every claim with its basis label and source, the terms, and what the recording does not show.
- **The experiments**: the two numbers as the score files have them, with what they do not show directly under them; the normal run and a changed run side by side; a card per pilot and per counted experiment; and what the specification leaves open.
- **The sources**: what was read or run, what was not read and what that costs the reader, the limits, a glossary with a filter, and one recording's own account of how it was made.

The site holds no fact of its own. Its words come from `content/`, and what has been run, compared, predicted and scored is read from the files when it is built. The pictures are illustrations; the evidence is the recording.

### The live site

The site is live at https://lejie710.github.io/lux/. It is the build of this repository's `main` branch, published by `.github/workflows/deploy.yml` (see "Hosting"). After the first deployment, on 2026-11-15 at commit `0fa1d15`, the public address was opened in a new, empty browser profile and walked from the opening to the last step, through both pages and by address; `docs/VERIFICATION.md` section 12 is the record. What that one walk supports, and no more:

- **Where it works.** Seen working in one Chromium-based desktop browser at 1440 x 900, and in a 390 x 844 window with phone emulation in the same browser. Firefox, Safari, a physical phone, a touch scroll and a screen reader were not tried in that walk. An iPhone was tried afterwards, and the story of that build did not stay up on it: see "Limits".
- **The first load.** A first visit asks for 14 files, about 0.66 MB as sent and 1.44 MB uncompressed: about 0.28 MB is what the opening screen uses, and about 0.37 MB is the pictures of the later steps, which arrive in the background. Scrolling the whole story asks for nothing more. The host compresses text with gzip and lets a browser keep a file for ten minutes; both are the host's behaviour and not a setting of this repository. Measured on one connection.
- **What leaves the device.** In that walk every request went to `lejie710.github.io` and every one was a plain read. No cookie was set or sent, and nothing was written to the browser's storage. The site has one input, the glossary filter: typing in it made no request, and what was typed was gone after a reload. The host itself receives a visitor's network address and browser name, as any web server does. The links to other sites (the firmware project's source files, the specification, the earlier site) ask those sites for something only when a reader follows one.

### Run it locally

Needs Node.js 22.12 or later in the 22 line, 24, or 26 and later (`engines` in `site/package.json`); only 24.22.0 with npm 11.19.1 has been used. `npm ci` downloads the pinned packages once; after that nothing is fetched. No address of another site is requested by the site's source, so the page asks no other address for anything; that was read from the source, and on the live site it was also measured in a browser (above).

```
cd site
npm ci
npm run dev
```

`npm ci` prints a line like `added 47 packages, and audited 48 packages in 7s` (the time varies), then a note on funding and `found 0 vulnerabilities`. Open `http://127.0.0.1:5183/`. It is the same site as the live one, built from the working tree.

The port is fixed, and the command stops with `Port 5183 is already in use` when something else holds it. Then name another one, and open that address:

```
npm run dev -- --port 5191
```

| Address | What it shows |
|---|---|
| `/` | The story, pinned while the page scrolls through its steps |
| `/?static` | Every step as a still section, one under the other. A reader who prefers reduced motion gets this without asking |
| `/?step=N` | The story frozen at step N, from 0 (the opening) to 21. Add `&evidence` to open that step's evidence |
| `/#step-N` | The scrolled story, landed on step N |
| `/#overview` | The strip after the story: the seven stops as seven small boards |
| `/#/experiments` | The experiments |
| `/#/sources` | The sources |
| `/#/experiments/<section>` | A page landed on one of its sections, named by the screen's `id` in the content (on the sources page also `read`, `not-read`, `limits`, `glossary`, `provenance`). Add `/evidence` to open that section's evidence, or `/<card>/evidence` for one card's |

In the scrolled story one press of Space or Page Down is one step on, and Shift with Space or Page Up one step back. The first thing the keyboard reaches is a link to `/?static`, the whole story as a plain page.

The site is one script of 940 kB (182 kB as the live host sends it, compressed with gzip), one stylesheet, two font files and the pictures. The build writes 17 font files, and a browser fetches only the two Latin ones. About two thirds of the script is the recordings and the content. The measured first load is given under "The live site".

### Hosting

The site is published on GitHub Pages at https://lejie710.github.io/lux/ by `.github/workflows/deploy.yml`. On every push to `main`, and when it is started by hand, that workflow runs the content check, the format check, the site's tests and the build, and hands `site/dist/` to the host only if all of them pass. A failing check publishes nothing. The repository's Pages source must be set to "GitHub Actions": the workflow's first run stopped at its Pages step because that setting had not been made, and passed when it was run again. No runner boots a virtual machine or records a run; the recordings are committed evidence.

The build suits any static host: every page lives after the hash sign of one address, `npm run build` writes `dist/` with relative paths, and a `404.html` leads back to the start. To look at the built site, run `npm run preview` after `npm run build`; it serves `dist/` at the same address and port as `npm run dev`, and takes `-- --port 5191` in the same way. Two settings are read from the environment or a `.env` file. Neither is needed locally. **A published build needs both**, and the workflow sets them to `/lux/` and `https://lejie710.github.io/lux/`.

| Setting | Use |
|---|---|
| `LUX_BASE` | The folder the site is served from, for example `/lux/`. Asset paths and the link in `404.html` then start there |
| `LUX_SITE_URL` | The full public address. A link preview needs an absolute address for its picture (`cover.jpg`); without this setting the tag holds a relative one, which preview services do not follow |

## Re-recording on Linux or WSL

A reader needs none of this to check the evidence. It is for someone who wants to see the runs repeat.

Tested on Ubuntu 24.04 inside WSL 2 only, with every command run as root; an ordinary user was not tried. The recorder needs these Ubuntu packages, and every recording stores their versions in its `provenance` block:

| Package | Used for |
|---|---|
| `qemu-system-x86` | the virtual machine |
| `ovmf` | the firmware and its empty variable store |
| `swtpm` | the software TPM |
| `binutils` | assembling and linking the guest loader |
| `python3` (3.12) | the recorder itself, standard library only |
| `git` | the prediction gate asks it whether a prediction is committed; needed for counted experiments only |
| `tpm2-tools` (optional) | decoding `eventlog.bin` yourself with `tpm2_eventlog` |

They are installed with the system's package manager, for example `sudo apt install qemu-system-x86 ovmf swtpm binutils python3 git`. That command was not run for this project on a clean system: the packages were already there.

`sbsigntool`, `efitools` and `openssl` were used once to create the committed key set and sign the loaders. A clone does not need them; their versions are recorded in `recorder/testkeys/MANIFEST.json`.

The recorder keeps its scratch files in a work directory: `~/lux-work`, or the path in `LUX_WORK_DIR`. It must be on a Linux file system. On WSL that means not under `/mnt/`, because unix sockets do not work on a Windows drive. The repository itself may live anywhere. All commands are run from the repository root.

### 1. Prepare (once per machine)

```
python3 -m recorder prepare
```

This verifies the committed test keys against their manifest, builds the guest loader and checks that it equals the committed signed one, checks the second signed loader, checks that the packaged firmware file is the one the recordings were made with, and makes two variable store templates with one enrolment boot each (about ten seconds per boot). Expected output:

```
firmware_sha256: 1286f2a3217d09b374d05951355d7a561c8bacecd74845c8a1fbb71a48c0de8d
keys: verified
loader_authenticode_sha256: 00c5018d3157edb92f96a08ba685a1c5913c5dd5fa2228b021dd9d4970eee50f
second_loader_sha256: 948c330302d28389dfdc584a694fa19a9527cbd0fe8d3050785be02c14b1b06f
signed_loader_sha256: 0cb3ced82bf84f1a235c3b81f8029d055bd846a261cdfd71ad6f9f0437e18a78
two_entry_template_sha256: 12f35963670eab15d8f0ae4210432c0036017f6b4411993df6b43cdaee200abf
vars_template_sha256: 57ec06981b573029dd48cd399a5546ad8e57dece61dac9cdeeb894e79e88cebf
prepared
```

If your tools build a different loader or a different template, or your firmware package is another version, the command says so and stops. It never generates new keys by itself.

### 2. Record a run

The committed recordings are evidence: `record` refuses to write over an existing name, and the tests and the content check expect `recordings/` to hold the 14 committed runs and no other. So use names of your own, and a folder of your own. `scratch/` in the repository root is ignored by git and by the tests:

```
python3 -m recorder record my-normal --experiment normal --out scratch
python3 -m recorder record my-e2 --experiment e2 --out scratch
python3 -m recorder record my-two --experiment normal-two-same --out scratch
```

Each takes about ten seconds and writes `scratch/<name>/recording.json` and `eventlog.bin`. Expected output for the normal run:

```
run my-normal: accepted, 28 events, agreement gate passed
written: scratch/my-normal/recording.json
```

and for the pilot: `run my-e2: refused, 26 events, agreement gate passed`. The normal run with two boot entries has 30 events.

Without `--out` a run is written into `recordings/`. A folder of your own there makes one unit test fail (`test_every_committed_recording_is_listed_here`) and changes the count the content check prints, until it is deleted. Exit codes of `record`: 0 for a recording; 1 for a refusal, with one sentence saying why, and nothing written; 3 when a changed run reached neither the loader's last line nor a refusal and was recorded as `timeout`.

**Do not boot a counted experiment.** Each of the four has had its one run, under the name `<experiment>-1`. `record` refuses a counted experiment unless the command carries `--for-the-record`, and those words are not for trying the command out:

```
$ python3 -m recorder record blind --experiment signature-byte
refused: experiment 'signature-byte' is counted: it is booted once, for the record. Pass --for-the-record when this boot is meant to be that one run
```

A run of your own, under another name or in another folder, is a repetition and not the counted run. `docs/COUNTED.md` says how each counted run was made.

### 3. Compare

The baseline, named first, must be a recording of a normal run, and for a changed run it must be the normal run that experiment changes (`normal-1` for the pilots):

```
python3 -m recorder compare recordings/normal-1/recording.json scratch/my-e2/recording.json --out scratch/normal-1_vs_my-e2.json
```

```
identical: false
registers differing (sha256): [4, 5, 7]
written: scratch/normal-1_vs_my-e2.json
```

When your machine reproduces the committed normal run, comparing it with your own says so:

```
python3 -m recorder compare recordings/normal-1/recording.json scratch/my-normal/recording.json --out scratch/normal-1_vs_my-normal.json
```

```
identical: true
registers differing (sha256): []
written: scratch/normal-1_vs_my-normal.json
```

`compare` refuses a recording with itself, with a renamed copy of itself, with a recording whose agreement gate did not pass, and a changed run against another normal run than its own.

`scripts/record-pilots.sh` and `scripts/record-baselines.sh` make the normal runs, the pilots and their comparisons again, and pass `--replace` on purpose. The recording time is part of each file, so after them the files differ from the committed ones even when every compared field is equal, and the committed predictions and scores, which name their baseline recordings by hash, no longer fit. Run them in a copy, not in a checkout you mean to commit.

### 4. Check the committed scores

Nothing is booted. This makes one score again from the committed files, in two commands. The first writes the comparison into the ignored folder `scratch/`:

```
python3 -m recorder compare recordings/normal-1/recording.json recordings/signature-byte-1/recording.json --out scratch/my-comparison.json
```

```
identical: false
registers differing (sha256): [4, 5, 7]
written: scratch/my-comparison.json
```

The second scores it:

```
python3 -m recorder check scratch/my-comparison.json --prediction predictions/signature-byte.json --recording recordings/signature-byte-1/recording.json --baseline recordings/normal-1/recording.json --repeat recordings/comparisons/normal-1_vs_normal-2.json
```

```
specification-required rows met: 1 of 1
open rows predicted correctly: 17 of 17
mismatches: none
```

**Exit code 0 means "scored", not "every row held".** A mismatch is a result and is listed by row. Exit code 1 means the score was refused: the comparison does not belong to that recording or baseline, the prediction was edited after the run, or the two normal runs are not identical. `docs/COUNTED.md` lists the normal run and the repeat comparison of the three other experiments.

## How a run is trusted

Every run ends the same way, whether the loader was accepted or refused: the guest is paused, its memory is saved, and the virtual machine is killed while paused, so the software TPM is still alive to be read. Three readings of the same boot, taken by different routes, must then agree on all 24 registers in all four hash banks:

1. a replay of the firmware's event log, cut out of the saved guest memory;
2. a replay of the extend commands found in the software TPM's own log;
3. the register values read from the TPM itself.

The first reading is written by the firmware and does not pass through the TPM. The second and third both come from the one software TPM process, by two routes, and both replays use the same extend function, so the three are not fully independent of each other. `docs/DESIGN.md` section 4.3 says exactly how far.

If they disagree anywhere, the command exits with an error and writes nothing. The same holds when the end of the boot was not seen in time, and when a normal run was not accepted: a hung boot never becomes a recording of the normal run.

## Pilots and counted experiments

The measure of this project is a prediction committed **before** an experiment is run. Experiments that were tried before any prediction existed cannot meet that. They are declared as **pilots**: shown, never counted.

| Pilot | What it changes | What the recording shows | Registers that differ from the normal run |
|---|---|---|---|
| `e1` | One byte of the loader's content, Secure Boot switched off | The changed loader ran | 4, 7 |
| `e2` | The same byte, Secure Boot on | Refused, `Access Denied` | 4, 5, 7 |
| `e4` | Secure Boot switched off, nothing else | The signed loader ran | 7 |
| `e5` | The signed loader's hash added to the revocation list (`dbx`) | Refused, `Access Denied` | 4, 5, 7 |

A **counted** experiment is one that had never been run when its prediction was committed. Four were run, once each (the table under "What the evidence shows"). A fifth, `rebuilt-firmware`, has no prediction and no firmware file, was not run, and is refused by the recorder.

The recorder refuses to run a counted experiment unless all of this holds: the command carries `--for-the-record`; `predictions/<experiment>.json` exists, is valid, describes the same change in the same words and carries the values that decide what the experiment tests; it is committed, and the file on disk is byte for byte the committed one; and two identical recordings of the normal run that the experiment changes are on file. The recording stores the prediction's hash, commit and values, so a prediction edited after its run is detected. A counted recording is never overwritten.

## Tests

The commands are written as on Linux or WSL. On Windows, where `python3` may not be a command, the unit tests and the content check run with `python` in its place; both were run that way too. The expected output below is that of a checkout whose `recordings/` folder holds only the committed runs.

Recorder, from the repository root. The unit tests need no virtual machine and change no file in the repository:

```
python3 -m unittest discover -s recorder/tests -t .
```

```
Ran 373 tests in 35.466s

OK (skipped=6)
```

The time varies. The six skipped tests boot the virtual machine. To include them, on a prepared machine:

```
bash scripts/test-with-vm.sh
```

It boots the normal run twice and the normal run with two boot entries once, asserts that the agreement gate passed, that the two runs are equal on every compared field, that a fresh run equals the committed `normal-1` and `normal-two-same-1`, and that nothing is left running. It never boots a changed run, and takes one to two minutes. Expected: `Ran 373 tests`, `OK`, then `virtual machines running: none`, `software TPMs running: none` and `guest memory files: none`.

The content check, from the repository root:

```
python3 scripts/check_content.py
```

```
content check: 5 files, 28 screens, 357 claims, 85 claims uefi-required, 28 claims uefi-platform, 21 claims tcg-unread, 38 claims this-firmware, 170 claims recording, 15 claims general, 14 recordings, 59 glossary entries
content check: passed, no problems
```

The site, from `site/`:

```
npm test
npm run build
npm run format:check
```

```
 Test Files  12 passed (12)
      Tests  418 passed (418)
```

`npm run build` prints a line that contains `built in`, and a warning that one chunk is larger than 500 kB. `npm run format:check` ends with `All matched files use Prettier code style!`.

`.github/workflows/check.yml` runs the recorder's unit tests, the content check and the three site commands on every push and pull request. It boots nothing and publishes nothing. `.github/workflows/deploy.yml` runs the content check and the same three site commands on a push to `main`, and publishes the built site when they pass; it boots nothing either. `docs/VERIFICATION.md` maps each acceptance check to a named test, lists what is not tested, and gives the counts per layer.

## Repository map

```
README.md            this file
docs/                the documentation; ENGINEERING.md is the entry point
recorder/            the recorder: a Python package, standard library only
  guest/             the guest loader's assembly source and the second signed loader
  testkeys/          the public test keys, the signed loader and their manifest
  tests/             the recorder's tests and the fixtures of two real boots
predictions/         one prediction per counted experiment, committed before its run
recordings/          one folder per run: recording.json and the raw eventlog.bin
  comparisons/       a normal run against its repeat, and against each changed run
  scores/            one score per counted run
content/             the words of the site as data, five JSON files in one shape
scripts/             check_content.py, and shell scripts for preparing, testing and recording
site/                the site: React, TypeScript and Vite
  src/content/       the two doors to the data: the content, and the files that say what was run
  src/model/         the story's steps, the state of an experiment, the addresses
  src/components/    the stage, the board, the evidence panel and the pages
  src/stage/         what changes as the reader scrolls: the step in view, the board's light, its canvas
  tools/             the script that makes the shipped pictures
.github/workflows/   check.yml, the offline checks; deploy.yml, the same checks and the publication of the site
```

| Document | What it holds |
|---|---|
| [`docs/ENGINEERING.md`](docs/ENGINEERING.md) | The entry point: purpose and requirements, the architecture of the whole system, two operations traced end to end, the file formats, the decisions, operating guidance |
| [`docs/VERIFICATION.md`](docs/VERIFICATION.md) | Acceptance checks mapped to tests, the failures most likely to hurt a reader, test counts, what was checked by eye, defects found, the release assessment, the deployment and the walk of the live site |
| [`docs/FRESH_CLONE_RUN.md`](docs/FRESH_CLONE_RUN.md) | This README followed in a new clone: what was typed, what came back, what it found, which steps were repeated after the README was corrected, and a third clone in which the packages were installed and the site's commands and the checks that boot nothing were typed |
| [`docs/RESULTS.md`](docs/RESULTS.md) | Every row of every counted run, the two numbers and their limits |
| [`docs/DESIGN.md`](docs/DESIGN.md) | The recorder's modules, the four file formats and decisions D1 to D8 |
| [`docs/PILOTS.md`](docs/PILOTS.md), [`docs/COUNTED.md`](docs/COUNTED.md), [`docs/MUTATION_CHECKS.md`](docs/MUTATION_CHECKS.md) | The pilots as recorded; how the counted experiments were staged; nine rules broken on purpose |
| [`content/README.md`](content/README.md), [`site/ASSETS.md`](site/ASSETS.md) | The shape of the content and what its check refuses; how each picture was made |

## Provenance of the committed recordings

QEMU 8.2.2 (`1:8.2.2+ds-0ubuntu1.18`), OVMF 2024.02 (`2024.02-2ubuntu0.10`, file `OVMF_CODE_4M.secboot.fd`, SHA-256 `1286f2a3217d09b374d05951355d7a561c8bacecd74845c8a1fbb71a48c0de8d`), swtpm 0.7.3, binutils 2.42, Python 3.12.3, on Ubuntu 24.04 under WSL 2. The key set and the signed loaders were created once with OpenSSL 3.0.13, sbsigntool 0.9.4 and efitools 1.9.2. Machine type `pc-q35-8.2`, CPU model `qemu64`, 512 MiB, software emulation, clock fixed at 2026-01-01. Every recording carries its own `provenance` block with these values and the full command lines.

## Sources and licences of what is used

Public sources only. Nothing from any employer or vendor system was read or used.

| What | How it is used | Licence or terms |
|---|---|---|
| UEFI Forum, *Unified Extensible Firmware Interface (UEFI) Specification*, version 2.11 | The chapters the story needs were read page by page, and the whole published PDF was searched by keyword; some chapters were not read, and figures have no text to read. Paraphrased and cited by section and PDF page. No table or figure is reproduced | Copyright UEFI Forum, Inc. All rights reserved |
| EDK II and its OVMF firmware | Run as packaged by Ubuntu; not redistributed here. Six of its source files are named as the basis of claims and linked from the sources page. They were read at the project's master branch, not at the tag of the packaged build, and the package's build settings were not confirmed. One of them has since been renamed on that branch, so its link leads to the tag `edk2-stable202402`, where it has the name given | BSD-2-Clause-Patent |
| QEMU | Run; not redistributed | GNU General Public License, version 2; stated per file in its source tree |
| swtpm | Run; not redistributed | BSD-3-Clause |
| tpm2-tools | The event type names it prints are kept as a test fixture; the program is not redistributed | BSD-3-Clause, by the copyright file of its Ubuntu package |
| GNU binutils, Python | Build the guest loader; run the recorder. Neither is redistributed | GNU General Public License, version 3 or later; Python Software Foundation License. Neither licence text was checked for this project |
| React, React DOM | The site's only runtime code besides its own | MIT |
| Vite, Vitest, Prettier, the React plugin for Vite, the React type packages; TypeScript | Build, test and format the site; not shipped to a reader | MIT; TypeScript is Apache-2.0 |
| Inter and IBM Plex Mono, through the Fontsource packages | Bundled into the built site; nothing is fetched from another site | SIL Open Font License 1.1 |
| The pictures | Generated illustrations of a fictional laptop and board, processed by `site/tools/make_assets.py`. Not photographs, not a real product | Part of this repository; see below |
| The recordings, fixtures, test keys and signed loaders | Output of this project's own runs, and test material made for it | Part of this repository; see below |

The method by which `recorder/pe.py` computes an image's Authenticode digest is the one named in Microsoft's *Windows Authenticode Portable Executable Signature Format*. The digest it computes is confirmed against what the firmware measured in the recordings, not against that document, and the site lists the document among those not read: no claim on the site cites it.

Names of specifications, standards bodies and software projects belong to their owners and are used here only to say where a statement comes from.

## Status and licence

Made by Le Jie Tan, who is named on the site's opening screen in the same place and form as on the earlier site. The repository is public at https://github.com/lejie710/lux, and the site is live at https://lejie710.github.io/lux/ since 2026-11-15. Its last screen links on to the earlier site, Nox, at https://lejie710.github.io/nox/, where the story of the running machine continues.

Licence: the software is under the MIT License (see [LICENSE](LICENSE)). That licence covers the code only: the explanatory text shown on the site and the images are not part of the grant. The images are generated illustrations, not photographs of real products or places. Text and images are copyright 2026 Le Jie Tan, all rights reserved. Quote them with a link, but do not republish them. The recordings are output of the firmware, virtual machine and TPM programs the recorder drives; those are separate projects under their own licences, listed above.

A personal project based on public specifications. Not affiliated with or endorsed by any employer or vendor.
