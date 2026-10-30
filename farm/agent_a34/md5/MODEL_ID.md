# Model identity of the Addendum 34 MD5 rewrite instances (recorded after the fact)

Recorded 2026-10-30T06:05:01Z (date -u) from the session's subagent transcripts. The model field of every assistant message in each
transcript, with the first message time:

| Round | Prompt file | Model | First message (UTC) |
|---|---|---|---|
| 1 | farm/agent_a34/md5/round1_prompt.md | claude-opus-5-5 | 2026-10-29T01:10:29Z |
| 2 (revision) | farm/agent_a34/md5/round2_prompt.md | claude-opus-5-5 | 2026-10-29T03:35:37Z |

Each instance was told only to read its prompt file (its whole task) and reply; the replies are round1_reply.md and
round2_reply.md, committed before the flow ran. The Addendum 35 instances are logged the same way in agents/a35/audit.jsonl.
