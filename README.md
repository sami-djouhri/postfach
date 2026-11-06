# postfach

![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-61DAFB?logo=react&logoColor=black)
![Tesseract](https://img.shields.io/badge/Tesseract%20OCR-4B8BBE)
![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)

Paper mail, digitised: scan a letter, run OCR over it, file it under a category,
find it again, export it as PDF. Part of the
[Saganta Suite](https://github.com/sami-djouhri/saganta-suite), usable on its
own. All user-facing text is German.

## Why the whole folder is encrypted and not single columns

The plain text of a letter lives in four places: the letter's OCR field, the
per-file OCR field, the full-text index, and the scan on disk.

The index is the one people miss. It is declared `content='letter'`, so it
supposedly stores no text of its own. In a measurement on real data, **132
readable words from two letters** could be pulled straight out of its blocks.

Encrypting individual columns would have protected nothing here and still looked
like protection. So the recommended setup puts the entire data directory inside
an encrypted volume, and the container mounts a path *inside* it. When the
volume is locked that path does not exist and Docker refuses to start with a
clear message.

That last detail is the point. If the mount pointed at the volume's mount point
instead, a locked volume would be an empty but existing directory: the service
would start, create a fresh database, and write new letters in clear text next
to the encrypted ones. Nothing about it would look like a failure.

In practice this means one variable. `POSTFACH_DATEN` is the host directory the
container mounts at `/app/data`, and Docker will **not** create it for you
(`create_host_path: false`), by design. Point it inside your unlocked encrypted
volume, or, if you would rather not encrypt at all, at any directory you have
created yourself:

```bash
echo 'POSTFACH_DATEN=/srv/postfach/daten' >> .env
mkdir -p /srv/postfach/daten
docker compose up -d
```

Without it the default is `$HOME/postfach-tresor/mount/daten`, which will not
exist, and the start fails with a message naming the missing path.

## Two ways in

A tenant header signed with a shared secret (the suite's way), or a classic
session with a bcrypt password (standalone). The header path has three states:
no secret configured, observe-and-log, and reject-unsigned. Run the middle one
until the logs stay quiet.

There is deliberately **no owner id in the code**. A new, empty mailbox is only
created for a proven tenant; an unknown one gets 403 and no fallback. That
fallback is precisely why the older auto-login token is being retired: it
announces every caller as the same user, so a second account sees the first
one's mail.

## Optional helpers, off by default

Three integrations are configured by URL and disabled when empty: a language
model for summarising a letter, a vision service that de-skews photos into PDFs,
and speech-to-text. None of them are required, and each fails closed with a
readable message rather than running into a timeout.

## Tests

```bash
bash run-tests.sh     # expects "Ran 9 tests ... OK"
```

Tests run in a throwaway container built from the **image**, not against the
source tree. A test against the tree proves the file is right, not that the
service has it.

## License

AGPL-3.0.

## About this snapshot

The recipe, not the data. The encrypted-volume scripts are the solution one
household chose, with fixed paths and assumptions; they are not in here, so pick
your own (LUKS, ZFS, or nothing). The reasoning above is the part worth keeping.

The development history stays private; the public one starts at the first
release and grows with each one.
