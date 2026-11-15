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
| **Site: unit tests of the model** (steps, experiment state, addresses, panel keys, the mark) | Complete state per step and the state of an experiment are plain data, testable without drawing anything | 92 |
| **Site: the content and the recordings as the site loads them** | Guards the site's own reading of the files | 45 |
| **Site: pages rendered to HTML, with no browser**, and the stylesheet read as text | Proves that a page shows what the content and the files hold, and no more | 198 |
| **Browser-level, automated** | None. Motion, layout and focus need a real window; they were checked by a scripted drive and by eye, outside the test suite | 0 |

Recorder total 373 (25 in `test_capture.py`, 48 in `test_check_content.py`, 28 in `test_committed_recordings.py`, 41 in `test_compare_prediction.py`, 65 in `test_counted_set.py`, 32 in `test_eventlog_gate.py`, 6 in `test_integration_vm.py`, 5 in `test_recorded_bytes.py`, 65 in `test_session_runner.py`, 50 in `test_staging.py`, 8 in `test_story_and_repository.py`). The split of the first three rows is by test class: `test_check_content.py` is the second row; `test_committed_recordings.py`, `test_recorded_bytes.py` and the classes `CommittedPredictions` and `TwoEntryNormalRuns` of `test_counted_set.py` are the third. Site total 335 in nine files.

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

The run with the virtual machine boots the plain normal run twice and the two-entry normal run once, and took about two minutes for the whole suite. No counted experiment and no pilot was booted for this document. The same commands were run again after the last change to the documents of that day and gave the same summary lines, apart from the times. The counts in this table are those of that commit: five recorder tests, four site tests and three claims were added afterwards.

### Last results

Run after the last change to the site and the content (sections 9 and 10), on the same machine, on Windows only:

| Check | Command | Summary line |
|---|---|---|
| Recorder unit tests, Windows | `python -m unittest discover -s recorder/tests -t .` | `Ran 373 tests in 35.466s`, `OK (skipped=6)` |
| Content check | `python scripts/check_content.py` | `content check: 5 files, 28 screens, 357 claims, 85 claims uefi-required, 28 claims uefi-platform, 21 claims tcg-unread, 38 claims this-firmware, 170 claims recording, 15 claims general, 14 recordings, 59 glossary entries`, `content check: passed, no problems` |
| Site tests | `npm test` | `Test Files  9 passed (9)`, `Tests  335 passed (335)` |
| Site build | `npm run build` | type check passed, one script of 939.24 kB (gzip 186.22 kB), `built in` under one second, one warning: a chunk larger than 500 kB |
| Site format | `npm run format:check` | `All matched files use Prettier code style!` |

**Not repeated after that change:** the recorder's unit tests under WSL and the suite with the virtual machine. The five tests added since read committed files only and boot nothing, so the README's expected `Ran 373 tests` for the suite with the virtual machine is the same test discovery with the six booting tests included; it was not run. The fresh-clone runs (`FRESH_CLONE_RUN.md`) and the mutation checks (`MUTATION_CHECKS.md`) were made before that change and were not repeated; each file states the counts of its own commit.

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
| Firefox, Safari, a physical phone, a phone held sideways, a window under 600 px tall, a screen with a device pixel ratio above 1, a screen reader | | **Not checked** |
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

### Open, known, not fixed

| # | What | Why it is open |
|---|---|---|
| O1 | The site is one script of 939 kB, and it grows with every recording | Splitting it by page means making the one synchronous door to the recordings asynchronous, a change of structure. Left with its measurement |
| O2 | A few status sentences in `content/experiments.json` repeat what the files show (for example the status of a counted card) | They are true and checked by reading. Nothing fails if one goes stale |
| O3 | Process cleanup when QEMU is killed from outside is not covered by a unit test | It needs real processes. The integration test and `scripts/check-clean.sh` cover it |
| O4 | `recorder/pe.py` names Microsoft's Authenticode format document as its method reference, while the site lists that document as not read | The digest is confirmed against what the firmware measured, and no claim on the site cites the document. The README says both |
| O5 | The exact printed wording of the UEFI specification's copyright line has not been checked against the publisher's page | To be done before publication; noted in `content/sources.json` |
| O6 | No licence has been chosen | The owner's decision |
| O7 | The rule `load-verify` in `recorder/storymap.py` gives as its basis "present when the loader is accepted, absent when it is refused". The refused pilot `e5` has the authority record all the same | The rule's name and the stop it assigns are right, and `PILOTS.md` and the site state what `e5` shows. The sentence in the code was written before `e5` was recorded and was left as it is; `DESIGN.md` section 7 carries a note |

## 6. Release assessment

**Implemented.** The recorder with its four commands; 14 committed recordings, 11 comparisons, 4 predictions and 4 scores; the content in five files; the content check; the site with the story in 22 steps, the experiments page, the sources page, the strip of seven stops and the evidence panel; build settings for a static host; link-preview tags and picture; a hosted workflow definition.

**Tested.** Everything in section 3, on one machine. The acceptance checks A1 to A20 pass. Nine rules were broken on purpose on the final code and each break was noticed. The normal runs were booted again for this document and equal the committed recordings. The README was followed in a new clone; three of its steps failed as written, the README was corrected, and those steps were typed again in a second new clone and matched; in a third new clone the packages were installed with `npm ci` and the site's commands, the content check, the unit tests and the making of one score were typed and matched, with nothing booted (section 8).

**Simulated, and labelled as such.** The machine is a virtual machine under software emulation and the TPM is a program; both are named on the site and in every limit list. Power sequencing does not exist there, and stop 1 says "described, not recorded". Tests that drive a whole run use a fake machine that replays a normal boot; the scores those tests produce mean nothing and only the path is proven (`DESIGN.md` section 10). The fixtures in `recorder/tests/fixtures/` are real output of two boots, made with an earlier key set. The pictures are illustrations.

**Unverified.**

- **The hosted workflow.** `.github/workflows/check.yml` has never run on a hosted runner. It uses the official checkout, Python and Node.js setup actions by major version, and every command in it passes locally on Windows and in WSL. A hosted runner may still differ: another Node.js or npm patch version, `npm ci` on another system than the one it succeeded on, another git version for the three tests that use real git. Whether the three setup actions resolve at the versions the file names was not checked, because nothing was fetched.
- **Publication.** Nothing is published. There is no public address, so no deployed page has been opened, and the previews of a pasted link have not been seen (section 7).
- **Any second machine.** The recordings were reproduced only on the machine that made them, in every run from a new clone as well. The recorder refuses another firmware package; what another QEMU version does was not tried.
- **Any browser but one**, any real phone, a screen with a device pixel ratio above 1, and a screen reader (section 4).
- **Motion.** It was judged by the timing a script read and by the author's own scrolling. Frame rate was not measured, and no second person has scrolled the story (section 10).
- **Repeatability of a changed run.** Each counted experiment was booted once, by rule.
- **What a Trusted Computing Group document or the Platform Initialization specification requires.** Neither was read. No statement on the site or in the results claims a requirement from either.
- **That no counted configuration was ever booted before its prediction.** The history and one audit of the work directory say so; no mechanism proves it, and the audit's script and output are not in the repository (`RESULTS.md`, "Checked a second time", marks the rows a reader cannot repeat).

**Assessment.** The evidence chain from a boot to a number on the page is implemented and tested end to end without a virtual machine, and the one link that needs a real boot, that a normal run repeats, was run again and holds. The result is honest only together with its caveats: four counted experiments, one run each, rows that are not independent, one firmware build in a virtual machine with a software TPM, and two documents unread. With those stated beside the numbers, as the README and the experiments page now do, the project is ready to be shown as a private repository. Before it is made public, two things remain: the hosted workflow must run green once, and a licence must be chosen. The author has scrolled the story by hand; nobody else has.

## 7. Link-preview metadata

Read from the built `site/dist/index.html`:

| Tag | Present | Value |
|---|---|---|
| `<title>` | yes | `Lux: what your laptop does before it wakes` |
| `meta name="description"` | yes | One sentence on what the site is |
| `og:type`, `og:site_name`, `og:title`, `og:description` | yes | `website`, `Lux`, the title, the description |
| `og:image` | yes | `og.jpg`, a relative address, in a plain build |
| `og:image:width`, `og:image:height`, `og:image:alt` | yes | 1200, 630, and a sentence that says the picture is an illustration |
| `twitter:card` | yes | `summary_large_image` |
| `og:url`, `link rel="canonical"` | only with `LUX_SITE_URL` | |

The picture `dist/og.jpg` is in the build and is 1200 x 630.

**An absolute address for the preview picture can only be set once a public address exists.** A build made with `LUX_SITE_URL` set to a placeholder address and `LUX_BASE=/lux/` was checked: `og:image` then holds the absolute address of `og.jpg`, `og:url` and the canonical link appear, the asset paths start with `/lux/`, and the link in `404.html` leads to `/lux/`. That shows the mechanism, not a working preview: no preview service has fetched the page, because there is no page to fetch. After publication, the address should be opened in a fresh browser profile and checked with a link-preview inspector.

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
- **Not the hosted workflow.**

An earlier clone at commit `dc52dbe` ran only the test commands on Windows, with the installed packages copied from the working tree. The three runs above replace it.

## 9. The last change to the look and to stops 4 to 6

Made on 2026-11-15 in nine commits, `5cf4d0a` to `cf1fc46`, after every run and check described above. No experiment was run again, and no recording, prediction or score was touched.

**What changed in the content.** Stops 4, 5 and 6 state values that the summary in `recording.json` does not hold and the raw event log beside it does: the `SecureBoot` variable is one byte, `01`; `BootOrder` is `00 00 01 00`; the value of `Boot0000` begins `09 01 00 00` and carries the text `UiApp`; the value of `Boot0001` begins `01 00 00 00` and carries the disk's name; and the 879 bytes of the `db` variable are 28 bytes followed, byte for byte, by the 851 bytes of the key record. `recorder/tests/test_recorded_bytes.py` (5 tests) reads each value from `recordings/normal-1/eventlog.bin` with the recorder's own parser and compares it with the sentence in the content. No sentence was added about what a specification requires, what the 28 bytes are, or why the console names option 0001 when the stored order lists 0000 first; stop 5 lists that last point as not shown.

**What changed in the look.**

| Change | Where |
|---|---|
| A step's statement is at most 52 px at weight 600 (was 68 px at 750), the title at most 92 px at weight 600; the three greys carry a cool tint | `site/src/styles/lux.css` |
| A lit part that a board step is not about rests at half its light, so the part the step is about is the warm point. Once every part is lit (steps 18 and 19) nothing rests | `layersAt` in `site/src/model/scene.ts`, two tests in `scene.test.ts` |
| On the last screen, in a window at least 800 px high and three wide to two high, the laptop is drawn at 660 x 495 at 1440 x 900 (was 535 x 401); as its screen lights, a shade from the hinge down turns down the light under the keys; "Continue in Nox" is a filled button | `lux.css`, one attribute in `components/Stage.tsx` |
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

Made on 2026-11-15 after section 9, in the commits `99c9865`, `40137be` and `a337644` and the commit that added this section. No experiment was run again, and no recording, prediction or score was touched.

| Change | Where |
|---|---|
| The last screen fades in a second generated picture of the lit laptop, in which the light under the keys is turned down. The shade that section 9 describes was removed from the stylesheet. The picture a link is previewed with was made again from the same second picture | `site/src/assets/laptop-awake.webp`, `site/public/og.jpg`, `site/tools/make_assets.py`, `site/src/styles/lux.css`, `site/ASSETS.md` |
| The opening's invitation to scroll names the author: "An explainer of the UEFI boot by Le Jie Tan, from public specifications and one recorded boot", the same place and form as on the earlier site | `content/story-a.json` |
| A page opened below the story shows the last step in the stage's last rows (defect 22) | `site/src/stage/useStepScroll.ts`, `stepPassed` in `site/src/model/scene.ts`, two tests |

**Checked.** The checks of section 3, "Last results", all run after the last of these changes. The screenshots of section 4, the row "After the final changes": every one was opened and read, and none showed overlap, clipped text or a line past the window's edge. The three pictures in `docs/images/` are from that set.

**Still unverified.**

- **Motion.** Judged by the timing a script read (section 9) and by the author's own scrolling. Frame rate was not measured, the fade of the new picture on the last screen was seen only as its end state on a screenshot, and no second person has scrolled the story.
- **Other browsers.** One Chromium-based browser only. Firefox and Safari were not opened.
- **A physical phone.** The narrow sizes are windows of a desktop browser, not a device, and none was held sideways.
- **A screen reader.** None was run. The spoken status line and the labels are tested as rendered HTML only.
- **A device pixel ratio above 1.** Every screenshot was taken at a ratio of 1, so how the pictures and the hairlines look on a dense screen was not seen.
- **The hosted check workflow.** `.github/workflows/check.yml` has never run (section 6).
- **Not repeated after these changes:** the evidence panel's keys and focus in a browser, the pages and panels from top to bottom at the narrow sizes (only the opening and the last step were taken again there), the recorder's unit tests under WSL, the suite with the virtual machine, the fresh-clone runs and the mutation checks.
- **The brightness of the new picture of the lit laptop** was not written into `site/ASSETS.md`; its table still holds the values of the first picture.
