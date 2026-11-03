# IO1 reader instructions (for the coordinator)

Spawn **one fresh Claude (Opus 5.5) per packet**: 10 packets, listed at the end. Same prompt for all, with `<P>`
replaced by the packet's pseudonym. Do not give a reader this file, the repository, `/home/claude/qa/`, the overnight
reports, STATUS.md, or any other packet's answer.

---
You are helping with a physical-design experiment. Read `/home/claude/ideas/overnight/pins/packets/<P>/README.md`
and do what it says. Use only the files in `/home/claude/ideas/overnight/pins/packets/<P>/` (you may run Python on
them, for example to parse the DEF, the per-net dumps and the path reports, and you may run its validate_pins.py). Do
not open any other file or folder on this machine, any repository, or the web, and do not try to identify the design.
Write exactly `/home/claude/ideas/overnight/pins/claude/<P>/pins.txt` (create the folder; optionally also
`rationale.md` there, at most 300 words). Then run
`python3 /home/claude/ideas/overnight/pins/packets/<P>/validate_pins.py /home/claude/ideas/overnight/pins/claude/<P>/pins.txt`;
it must print OK. You get one selection and will not see any result. When done, reply with the file's contents and
the validator's output. Take at most 45 minutes.
---

Rules (pre-registered, docs/qa_week/IO_PREREG.md):
- One selection per packet; no rescue after any outcome (the reader sees none).
- If the coordinator's own run of validate_pins.py rejects the file, show that reader the validator's message once
  (format only) and let it fix the file; a file still invalid then counts as ABSTAIN (write `ABSTAIN` as its pins.txt
  and say so in STATUS.md).
- Readers may abstain.

Packets: PACKET_LIST
