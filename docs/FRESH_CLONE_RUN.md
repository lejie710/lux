# A run from a fresh clone, following the README

The repository was cloned into a new, empty folder outside the project at commit `b3222a5`, and `README.md` was followed in its own order, typing what it says. This file records what was typed, what came back, and every place where the README was wrong, incomplete, ambiguous or assumed something it does not state. Nothing in the repository was changed to make a step pass.

Run on 2026-11-15. No counted experiment was booted. The clone and its work directory were deleted afterwards.

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
| Windows | Windows 11 Enterprise, version 10.0.26100.9711 |
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
