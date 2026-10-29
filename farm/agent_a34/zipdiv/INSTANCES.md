# Addendum 34, zipdiv: the instances that were given round1_prompt.md

Every instance was a fresh Claude sub-agent with no other context. Each got the same prompt file
(`round1_prompt.md`, sha256 020b2f704db52ecfead0ae71832e05b33136d8fe1f5ec91c8d5f9ce7df9b0e2b, committed in 6ed27bb
before the first instance started) through a one-line wrapper. Times are UTC, Oct 29 2026.

| Instance | Started | Ended | Wrapper | Outcome |
|---|---|---|---|---|
| 1 | 07:26:31 | 08:48:30 | registered wrapper (below) | No reply. After its one Read it spent four responses at the 128,000-token output limit on private reasoning, and the harness ended it. |
| 2 | 08:49:10 | 10:11:50 | identical to instance 1 | No reply. Same as instance 1 (512,222 output tokens). |
| 3 | 10:12:22 | 10:43:23 | registered wrapper + one sentence (below) | Replied after one response at the limit (266,678 output tokens): `round1_reply.md`, RTL `round1_zipdiv.v`. |

Registered wrapper (the one MD5's instances got):

> Read the file /home/claude/eda/farm/agent_a34/zipdiv/round1_prompt.md with the Read tool. That file is your entire
> task. Do not open any other file, run any command, or search anything. Reply with exactly the format the file asks for
> and nothing else.

Instance 3's wrapper adds one sentence after "search anything.":

> Keep your private reasoning brief: decide on your change, then write the complete reply in this same response.

That sentence adds no information about the design, the flow, the gate or the earlier instances. It was a deviation from
the registered wrapper, decided at 10:12 UTC before instance 3 existed and logged then. For comparison, MD5's round-1
instance replied only on its fourth response (three at the output limit), and its round-2 instance replied on its second.
A reply is the only thing gated. Instances 1 and 2 produced no reply, so they are not failed proposals. The gate
(`farm/rtl34/verify_zipdiv.py`, final version committed in eab6581 before instance 3's reply) and the measure are
unchanged.
