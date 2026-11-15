# A run from a fresh clone, following the README

The repository was cloned into a new, empty folder outside the project at commit `b3222a5`, and `README.md` was followed in its own order, typing what it says. This file records what was typed, what came back, and every place where the README was wrong, incomplete, ambiguous or assumed something it does not state. Nothing in the repository was changed to make a step pass. Sections 1 to 5 are that run as it was. Section 6 records what was corrected in the README afterwards and which steps were then typed again in a second new clone. Section 7 records a third new clone, at commit `2d2c5ba`, in which `npm ci` was run and the site's commands and the checks that boot nothing were typed in the clone itself.

All three runs were made on 2026-11-15. No counted experiment was booted. The first and the third clone and both work directories were deleted afterwards. The second clone is a folder outside the repository that nothing depends on.

## 1. Result in one table

| README part | Followed as written | Result |
|---|---|---|
| Run it locally: `npm ci` | Yes | Passed: 47 packages installed from the lock file, 0 vulnerabilities reported |
| Run it locally: `npm run dev`, open `http://127.0.0.1:5183/` | No: the port was taken (finding F2) | Failed as written. Passed on port 5191: the first page renders |
| Re-recording 1: `prepare` | Yes, with `LUX_WORK_DIR` set | Passed: all eight output lines equal the README's |
| Re-recording 2: three recordings and the refusal example | Yes | Passed: every output line equals the README's |
| Re-recording 3: `compare` | Yes | Passed: output equals the README's; `identical: true` against the committed normal run |
| Re-recording 4: make one score again | Yes | Passed: `1 of 1`, `17 of 17`, `mismatches: none` |
| Tests: recorder unit tests | Yes in WSL; on Windows only with `python` (finding F1) | Passed: `Ran 368 tests`, `OK (skipped=6)` |
| Tests: `bash scripts/test-with-vm.sh` | Yes | **Failed** while the recordings of step 2 were in `recordings/` (finding F3). Passed after they were removed: `Ran 368 tests`, `OK`, three lines ending in `none` |
| Tests: content check | Yes | Passed, both lines equal the README's (with the recordings of step 2 present the count line differs, finding F3) |
| Tests: `npm test`, `npm run build`, `npm run format:check` | Yes | Passed: 9 files, 329 tests; `built in 728ms` with the chunk warning; `All matched files use Prettier code style!` |
| Opening the built site | The README gives no step (finding F4) | Served with `npm run preview` on port 5191: the experiments page renders with 6 of 6, 72 of 72 and the caveat under them |

## 2. Environment

| Item | Version |
|---|---|
| Windows | Windows 11, version 10.0.26100.9711 |
| Python on Windows | 3.12.10, as `python`; `python3` is not a working command there |
| Node.js, npm | 24.22.0, 11.19.1 |
| git on Windows | 2.54.0.windows.1, `core.autocrlf=true` |
| Browser for the screenshots | Microsoft Edge 157.0.4341.42, headless, window 1440 x 900 |
| WSL distribution | Ubuntu 24.04.5 LTS under WSL 2, kernel 6.18.33.2-microsoft-standard-WSL2, commands run as root |
| Python in WSL | 3.12.3 (`3.12.3-0ubuntu2.1`) |
| QEMU | `qemu-system-x86` `1:8.2.2+ds-0ubuntu1.18` |
| Firmware package | `ovmf` `2024.02-2ubuntu0.10` |
| swtpm | `0.7.3-0ubuntu5.24.04.1` |
| binutils, git in WSL | `2.42-4ubuntu2.10`, `1:2.43.0-1ubuntu7.3` |
| tpm2-tools | `5.6-1build4` (installed, not used in this run) |

This is the machine the committed recordings were made on, with the same package versions. So this run shows that a clean copy of the committed files is enough; it does not show that another machine reproduces anything.

## 3. What was typed and what came back

### 3.1 The site (Windows, from `site/`)

| Command | Output | Against the README |
|---|---|---|
| `npm ci` | `added 47 packages, and audited 48 packages in 13s`, `found 0 vulnerabilities` | The README shows no output for it. This step needs the network |
| `npm run dev` | `Error: Port 5183 is already in use` | Not as the README says. Another process on this machine, not part of the clone, held the port |
| `npm run dev -- --port 5191` (not in the README) | Server started; `http://127.0.0.1:5191/` answered 200 | The screenshot of `/` shows the opening the README's first picture describes: the dark laptop, "Lux", "Before light.", "What your laptop does before it wakes.", the invitation to scroll, the note "Illustration, not a real product. The evidence is the recording." |
| `npm test` | `Test Files  9 passed (9)`, `Tests  329 passed (329)` | Equal |
| `npm run build` | `index-*.js 936.94 kB, gzip: 185.68 kB`, the warning that a chunk is larger than 500 kB, `built in 728ms` | Equal to what the README describes, including 936 kB and 186 kB |
| `npm run format:check` | `All matched files use Prettier code style!` | Equal |
| `npm run preview -- --port 5191` (not in the README) | Built site served; `/#/experiments` rendered | See finding F4 |

`git status` in the clone was clean after all of these: `node_modules/` and `dist/` are ignored.

### 3.2 The recorder (WSL, from the repository root on the Windows drive)

`LUX_WORK_DIR` was set to a new directory in the Linux home, because the default `~/lux-work` already existed on this machine and belongs to the original repository. The README allows this setting.

| Command | Output | Against the README |
|---|---|---|
| `python3 -m recorder prepare` | The eight lines from `firmware_sha256: 1286f2a3...de8d` to `prepared`, exit 0. Run twice | Equal, line for line, all seven hashes |
| `python3 -m recorder record my-normal --experiment normal` | `run my-normal: accepted, 28 events, agreement gate passed`, `written: recordings/my-normal/recording.json` | Equal |
| `python3 -m recorder record my-e2 --experiment e2` | `run my-e2: refused, 26 events, agreement gate passed`, exit 0 | Equal |
| `python3 -m recorder record my-two --experiment normal-two-same` | `run my-two: accepted, 30 events, agreement gate passed` | Equal (30 events) |
| `python3 -m recorder record blind --experiment signature-byte` | `refused: experiment 'signature-byte' is counted: it is booted once, for the record. Pass --for-the-record when this boot is meant to be that one run`, exit 1 | Equal. Nothing was booted: the refusal comes before anything is staged |
| `python3 -m recorder compare recordings/normal-1/recording.json recordings/my-e2/recording.json --out recordings/comparisons/normal-1_vs_my-e2.json` | `identical: false`, `registers differing (sha256): [4, 5, 7]`, `written: recordings/comparisons/normal-1_vs_my-e2.json` | Equal |
| The same for `my-normal`, with an output path of this run's own choosing | `identical: true`, `registers differing (sha256): []` | Equal to the sentence in the README; the command itself is not given there (finding F6) |
| Step 4, `compare` then `check` for `signature-byte-1` | `compare` printed its own three lines; `check` printed `specification-required rows met: 1 of 1`, `open rows predicted correctly: 17 of 17`, `mismatches: none`, exit 0 | The three lines of `check` are equal (finding F5 on the rest) |
| `python3 -m unittest discover -s recorder/tests -t .` | `Ran 368 tests in 63.057s`, `OK (skipped=6)` in WSL; `Ran 368 tests in 32.147s`, `OK (skipped=6)` on Windows with `python` | Equal, apart from the time, which the README says varies |
| `python3 scripts/check_content.py` | `content check: 5 files, 28 screens, 354 claims, ... 14 recordings, 59 glossary entries`, `content check: passed, no problems` | Equal, in a clean tree |
| `bash scripts/test-with-vm.sh`, clean tree | `Ran 368 tests in 98.257s`, `OK`, `virtual machines running: none`, `software TPMs running: none`, `guest memory files: none`, exit 0 | Equal |

Boots made by this run: the enrolment boots of `prepare` (twice), the three recordings above, and the normal runs of `test-with-vm.sh` (twice). All are normal runs or the pilot `e2`. After the last step no virtual machine, no software TPM and no guest memory file was left, and no server was listening.

## 4. Findings

Ordered by how much they would cost a new reader.

| # | Kind | What the README says or leaves out | What happened |
|---|---|---|---|
| F3 | Wrong when followed in order | Section "2. Record a run" writes into `recordings/` by default and says only that `--out` exists "to keep your runs out". The "Tests" section, which comes later, says the unit tests "change no file in the repository" and gives fixed expected output | With `my-normal`, `my-e2` and `my-two` in `recordings/`, the unit suite fails one test, `test_committed_recordings.CommittedRecordings.test_every_committed_recording_is_listed_here` (`Items in the first set but not the second: 'my-two', 'my-normal', 'my-e2'`). `bash scripts/test-with-vm.sh` then exits 1 and never prints its three lines ending in `none`. The content check still passes but prints `17 recordings`, not 14. The README does not say that a reader's own recordings must be removed before the tests, and gives no clean-up step. After deleting the three folders, the two comparisons and `my-comparison.json`, everything passed. A build of the site made in that state was not inspected |
| F1 | Assumed, not stated | Every Python command is written `python3`, and the README does not say on which system the tests and the content check are meant to be run | On Windows as installed here `python3` is not a command: it prints `Python was not found; run without arguments to install from the Microsoft Store`. The same commands pass with `python`. `docs/VERIFICATION.md` section 8 used `python` on Windows; the README never mentions it |
| F2 | Incomplete | "Open `http://127.0.0.1:5183/`". The port is fixed and strict in `site/vite.config.ts`, and the README offers no way to choose another | `npm run dev` stopped with `Port 5183 is already in use`, because another process on the machine held it. `npm run dev -- --port 5191` works and is nowhere in the README |
| F4 | Incomplete | "Hosting" says `npm run build` writes `dist/`. No step says how to look at the built site | `npm run preview` exists in `site/package.json` (same fixed port) and is not mentioned. It was used here with `-- --port 5191`. Opening `dist/index.html` straight from the disk was not tried |
| F5 | Ambiguous | Step 4 shows two commands and one output block of three lines | The block is the output of `check` only. `compare` prints three lines of its own first (`identical: false`, `registers differing (sha256): [4, 5, 7]`, `written: my-comparison.json`). The step also leaves `my-comparison.json` in the repository root, untracked and not ignored, which the README does not say |
| F6 | Incomplete | Step 3: "Comparing `recordings/normal-1/recording.json` with `recordings/my-normal/recording.json` prints `identical: true`" | No command is given, and `compare` requires `--out`, so the reader has to invent an output path |
| F7 | Assumed, not stated | The package table lists what the recorder needs, with no install command, and does not say which user runs the commands | The packages were already installed on this machine, so installing them from nothing was not exercised. Everything was run as root; an ordinary user was not tried |
| F8 | Small mismatch | "Needs Node.js 22.12 or later in the 22 line, or 24" | `site/package.json` also accepts 26 and later. Only 24.22.0 was exercised. The npm version is not stated anywhere in the README |
| F9 | Not shown | No expected output for `npm ci`, no expected duration for `bash scripts/test-with-vm.sh` | About 13 seconds and about 100 seconds here |
| F10 | Not verified here | "one stylesheet, two fonts and the pictures", "about 0.7 MB" for the first load | The build emits 23 font files; which of them a first load fetches, and the transferred size, were not measured in this run |
| F11 | Out of date beside this file | `docs/VERIFICATION.md` section 8 says `npm ci` was not run in a clone and that the hosted workflow will be the first to show it | In this run `npm ci` succeeded from the lock file in a clean clone. That section, and the README's document table, do not name this file |

What matched without remark: the question and the headline table against `recordings/scores/` as shown on the built experiments page (6 of 6, 72 of 72, 4 scored, the caveat directly under them); the three pictures the README embeds exist; every path the README names in its evidence table and repository map exists in the clone; the shell scripts keep their line endings in a clone made with `core.autocrlf=true`; the repository works from a Windows drive under WSL, as the README says.

## 5. What this run does not show

- **Not a second machine.** Same computer, same package versions as the committed recordings.
- **Not the default port.** The site was never seen on 5183 from the clone.
- **Not a person's eye on motion.** Two still screenshots of two addresses; no scrolling, no keyboard, no other browser, no phone.
- **Not the hosted workflow.** It has still never run.
- **Not a counted experiment.** None was booted, by rule; only the refusal of one was seen.
- **Not a clean install of the Ubuntu packages**, and not an ordinary Linux user.

## 6. After the README was corrected

The README was corrected in commit `89fa143` for findings F1 to F10; two numbers in it (how many font files the build writes, and how long the test with the virtual machine takes) were set from this second pass in the commit that adds this section. The repository was then cloned again into a new, empty folder at that commit, on the machine of section 2, and the steps the findings touch were typed again. The recorder used a new work directory through `LUX_WORK_DIR`, so `prepare` made its templates from nothing.

| Finding | What the README says now | Typed again, and what came back |
|---|---|---|
| F3 | The recording examples carry `--out scratch`, a folder that git and the tests ignore; the README says what happens without it | In the second clone, under WSL, in the README's order: `prepare` (the eight lines, equal); the three recordings (`accepted, 28 events`, `refused, 26 events`, `accepted, 30 events`, each `written: scratch/<name>/recording.json`); the refusal of the counted experiment (the README's line, exit 1, nothing booted). Then, **with those recordings still on disk**: `Ran 368 tests`, `OK (skipped=6)`; `bash scripts/test-with-vm.sh` gave `Ran 368 tests in 63.545s`, `OK`, the three lines ending in `none`, exit 0, 65 seconds in all; the content check printed `14 recordings` and `passed, no problems`; `git status` was clean |
| F1 | Says the commands are written as on Linux or WSL and that Windows uses `python` | In the second clone on Windows: `python -m unittest discover -s recorder/tests -t .` gave `Ran 368 tests in 29.151s`, `OK (skipped=6)`; `python scripts/check_content.py` gave both lines of the README |
| F5, F6 | Each `compare` and the `check` has its own command and its own output block, and every output path lies in `scratch/` | In the second clone: `identical: false`, `[4, 5, 7]`, `written: scratch/normal-1_vs_my-e2.json`; `identical: true`, `[]`, `written: scratch/normal-1_vs_my-normal.json`; `identical: false`, `[4, 5, 7]`, `written: scratch/my-comparison.json`; then `1 of 1`, `17 of 17`, `mismatches: none`. All equal |
| F2 | Quotes the message of a taken port and gives `npm run dev -- --port 5191` | In the working tree, not in the clone: `npm run dev` printed `Error: Port 5183 is already in use`, because the same other process still held the port; `npm run dev -- --port 5191` answered 200 with the site's title |
| F4 | Names `npm run preview` after `npm run build` | In the working tree: `npm run preview -- --port 5191` answered 200 and served `og.jpg` |
| F7 | Says the commands were run as root, and gives one `apt install` line with the note that it was not exercised | Not exercised: the packages were installed already. Again run as root |
| F8 | Names what `engines` accepts and that only Node.js 24.22.0 with npm 11.19.1 was used | Read against `site/package.json` |
| F9 | Shows the last line of `npm ci` and says `test-with-vm.sh` takes one to two minutes | 65 seconds in the second clone, about 100 in the first |
| F10 | Says the first-load figure is added up from the built files and was not measured in a browser | The build writes 17 font files (12 `.woff2`, 5 `.woff`), counted in `dist/assets` in this pass, not the 23 that finding F10 states. Script 177.5 kB and stylesheet 7.5 kB after gzip. Still no network log from a browser |
| F11 | The document tables of the README and of `ENGINEERING.md` name this file, and `VERIFICATION.md` section 8 summarises it | Read |

In the working tree at the same commit: `npm test` gave `Test Files  9 passed (9)`, `Tests  329 passed (329)`; `npm run build` gave 936.94 kB, gzip 185.68 kB, the chunk warning and `built in`; `npm run format:check` gave `All matched files use Prettier code style!`.

**What this second pass is not.** It is not a complete run from start to end in one clone. `npm ci` was not repeated, because nothing was downloaded for it, so the site's commands were run in the working tree and not in the second clone. The default port 5183 was again not seen. Taken together, every step of the corrected README has been typed and has matched, either in a new clone or, for the site's commands, in the working tree at the same commit; a single pass that does all of it in one new clone has not been made. Section 7 closes the first of these gaps: there `npm ci` and every site command were run in one new clone.

Boots made by the second pass: the enrolment boots of `prepare`, the three recordings above, and the three normal runs of `test-with-vm.sh`. All are normal runs or the pilot `e2`. Afterwards no virtual machine, no software TPM and no guest memory file was left.

## 7. A third clone: the packages installed, the site and the offline checks in one clone

The repository was cloned a third time, from the local repository into a new, empty folder outside it, at commit `2d2c5ba`, on the machine of section 2. Before anything was installed the clone's `site/` folder held no `node_modules/` and no `dist/`. Nothing was copied into the clone. This run exists because the second pass had not repeated `npm ci`.

### 7.1 Environment

| Item | Version |
|---|---|
| Windows | Windows 11, version 10.0.26100.9711 |
| Node.js, npm | 24.22.0, 11.19.1 |
| Python on Windows | 3.12.10, as `python`; `python3` still prints `Python was not found` |
| git on Windows | 2.54.0.windows.1, `core.autocrlf=true` |
| Browser for the screenshot | Microsoft Edge 157.0.4341.42, headless, window 1440 x 900 |
| WSL distribution | Ubuntu 24.04.5 LTS under WSL 2, kernel 6.18.33.2-microsoft-standard-WSL2, commands run as root |
| Python, git in WSL | 3.12.3, 2.43.0 |

### 7.2 What was typed and what came back

On Windows, from the clone's `site/` folder:

| Command | Output | Against the README |
|---|---|---|
| `npm ci` | `added 47 packages, and audited 48 packages in 7s`, `15 packages are looking for funding`, `found 0 vulnerabilities`. The packages came from the public npm registry, as the lock file pins them; `node_modules/` was 101 MB afterwards | The line the README quotes came back, with 7 seconds where it said 13. It is not the last line, which the README said it was (finding F12) |
| `npm run dev` | `Error: Port 5183 is already in use` | Equal to the message the README quotes: another process on the machine, not part of the clone, held the port |
| `npm run dev -- --port 5200` | Server started; `http://127.0.0.1:5200/` answered 200 with the title `Lux: what your laptop does before it wakes` | The README's own example uses port 5191; 5200 was chosen for this run. One screenshot of `/` shows the opening the README's first picture describes: the dark laptop, "Lux", "Before light.", "What your laptop does before it wakes.", "Scroll to follow one boot", the three links of the navigation and the note "Illustration, not a real product. The evidence is the recording." |
| `npm test` | `Test Files  9 passed (9)`, `Tests  331 passed (331)` | Equal |
| `npm run build` | `index-*.js 936.99 kB`, `gzip: 185.69 kB`, the warning that a chunk is larger than 500 kB, `built in 586ms`; 17 font files in `dist/assets` | Equal to what the README describes: 936 kB, 186 kB, 17 font files |
| `npm run format:check` | `All matched files use Prettier code style!` | Equal |
| `npm run preview -- --port 5201` | The built site answered 200 with the same title and served `og.jpg` | As the README's "Hosting" section says, on another port than its example. No screenshot was taken of it |

On Windows, from the clone's root, with `python` as the README says for Windows:

| Command | Output | Against the README |
|---|---|---|
| `python scripts/check_content.py` | `content check: 5 files, 28 screens, 354 claims, 85 claims uefi-required, 28 claims uefi-platform, 21 claims tcg-unread, 38 claims this-firmware, 167 claims recording, 15 claims general, 14 recordings, 59 glossary entries`, `content check: passed, no problems` | Equal, both lines |
| `python -m unittest discover -s recorder/tests -t .` | `Ran 368 tests in 32.777s`, `OK (skipped=6)` | Equal, apart from the time |

Under WSL, as root, from the clone's root on the Windows drive, the two commands of the README's "4. Check the committed scores":

| Command | Output | Against the README |
|---|---|---|
| `python3 -m recorder compare recordings/normal-1/recording.json recordings/signature-byte-1/recording.json --out scratch/my-comparison.json` | `identical: false`, `registers differing (sha256): [4, 5, 7]`, `written: scratch/my-comparison.json`, exit 0 | Equal, all three lines. The command made the folder `scratch/` itself |
| `python3 -m recorder check scratch/my-comparison.json --prediction predictions/signature-byte.json --recording recordings/signature-byte-1/recording.json --baseline recordings/normal-1/recording.json --repeat recordings/comparisons/normal-1_vs_normal-2.json` | `specification-required rows met: 1 of 1`, `open rows predicted correctly: 17 of 17`, `mismatches: none`, exit 0 | Equal, all three lines |

`git status` in the clone was clean after all of this, with `node_modules/`, `dist/` and `scratch/` on disk. Both servers were stopped, and the clone was deleted.

### 7.3 Finding

| # | Kind | What the README said | What happened |
|---|---|---|---|
| F12 | Small mismatch | "`npm ci` ends with a line like `added 47 packages, and audited 48 packages in 13s`" | That line is followed by a note on funding and by `found 0 vulnerabilities`, so it is not the end of the output, and it took 7 seconds here. The README now says "prints a line like", gives 7 seconds, says the time varies and names the two lines that follow |

### 7.4 What this third run does not show

- **Nothing was booted.** `prepare`, the three recordings, the refusal of a counted experiment, the two comparisons of step 3 and `bash scripts/test-with-vm.sh` were not typed in this clone. They were last typed in the second clone (section 6), at commit `89fa143`.
- **Not one pass of the whole README in one clone.** The first run was that, against the README before its corrections. With this run every part of the corrected README has matched in a new clone, the booting steps in the second and everything else in the third; no single clone has done both.
- **Not the default port.** The same other process held 5183, so the site was seen on 5200 and 5201 only.
- **Not a cold package cache.** Whether npm fetched all 47 packages over the network in this run or took some from its cache on this machine was not looked at.
- **Not a second machine, not another Node.js or npm version, not the hosted workflow.**
- **One still screenshot of one address.** No scrolling, no keyboard, no other page, no other browser.
- **The unit tests under WSL and the content check under WSL** were not repeated in this clone; both ran on Windows.
