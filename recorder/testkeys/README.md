# Test keys: public, for this virtual machine only

**Everything in this directory is public test material. The private keys are
published on purpose. Never enrol these certificates on a real machine, never
trust anything signed with them, and never reuse them anywhere.**

## What is here

| File | What it is |
|---|---|
| `PK.key`, `KEK.key`, `db.key` | Private keys of the three Secure Boot levels (platform key, key exchange key, signature database) |
| `PK.crt`, `KEK.crt`, `db.crt` | The matching self-signed certificates |
| `*.esl` | Each certificate wrapped as a UEFI signature list |
| `*.auth` | Signed variable updates that enrol the lists (PK signs PK and KEK, KEK signs db) |
| `loader-signed.efi` | The guest loader, signed once with the db key |
| `MANIFEST.json` | SHA-256 of every file above, the loader's Authenticode digest, and the hash of the variable store template that enrolling these keys produces |

Owner identifier in every signature list: `11111111-2222-3333-4444-555555555555`.
Timestamp in every signed update: `2026-01-01 00:00:00`. The certificates'
validity dates are the day they were generated; the tool used does not allow
fixing them.

## Why private keys are committed

The firmware measures the Secure Boot certificates into TPM register 7. Two
machines with different keys can never produce the same register 7, so a
recording could not be reproduced by anyone else. Committing one fixed key set
is what makes every committed recording reproducible. The cost is that secret
scanners may flag this directory.

## Why they are never regenerated

New keys would change register 7 in every future recording and make every
committed recording unreproducible, without any visible error. The recorder
therefore generates keys only on an explicit request and only when this
directory holds no key material, and it checks every file against
`MANIFEST.json` before each run. Signing is not repeatable either, so
`loader-signed.efi` is a fixed artifact, not a build product.
