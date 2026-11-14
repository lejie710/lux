# Mutation checks

A test suite that passes proves little unless it can also fail. For three rules the project's question depends on, the rule was broken on purpose, the full suite was run, and the rule was restored. Each time at least one test had to fail. All three did.

Suite before and after: `Ran 168 tests`, `OK (skipped=4)`. The four skipped tests are the integration test that boots the virtual machine; it was not part of these checks.

## 1. The extend order in the replay

- **Rule.** A register is extended as: new value = hash of (old value followed by digest). Both replays of the agreement gate depend on it.
- **File.** `recorder/banks.py`, function `extend`.
- **Change.** `hashlib.new(bank, old_value + digest)` became `hashlib.new(bank, digest + old_value)`.
- **Result.** 13 tests failed. The ones aimed at this rule:
  - `test_eventlog_gate.ExtendRule.test_extend_hashes_old_value_then_digest`
  - `test_eventlog_gate.Replay.test_replay_follows_the_extend_rule_in_order`
  - `test_eventlog_gate.Replay.test_real_log_replay_equals_real_live_read`
  - `test_eventlog_gate.Replay.test_real_extend_list_replay_equals_real_live_read`
  - `test_eventlog_gate.Gate.test_real_boots_pass`
  - `test_committed_recordings.CommittedRecordings.test_each_recording_follows_from_its_own_event_log`
- **Why it matters.** The two replays share this one function, so a wrong order would keep them equal to each other. Only the comparison with values a real TPM returned exposes it, which is what the fixture tests and the committed recordings provide.

## 2. The prediction gate

- **Rule.** A counted experiment must not run unless its prediction is committed.
- **File.** `recorder/runner.py`, function `record_run`.
- **Change.** `if experiment.kind == experiments.KIND_COUNTED:` became `if False and experiment.kind == experiments.KIND_COUNTED:`, so the check was skipped.
- **Result.** 4 tests failed:
  - `test_session_runner.WholeRun.test_counted_experiment_without_prediction_is_refused_before_anything_starts`
  - `test_session_runner.WholeRun.test_counted_experiment_with_uncommitted_prediction_is_refused`
  - `test_session_runner.WholeRun.test_counted_experiment_with_committed_prediction_runs_and_names_it`
  - `test_session_runner.CommandLine.test_counted_experiment_is_refused_with_exit_code_1_and_no_file`
- **Why it matters.** Without the gate the headline numbers would not be blind. The tests cover both directions: a counted run is refused before any machine is created, and a permitted one stores the prediction's hash and commit.

## 3. The comparison of register values

- **Rule.** Two recordings differ at a register when its value differs in either one.
- **File.** `recorder/compare.py`, function `compare_pcrs`.
- **Change.** The condition `left.get(str(index)) is None or left.get(str(index)) != right.get(str(index))` lost its second half, so only a missing value counted as a difference.
- **Result.** 6 tests failed:
  - `test_compare_prediction.CompareRecordings.test_one_changed_register_value_is_reported_in_its_bank_only`
  - `test_compare_prediction.CompareRecordings.test_a_missing_register_counts_as_differing`
  - `test_compare_prediction.CompareRecordings.test_refused_boot_against_normal_boot`
  - `test_committed_recordings.CommittedRecordings.test_the_pilot_differs_in_registers_4_5_and_7_only`
  - `test_committed_recordings.CommittedRecordings.test_committed_comparisons_equal_a_fresh_comparison`
  - `test_session_runner.CommandLine.test_compare_and_check_commands`
- **Why it matters.** With this fault every changed run would be reported as leaving all registers untouched, and every prediction row of the form "this register changes" would be scored wrong.

## How to repeat a check

Make the change by hand, run `python3 -m unittest discover -s recorder/tests -t .`, confirm the named tests fail, then restore the file with `git checkout -- <file>` and run the suite again.

## What these checks do not show

Three rules were checked, not every line. The checks say nothing about the code that only runs with a real virtual machine (`session.QemuMachine`); that code is exercised by the integration test and by the committed recordings, not by mutation.
