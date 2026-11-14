# Mutation checks

A test suite that passes proves little unless it can also fail. For nine rules the project's question depends on, the rule was broken on purpose, the full suite was run, and the rule was restored. Each time at least one test had to fail. All nine did.

Checks 1 to 7 break rules of the recorder, check 8 a rule of the content check, and check 9 a rule of the site. All nine were made on the final code. For checks 1 to 8 the recorder's suite before and after each was `Ran 368 tests`, `OK (skipped=6)`; for check 9 the site's suite was `Tests  329 passed (329)`. The skipped tests are the ones that boot the virtual machine; they were not part of these checks. Checks 1 to 7 had been made before on earlier revisions (suites of 231 and 356 tests), where each also failed; the lists below are from the repeat on the final code.

## 1. The extend order in the replay

- **Rule.** A register is extended as: new value = hash of (old value followed by digest). Both replays of the agreement gate depend on it.
- **File.** `recorder/banks.py`, function `extend`.
- **Change.** `hashlib.new(bank, old_value + digest)` became `hashlib.new(bank, digest + old_value)`.
- **Result.** 22 tests failed. The ones aimed at this rule:
  - `test_eventlog_gate.ExtendRule.test_extend_hashes_old_value_then_digest`
  - `test_eventlog_gate.Replay.test_replay_follows_the_extend_rule_in_order`
  - `test_eventlog_gate.Replay.test_real_log_replay_equals_real_live_read`
  - `test_eventlog_gate.Replay.test_real_extend_list_replay_equals_real_live_read`
  - `test_eventlog_gate.Gate.test_real_boots_pass`
  - `test_committed_recordings.CommittedRecordings.test_each_recording_follows_from_its_own_event_log`

  The other 16 are tests that record a whole run from the fixtures, or check the shape of one; they fail because the agreement gate then refuses the run.
- **Why it matters.** The two replays share this one function, so a wrong order would keep them equal to each other. Only the comparison with values a real TPM returned exposes it, which is what the fixture tests and the committed recordings provide.

## 2. The prediction gate

- **Rule.** A counted experiment must not run unless its prediction is committed.
- **File.** `recorder/runner.py`, function `record_run`.
- **Change.** `if experiment.kind == experiments.KIND_COUNTED:` became `if False and experiment.kind == experiments.KIND_COUNTED:`, so the check was skipped.
- **Result.** 9 tests failed. These seven, and two tests of `test_counted_set.CountedPipeline` that run a counted experiment from staging to a score:
  - `test_session_runner.WholeRun.test_counted_experiment_without_prediction_is_refused_before_anything_starts`
  - `test_session_runner.WholeRun.test_counted_experiment_with_uncommitted_prediction_is_refused`
  - `test_session_runner.WholeRun.test_counted_experiment_with_committed_prediction_runs_and_names_it`
  - `test_session_runner.WholeRun.test_counted_experiment_is_refused_when_the_normal_run_does_not_repeat`
  - `test_session_runner.WholeRun.test_a_prediction_edited_behind_git_is_refused_before_anything_starts`
  - `test_session_runner.WholeRun.test_the_changed_byte_comes_from_the_committed_prediction_and_is_recorded`
  - `test_session_runner.CommandLine.test_counted_experiment_is_refused_with_exit_code_1_and_no_file`
- **Why it matters.** Without the gate the headline numbers would not be blind. The tests cover both directions: a counted run is refused before any machine is created, and a permitted one stores the prediction's hash, commit and parameters.

## 3. The comparison of register values

- **Rule.** Two recordings differ at a register when its value differs in either one.
- **File.** `recorder/compare.py`, function `compare_pcrs`.
- **Change.** The condition `left.get(str(index)) is None or left.get(str(index)) != right.get(str(index))` lost its second half, so only a missing value counted as a difference.
- **Result.** 6 tests failed. These five, and `test_counted_set.TwoEntryNormalRuns.test_only_register_1_differs_from_the_plain_normal_run`:
  - `test_compare_prediction.CompareRecordings.test_one_changed_register_value_is_reported_in_its_bank_only`
  - `test_compare_prediction.CompareRecordings.test_a_missing_register_counts_as_differing`
  - `test_compare_prediction.CompareRecordings.test_refused_boot_against_normal_boot`
  - `test_committed_recordings.CommittedRecordings.test_the_pilot_differs_in_registers_4_5_and_7_only`
  - `test_committed_recordings.CommittedRecordings.test_committed_comparisons_equal_a_fresh_comparison`
- **Why it matters.** With this fault every changed run would be reported as leaving all registers untouched, and every prediction row of the form "this register changes" would be scored wrong.

## 4. The committed bytes of the prediction

- **Rule.** The prediction file on disk must be byte for byte the file git has committed. Git's "nothing changed" answer is not enough, because git can be told to stop looking at a file.
- **File.** `recorder/prediction.py`, function `require_committed`.
- **Change.** `if digest != hashlib.sha256(path.read_bytes()).hexdigest():` became `if False:`, so the comparison of the two hashes was skipped.
- **Result.** 4 tests failed. These three, and `test_counted_set.ChangedBootOrderCommand.test_it_is_refused_while_the_prediction_is_not_committed`:
  - `test_compare_prediction.PredictionGate.test_a_file_that_differs_from_the_committed_bytes_refuses`
  - `test_compare_prediction.PredictionGateWithRealGit.test_an_edit_hidden_from_git_status_is_still_refused`
  - `test_session_runner.WholeRun.test_a_prediction_edited_behind_git_is_refused_before_anything_starts`
- **Why it matters.** The second of these uses a real temporary git repository and the real `git update-index --assume-unchanged`: it is the case that passed the gate before the review. Without this rule a recording could store the hash of an edited prediction next to a commit that holds another text.

## 5. The two stores of a boot order experiment differ in one variable

- **Rule.** The variable store with the changed boot order is accepted only if it differs from the store with the original order in the value of `BootOrder` and in no other byte.
- **File.** `recorder/staging.py`, function `require_only_boot_order_differs`.
- **Change.** `if not varstore.only_this_variable_differs(original, changed, "BootOrder"):` became `if False and not ...`, so only the order itself was still checked.
- **Result.** 2 tests failed:
  - `test_counted_set.TwoEntryStaging.test_a_changed_order_store_that_differs_in_anything_else_is_refused`
  - `test_session_runner.Preparation.test_a_changed_order_store_that_differs_in_anything_else_is_not_kept`
- **Why it matters.** The experiment claims to change one thing. This rule is the proof, taken from the two files before any boot. Without it a store that also differed elsewhere would be booted, and its effect would be blamed on the order.

## 6. Nothing of the changed boot order is made before a prediction is committed

- **Rule.** `prepare --changed-boot-order` is refused unless a boot order prediction is committed.
- **File.** `recorder/cli.py`, function `_prepare`.
- **Change.** The call `_require_boot_order_prediction()` was removed.
- **Result.** 3 tests failed:
  - `test_counted_set.ChangedBootOrderCommand.test_it_is_refused_without_a_prediction`
  - `test_counted_set.ChangedBootOrderCommand.test_it_is_refused_while_the_prediction_is_not_committed`
  - `test_counted_set.ChangedBootOrderCommand.test_a_prediction_for_another_experiment_does_not_open_it`
- **Why it matters.** The store with the changed order is the changed configuration of a counted experiment. If it could be made early, it could be tried out early, and the prediction would no longer be blind.

## 7. A changed run is compared with the normal run it changes

- **Rule.** `compare` refuses a changed run against a recording of another normal run than the one its experiment names.
- **File.** `recorder/compare.py`, function `require_comparable`.
- **Change.** `if baseline["run"]["experiment"] != expected:` became `if False and ...`.
- **Result.** 2 tests failed:
  - `test_counted_set.BaselineRules.test_a_boot_order_run_is_compared_with_its_two_entry_normal_run_only`
  - `test_counted_set.BaselineRules.test_a_pilot_is_compared_with_the_plain_normal_run_only`
- **Why it matters.** There are three normal runs now. The plain one and the two-entry ones differ in register 1 by themselves. A boot order run compared with the plain normal run would show that difference as if the changed order had caused it.

## 8. An evidence line is in the recording letter for letter

- **Rule.** The text of an evidence line must equal the field of the recording it names, character by character.
- **File.** `scripts/check_content.py`, method `check_evidence`.
- **Change.** `if found != text:` became `if False and found != text:`, so a line that differs from the recording was accepted.
- **Result.** 3 tests failed:
  - `test_check_content.SmallContent.test_an_evidence_line_that_differs_by_one_character_fails`
  - `test_check_content.SmallContent.test_a_console_line_and_a_loader_report_line_are_checked_too`
  - `test_check_content.CommittedContent.test_main_returns_one_for_a_broken_copy`
- **Why it matters.** Every screen of the site shows one line and says it comes from a recording. This comparison is the only thing that makes that sentence true after an edit of the content.

## 9. The two headline numbers are the sum over the score files

- **Rule.** The numbers on the experiments page are the sums of the four fields of every score file on file.
- **File.** `site/src/model/experiments.ts`, function `totals`.
- **Change.** `openCorrect: sum.openCorrect + score.open_correct` became `openCorrect: score.open_correct`, so the page would show the last score file's count in place of the sum.
- **Result.** 2 of the site's 329 tests failed:
  - `model/experiments.test.ts`, "a counted experiment", "sums the two headline numbers over every score on file"
  - `Pages.test.tsx`, "the experiments page", "shows the two numbers the committed score files add up to, and under them what they do not show"
- **Why it matters.** The headline is not written anywhere; it is computed. A wrong sum would put a number on the page that no file holds.

## How to repeat a check

Make the change by hand, run `python3 -m unittest discover -s recorder/tests -t .` (for check 9, `npm test` in `site/`), confirm the named tests fail, then restore the file with `git checkout -- <file>` and run the suite again.

## What these checks do not show

Nine rules were checked, not every line. Each was broken in one way; another way of breaking the same rule may go unnoticed. The checks say nothing about the code that only runs with a real virtual machine (`session.QemuMachine`); that code is exercised by the integration test and by the committed recordings, not by mutation.
