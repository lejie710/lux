# Content

The words of the site, as data. Five JSON files, one shape, format `lux-content/2`. A site builder loads them; `scripts/check_content.py` checks them against the committed recordings. Nothing here is site code.

```
python3 scripts/check_content.py
```

It prints one line per problem and exits 1 if there is any. The last section of this file lists what it checks.

## Files

| File | Holds | Top-level fields besides `format`, `file`, `language` |
|---|---|---|
| `story-a.json` | The opening screen and stops 1 to 3 | `opening` (a screen), `stops` |
| `story-b.json` | Stops 4 and 5 | `stops` |
| `story-c.json` | Stops 6 and 7 | `stops` |
| `experiments.json` | The experiments section | `section` (`id`, `nav_label`), `screens` |
| `sources.json` | The sources and about screens, and everything the other files point to | `screens`, `basis_labels`, `glossary`, `sources`, `firmware_sources`, `not_read`, `limits`, `stage_names`, `reading_notes`, `picture_note`, `disclaimer`, `trademark_note`, `names_kept_out_of_statements` |

Every file has `format: "lux-content/2"`, `file` (its own name) and `language: "en"`. Text that every screen shares has one home, in `sources.json`: the basis labels, the glossary, the note under every picture (`picture_note`), the notes on how to read a page number or an event type name (`reading_notes`), and the note on stage names (`stage_names`).

## A stop

`stops` is a list. The three story files together hold stops 1 to 7, each once, in rising order.

| Field | Type | Meaning |
|---|---|---|
| `number` | integer 1 to 7 | The stop |
| `of` | 7 | Always 7 |
| `id` | `"stop-N"` | |
| `label` | text | The short name shown beside "N of 7" |
| `stage_name` | object or null | The name the firmware's source uses for this stage. Null for stops 1, 6 and 7. See below |
| `label_basis` | text, optional | Where the label comes from, when the stop has no stage name |
| `threads` | list | Any of `"secure-boot"`, `"measured-boot"` |
| `mapping` | object | `rules`: the recorder's `stop_rule` names that place events at this stop (empty for stops 1 and 2). `events`: one line saying which events. `rests_on`: what the mapping rests on. `claims`: optional |
| `not_shown` | list of text, at least one | What the recording does not show for this stop |
| `headline` | screen id | The one screen whose statement stands for the stop. The seven headline statements, read in a row, tell the boot |
| `screens` | list, at least one | The screens of the stop, in reading order |

`stage_name` is `{name, expansion, attribution, claims}`. SEC, PEI, DXE and BDS are not terms of UEFI 2.11. `attribution` must say that the Platform Initialization specification, where the names come from, was not read for this project. No claim that cites UEFI 2.11 as a requirement may name one of the four.

`mapping.rules` must equal the set of `stop_rule` values that `recordings/normal-1/recording.json` stores for the events of that stop. The mapping of an event to a stop is this project's own.

## A screen

Every screen, in every file, has the same core.

| Field | Type | Limit |
|---|---|---|
| `id` | text | Unique |
| `kind` | text | One of `opening`, `stop`, `pilot`, `closing`, `intro`, `side-by-side`, `cards`, `list`, `sources-page`, `about` |
| `stop` | integer or null | The stop a story screen belongs to; null elsewhere |
| `statement` | `{text, emphasis}` | `text`: at most 14 words. `emphasis`: null, or one phrase copied letter for letter from `text`, set in the warm colour |
| `support` | text or null | Exactly one sentence, at most 30 words |
| `evidence` | object | One line from a committed recording. See below. Null only on a `side-by-side` screen, where each side carries its own |
| `detail` | object | What "Open the evidence" shows. See below |
| `claims` | list, at least one | See below |
| `picture` | object or null | Required on story screens; null elsewhere. See below |

A statement or a supporting sentence never names a product or a project. The names in `sources.json` `names_kept_out_of_statements` are refused there; they appear only in evidence lines, which are verbatim, and in sources.

Fields that only some kinds have:

| Kind | Extra fields |
|---|---|
| `opening` | `eyebrow`, `title` (`{text, emphasis}`), `invitation` (`label`, `line`), `scope_note` |
| `stop` | `thread`, `thread_first_appearance`, optional |
| `pilot` | `pilot_label`: the sentence that says this run was made before any prediction and is not counted |
| `closing` | `picture_caption`, `handover` (the way on to the earlier site: `to`, `text`, `link_label`, `note`, and `url`, which is null until that site has a public address and then begins `https://`; the label is a link only when `url` is set) |
| `intro` | `eyebrow`, `question`, `measure` (list of text), `score` (`claimed` is false until a counted experiment has run) |
| `side-by-side` | `eyebrow`, `experiment`, `status` (`label`, `text`, `counted`), `change` (`text`, `file`, `field`), `sides`: exactly two, each `{id, run, label, statement, outcome, picture, evidence}` with a statement of at most 14 words and a recorded evidence line |
| `cards` | `eyebrow`, `status_source`, `cards`: each `{id, label, title, status, counted, result, claims}`, plus `change`, `result_note`, `specification_note` on pilots. `result` is null until the run is recorded, and then names the run and its comparison file (`{run, comparison}`); what the run showed is read from those files, not repeated here |
| `list` | `eyebrow`, `items`: each `{id, title, text, claims}` |
| `sources-page`, `about` | `title`; `about` also has `paragraphs` |

## Evidence

Recorded evidence:

| Field | Meaning |
|---|---|
| `recorded` | `true` |
| `kind` | `"event"`, `"console"` or `"loader_report"` |
| `run` | The run, for example `"normal-1"` |
| `file` | `recordings/<run>/recording.json` |
| `field` | The exact place: `events[24].summary`, `console[0]` or `loader_report[10]` |
| `position` | The number inside the brackets: the place in that JSON array, counted from 0 |
| `text` | The line, copied letter for letter from that place. Never reworded |
| `event_index` | Events only: the event's own `index` field, counted from 1. Position 24 is index 25 |
| `highlight` | Optional: a part of `text` to set in colour |
| `caption` | Optional: one line under the evidence |

The register and type of an event are not repeated in the content. The site reads them from the recording at the same position.

Evidence that does not exist:

```json
{"recorded": false, "kind": "not-recorded", "label": "Described, not recorded: a virtual machine has no power sequencing."}
```

It has a `label` that says so, an optional `caption`, and no `text` or `file`. Stop 1 uses it, and so do the experiment cards that have no committed recording.

## Detail

| Field | Type | Meaning |
|---|---|---|
| `console_lines` | list of `{run, positions, note?}` | Console lines to show, by place in the `console` array, from 0 |
| `loader_report_lines` | list of `{run, positions, prefix?, highlight?, note?}` | Lines of the loader's report, by place in `loader_report`, from 0 |
| `events` | list of `{run, indexes, note?}` | Events to show, by their own `index` field, from 1 |
| `pcrs` | list of `{run, bank, registers, note?}` | Registers to show. The value is the one read at the end of the run |
| `explanation` | text | Two to four sentences |
| `definitions` | list | Every term the screen uses. See below |
| `not_shown` | list of text, optional | What the recording does not show |
| `comparison` | `{file, baseline, changed}`, optional | The comparison file a two-run screen rests on |
| `other_fields` | list of `{file, field, value?, why}`, optional | Other fields of a recording worth showing |
| `console_note`, `pilot_note`, `basis_labels` | optional | One line each; `basis_labels` is a list of basis values to explain on that screen |

All four lists are always present and may be empty. The side-by-side screen adds the comparison's own fields (`first_differing_event`, `pcrs_differing`, `pcrs_same`, `events_only_in_baseline`, `events_only_in_changed`, `console_first_differing_line`, `status_mismatch`).

A definition is one of two things:

```json
{"glossary": "secure-boot"}
{"term": "LUX MM line", "definition": "One block as the loader printed it: ..."}
```

The first points at an entry of the glossary in `sources.json` by `id`. The second defines a term that only this screen needs. A term that is in the glossary, under its `term` or one of its `also` names, is never defined again on a screen, and a term defined on two screens has the same words on both. A local definition may carry a `basis` and what that basis needs, and is then checked as a claim.

## Claims

Every factual statement is backed by one or more claims. A claim has `text`, `basis`, and what its basis needs. `id`, `note` and `derived` are optional.

| `basis` | Means | Must carry | Must not carry |
|---|---|---|---|
| `uefi-required` | UEFI 2.11 has a sentence that requires or defines it | `citation` | |
| `uefi-platform` | UEFI 2.11 has a sentence that leaves it to the firmware maker | `citation` | |
| `tcg-unread` | It belongs to a Trusted Computing Group document that was not read for this project | | `citation`. May carry `uefi_pointer` (the place where UEFI 2.11 points away) and `reason` |
| `this-firmware` | What this firmware did, or how its own source names things | `source` | `citation` |
| `recording` | Read straight from a committed recording or comparison | `run`, `field`; `file` optional | `citation` |
| `general` | Uncontroversial background, such as what a hash is | | `citation` |

`citation` and `uefi_pointer` have the same shape:

| Field | Value |
|---|---|
| `document` | `"UEFI Specification"` |
| `version` | `"2.11"` |
| `section` | The section number, as text: `"32.5.3.3"` |
| `title` | The section title |
| `pdf_page` | A whole number: the page of the published PDF to open. Not the number printed at the foot of the page |
| `pdf_pages` | Optional: every page the passage touches, rising, `pdf_page` among them |

`source`, on a `this-firmware` claim, is one of two things. Either it begins `observed in recording <run>` and names a committed run, or it is the path of a firmware source file and the claim also has `source_ref`, the `id` of an entry in `sources.json` `firmware_sources`. Such an entry has `path`, `url`, `read_at` and `licence`, and its `path` equals the claim's `source`.

`run`, on a `recording` claim, is one run or several separated by a comma and a space: `"normal-1, e2"`. `field` names at least one field of a recording or comparison file.

Two rules of wording. A claim whose basis is `tcg-unread` or `this-firmware` never says or implies that a specification says, states, requires or defines the behaviour; it may say that UEFI 2.11 states no rule. And `general` stays rare: at most one claim in ten.

## Pictures

```json
{"plate": "board", "lit": ["power", "firmware", "processor"], "newly_lit": ["firmware"], "screen": "none", "note": "..."}
```

| Field | Value |
|---|---|
| `plate` | `"board"` or `"laptop"` |
| `lit` | The parts that glow, from: `power`, `firmware`, `processor`, `memory`, `controllers`, `storage`, `security`, `ribbon` |
| `newly_lit` | The parts that are lit here and were dark on the screen before |
| `attention` | Optional: the lit parts this screen is about, which are given a slightly stronger light. Without it, the newly lit parts are |
| `screen` | `"none"` on the board plate, where no screen is in view; `"dark"` or `"dawn"` on the laptop plate |
| `note` | Why these parts. Always says, or implies, that it is an illustration |
| `view`, `reasons` | Optional: the camera position, and one line per part |

Light never goes out along the story: each story screen's `lit` contains the `lit` of the screen before it. A picture is an illustration. It is never evidence, and no claim rests on one.

## The glossary and the other lists in `sources.json`

| List | Each entry |
|---|---|
| `basis_labels` | `{basis, label, meaning}` for the six basis values |
| `glossary` | `{id, term, also, definition, basis, ...}`. `also` lists other names the site uses for the same thing. The entry is checked as a claim |
| `sources` | What was read or run: `{id, kind, title, version, url, licence, how_used, claims, ...}` |
| `firmware_sources` | Firmware source files named as the basis of a claim: `{id, kind, project, path, url, read_at, licence}` |
| `not_read` | Documents that were not read, and what that costs the reader |
| `limits` | `{id, title, text, claims}` |

## What the check refuses

| Code | It fails when |
|---|---|
| `format` | A file has another format string, language or file name, a screen has an unknown kind, or a `handover.url` is neither null nor an `https://` address |
| `character` | An em-dash, en dash, horizontal bar, minus sign, replacement character or control character appears anywhere, this file included |
| `statement` | A statement is missing, has more than 14 words, or its emphasis is not a phrase of it |
| `support` | A supporting sentence has more than 30 words or is not exactly one sentence |
| `names` | A statement or supporting sentence names a product or project |
| `evidence` | An evidence line is missing, or its text is not found letter for letter at the file, field and position it names |
| `detail` | A console line, event or register that is named does not exist in that run, or the explanation is not two to four sentences |
| `definition` | A definition points at no glossary entry, repeats one, or the same term is defined in two ways |
| `claim` | A claim has no basis or an unknown one, a screen has no claim, or a claim lacks what its basis needs |
| `citation` | A UEFI basis has no full citation, or another basis carries one |
| `phrase` | Wording such as "the specification says" is on a `tcg-unread` or `this-firmware` claim |
| `stage` | A claim that cites UEFI 2.11 as a requirement names SEC, PEI, DXE or BDS, or a stage name is attributed without saying that its defining document was not read |
| `stop` | A stop number from 1 to 7 is missing or repeated, or a stop lacks a field |
| `picture` | A picture names an unknown part, light goes out along the story, or attention is drawn to a part that is not lit |
| `general` | More than one claim in ten has the basis `general` |

The check proves form and the letter-for-letter match with the recordings. It cannot prove that a paraphrase of the specification is right; that was checked by reading, against the section and page each claim cites.
