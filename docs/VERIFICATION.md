# Lux: verification and release evidence

What was checked, how, and what was not. The question the project answers is:

> When one thing in a PC's boot chain is changed, what does the specification require, what does it leave open, and what does this firmware actually do?

Every check below protects one link between that question and what a reader sees: a recording follows from its boot, a prediction came before its run, a score follows from the files, a quoted line is in a recording, a statement says where it comes from, and the page shows what the files hold and no more. Three checks are of another kind and are marked "presentation": A14 and A19 check the requirements R1 and R9 of `ENGINEERING.md` (the layout of a screen, reading without motion), and A20 checks the link on to the earlier site. They protect the reader's way through the page, not a link of the question.

Test names are given as file, class and method for the recorder (`recorder/tests/`), and as file and title for the site (`site/src/`).

## 1. Acceptance checks

| # | Given | When | Then | Automated test |
|---|---|---|---|---|
| A1 | A boot whose event log, TPM log and live register read agree | the agreement gate runs on the two real boots kept as fixtures | the gate passes for both, in four hash banks | `test_eventlog_gate.py` `Gate.test_real_boots_pass` |
| A2 | The same boot with one bit flipped in one digest, or in one live register value | the gate runs | the gate fails; the command exits 1 and writes no recording | `Gate.test_one_flipped_bit_in_one_digest_fails`, `Gate.test_one_flipped_bit_in_the_live_read_fails`; `test_session_runner.py` `CommandLine.test_gate_failure_gives_exit_code_1_and_writes_nothing` |
| A3 | The 14 committed recordings | each raw `eventlog.bin` is replayed | every register value in every recording equals the replay | `test_committed_recordings.py` `CommittedRecordings.test_each_recording_follows_from_its_own_event_log` |
| A4 | The committed recordings `normal-1` and `normal-2` | they are compared | `identical` is true; the same holds for both two-entry normal runs | `CommittedRecordings.test_the_two_normal_runs_are_identical`, `test_the_committed_pairs_may_be_compared_and_the_normal_run_repeats` |
| A5 | A prepared Linux machine | the normal run is booted twice, and the two-entry normal run once | the two fresh runs are equal on every compared field, a fresh run equals the committed `normal-1`, a fresh two-entry run equals the committed `normal-two-same-1`, and no process is left | `test_integration_vm.py` `NormalRunRepeats.*` and `TwoEntryNormalRunRepeats.*` (six tests, run only with `LUX_VM_TESTS=1`) |
| A6 | The counted experiment `signature-byte` and no prediction file | `record` is asked to run it | it is refused before any machine is created | `test_session_runner.py` `WholeRun.test_counted_experiment_without_prediction_is_refused_before_anything_starts` |
| A7 | A committed prediction that was then edited and hidden from `git status` with `git update-index --assume-unchanged`, in a real temporary repository | the prediction gate asks whether it is committed | refused: the bytes on disk are not the committed bytes | `test_compare_prediction.py` `PredictionGateWithRealGit.test_an_edit_hidden_from_git_status_is_still_refused` |
| A8 | A counted experiment, in an empty folder, with the look-up of its prediction replaced by a failure | `record` is run without `--for-the-record` | refused before the prediction is looked at; nothing is staged. The test does not have a committed prediction present | `test_session_runner.py` `CommandLine.test_a_counted_experiment_is_not_booted_by_a_command_that_does_not_say_so` |
| A9 | The four committed counted recordings | each is read | each names the prediction that is still on file, by path and hash, and stores a commit, of which the test checks only that it is a full 40-character hash; there is exactly one recording per counted experiment. That the stored commits (`76ce581` and `b6270c1`) are ancestors of the four recording commits was checked by hand with `git merge-base --is-ancestor` | `test_committed_recordings.py` `CountedRuns.test_each_run_was_recorded_under_the_prediction_that_is_still_on_file`, `test_each_counted_experiment_has_exactly_one_recording` |
| A10 | The committed recording `signature-byte-1`, its normal run and its prediction | the comparison and the score are made again | they equal the committed comparison and score file: 1 of 1 and 17 of 17, no mismatch; over all four score files the totals are 6 of 6 and 72 of 72 | `CommittedRecordings.test_committed_comparisons_equal_a_fresh_comparison` (the comparison), `CountedRuns.test_each_score_file_follows_from_the_committed_files` (the score, from the committed comparison), `test_the_two_numbers_are_the_sum_over_the_score_files` |
| A11 | A prediction file edited after the run | `check` is asked to score | refused | `test_session_runner.py` `CommandLine.test_check_refuses_an_edited_prediction` |
| A12 | The content, in which stop 6 quotes `variable db, 851 data bytes` from `events[24].summary` of `normal-1` | the content check runs | it passes; with one character of an evidence line changed, or the line taken from another place, it fails with the rule `evidence` | `test_check_content.py` `CommittedContent.test_the_committed_content_passes`, `SmallContent.test_an_evidence_line_that_differs_by_one_character_fails`, `test_an_evidence_line_from_the_wrong_place_fails` |
| A13 | A claim with the basis "required by UEFI 2.11" and no citation; and a claim about this firmware worded "the specification says" | the content check runs | both fail, with the rules `citation` and `phrase` | `SmallContent.test_a_uefi_basis_without_a_citation_fails`, `test_the_specification_says_on_an_unread_or_firmware_claim_fails` |
| A14, presentation | The screen `s6-verify` of stop 6 | the stage is drawn | it shows exactly one statement, one evidence line and one control for the rest, with "6 of 7" and the stop's label | `App.test.tsx`, "stops 2 to 7 on the stage", "s6-verify shows one statement, one evidence line and one way to the rest" |
| A15 | The same screen | its evidence panel is drawn | the panel holds every claim, every term, the explanation, every console line, every record's digest and every register value the content names | `App.test.tsx`, "the evidence panel for every screen", "s6-verify: every claim, term and line" (one test per screen, 21 in all) |
| A16 | The committed score files | the experiments page is drawn | it shows the two numbers the score files add up to and how many experiments they are summed over, and directly under them the sentence that says the rows are not independent | `Pages.test.tsx`, "the experiments page", "shows the two numbers the committed score files add up to, and under them what they do not show" |
| A17 | No recording, prediction or score on file | the experiments page is drawn | every card says not yet run, and no score is claimed | `Pages.test.tsx`, "the experiments page with nothing on file" (three tests) |
| A18 | A pilot recording on file | its card and its screens are drawn | it is labelled a pilot, shown and not counted, and it is in no headline number | `Pages.test.tsx`, "shows each pilot on file as a pilot, with what its comparison file holds"; `model/experiments.test.ts`, "a pilot on file", "is never scored into the headline numbers"; `content/load.test.ts`, "marks every pilot screen with the sentence that says it is not counted" |
| A19, presentation | A reader who prefers reduced motion, or the address `?static` | the mode is chosen | the story is drawn as still sections with nothing pinned | `model/switches.test.ts`, "is still for ?static and for reduced motion"; `App.test.tsx`, "?static: every step as a still section" |
| A20, presentation | The last screen of the story | the stage is drawn | the way on is a link to `https://lejie710.github.io/nox/`, never a dead link | `App.test.tsx`, "links the way on to the earlier site's public address"; `test_check_content.py` `SmallContent.test_the_way_on_is_an_https_address_or_null_and_never_a_dead_link` |

A5 needs a virtual machine and is not part of the hosted workflow. Every other check runs offline, without one.

## 2. The failures most likely to hurt a reader

The reader assesses validation work. What hurts that reader most is a claim that turns out not to follow from its evidence. Ranked by harm, with likelihood in words.

| # | Failure | Likelihood and impact | Covered by |
|---|---|---|---|
| 1 | **A headline number that is not blind, or does not follow from the files.** A counted run made before its prediction, a prediction edited afterwards, or a score that the recording does not support | Unlikely after the gate was hardened; the worst case, because the measure itself would be false | A6 to A11. Mutation checks 2 and 4 in `MUTATION_CHECKS.md` broke the gate on purpose and tests failed; check 9 broke the sum behind the two numbers. **Not covered by any test:** that nobody booted a counted configuration with other tools before its prediction. That rests on the history and on one audit of the work directory (`RESULTS.md`, "Limits") |
| 2 | **A sentence that presents this project's paraphrase as a requirement of the specification, and is wrong** | Possible: paraphrase is a human step. High impact, because the reader may know the specification | **Not tested.** The content check proves that a citation is complete (`test_each_missing_part_of_a_citation_fails`) and that every cited page in a prediction is one of the pages of the reading (`test_counted_set.py` `CommittedPredictions.test_every_specification_row_cites_a_page_of_the_verified_reading`). Whether the paraphrase is right was checked by reading against the cited page, and no test can do that |
| 3 | **A quoted line, record or register that is not in the recording it names** | Likely during any edit of the content; high impact | A12, A15. Also `content/load.test.ts`, "refuses an evidence line that is not the recorded event's own". Mutation check 8 |
| 4 | **A recording that does not follow from its boot**: readings that disagree, a boot paused before its last record, the wrong part of memory taken for the event log, a hung boot taken for a normal run | Each happened or nearly happened while the recorder was built; high impact | A1 to A3. `test_session_runner.py` `RunBoot.test_a_refused_boot_is_not_over_before_the_firmware_says_so`, `WholeRun.test_two_log_candidates_raise`, `WholeRun.test_a_normal_run_that_was_not_accepted_is_not_recorded`. Remaining risk, stated in `DESIGN.md` risk 6: a record written more than three quiet seconds after the firmware's last line |
| 5 | **The reader takes the numbers for more than they are**: 72 of 72 read as 72 independent predictions, or a pilot read as a result | Likely, because a large round score invites it; medium impact | A16 puts the caveat directly under the numbers, and A18 labels every pilot. The README states both in the same paragraph as the numbers. Whether a reader takes it in is **not measured** |
| 6 | **A changed run blamed on the wrong change**: a store that differs in more than the boot order, a byte in another part of the file than the one named, a run compared with the wrong normal run | Unlikely; high impact, because "one thing changed" is the premise | `test_counted_set.py` `TwoEntryStaging.test_a_changed_order_store_that_differs_in_anything_else_is_refused`, `BaselineRules.test_a_boot_order_run_is_compared_with_its_two_entry_normal_run_only`; `test_committed_recordings.py` `CountedRuns.test_the_signature_recordings_prove_which_byte_was_changed`. Mutation checks 5 and 7 |
| 7 | **A keyboard or reduced-motion reader is stuck or skips a screen**: focus leaves the evidence panel, a key press passes over a short step, the still page is missing | Happened three times during the build; medium impact | The rules are tested as functions (`components/panel.test.ts`, seven key tests; `model/scene.test.ts`, "stepKey"; `App.test.tsx`, "makes no stretch of scrolling shorter than a window's own paging") and as rendered pages (A19). **Not covered by an automated test:** focus in a real browser. It was driven by script in one browser (section 4) |
| 8 | **The page looks wrong in the reader's window**: another browser, a phone held sideways, a short window, a slow first load | Possible; low to medium impact, because the evidence is still reachable | **Not tested** beyond one browser at two sizes. Stylesheet rules are tested as text (motion only by `transform` and `opacity`, contrast ratios, the board's size on a tall stage) |

The untested parts of rows 1, 2, 5, 7 and 8 are carried into the limits of the README.

## 3. Test mix and counts

| Layer | Why this layer | Tests |
|---|---|---|
| **Recorder: unit tests, tests on fixtures of two real boots, and whole runs through a fake machine** | The rules the question depends on are pure functions over bytes and documents, so most faults can be caught where one function is wrong, with no virtual machine | 268 |
| **Recorder: the content check's own tests** | A check that cannot fail proves nothing, so each rule is broken once on small content | 48 |
| **Recorder: tests of the committed evidence** (recordings, comparisons, scores, predictions) | The published files, not only the code, must still follow from each other | 48 |
| **Recorder: integration with real `git`** | The prediction gate sends real git commands; a fake only proves the answers | 3 |
| **Recorder: integration with a real virtual machine** | Only a real boot shows that a normal run repeats on this machine | 6, skipped unless `LUX_VM_TESTS=1` |
| **Site: unit tests of the model** (steps, experiment state, addresses, panel keys, the mark) **and of the stage** (the board's light over time, the pieces a frame is drawn from, the words kept in the stage) | Complete state per step, the state of an experiment, and the level of every light at a time after a step change are plain data, testable without drawing anything | 158 |
| **Site: the content and the recordings as the site loads them** | Guards the site's own reading of the files | 45 |
| **Site: pages rendered to HTML, with no browser**, and the stylesheet read as text | Proves that a page shows what the content and the files hold, and no more | 217 |
| **Browser-level, automated** | None. Motion, layout and focus need a real window; they were checked by a scripted drive and by eye, outside the test suite | 0 |

Recorder total 373 (25 in `test_capture.py`, 48 in `test_check_content.py`, 28 in `test_committed_recordings.py`, 41 in `test_compare_prediction.py`, 65 in `test_counted_set.py`, 32 in `test_eventlog_gate.py`, 6 in `test_integration_vm.py`, 5 in `test_recorded_bytes.py`, 65 in `test_session_runner.py`, 50 in `test_staging.py`, 8 in `test_story_and_repository.py`). The split of the first three rows is by test class: `test_check_content.py` is the second row; `test_committed_recordings.py`, `test_recorded_bytes.py` and the classes `CommittedPredictions` and `TwoEntryNormalRuns` of `test_counted_set.py` are the third. Site total 420 in twelve files (338 in nine before section 13).

Coverage was not measured as a number. The mutation checks do the work a coverage figure cannot: nine rules were broken on purpose on the final code, seven in the recorder, one in the content check and one in the site, and each break failed at least two tests (`MUTATION_CHECKS.md`).

### Results at the commit that added this file

Run on that commit, on one machine: Windows 11 with Python 3.12.10 and Node.js 24.22.0 (npm 11.19.1); Ubuntu 24.04 under WSL 2 with Python 3.12.3, QEMU 8.2.2, OVMF 2024.02, swtpm 0.7.3.

| Check | Command | Summary line |
|---|---|---|
| Recorder unit tests, Windows | `python -m unittest discover -s recorder/tests -t .` | `Ran 368 tests in 33.606s`, `OK (skipped=6)` |
| Recorder unit tests, WSL | `bash scripts/test.sh` | `Ran 368 tests`, `OK (skipped=6)` |
| Recorder tests with the virtual machine, WSL | `bash scripts/test-with-vm.sh` | `Ran 368 tests`, `OK`, then `virtual machines running: none`, `software TPMs running: none`, `guest memory files: none` |
| Content check | `python scripts/check_content.py` | `content check: 5 files, 28 screens, 354 claims, 85 claims uefi-required, 28 claims uefi-platform, 21 claims tcg-unread, 38 claims this-firmware, 167 claims recording, 15 claims general, 14 recordings, 59 glossary entries`, `content check: passed, no problems` |
| Site tests | `npm test` | `Test Files  9 passed (9)`, `Tests  331 passed (331)` |
| Site build | `npm run build` | type check passed, `built in` under one second, one warning: a chunk larger than 500 kB |
| Site format | `npm run format:check` | `All matched files use Prettier code style!` |

The run with the virtual machine boots the plain normal run twice and the two-entry normal run once, and took about two minutes for the whole suite. No counted experiment and no pilot was booted for this document. The same commands were run again after the last change to the documents of that day and gave the same summary lines, apart from the times. The counts in this table are those of that commit: five recorder tests, seven site tests and three claims were added afterwards.

### Last results

Run after the last change to the site and the content (sections 9 to 12), on the same machine, on Windows only:

| Check | Command | Summary line |
|---|---|---|
| Recorder unit tests, Windows | `python -m unittest discover -s recorder/tests -t .` | `Ran 373 tests in 31.480s`, `OK (skipped=6)` |
| Content check | `python scripts/check_content.py` | `content check: 5 files, 28 screens, 357 claims, 85 claims uefi-required, 28 claims uefi-platform, 21 claims tcg-unread, 38 claims this-firmware, 170 claims recording, 15 claims general, 14 recordings, 59 glossary entries`, `content check: passed, no problems` |
| Site tests | `npm test` | `Test Files  9 passed (9)`, `Tests  338 passed (338)`; after section 13, `Test Files  12 passed (12)`, `Tests  420 passed (420)` |
| Site build | `npm run build` | type check passed, one script of 939.97 kB (gzip 186.57 kB); after section 13, 953.82 kB (gzip 191.25 kB), `built in` under one second, one warning: a chunk larger than 500 kB |
| Site format | `npm run format:check` | `All matched files use Prettier code style!` |

**Not repeated after that change:** the recorder's unit tests under WSL and the suite with the virtual machine. The five tests added since read committed files only and boot nothing, so the README's expected `Ran 373 tests` for the suite with the virtual machine is the same test discovery with the six booting tests included; it was not run. The fresh-clone runs (`FRESH_CLONE_RUN.md`) and the mutation checks (`MUTATION_CHECKS.md`) were made before that change and were not repeated; each file states the counts of its own commit. The same offline commands also passed on a hosted runner, at two earlier commits (section 12).

## 4. What was looked at, and what was only checked by script

| What | How | By eye or by script |
|---|---|---|
| All 22 steps of the story, the experiments and sources pages section by section, the strip of seven stops, the still page, and six evidence panels, at 1440 x 900; the steps, the pages and the strip also at 390 x 844 | Screenshots of the running site in a headless Chromium-based browser, read one by one. The phone width was taken through a frame of that width | **By eye**, on screenshots. Three of them were in `docs/images/` at the time |
| The same 22 steps, both pages from top to bottom, and the evidence panel of every step, in true windows of 375 x 812 and 430 x 932; the navigation alone at twelve widths from 280 to 761 px; twelve steps at 375 x 667 | A headless Chromium-based browser driven through its debugging port, with the window size set there and no frame. The script also measured each page for content wider than the window and found none | **By eye**, on screenshots, and by measurement. The script and the screenshots are not in the repository |
| After the last change to the look (section 9): all 22 steps, the first screen of the experiments and sources pages and of the still page at 1440 x 900; steps 0, 12 and 21 in a true window of 390 x 844; the last step at 1180 x 820; the experiment screen of the experiments page | Screenshots of the running site in a headless Chromium-based browser, read one by one; the narrow and the 1180 x 820 windows through the debugging port, which also measured each page for content wider than the window and found none | **By eye**, on screenshots. Three of them were the pictures in `docs/images/` until the final set |
| After the final changes (section 10): all 22 steps, the first screen of the experiments page, its two-run screen and its counted set, the first screen of the sources page and its glossary, the first screen of the still page, the strip of seven stops, and the evidence panels of step 12 and of the two-run screen, at 1440 x 900; the opening and the last step also at 375 x 812, 390 x 844, 430 x 932, 1280 x 720 and 1024 x 768 | Screenshots of the running site in a headless Chromium-based browser at a device pixel ratio of 1, read one by one; the scrolled sections and the other window sizes through the debugging port, which measured the opening and the last step for content wider than the window and found none | **By eye**, on screenshots. Three of them are the pictures in `docs/images/` |
| Brightness of the machine before power | Mean luminance of regions of the screenshots and of the pictures, printed by `site/tools/make_assets.py` and recorded in `site/ASSETS.md` | By script, after a judgement by eye that the first version was too dark |
| Scrolling: Space and Shift with Space, Page Down and Page Up through all 22 steps, a jump to `#step-12`, the strip after the last step, reduced motion giving the still page | The running site driven in real time through the browser's debugging port | **By script only** |
| The evidence panel: Enter and Space open it, Tab stays inside it from a control and from the claims heading, Escape closes it, focus returns to the opener, the page does not move | The same scripted drive | **By script only** |
| Both pictures of the two-run screen painted on a fresh load | Five loads with the cache off | By script |
| The way on to the earlier site | The running site in a browser: the last step holds a link with the address `https://lejie710.github.io/nox/` | By script. The link was not followed |
| The sentence under the two numbers, and the note on a prediction's date | The running site at 1024 x 768 and 375 x 812: the positions of the parts of the first experiments screen were measured, and one phone screenshot was read | By script and by eye. On the phone size the first screen is now 36 px taller than the window |
| Keyboard and focus on the experiments and sources pages (focus moving to the heading on a change of page, the glossary filter) | Tested as rendered HTML only | **Not driven in a real browser** |
| The story scrolled by a person's hand on a real screen | The author scrolled the site in his own browser on the day of the final changes, and those changes answer what he saw | **By the author only.** No second person, and nothing about it was measured |
| Firefox, a window under 600 px tall, a screen reader | | **Not checked** |
| A phone held sideways | Section 13: a window turned to 844 x 390 and back by script, in a desktop Chromium-based browser made to look like a phone. The picture is right at each size; the reader's place is lost (the old build does the same) | By script, in that one browser. Not on a phone |
| Safari on a physical phone | The author opened the published build of `3a2767e` on an iPhone 14 Pro Max: the scrolled story ended the page after a little scrolling; the still page, read to its end, and a frozen step did not (section 13) | **By the author, on the old build only.** The build of section 13 has not been opened on a phone |
| A device pixel ratio above 1 | Section 13: screenshots at ratio 3 and memory at ratios 1, 2 and 3, in a desktop Chromium-based browser made to look like a phone | By script, with the screenshots compared pixel by pixel, in that one browser. Not on a dense screen itself |
| The paraphrases of UEFI 2.11 | Each read against the section and PDF page it cites | By reading; no script can check it |
| The link-preview tags (section 7) | The built `dist/index.html` read, and one build made with a placeholder address | By script. No preview service was asked |

## 5. Defects found and their fixes

These were found by review, by a test or by driving the site. None was planted. Where a note or a commit records it, that is named. "Review" means a separate pass over the finished code or text, made within this project and not by an outside party. No record of a review is in the repository apart from the fix and the test named in each row.

### In the recorder

| # | Defect | Found by | Fix | Now covered by |
|---|---|---|---|---|
| 1 | The prediction gate trusted git's "nothing changed" answer. A prediction edited and hidden with `git update-index --assume-unchanged` passed | Review of the code | The gate reads the committed file out of git and compares its hash with the file on disk (`DESIGN.md` section 11, row 12; commit `cba640e`) | A7; mutation check 4 |
| 2 | Which byte a counted experiment changes was a field of the code, so it could have been chosen after the prediction | Review of the code | It is a parameter of the committed prediction, and the prediction's `change` sentence must equal the experiment's (row 13) | `test_session_runner.py` `WholeRun.test_the_changed_byte_comes_from_the_committed_prediction_and_is_recorded` |
| 3 | A hung boot could be recorded as a normal run, and two hung runs would have compared as identical | Review of the code | A normal run that is not accepted raises and writes nothing; a changed run's timeout is recorded and exits with code 3 (row 14) | `WholeRun.test_a_normal_run_that_was_not_accepted_is_not_recorded`, `CommandLine.test_a_recorded_timeout_gives_exit_code_3` |
| 4 | A refused boot was ended after a quiet period alone, which could come before its last records | Review of the code | The quiet period starts only after the firmware's own line that no boot option is left (row 15) | `RunBoot.test_a_refused_boot_is_not_over_before_the_firmware_says_so` |
| 5 | `compare` accepted a recording with itself or with a renamed copy, which reads as "identical" without a second boot | Review of the code | Equal hashes, equal recording times, a failed gate and a baseline that is not normal are each refused (row 16) | `test_compare_prediction.py` `ComparableAndRepeat.test_a_recording_is_not_compared_with_itself`, `test_a_renamed_copy_is_not_a_second_boot` |
| 6 | `record` wrote over an existing recording, so a counted run could have been repeated until it pleased | Review of the code | It refuses without `--replace`, and never replaces a counted recording (row 17) | `CommandLine.test_an_existing_recording_is_not_overwritten_without_replace`, `test_a_counted_recording_is_never_replaced` |
| 7 | An event with digests only in unknown hash banks counted as matching, so a gate check could pass on nothing | Review of the code | It counts as a mismatch, and the log's header, every event and the live read must name the same four banks (row 19) | `Gate.test_an_event_with_only_unknown_bank_digests_does_not_count_as_matching`, `test_a_log_header_that_declares_other_banks_fails` |
| 8 | Once predictions were committed, a typed `record` command would have spent a counted experiment's one run. A test and a README example relied on "no prediction exists" for their refusal | Noticed right after the predictions were committed. The test was stopped by the repeat precondition and by its replaced machine, so nothing was booted | `record` needs `--for-the-record`, checked before the prediction is looked at (row 34; commit `e1d63f7`) | A8 |
| 9 | The first version of the boot order experiment edited the store file offline, so "the firmware accepted this write" was an argument and not an observation | Design review before any counted run | The order is written by the firmware in a preparation boot (decision D6) | `test_counted_set.py` `TwoEntryStaging.*`, mutation check 5 |

### In the content and the site

| # | Defect | Found by | Fix | Now covered by |
|---|---|---|---|---|
| 10 | The evidence panel lost Escape and its Tab loop after a click on plain text; then focus could not return to the opener while the page was still out of reach | Review, and driving the site | Keys are heard on the document while the panel is open; focus returns in an effect after the panel has closed (commit `62ff35a`) | `components/panel.test.ts`, "closes on Escape, wherever focus is", "brings focus in when it sits on the panel itself" |
| 11 | Opened from a citation marker, the panel let Tab leave it when no control followed the claims heading | Driving the site after the first fix | Tab goes on from the heading to the next control, or wraps (commit `55c3f64`) | `components/panel.test.ts`, "lets Tab go on from a heading inside the panel, to the control that follows it" |
| 12 | A window's own paging was longer than a short step of the story, so Space or Page Down could pass over a screen | Review | One key press is one step, and no stretch of scrolling is shorter than a window (commit `e117692`) | `model/scene.test.ts`, "stepKey" (three tests); `App.test.tsx`, "makes no stretch of scrolling shorter than a window's own paging, so no screen can be passed over" |
| 13 | The machine before power was close to the black of the page: on an ordinary screen the laptop was hard to tell from the background, and the running laptop was dimmer than the one before power | Looking at the site | The dark pictures are lifted by one curve each, the lid gets a rim and a sheen, the background stays black; measured before and after (commits `9706662`, `49c1198`; `site/ASSETS.md`) | Measured values in `site/ASSETS.md`. No test: it is a judgement of the eye |
| 14 | On short, wide windows the title touched the laptop; on a phone the processor was half out of frame | Review of screenshots | The title size follows the stage's height; a tall stage draws the board large and slides it to the parts a step is about (commit `e67434d`) | `App.test.tsx`, "sizes the opening's title from the stage's height too", "draws the board large on a tall stage", `model/scene.test.ts`, "focusAt" |
| 15 | The content said that no recording of the pilots `e1`, `e4` and `e5` existed after they had been recorded; later, sentences said the counted experiments had not been run after they had | Review of the facts | The sentences were brought in line with the committed files, and what has been run is read from the files (commits `7a006d1`, `1cc1126`, `dd16060`) | The state on the page comes from the files (A16 to A18). A status sentence in the content is still kept true by hand |
| 16 | A statement that the authority record follows the loader's acceptance did not hold: the record is present in the refused pilot `e5` | Review of the facts against the recordings | The content names the runs where the record is present or absent and states no rule (commit `2b900e6`) | `test_committed_recordings.py` `OtherPilots.test_e5_logs_the_authority_record_although_the_loader_is_refused` |
| 17 | "Continue in Nox" was a link that led nowhere | Review | The label is a link only when the content holds an `https://` address, and the content check refuses anything else; the address is now set | A20 |
| 18 | A prediction's panel showed "Written 2026-11-15" beside a run recorded on 2026-11-14 (UTC), which reads as if the run came first. The prediction's date is a local calendar date, eight hours ahead of UTC | A second check of the results | The panel says that the date is a local one and names the commit the run was scored under; `RESULTS.md` puts every time on one clock | `Pages.test.tsx`, "says that a prediction's date is a local one, and names the commit it was scored under" |
| 19 | The two headline numbers stood on the experiments page with their caveat one press away | Review of the page against the README | The sentence that the rows are not independent stands directly under the numbers, from the content | A16 |
| 20 | The larger laptop made for the last screen was also drawn on the experiment screen and the screen before the last, where the light under its keys is not turned down. On the experiment screen its lid sat 11 px under the pilot label and its base ran 9 px into a two-line evidence line. In a window of about 1180 x 820 the larger laptop also touched a two-line evidence line on the last screen | Review of screenshots | The laptop is enlarged on the last screen only, and only in a window at least three wide to two high and 800 px high (commit `2ebfe4b`) | No test: a judgement of the eye. Screenshots of steps 15, 20 and 21 at 1440 x 900 and of step 21 at 1180 x 820 were read after the fix |
| 21 | When stop 5 began to state the stored boot order from the raw log (0000 first), the limit "why option 0000 was not started" was dropped, although the log still does not show why the console names 0001. The same stop said "the recording shows" bytes that only the raw log holds | Review of the facts against the raw log | The limit is stated again in the form the log supports, and the sentence names the raw event log (commit `cf1fc46`) | Read by hand. `test_recorded_bytes.py` guards the byte values, not the wording of a limit |
| 22 | A page opened at `/#overview`, below the story, showed the opening in the last rows of the pinned stage above the strip: the title cut off under the navigation and across the name beside the mark. No marker lies on the window's middle line there, so the step kept its first value | Reading the final screenshots | On the first report of the markers, when none is on the middle line, the step is the last one whose marker starts above it | `model/scene.test.ts`, "stepPassed" (two tests). The landing was then driven in a headless browser: `/#overview` shows the last step, `/#step-12` step 12, `/` the opening |
| 23 | In a wide window under about 1240 px across, the evidence capsule in the foot is two to four lines high and lay over the laptop of steps 15, 20 and 21: over the palm rest on the last step at 1024 x 768, over the whole keyboard on step 15 there, and over the palm rest on step 15 at 1180 x 820. The record of section 10 said that no final screenshot showed overlap | A closing audit that read the project's own shot of the last step at 1024 x 768 | In a window between 761 and 1240 px across the laptop of those steps is smaller and ends above the capsule, and smaller again when the window is at most 700 px high (commit `64c970a`) | No test: a judgement of the eye. Steps 15, 20 and 21 were shot again at thirteen window sizes and read; the measured edges are in section 11 |
| 24 | On a card of the counted set at 1440 x 900 the value "1 and 4" broke into two lines beside its long label | The same audit | On a card a value does not shrink, so its label wraps beside it (commit `64c970a`) | No test. The counted set was shot again and read |
| 25 | Three stale sentences and a dead link. The opening's evidence still said that the only changed run committed was a pilot and that no score was claimed; the sources page still said that no licence had been chosen and gave no licence for two tools that the README names; the link to the reset vector file on the firmware project's master branch answered "not found", because that branch has renamed the file | The same audit | The sentences say what is committed; the link leads to the tag `edk2-stable202402`, where the file has its name, and the page says so (commit `778bfa2`) | The content check passes before and after: it cannot see a stale explanation or a dead address. Read by hand; the tag's page was opened on 2026-11-15 |
| 26 | From a middle step of the scrolled story the End key carries the page to its foot, and the stage could stay on the step the jump left behind: the last markers can pass the window's middle line between two observations, and the rule of defect 22 was applied to the first observation only. Seen on the live site: the page at its foot with the stage on stop 5 of 7, and in a second drive on the step before the last | The walk of the live site (section 12) | Whenever an observation has no marker on the middle line, the step is the last one whose marker starts above it (`stepShown` in `site/src/model/scene.ts`, used by `site/src/stage/useStepScroll.ts`; commit `8413843`) | `model/scene.test.ts`, three tests of `stepShown`. A scripted drive of a local build pressed End and then Home from five different steps, ten times in all, and landed on the last step and on the opening every time. The site's tests do not open a browser, so the observer itself is not under test |
| 27 | On an iPhone, in its own browser, the scrolled story of the published site ended the page after a little scrolling ("A problem occurred"). The stage held 17 full copies of the lit board picture over the dark one at all times, each as large as the board's box (2925 x 1829 pixels on a phone 390 px wide at three screen pixels to one), eight of them with a filter and a blend mode, and the words of all 22 steps over those. The cause is not proven: memory is what the numbers of section 13 point to, and the phone's browser does not say why it ends a page | The author, on his phone, after publication | In the scrolled story the board is drawn on one canvas with at most 1920 x 1200 pixels, and the stage holds one step's words; a still is drawn as before (decision P6 of `ENGINEERING.md`; commits `4cd49a2`, `f7b6929`, `1a31fce`, `5142885`, `d11246d`) | `stage/light.test.ts`, `stage/cutouts.test.ts`, `stage/words.test.ts`, and in `App.test.tsx` "keeps in the page only the words of the step in view", "draws the board's lights on one canvas", "draws in each section only the layers its step shows, and makes no canvas" and "the board as layers". Section 13 gives the measurements. **Open: not yet seen fixed on the phone** |

### Open, known, not fixed

| # | What | Why it is open |
|---|---|---|
| O1 | The site is one script of 940 kB, and it grows with every recording | Splitting it by page means making the one synchronous door to the recordings asynchronous, a change of structure. Left with its measurement |
| O2 | A few status sentences in `content/experiments.json` repeat what the files show (for example the status of a counted card) | They are true and checked by reading. Nothing fails if one goes stale |
| O3 | Process cleanup when QEMU is killed from outside is not covered by a unit test | It needs real processes. The integration test and `scripts/check-clean.sh` cover it |
| O4 | `recorder/pe.py` names Microsoft's Authenticode format document as its method reference, while the site lists that document as not read | The digest is confirmed against what the firmware measured, and no claim on the site cites the document. The README says both |
| O5 | The exact printed wording of the UEFI specification's copyright line has not been checked against the publisher's page | It was not done before the site was published on 2026-11-15, and is still open; noted in `content/sources.json` |
| O6 | Closed. The code is under the MIT License and the site's text and images are reserved (commit `2c82429`) | It was the owner's decision, and it is made |
| O7 | The rule `load-verify` in `recorder/storymap.py` gives as its basis "present when the loader is accepted, absent when it is refused". The refused pilot `e5` has the authority record all the same | The rule's name and the stop it assigns are right, and `PILOTS.md` and the site state what `e5` shows. The sentence in the code was written before `e5` was recorded and was left as it is; `DESIGN.md` section 7 carries a note |

## 6. Release assessment

**Implemented.** The recorder with its four commands; 14 committed recordings, 11 comparisons, 4 predictions and 4 scores; the content in five files; the content check; the site with the story in 22 steps, the experiments page, the sources page, the strip of seven stops and the evidence panel; build settings for a static host; link-preview tags and picture; two hosted workflows, one that checks and one that checks and publishes; the site published at `https://lejie710.github.io/lux/`.

**Tested.** Everything in section 3, on one machine. The acceptance checks A1 to A20 pass. Nine rules were broken on purpose on the final code and each break was noticed. The normal runs were booted again for this document and equal the committed recordings. The README was followed in a new clone; three of its steps failed as written, the README was corrected, and those steps were typed again in a second new clone and matched; in a third new clone the packages were installed with `npm ci` and the site's commands, the content check, the unit tests and the making of one score were typed and matched, with nothing booted (section 8). The check workflow passed on a hosted runner at two commits, the publishing workflow at one, and the published site was walked once in a fresh browser profile (section 12).

**Simulated, and labelled as such.** The machine is a virtual machine under software emulation and the TPM is a program; both are named on the site and in every limit list. Power sequencing does not exist there, and stop 1 says "described, not recorded". Tests that drive a whole run use a fake machine that replays a normal boot; the scores those tests produce mean nothing and only the path is proven (`DESIGN.md` section 10). The fixtures in `recorder/tests/fixtures/` are real output of two boots, made with an earlier key set. The pictures are illustrations.

**Unverified.**

- **The hosted runner, beyond three runs.** The two workflows have passed on one runner image at the commits section 12 names. Another Node.js or npm patch version, or a later version of an action taken by its major number, may still differ. The runner boots nothing, so it says nothing about the recordings.
- **The live site, beyond one walk.** One Chromium-based desktop browser, one connection, one day, at commit `0fa1d15`. No preview service has fetched the page, the 13 links that lead to other sites were not requested, and the fix of defect 26 was driven on a local build only (section 12).
- **Any second machine.** The recordings were reproduced only on the machine that made them, in every run from a new clone as well. The recorder refuses another firmware package; what another QEMU version does was not tried.
- **Any browser but one**, and a screen reader (section 4). One real phone was tried, and the scrolled story failed on it (defect 27).
- **The fix of defect 27 on a phone.** It was measured and looked at only in a desktop Chromium-based browser made to look like a phone, in which the fault never showed with either build. That it ends the fault on the phone is not known until the phone has opened the new build (section 13).
- **Motion.** It was judged by the timing a script read and by the author's own scrolling. Frame rate was not measured, and no second person has scrolled the story (section 10).
- **Repeatability of a changed run.** Each counted experiment was booted once, by rule.
- **What a Trusted Computing Group document or the Platform Initialization specification requires.** Neither was read. No statement on the site or in the results claims a requirement from either.
- **That no counted configuration was ever booted before its prediction.** The history and one audit of the work directory say so; no mechanism proves it, and the audit's script and output are not in the repository (`RESULTS.md`, "Checked a second time", marks the rows a reader cannot repeat).

**Assessment.** The evidence chain from a boot to a number on the page is implemented and tested end to end without a virtual machine, and the one link that needs a real boot, that a normal run repeats, was run again and holds. The result is honest only together with its caveats: four counted experiments, one run each, rows that are not independent, one firmware build in a virtual machine with a software TPM, and two documents unread. Those are stated beside the numbers, in the README and on the experiments page. The hosted check workflow has passed, and the repository is public and the site live since 2026-11-15 (section 12). The licence is chosen: the MIT License for the code, with the site's text and images reserved. The author has scrolled the story by hand; nobody else has.

## 7. Link-preview metadata

Read from the built `site/dist/index.html`:

| Tag | Present | Value |
|---|---|---|
| `<title>` | yes | `Lux: what your laptop does before it wakes` |
| `meta name="description"` | yes | One sentence on what the site is |
| `og:type`, `og:site_name`, `og:title`, `og:description` | yes | `website`, `Lux`, the title, the description |
| `og:image` | yes | `cover.jpg`, a relative address, in a plain build |
| `og:image:width`, `og:image:height`, `og:image:alt` | yes | 1200, 630, and a sentence that says the picture is an illustration |
| `twitter:card` | yes | `summary_large_image` |
| `og:url`, `link rel="canonical"` | only with `LUX_SITE_URL` | |

The picture `dist/cover.jpg` is in the build and is 1200 x 630. It is the README's cover fitted to that size. Until 2026-11-15 the file was named `og.jpg` and held another picture; the records below that name `og.jpg` describe that earlier file. It was renamed so that services which had stored the earlier picture under its address fetch the new one.

**An absolute address for the preview picture needs a public address.** Before there was one, a build made with `LUX_SITE_URL` set to a placeholder address and `LUX_BASE=/lux/` was checked: `og:image` then holds the absolute address of `og.jpg`, `og:url` and the canonical link appear, the asset paths start with `/lux/`, and the link in `404.html` leads to `/lux/`. That showed the mechanism. Since 2026-11-15 the published build carries the real address, and the tags were read as served from a fresh browser profile (section 12). It is still not a seen preview: no preview service has been asked to fetch the page.

The tags are also pinned by a test: `Pages.test.tsx`, "previews a link with a picture, a title and a description".

## 8. A run from a fresh clone

Recorded in full, command by command, in [`FRESH_CLONE_RUN.md`](FRESH_CLONE_RUN.md). In short:

| Run | What was done | Result |
|---|---|---|
| First, at commit `b3222a5` | The README followed in its own order in a new clone: `npm ci`, the site's commands, and under WSL `prepare`, three recordings, the refusal of a counted experiment, `compare`, `check`, the tests with and without the virtual machine, the content check | Every output line the README printed came back equal, and `npm ci` succeeded from the lock file (47 packages). **Three steps failed as written:** `python3` is not a command on Windows; `npm run dev` stopped because another process held the fixed port; and the README's own recording examples, written into `recordings/`, made its later test section fail. Eleven findings in all |
| Second, at commit `89fa143` | The README was corrected for those findings. In a second new clone the recorder steps were typed again in order, with the recordings now written to the ignored folder `scratch/`, then the tests with and without the virtual machine and the content check, under WSL and with `python` on Windows | Every line equal to the corrected README, with the reader's own recordings still on disk, and a clean `git status` afterwards. `npm ci` was not repeated there, and the site's commands were run in the working tree, not in the clone |
| Third, at commit `2d2c5ba` | A third new clone with no installed packages in it. `npm ci` from the lock file, then in that clone: `npm test`, `npm run build`, `npm run format:check`, `npm run dev` on port 5200 with one headless screenshot of the first page, `npm run preview` on port 5201; on Windows with `python` the content check and the recorder's unit tests; under WSL the two commands that make the score of `signature-byte-1` again. Nothing was booted | `added 47 packages, and audited 48 packages in 7s`, `found 0 vulnerabilities`; 9 files and 331 tests passed; 936.99 kB, gzip 185.69 kB, the chunk warning, `built in`; Prettier clean; the opening screen rendered; both lines of the content check; `Ran 368 tests`, `OK (skipped=6)`; `identical: false`, `[4, 5, 7]`; `1 of 1`, `17 of 17`, `mismatches: none`. Every line equal to the README. One finding: the line of `npm ci` that the README quoted is not the last line of its output; the README was corrected |

What the three runs together still do not show:

- **Not one pass of the corrected README in one clone.** The steps that boot the virtual machine (`prepare`, the recordings, `bash scripts/test-with-vm.sh`) were typed in the first and second clone and not in the third; `npm ci` and the site's commands were typed in the first and third and not in the second. Every part of the corrected README has matched in a new clone, but no single clone has done all of it since the corrections.
- **Not a cold package cache.** Whether `npm ci` fetched every package over the network in the third run or took some from npm's cache on this machine was not looked at.
- **Not the default port.** In all three runs another process on the machine held port 5183, so the site was seen on ports 5191, 5200 and 5201 only. `npm run dev` printed the message the README quotes.
- **Not a clean install of the Ubuntu packages, not an ordinary Linux user, not a second machine.**
- **Not the hosted workflow.** It ran afterwards (section 12).

An earlier clone at commit `dc52dbe` ran only the test commands on Windows, with the installed packages copied from the working tree. The three runs above replace it.

## 9. The last change to the look and to stops 4 to 6

Made on 2026-11-15 in nine commits, `5cf4d0a` to `cf1fc46`, after every run and check described above. No experiment was run again, and no recording, prediction or score was touched.

**What changed in the content.** Stops 4, 5 and 6 state values that the summary in `recording.json` does not hold and the raw event log beside it does: the `SecureBoot` variable is one byte, `01`; `BootOrder` is `00 00 01 00`; the value of `Boot0000` begins `09 01 00 00` and carries the text `UiApp`; the value of `Boot0001` begins `01 00 00 00` and carries the disk's name; and the 879 bytes of the `db` variable are 28 bytes followed, byte for byte, by the 851 bytes of the key record. `recorder/tests/test_recorded_bytes.py` (5 tests) reads each value from `recordings/normal-1/eventlog.bin` with the recorder's own parser and compares it with the sentence in the content. No sentence was added about what a specification requires, what the 28 bytes are, or why the console names option 0001 when the stored order lists 0000 first; stop 5 lists that last point as not shown.

**What changed in the look.**

| Change | Where |
|---|---|
| A step's statement is at most 52 px at weight 600 (was 68 px at 750), the title at most 92 px at weight 600; the three greys carry a cool tint | `site/src/styles/lux.css` |
| A lit part that a board step is not about rests at half its light, so the part the step is about is the warm point. Once every part is lit (steps 18 and 19) nothing rests | `layersAt` in `site/src/model/scene.ts`, two tests in `scene.test.ts` |
| On the last screen, in a window at least 800 px high and three wide to two high, the laptop is drawn at 660 x 495 at 1440 x 900 (was 535 x 401); as its screen lights, a shade from the hinge down turns down the light under the keys (the shade was removed again, section 10); "Continue in Nox" is a filled button | `lux.css`, one attribute in `components/Stage.tsx` |
| A step's statement arrives sooner; the rail and the foot no longer fade out at each step change | `lux.css` |
| The opening's laptop stands lower under the navigation | `lux.css` |
| In a window wider than 760 px the evidence line and "Open the evidence" form one capsule | `lux.css` |

**Checked.** The checks of section 3, "Last results". The site's test that nothing but `transform` and `opacity` moves still passes, and no existing test was edited. The screenshots of section 4, first row. During the change, steps 0, 2, 6, 12, 15, 19, 20 and 21 were also read at 1280 x 720 after each commit; in a review after it, the last step at 1366 x 768 and 1920 x 1080.

**Not verified, or known and left.** Two points of this list were overtaken by section 10: the shade is gone, and the author has scrolled the story.

- **Motion was not seen by eye.** That the statement is readable sooner (about 0.6 s after a step change, before about 1.15 s) was measured by reading the computed opacity at sampled times in a headless browser. Frame rate was not measured. A person has still not scrolled the story by hand (section 4).
- **For about 0.4 s after a step change** the evidence line and the control still seen are those of the step being left, and that control does not respond; the control of the new step is in place under it. Keyboard reach and the return of focus were not driven again in a browser; the panel's code and its tests are unchanged.
- **Under 800 px of height the last screen is calmer but not larger**: at 1280 x 720 its laptop is 428 x 321, smaller than the opening's. The same holds in a window narrower than three to two.
- **On steps 6, 7, 10, 12 and 13 the part the step is about is the small security chip**, so the warm point is small and the board reads as evenly dim. Steps 18 and 19 are at full light by decision, so they have no single warm point.
- **The shade also darkens the metal deck** of the laptop on the last screen. Whether that reads as too dark is a judgement nobody but the builder has made.
- **The section titles of the experiments and sources pages and the title of the evidence panel** keep their heavier weight; only the statements changed.
- **One claim at stop 5** names the first four bytes of a boot option "attributes" and its text "description" under the basis "recording". The numbers are in the bytes; the two names are a reading of the bytes against the UEFI layout, for which no citation was added. The sentence says "this page calls".
- **The suite with the virtual machine, the unit tests under WSL, the fresh-clone runs and the mutation checks were not repeated** after this change (section 3).

## 10. The final changes

Made on 2026-11-15 after section 9, in the commits `99c9865`, `40137be`, `a337644` and `8454239`, and the commit that added this section. No experiment was run again, and no recording, prediction or score was touched.

| Change | Where |
|---|---|
| The last screen fades in a second generated picture of the lit laptop, in which the light under the keys is turned down. The shade that section 9 describes was removed from the stylesheet. The picture a link is previewed with was made again from the same second picture | `site/src/assets/laptop-awake.webp`, `site/public/og.jpg`, `site/tools/make_assets.py`, `site/src/styles/lux.css`, `site/ASSETS.md` |
| The opening's invitation to scroll names the author: "An explainer of the UEFI boot by Le Jie Tan, from public specifications and one recorded boot", the same place and form as on the earlier site | `content/story-a.json` |
| A page opened below the story shows the last step in the stage's last rows (defect 22) | `site/src/stage/useStepScroll.ts`, `stepPassed` in `site/src/model/scene.ts`, two tests |

**Checked.** The checks of section 3, "Last results", all run after the last of these changes. The screenshots of section 4, the row "After the final changes": every one was opened and read, and none was seen to show overlap, clipped text or a line past the window's edge. That reading missed one: the shot of the last step at 1024 x 768 shows the evidence capsule lying over the laptop (defect 23, section 11). The three pictures in `docs/images/` are from that set.

**Still unverified.**

- **Motion.** Judged by the timing a script read (section 9) and by the author's own scrolling. Frame rate was not measured, the fade of the new picture on the last screen was seen only as its end state on a screenshot, and no second person has scrolled the story.
- **Other browsers.** One Chromium-based browser only. Firefox and Safari were not opened.
- **A physical phone.** The narrow sizes are windows of a desktop browser, not a device, and none was held sideways.
- **A screen reader.** None was run. The spoken status line and the labels are tested as rendered HTML only.
- **A device pixel ratio above 1.** Every screenshot was taken at a ratio of 1, so how the pictures and the hairlines look on a dense screen was not seen.
- **The hosted check workflow.** It had never run when this section was written. It has since (section 12).
- **Not repeated after these changes:** the evidence panel's keys and focus in a browser, the pages and panels from top to bottom at the narrow sizes (only the opening and the last step were taken again there), the recorder's unit tests under WSL, the suite with the virtual machine, the fresh-clone runs and the mutation checks.
- **The brightness of the new picture of the lit laptop** was not written into `site/ASSETS.md`; its table still holds the values of the first picture.

## 11. Closing corrections

Made on 2026-11-15 after section 10, in the commits `778bfa2` and `64c970a`, and the commit that added this section. They answer a closing audit of the repository at commit `40984d1` (defects 23 to 25). No experiment was run again, and no recording, prediction or score was touched.

| Change | Where |
|---|---|
| The opening's evidence says that four pilots and four counted runs are committed. The sources page states the licence of the recordings and of two tools as the README does | `content/story-a.json`, `content/sources.json` |
| The reset vector file is linked at the tag `edk2-stable202402`. The five other firmware source links still lead to the master branch, where those files were read | `content/sources.json`, `content/story-a.json` |
| In a window between 761 and 1240 px across, the laptop of steps 15, 20 and 21 is 39 percent of the stage's height (32 percent when the stage is at most 700 px high), so it ends above the evidence capsule | `site/src/styles/lux.css` |
| On a card of the experiments page a value keeps its width and the label wraps | `site/src/styles/pages.css` |

**Checked.** The checks of section 3, "Last results", all run after these changes. Steps 15, 20 and 21 were shot through the browser's debugging port in true windows of 1024 x 768, 1024 x 700, 1024 x 650, 1180 x 820, 1100 x 720, 1200 x 760, 1000 x 1000, 900 x 720, 800 x 1100, 1280 x 1024, 1440 x 900, 1366 x 768 and 1280 x 720, and the edges of the laptop's box and of the foot were read by script. Twelve of the shots were opened and read: steps 15 and 21 at 1024 x 768 and at 1180 x 820, step 20 at 1024 x 768, and step 15 at 1024 x 700, 1024 x 650, 1100 x 720, 1000 x 1000, 1280 x 1024, 1366 x 768 and 1280 x 720. The counted set of the experiments page was shot at 1440 px across and read.

| Window | Step | Laptop's box ends at | Capsule begins at |
|---|---|---|---|
| 1024 x 768 | 15 | 548 px | 559 px |
| 1024 x 768 | 21 | 548 px | 618 px |
| 1024 x 700 | 15 | 474 px | 494 px |
| 1024 x 650 | 15 | 440 px | 444 px |
| 1180 x 820 | 15 | 585 px | 669 px |
| 1000 x 1000 | 15 | 714 px | 778 px |
| 900 x 720 | 15 | 514 px | 514 px |

At 1440 x 900, 1366 x 768, 1280 x 720 and 1280 x 1024 the measured edges are the same as before the change, to the pixel. The tag's page of the reset vector file was opened and begins "First code executed by processor after resetting".

**Still unverified, or known and left.**

- **Everything listed at the end of section 10** still held when this section was written; the hosted workflow has run since (section 12).
- **Between 761 and 1240 px across the laptop is small**: 324 px wide on step 15 at 1024 x 768, and 210 px wide at 1024 x 650. It is clear of the words and of the capsule; it is not the picture the wide window has.
- **Under 650 px of height in such a window** the capsule and the laptop were not shot. A window under 600 px tall is untested, as before.
- **At 1366 x 768 and 1280 x 720 the box of the laptop on step 15 ends 13 and 17 px below the top of the capsule.** The box is larger than the drawn laptop, and on the screenshots the two do not touch; that is a judgement of the eye, unchanged by this section.
- **The five firmware source links to the master branch** loaded on 2026-11-15. A branch moves, so any of them may stop loading, as the sixth did.
- **The address `https://uefi.org/specs/UEFI/2.11/`** refused the tool that fetched the others. It was not opened in a browser for this section.
- **The fresh-clone runs, the mutation checks, the unit tests under WSL and the suite with the virtual machine** were not repeated after these changes.

## 12. Publication and the live site

On 2026-11-15, after section 11, the repository was made public at `https://github.com/lejie710/lux` and the site was published on GitHub Pages at `https://lejie710.github.io/lux/`. No experiment was run again, and no recording, prediction or score was touched. No runner boots a virtual machine or records a run.

### The hosted runs

Read from the repository's public list of workflow runs on 2026-11-15. Times are UTC.

| Workflow | Commit | Started | Result |
|---|---|---|---|
| `Check` | `6dab704` | 10:56 | Passed: both jobs, every step |
| `Check` | `0fa1d15` | 11:29 | Passed: both jobs, every step. The recorder job ran the unit tests and the content check; the site job ran `npm ci`, the format check, the build and the tests |
| `Deploy`, first attempt | `0fa1d15` | 11:29 | **Failed.** The content check, `npm ci`, the format check, the tests and the build passed; the step `actions/configure-pages` failed, because Pages had not yet been switched on in the repository's settings. Nothing was uploaded or published |
| `Deploy`, second attempt | `0fa1d15` | finished 11:33 | Passed, after the Pages source was set to "GitHub Actions". The index of the site as served was last modified at 11:33:47 |

`.github/workflows/deploy.yml` was added in commit `0fa1d15`. It sets `LUX_BASE=/lux/` and `LUX_SITE_URL=https://lejie710.github.io/lux/`, the two settings of section 7.

### The walk of the live site

The published address was opened on the same day in a new, empty profile of one Chromium-based desktop browser, run headless, with no cache, no cookies and no storage: what a first visitor has. The windows were 1440 x 900 and a true 390 x 844 window with phone emulation. The scripts, the screenshots and the list of every request are not in the repository.

| What | Result |
|---|---|
| The 22 steps by `?step=N`, one evidence panel, the first screens of the two pages and of the still page, at 1440 x 900 | Every screenshot was opened. Each is byte for byte equal to the screenshot of the same address taken from the local build |
| The pages read from top to bottom, at 1440 x 900 and at 390 x 844 | No missing picture, no fallback font and no path that fails under `/lux/`. Both fonts report as loaded, every picture has its natural size, and every request answered 200 |
| The scrolled story | The wheel passed all 22 steps in order and mirrored them on the way back. Page Down, Page Up, Space and Shift with Space each moved one step |
| The End key | Found defect 26 (section 5). The published build has it until the commit that fixes it is published |
| Addresses opened directly, then reloaded | 13 addresses, among them `#step-12`, `#overview`, `#/experiments/experiment-e2`, `#/sources/glossary`, `?step=12&evidence` and `?static`, landed where the README's table says, before and after the reload. An unknown path answers 404 with the site's own page and a link back |
| The link to the earlier site | Leads to `https://lejie710.github.io/nox/`, which answered 200 |
| The README's demonstration steps | Each address and each key of its table behaved on the live site as the table says |
| The first load | 14 files, 658,416 bytes of body as sent (661,781 bytes on the wire in the browser, headers included) and 1,443,573 bytes uncompressed. The opening screen uses 284,700 bytes of that; the other 373,716 are the seven pictures of later steps, fetched in the background. The script is 182,202 bytes as sent, of 939,807. Scrolling the whole story asked for nothing more. The experiments page opened directly: 9 files, 374,799 bytes; the sources page: 7 files, 286,626 bytes. Only two of the 17 font files were ever requested |
| What the host does | It compresses the index, the script, the stylesheet and the icon with gzip, and does not offer brotli. Every file carries a cache lifetime of ten minutes. Neither can be set from the repository |
| What leaves the device | 887 requests in the walk: 690 to `lejie710.github.io` and 197 addresses that begin `data:`, which are pictures written inside the script and the stylesheet and cause no request. No other host, and no method but GET. No cookie was set or sent. Local storage, session storage, IndexedDB, cache storage and service workers were empty after the first screen and at the end. Typing in the glossary filter made no request, left the address as it was, and was gone after a reload |
| The link-preview tags as served | The title, the description, `og:type`, `og:site_name`, `og:url`, the canonical link and `twitter:card` are present. `og:image` is `https://lejie710.github.io/lux/og.jpg`, which answered 200 as `image/jpeg`, 66,058 bytes, 1200 x 630, the same bytes as `site/public/og.jpg` |

### What the walk does not show

- **One browser.** Firefox and Safari were not opened. No physical phone, no touch scroll, no screen reader, no slow connection.
- **One connection, one day.** The sizes are what the host sent then.
- **No preview service.** The tags were read; no service that draws a preview was asked to fetch the page.
- **The 13 links that lead to other sites** (the firmware project's source files, the TPM emulator, the specification's publisher, the virtual machine's project) were not requested in the walk.
- **One card's evidence address** was not opened by address. All twelve evidence controls on the two pages opened their panels.
- **Six of 42 compared screenshots differ from the local ones.** One shows a value on one line that the older local shot wrapped (defect 24, fixed before publication). One page sits 1 px higher with the same words. The others differ faintly in a moving part of the picture; that was put down to the moment of the shot and was not proven.
- **A page opened directly at the experiments or the sources fetches the dark laptop picture of the opening (30 kB) without using it**, because the index preloads it. Known and left.
- **The fix of defect 26 on the live site.** It was driven on a local build of commit `8413843`. On the published build of `0fa1d15` the same drive showed the defect once; most of its other tries did not load in the time the script allowed and say nothing.
- **Any later deployment.** Each push to `main` publishes again. The walk is of the build of `0fa1d15` only.

## 13. The page that ended on a phone, and the board of the scrolled story drawn on one canvas

**The report.** On 2026-11-16, after publication, the author opened the live site (the build of commit `3a2767e`) on his own phone, an iPhone 14 Pro Max, in its own browser. After a little scrolling of the story the browser ended the page and showed "A problem occurred". On the same phone the still page (`?static`), read to its end, and a frozen step (`?step=12`) stayed up. Nothing was recorded again, and no recording, prediction, score or sentence of the content was touched: this is a fault of how the site draws.

**What every number in this section is, and is not.** All of them were taken on 2026-11-16 and 2026-11-17 in one desktop Chromium-based browser, run headless on a Windows laptop with an integrated graphics adapter and made to look like a phone: a window of 390 x 844 or 430 x 932 (the size of the phone above), touch input, a phone's user agent. A few rows name a desktop window of 1440 x 900 in the same browser instead. **It is a desktop browser pretending to be a phone. It is not the phone's engine.** No run in it ever ended a page, with the old build or the new, so the fault itself was never reproduced here and nothing below shows that it is gone. The device pixel ratio was set as the browser's own scale factor at start-up, because the ratio a page is merely told does not change how many pixels this browser draws. The scripts and the screenshots are not in the repository.

### What was measured before the change, and what it points to

The method: the browser's debugging port, driven by script. Three things were read. (1) The browser's own memory report, taken at chosen moments: tiles, decoded pictures, shared images, the caches of its drawing library, compositor resources and canvases, added up and called "graphics memory" below. (2) The compositor's list of layers, during and after a step change. (3) The private bytes of the browser's graphics process, sampled twice a second through a walk of the story.

In the old build the scrolled story kept 17 elements over the dark board picture at all times, lit or not: nine cut-outs and eight added lights, each a copy of the 1920 x 1200 lit picture as large as the board's box, each with a stylesheet mask, the eight added lights also with a filter and a blend mode. On a stage taller than wide the box is two and a half times the stage's width: 2925 x 1829 pixels in a window of 390 x 844 at three screen pixels to one. At rest this browser flattened them. During a step change it gave up to 18 of them a layer of their own at that size (about 400 MB at four bytes a pixel) for 1.3 to 3.3 s, and graphics memory went from 112.2 MB at the opening to 924.2 MB in the middle of the change from step 17 to step 18. The figure follows the screen: 215.4 MB at one screen pixel to one, 468.0 MB at two, 924.2 MB at three, and 1090.5 MB in a window of 430 x 932 at three.

**The cause is not proven.** The phone's browser gives no reason when it ends a page. What supports memory as the cause: the cost above grows with the square of the screen's density and is paid exactly while a step changes, and on the phone the two addresses that hold only the layers of one step stayed up while the one that holds all 17 did not. What is missing: the fault in a browser where it can be measured, and any figure from the phone's own engine, which decides in its own way what gets a layer.

### What changed

Decision P6 of `ENGINEERING.md`, in commits `4cd49a2`, `f7b6929`, `1a31fce`, `5142885` and `d11246d`:

- In the scrolled story the board is one canvas that never has more pixels than its pictures (1920 x 1200). The light that spreads over it is timed in script with the stylesheet's former waits, lengths and curve.
- The stage of the scrolled story holds the words of the step in view and, for 0.7 s, of a step just left. It held the words of all 22.
- The still page and a frozen step are drawn as before: layers of the page, only those the step lights. They were drawn on a canvas too in the first build of this change (`f7b6929`); two independent checks of that build found that the still page then took more memory in this browser than it had and showed a board unlit for a moment when a section was jumped to, so they were given back the form that the phone had kept open.
- Where the canvas cannot be made or drawn, or pixels read back from a canvas are not the pixels drawn, the scrolled story shows the step as layers, changed at once.

### Memory, before and after

The old build is commit `3a2767e`, the new one commit `d11246d`, both built locally and served from the same machine, each measured in a fresh browser. A window of 390 x 844 at three screen pixels to one unless a row says otherwise. MB.

| Measurement, the scrolled story | Old build | New build |
|---|---|---|
| Graphics memory in the middle of a step change (1.3 s into step 17 to 18) | 924.2 | 440.6 |
| The same in a window of 430 x 932 | 1090.5 | 461.2 |
| The same at two screen pixels to one, and at one | 468.0, 215.4 | 363.8, 335.2 |
| Graphics memory at rest: at the opening, on step 18 | 112.2, 140.5 | 367.2, 329.0 |
| The same at rest at two screen pixels to one, and at one (opening, step 18) | 56.9 and 99.2, 20.6 and 79.9 | 313.6 and 300.9, 277.1 and 280.8 |
| Layers of the board's size alive at once in a step change | up to 18, each 2925 x 1829 | 1: the canvas, whose own pixels are 1920 x 1200 (9.2 MB) and which is there at rest too |
| All layers that draw, at the peak of a step change and at rest | up to 36, 6 to 10 | up to 18, 8 to 12 |
| Graphics process, private bytes, over a walk down and back: at the opening, highest, 15 s after the walk | 158.6, 741.7, 263.1 | 257.7, 388.7, 236.5 |
| The same in a window of 430 x 932: at the opening, highest | not walked | 261.3, 422.6 |
| Page process, private bytes, highest in the walk | 76.3 | 77.9 |
| Script heap over the walk | 3.1 to 4.0 | 2.7 to 3.8 |
| Elements in the page; blocks of words; masked copies of the lit picture | 780; 22; 17 | 183 to 202; 1; 0 |
| Canvases that hold pixels | 0 | 18 (one of 1920 x 1200 and 17 cut-outs), 36.3 MB at four bytes a pixel, the same at every size and ratio measured |
| Step renders for 21 steps; script time in the walk down | 21; 0.28 s | 21; 1.43 s |

| Measurement, the still page (`?static`) | Old build | First build of the change (`c07b6c5`, canvas in every mode) | New build |
|---|---|---|---|
| Graphics memory at the top, and in the middle after one reading | 137.3, 234.0 | 319.2, 627.7 | 137.3, 231.1 |
| The same in a window of 430 x 932 | 154.5, 258.7 | not measured | 154.5, 258.7 |
| Masked copies of the lit picture in the page; canvases ever made | 128; 0 | 0; 65 | 128; 0 |

Read together, for this browser only:

- **The peak of the scrolled story fell to less than half and no longer follows the screen.** 924.2 MB became 440.6 MB at 390 x 844, and 1090.5 MB became 461.2 MB at the phone's own size. The highest reading of the graphics process over a whole walk fell from 741.7 to 388.7 MB.
- **The level at rest rose.** 112.2 MB became 367.2 MB at the opening and 140.5 MB became 329.0 MB at rest on step 18, because the canvas and its cut-outs are held all the time where the old layers were flattened at rest. About 92 MB of that is the browser's own store of decoded pictures, which it keeps for as long as it sees fit; about 63 MB is what it counts for the canvases. Whether a phone's browser judges a page by its peak or by its level at rest is not known here. Readings of this kind moved by up to 15 MB between two runs of nearly the same code.
- **At one screen pixel to one the new build takes more than the old at every moment measured**, the middle of a step change included (335.2 MB against 215.4 MB). The ceiling is paid for on a screen that never needed it.
- **The still page takes what it took.** The report is the same to within 3 MB, and the page holds the same 128 masked elements and no canvas.
- **A turn of the phone is heavy in both builds, and a little heavier in the new one.** Five turns to sideways and back, on step 12: the graphics process reached 823 MB with the old build and 898 MB with the new, the page process 89 and 148 MB. The cut-outs are made again at each new size; the pictures are not fetched or decoded again.
- **Nothing grows.** Over 25 fast round trips of the new build the graphics process read 611 MB after the first and 525 to 573 MB after the others, and 260 MB 20 s later (the old build: 917, 891 to 947 and 563 MB); the script heap ended at 3.3 MB, and the page held the same 18 canvases from the first trip to the last (36 were ever made).

### The look, before and after

Screenshots of the old and the new build, compared pixel by pixel: every frozen step, the scrolled story at rest on seven steps (3, 6, 9, 12, 15, 18, 21; taken 9 s after arriving), and four sections of the still page, each jumped to and shot at once and again 1.5 s later. Three windows: 390 x 844 and 430 x 932 at three screen pixels to one, and 1440 x 900 at one. Two runs of the old build differed from each other by at most one level of 255 on one picture (the opening), which is the noise of this comparison.

| Compared | Result |
|---|---|
| The 22 frozen steps, in each of the three windows | Identical to the old build in 64 of the 66 pictures. The other two are the opening at the two phone sizes, which differ by one level of 255 on a few pixels, as two runs of the old build do |
| The still page, four sections jumped to, in each of the three windows | Identical to the old build in every picture, and each first picture identical to the one 1.5 s later: a board is never shown unlit. (In the first build of this change, `c07b6c5`, the first picture after a jump showed the board without its lights.) |
| The scrolled story at rest, seven steps in each window | Every picture differs from the old build's, in two ways. The words over the board are smoothed in grey where the old build smoothed them with coloured fringes; that is every large single difference (up to 149 of 255, on the edges of letters), and it also touches the steps where the laptop covers the board, because the canvas lies under the words there too. And the board itself is the canvas enlarged by the compositor where the old picture was enlarged while it was painted. Over the whole screen the mean difference is 0.11 to 0.48 of 255 in 20 of the 21 pictures, and 0.4 to 1.5 percent of the pixels differ by more than 8 levels. The one exception is step 18 at 430 x 932 (mean 1.36, 6.2 percent): there the old build's scrolled picture differs as much from its own frozen step (mean 1.23), which is the softness described under this table, and the new build's does not. A phone's screen has no coloured fringes to lose |
| The same seven scrolled pictures against the first build of the change (`c07b6c5`), on which an independent check of the look was made | Identical, all seven, at 390 x 844 |
| The board's canvas after each landing, against the canvas that `c07b6c5` drew for the same step on its frozen page | Pixel for pixel equal on all 50 landings with a board at 390 x 844 at ratio 3 |
| The laptop of the ending (steps 15, 20, 21) in the scrolled story against its frozen step and against the old build, 390 x 844 at ratio 3 | No channel of any pixel of the laptop differs by more than 1 level. An independent check had measured it softer (edges at 0.90 to 0.97 of the old value); that was reproduced only with the words hidden by a style added for the measurement, which changes how the browser splits the stage into layers, and not on the page as a reader gets it |

What the independent check of the look found on the first build and what still holds: with the words hidden, the board of the scrolled story differed from the old build's by a mean of 0.20 to 0.41 of 255 (largest 13 to 31) on the phone profile. Walking the old build step by step on that profile, it drew some lit parts soft on 11 of the 22 steps (3 and 5 to 14), and how soft depended on the path taken to the step; the new build draws the same picture by every path. So on that profile the scrolled picture is a little crisper than the live site's was in this browser. None of it could be seen at full size.

### Behaviour that was driven

At commit `d11246d`, by script through the debugging port.

| What | Result |
|---|---|
| 496 checks as a phone (390 x 844 at ratio 3) and the same 496 as a desktop window (1440 x 900) | None failed. All 22 steps land forward, backward, on 12 long jumps and after 5 interrupted sequences (59 landings in each window); the still page has 22 sections; `?step=0` to `?step=21` each show their step as layers with no canvas and no animation frame; `?step=99` falls back to the story; reduced motion gives the still page with no canvas and no frame; the evidence panel opens as a modal from both of its controls, 30 Tab and 15 Shift Tab presses stay inside it, the page behind does not scroll, Escape closes it and focus returns to the control that opened it; the marks of the rail jump; `#step-12`, `?static#step-7`, `?step=5&evidence`, `#/experiments` and `#/sources` work; Space, Page Down, Page Up and the step buttons move one step; six trips to another page and back leave the same listeners and the same 18 canvases |
| Frames | None asked for at rest (10 s on a step: no frame, no draw, no timer). None from 0.9 s after the board has left view (steps 0, 15, 20, 21). None while the page is hidden in the middle of the longest change, and the right picture when it is shown again, pixel for pixel |
| Fast flings, four cycles from top to bottom and back | The story landed at the top each time, the canvases stayed at 18, and step 12 afterwards was pixel for pixel its reference. Graphics process at most 577 MB |
| A real loss of the graphics process (the browser's own crash address) on step 12 | The board was drawn again, and step 18 afterwards was pixel for pixel its reference |
| Every way the canvas was made to fail: no 2d context, a context that throws, pixel readback that throws, pixel readback that returns clear pixels, drawing that throws in the middle of the story, a decode that rejects, the lit picture blocked, the dark picture blocked | In every case the scrolled story showed the step as layers, with exactly the step's lit parts, and went on to the next step; no picture was left blank. With no decode function, with no resize observer, and with the canvases' pixels cleared and the browser's "context restored" event sent, the canvas drew the full picture |
| The time from the start of the page to the first drawn board, three loads with an empty cache | 690, 429 and 402 ms |

### Found by the two independent checks at closing, and what was done

| Finding on the first build of the change (`c07b6c5`) | What was done |
|---|---|
| The still page took more memory than before, on the one page that the phone had kept open | The still page and a frozen step are layers again (`5142885`); measured equal to the old build |
| A still section jumped to showed its board unlit for 0.15 to 0.6 s | Gone with the same change; shot and compared |
| A still section that came near and left while its pictures loaded kept its canvas for good | The code that held a canvas per still section is removed |
| Pixel readback that came back clear gave a board with no lights and no fallback | A check before any cut-out is made; the stage then shows layers (`5142885`, with a test of the rule) |
| Canvas pixels cleared by the browser were redrawn from cut-outs that were blank too | The canvas and its cut-outs are made again on the browser's "context restored" event and when a page comes back from the back and forward cache (`5142885`) |
| A change of canvas size held the old and the new cut-outs together and decoded every picture again | The old ones are given back first (`5142885`), and the pictures are fetched once for the page (`d11246d`). The peak of a turn did not fall: it is the browser's own, and the old build has it too |
| The level at rest rose | Accepted, with its measurement above. Not lowered |
| The laptop of the ending looked softer in the scrolled story | Not reproduced on the page as a reader gets it (row above). Nothing changed |
| Script time for a walk down rose | Accepted, with its measurement above. Long tasks in the walk down: 3 in each build |

### Known and left

- **A turn of the phone loses the reader's place.** Turning the window sideways on step 12 shows step 21, and turning it back shows step 10. The old build does the same; it is not part of this change and is not fixed.
- **Two ways of drawing one step.** The canvas of the scrolled story and the layers of a still are kept equal by a test of their levels and by the comparison above, not by construction.

### Not verified

- **The phone.** No real phone has opened the new build. Whether the page now stays up on the iPhone is not known, and this section will be changed to say what happened when it has been tried. Until then defect 27 is open.
- **The cause.** Memory is where the numbers point; the phone's browser gives no reason when it ends a page.
- **Any other engine.** Firefox was not opened. How the phone's engine accounts for one canvas of 1920 x 1200 and 17 smaller ones, whether it gives the words over a canvas a surface of their own, and whether its fades look as they did, was not measured.
- **The level at rest on a phone**, which rose in the desktop browser.
- **Sharpness on a dense screen itself.** The canvas has at most 1920 pixels across a board that is drawn up to 3225 screen pixels wide on the phone; the old layers were limited by the same 1920-pixel pictures. Compared on screenshots only.
- **The speed of the script's own blur on a phone.** About half a second of work on the laptop, in slices of at most 12 ms; not timed on a phone. The first light after opening the page is where a hitch would show.
- **Frame rate.** Frames were counted, not timed.
- **A turn of the phone and a visit to another app and back**, on a phone. **The back and forward cache** was not driven in any browser.
- **The fresh-clone runs, the mutation checks, the unit tests under WSL and the suite with the virtual machine** were not repeated. The recorder's unit tests and the content check were run on Windows and pass as in section 3.
