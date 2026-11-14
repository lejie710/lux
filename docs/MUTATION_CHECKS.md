# Mutation checks

A test suite that passes proves little unless it can also fail. For four rules the project's question depends on, the rule was broken on purpose, the full suite was run, and the rule was restored. Each time at least one test had to fail. All four did.

Suite before and after each check: `Ran 231 tests`, `OK (skipped=5)`. The five skipped tests are the integration test that boots the virtual machine; it was not part of these checks. The checks were repeated after the review changes, and the lists below are from that repeat.

## 1. The extend order in the replay

- **Rule.** A register is extended as: new value = hash of (old value followed by digest). Both replays of the agreement gate depend on it.
- **File.** `recorder/banks.py`, function `extend`.
- **Change.** `hashlib.new(bank, old_value + digest)` became `hashlib.new(bank, digest + old_value)`.
- **Result.** 19 tests failed. The ones aimed at this rule:
  - `test_eventlog_gate.ExtendRule.test_extend_hashes_old_value_then_digest`
  - `test_eventlog_gate.Replay.test_replay_follows_the_extend_rule_in_order`
  - `test_eventlog_gate.Replay.test_real_log_replay_equals_real_live_read`
  - `test_eventlog_gate.Replay.test_real_extend_list_replay_equals_real_live_read`
  - `test_eventlog_gate.Gate.test_real_boots_pass`
  - `test_committed_recordings.CommittedRecordings.test_each_recording_follows_from_its_own_event_log`

  The other 13 are tests that record a whole run from the fixtures, or check the shape of one; they fail because the agreement gate then refuses the run.
- **Why it matters.** The two replays share this one function, so a wrong order would keep them equal to each other. Only the comparison with values a real TPM returned exposes it, which is what the fixture tests and the committed recordings provide.

## 2. The prediction gate

- **Rule.** A counted experiment must not run unless its prediction is committed.
- **File.** `recorder/runner.py`, function `record_run`.
- **Change.** `if experiment.kind == experiments.KIND_COUNTED:` became `if False and experiment.kind == experiments.KIND_COUNTED:`, so the check was skipped.
- **Result.** 7 tests failed:
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
- **Result.** 5 tests failed:
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
- **Result.** 3 tests failed:
  - `test_compare_prediction.PredictionGate.test_a_file_that_differs_from_the_committed_bytes_refuses`
  - `test_compare_prediction.PredictionGateWithRealGit.test_an_edit_hidden_from_git_status_is_still_refused`
  - `test_session_runner.WholeRun.test_a_prediction_edited_behind_git_is_refused_before_anything_starts`
- **Why it matters.** The second of these uses a real temporary git repository and the real `git update-index --assume-unchanged`: it is the case that passed the gate before the review. Without this rule a recording could store the hash of an edited prediction next to a commit that holds another text.

## How to repeat a check

Make the change by hand, run `python3 -m unittest discover -s recorder/tests -t .`, confirm the named tests fail, then restore the file with `git checkout -- <file>` and run the suite again.

## What these checks do not show

Four rules were checked, not every line. The checks say nothing about the code that only runs with a real virtual machine (`session.QemuMachine`); that code is exercised by the integration test and by the committed recordings, not by mutation.
