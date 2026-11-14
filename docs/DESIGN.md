# Lux recorder: design

Status: first version, written before the code. Later steps extend it as the package is built.

## 1. Purpose and the question

Lux asks one question:

> When one thing in a PC's boot chain is changed, what does the specification require, what does it leave open, and what does this firmware actually do?

The recorder is the part that produces evidence. It boots open-source UEFI firmware (OVMF, built from EDK II) in a QEMU virtual machine with a software TPM (swtpm), captures what the boot left behind, and writes one JSON file per boot. A static site loads those files directly. The recorder also compares two recordings and checks a comparison against a prediction that was committed before the run.

Scope: open-source firmware in a virtual machine with a software TPM, under software emulation. Nothing here describes any vendor's firmware on real hardware.

Two kinds of changed run exist. A **pilot** was run before any prediction existed; it is shown and never counted. A **counted** run needs a committed prediction first, and the recorder enforces that (section 6).

## 2. Pipeline

```mermaid
flowchart TD
    A[Prepare once: test keys, signed loader, variable store template] --> B[Stage one run from an experiment description]
    P[Committed prediction file] -->|required for counted runs| B
    B --> C[Boot under the recorder: swtpm, then QEMU with QMP]
    C --> D[Wait for the loader's final marker or the firmware's refusal line, then settle]
    D --> E[Pause guest, save guest memory, kill QEMU]
    E --> F1[Serial log]
    E --> F2[Extend list from the swtpm log]
    E --> F3[Live PCR read from swtpm]
    E --> F4[Event log cut from saved memory]
    F2 --> G{Three-way agreement gate}
    F3 --> G
    F4 --> G
    G -->|fail: non-zero exit, no recording| X[Stop]
    G -->|pass| H[Normalise]
    F1 --> H
    H --> I[Write recording JSON]
    I --> J[Compare two recordings]
    J --> K[Check comparison against the prediction]
```

Every run ends by the same path, whether the loader was accepted or refused.

## 3. Module boundaries

The package is `recorder/`. Modules marked *pure* touch no process, socket or clock; they run on any Python 3.12 and carry most of the tests. Only `keys`, `loader` (build part) and `session` need the Linux tools.

**`provenance`** collects what a reader needs to reproduce a run: package versions as the package manager reports them, the SHA-256 of the firmware file, key fingerprints, and the full command lines. The date is passed in as data, never read inside a function that also builds compared fields.

**`keys`** owns the committed Secure Boot test keys (PK, KEK, db) in `recorder/testkeys/`. It loads them, checks them against a hash manifest, and reports fingerprints. It can generate keys only through an explicit command that refuses when the directory is not empty, because PCR 7 depends on the certificate bytes and new keys would silently invalidate every recording.

**`pe`** (*pure*) reads PE/COFF headers: section table, the certificate table (the signature area), and the Authenticode SHA-256 of an image. The recorder uses it to predict the PCR 4 image digest before a boot and to prove where a changed byte lies.

**`loader`** builds the assembly loader with the installed assembler and linker (no timestamp), and verifies the committed signed loader against the manifest. Signing output is not repeatable, so the signed file is a fixed committed artifact, not a build product. It also makes changed copies: one byte inside a section, or one byte inside the signature area, each refused unless `pe` confirms the location.

**`experiments`** (*pure*) holds each experiment as a small frozen description: identifier, kind (`normal`, `pilot`, `counted`), which loader variant goes on the disk, edits to the variable store, firmware file, and the one sentence saying what changed. Descriptions are data. Adding an experiment adds a description, not a code path.

**`staging`** turns a description into a fresh run directory: boot disk tree, a copy of the template store, the changed loader. It does not start anything. Run directories live under a Linux path because unix sockets do not work on the Windows-mounted drive.

**`session`** starts swtpm and QEMU, speaks QMP (the machine protocol QEMU offers on a socket), watches the serial file, and performs the one ending: pause, save memory, kill QEMU while paused, read the PCRs from the still-running swtpm, stop swtpm. QEMU always runs under an outer timeout, and a `finally` path kills both processes.

**`capture`** (*pure parsers*) turns raw artifacts into Python values: cleaned console lines, the extend list from the swtpm log, the PCR values from TPM response bytes, and candidate event logs found in saved memory.

**`eventlog`** (*pure*) parses the event log binary and gives each event a type name and a plain one-line summary. Names follow the ones tpm2-tools prints; they are tool names, not specification citations.

**`gate`** (*pure*) replays the event log and the extend list and compares both with the live read (section 4.3).

**`normalise`** (*pure*) removes or masks whatever legitimately varies (run directory paths, wall-clock values) and sorts nothing that has a meaningful order.

**`recording`** (*pure*) builds the recording dictionary and writes it deterministically: UTF-8, LF line ends, two-space indent, sorted keys, lowercase hex.

**`compare`** (*pure*) compares two recordings on the compared fields only and produces the comparison document (section 5).

**`prediction`** (*pure* except one git query) loads and validates prediction files, answers "is a prediction for this experiment committed and unmodified", and scores a comparison against a prediction.

**`storymap`** (*pure*) assigns each event to a story stop from declared rules (section 7).

**`cli`** is the entry point: `prepare`, `record`, `compare`, `check`. Every failure is a non-zero exit code with one plain sentence.

**`errors`** defines the small exception family (`GateFailure`, `PredictionMissing`, `StagingRefused`, `ToolMissing`) so callers never catch bare exceptions.

## 4. The recording format

One file per run: `recordings/<run-name>/recording.json`.

### 4.1 Shape

```json
{
  "format": "lux-recording/1",
  "run": {"name": "normal-1", "experiment": "normal", "kind": "normal",
          "change": "none"},
  "provenance": {
    "recorded_at": "2026-11-14T10:00:00Z",
    "tools": {"qemu": "…", "ovmf": "…", "swtpm": "…", "tpm2-tools": "…",
              "sbsigntool": "…", "efitools": "…", "binutils": "…", "python": "…"},
    "host_os": "Ubuntu 24.04",
    "firmware": {"file": "OVMF_CODE_4M.secboot.fd", "sha256": "…"},
    "vars_template_sha256": "…",
    "loader": {"file_sha256": "…", "authenticode_sha256": "…"},
    "keys": {"PK": "…", "KEK": "…", "db": "…"},
    "qemu_command_line": "timeout -s KILL 300 qemu-system-x86_64 … <run-dir>/vars.fd …",
    "swtpm_command_line": "swtpm socket --tpm2 … <run-dir>/tpm …",
    "prediction": null
  },
  "outcome": {"result": "accepted", "trigger": "final-marker", "ending": "paused-then-killed"},
  "timing": {"seconds_to_trigger": 5.8, "seconds_to_pause": 8.8},
  "console": ["BdsDxe: loading Boot0001 …", "…"],
  "events": [
    {"index": 1, "pcr": 0, "type": "EV_S_CRTM_VERSION", "type_code": "0x00000008",
     "digest_sha256": "…", "summary": "firmware version string 2024.02-2ubuntu0.10",
     "stop": 3, "stop_rule": "pcr0-firmware"}
  ],
  "pcrs": {"sha256": {"0": "…", "23": "…"}, "sha1": {}, "sha384": {}, "sha512": {}},
  "event_log": {"sha256": "…", "bytes": 9657, "events": 28},
  "vars_after_sha256": "…",
  "gate": {"passed": true, "banks": 4, "pcrs_per_bank": 24, "checks": {
    "event_log_replay_equals_live": true, "extend_list_replay_equals_live": true,
    "event_sequence_equals_extend_sequence": true, "all_extends_answered_ok": true,
    "content_digests_recomputed": 21, "log_candidates_parsed": 1}},
  "may_vary": ["provenance.recorded_at", "timing.seconds_to_trigger", "timing.seconds_to_pause"]
}
```

`outcome.result` is one of `accepted`, `refused`, `timeout`. `provenance.prediction` is `null` for normal and pilot runs; for a counted run it holds the prediction file's path, SHA-256 and the commit that contains it. `keys` values are SHA-256 fingerprints of the certificates.

### 4.2 Rules

- **`may_vary` is the complete list of fields a comparison ignores.** Everything else must match between two normal runs. The raw swtpm log and swtpm's saved state differ between identical boots and are therefore never part of a recording.
- Paths under the run directory are written as `<run-dir>`, so no user name or machine path reaches the repository.
- An event's `summary` is derived from the event's own data. For events whose digest is defined by their content (variables, separators, action strings, the version string), the recorder recomputes the digest and counts the matches in the gate block.
- Guest memory is deleted as soon as the event log is cut out of it; it is never committed.

### 4.3 The agreement gate

Three independent readings of the same boot must agree on all 24 PCRs in all four hash banks:

1. replay of the event log (start value, then new = hash of old followed by digest, per event);
2. replay of the extend commands found in the swtpm log;
3. the live read from the TPM after the guest was paused.

Additional conditions: event *n* and extend *n* carry the same PCR and digest for every *n*; the TPM answered every extend with success; **exactly one** memory candidate parses as an event log. The log is chosen by structure and then tested, never chosen because its replay matches. A failed gate raises `GateFailure`, the command exits non-zero, and no recording is written.

## 5. The comparison format

`compare` takes a baseline and a changed recording and writes:

```json
{
  "format": "lux-comparison/1",
  "baseline": {"run": "normal-1", "recording_sha256": "…"},
  "changed": {"run": "e2", "recording_sha256": "…"},
  "identical": false,
  "outcome": {"baseline": "accepted", "changed": "refused"},
  "first_differing_event": {"index": 25, "stop": 6,
    "baseline": {"pcr": 7, "type": "EV_EFI_VARIABLE_AUTHORITY", "digest_sha256": "…"},
    "changed": {"pcr": 4, "type": "EV_EFI_ACTION", "digest_sha256": "…"}},
  "pcrs_differing": {"sha256": [4, 5, 7]},
  "pcrs_same": {"sha256": [0, 1, 2, 3, 6]},
  "events_only_in_baseline": [],
  "events_only_in_changed": [],
  "console_first_differing_line": 2,
  "other_fields_differing": []
}
```

Events are matched as (PCR, type, digest) in log order. "Only in one run" lists events with no equal partner in the other run. With `identical: true` every other field is empty; that is the repeat precondition for two normal runs.

## 6. The prediction file format

One file per counted experiment: `predictions/<experiment-id>.json`.

```json
{
  "format": "lux-prediction/1",
  "experiment": "boot-order",
  "written": "2026-11-20",
  "change": "BootOrder lists the second entry first",
  "rows": [
    {"id": "continues", "field": "outcome.result", "expect": "accepted",
     "basis": "uefi-required",
     "citation": {"document": "UEFI Specification", "version": "2.11",
                  "section": "3 Boot Manager", "page": 152}},
    {"id": "pcr1", "field": "pcrs_differing.sha256", "expect_contains": [1],
     "basis": "tcg-unread", "citation": null,
     "reason": "seen in the normal run's log on this firmware"}
  ]
}
```

The four basis labels:

| Label | Meaning | What the row must carry |
|---|---|---|
| `uefi-required` | Required by UEFI 2.11 | Section title and page |
| `uefi-platform` | UEFI 2.11 says so in words and leaves the choice to the platform | Section title and page |
| `tcg-unread` | Belongs to a Trusted Computing Group document that has not yet been read | No citation; a reason |
| `this-firmware` | This firmware's own behaviour | A source file or an earlier recording |

Validation rejects a row whose label and citation do not fit this table. Pages are page numbers of the published PDF file.

**The rule.** `record` refuses to start a `counted` experiment unless its prediction file exists, validates, is tracked by git, and has no uncommitted change. If git cannot answer, the answer is no. The recording stores the prediction's SHA-256 and commit; `check` fails if the prediction file no longer has that hash, so a prediction cannot be edited after its run without the check saying so. The result is two numbers: `uefi-required` rows met, and open rows (the other three labels) predicted correctly. A mismatch is reported as a mismatch.

## 7. Event to story stop

The site tells the boot as seven stops: reset, SEC, PEI, DXE, BDS, load and verify, handoff. **UEFI 2.11 does not define SEC, PEI, DXE or BDS**, and the event log carries no timestamps or phase markers. The mapping is therefore this project's own, declared as rules in `storymap`, and each rule states its basis.

| Rule | Events | Stop | Basis |
|---|---|---|---|
| `pcr0-firmware` | Version string and firmware blobs in PCR 0 | 3 | Log order observed; phase attribution from EDK II documentation, not yet confirmed in source |
| `pcr7-policy` | Secure Boot variables and the first PCR 7 separator | 4 | Same |
| `pcr1-config` | Platform configuration and boot variables in PCR 1 | 5 | Same |
| `boot-attempt` | "Calling EFI Application" action, separators for PCR 0 to 6 | 5 | Observed position, directly before the load |
| `authorise` | Authority record in PCR 7, image digest in PCR 4, "Returning from EFI Application" | 6 | Observed: present when accepted, absent or replaced when refused |
| `exit-boot-services` | The two exit actions in PCR 5 | 7 | Observed: only after the loader's exit call |

Stops 1 and 2 have no events and the recording says so. An event matching no rule gets `stop: null`, and a test fails if that happens in a committed recording.

## 8. Decisions

### D1. The guest loader is assembly, built with the installed assembler

*Context.* The loader must call `ExitBootServices`, print a final marker and then idle. No C compiler is installed and nothing may be downloaded.
*Chosen.* About 190 lines of commented assembly, linked without a timestamp.
*Weighed.* C (clearer, but needs a compiler download); Python that emits machine code (deterministic, but the bytes are harder to read than assembly).
*Consequences.* One toolchain, a byte-identical unsigned build, and a predictable image digest. **Cost:** readers who know Python must read assembly to trust the loader, and each new guest behaviour is slow to add.

### D2. The test keys are generated once and committed

*Context.* PCR 7 contains the certificate bytes, so two machines with different keys can never produce equal recordings.
*Chosen.* PK, KEK and db are generated once with a fixed owner identifier and fixed timestamps, and committed with their private halves, the signed loader and a hash manifest.
*Weighed.* Keys per machine (breaks reproduction); the distribution's packaged test store (one certificate in all three roles, leftover boot entries).
*Consequences.* Anyone can reproduce PCR 7 exactly. **Cost:** private keys sit in a public repository. They are test keys for this virtual machine only and must never be trusted anywhere; the README beside them says so, and secret scanners may still flag them.

### D3. Every run ends by pause, capture, kill

*Context.* When the guest powers off, QEMU tells swtpm to stop and the PCRs are gone before they can be read.
*Chosen.* The loader idles; the recorder pauses the guest, saves memory, and kills QEMU while paused, so swtpm stays alive for the live read. Refused boots take the same path.
*Weighed.* Guest power-off (loses the live read and the event log); a guest program that reads the log itself (changes the measurements it reports).
*Consequences.* One ending for every outcome and a three-way check. **Cost:** a 512 MiB memory file per run that must be deleted, a signature search to find the log, and an end condition based on a quiet period rather than a guest signal.

## 9. Risks that could mislead a reader

| # | Failure | Why it misleads | Covered by |
|---|---|---|---|
| 1 | A run with disagreeing readings is published | The PCR table would not follow from the event list | `test_gate`: a one-bit change in one digest must fail the gate; the CLI test asserts a non-zero exit and no file |
| 2 | The wrong memory region is taken as the event log | Events shown were never extended | `test_capture`: decoy headers that do not parse; two parsing candidates must raise |
| 3 | A counted run starts without a committed prediction | The headline numbers would not be blind | `test_prediction`: missing, untracked, modified and git-unavailable all refuse |
| 4 | Keys are regenerated unnoticed | Every PCR 7 value changes with no visible cause | `test_keys`: generation refuses a non-empty directory; manifest mismatch raises |
| 5 | A varying field leaks into the comparison, or a compared field is hidden in `may_vary` | False differences, or real ones masked | `test_compare`: recordings differing only in `may_vary` are identical; any other single-field change is reported |
| 6 | A refused boot is paused before its last extends | The changed run looks shorter than it is | `test_session` with a fake clock and growing files; the settle rule is recorded in the outcome |
| 7 | The changed byte lands in the wrong area | A signature-area change reported as a code change, or the reverse | `test_pe` and `test_loader`: location proven from headers, wrong area refused |
| 8 | A type name or stop is wrong | The story attaches an event to the wrong step | `test_eventlog` against tpm2-tools output kept as a fixture; `test_storymap` requires every event to match exactly one rule |

## 10. Test mix

The standard library `unittest` runs everywhere; no test runner is installed inside Linux, and nothing is installed for this project.

- **Unit tests on pure modules, the large majority.** Parsers and the gate are tested with small byte fixtures built in the test itself, so a failure points at one function. Each has a negative case that must fail.
- **Fixture tests.** One real swtpm log excerpt, one real event log and its tpm2-tools decoding are committed as fixtures; they pin the two undocumented formats the recorder depends on.
- **Tests with fakes for `session` and `staging`.** Fake process, socket and clock objects exercise the ending path, the timeout and the cleanup without booting anything. All five experiment descriptions are staged this way, including those that may not yet be run.
- **Refusal tests.** Prediction gate and key regeneration, as listed in section 9.
- **Two real boots, run by hand, not by the test suite:** the normal run twice (the repeat precondition) and the declared pilot. They need the virtual machine and about ten seconds each.

Not tested: behaviour on another QEMU version or machine type, hardware acceleration, and whether a third boot of one variable store equals the second.
