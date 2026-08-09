# Operations

How to run things. Windows, Python 3.14, single machine.

Paths below are absolute where being wrong about them would be expensive.

## Safety

Read this before running anything. It is an operational rule, not a preference,
and it is not relaxed when something would be convenient.

**Mistfall Hunter ships kernel-level anti-cheat.** Therefore, while the game is
installed on this machine, nothing in this repo and nothing you run alongside it
may:

- inject a plugin, DLL, or script into the game process
- open a handle to the game process or read its memory
- capture, proxy, or modify the game's network traffic
- hook the game's swapchain, or draw any overlay over the game window
- synthesise keyboard or mouse input into the game window

The cost of getting this wrong is a permanent ban on the operator's own account,
and several of the above are plainly outside the EULA. There is no "just for a
test" version of any of them, and no debug flag that makes one acceptable.

Three practical rules that follow:

1. **Read-only means read-only.** Probes in this repo open files, read a bounded
   number of bytes, and write nothing. `probe_paks.py` reads 144 bytes per
   `.utoc` and 221 per `.pak`; that is the model to copy.
2. **Never hold a lock on a file the game is writing.** The log is
   live-appending while the game runs. Open it for shared read and get out.
3. **`GSDKCache\` is out of bounds.** `accountList.json`, `user.json`,
   `user_infos.json` and `gsdk_app_log.db` sit under the install dir next to the
   anti-cheat binaries. They were listed once and never opened. Keep it that way.

The full reasoning is in [`FINDINGS.md`](FINDINGS.md) section 2 and
[ADR-001](adr/ADR-001-no-game-process-interaction.md).

## Install git hooks - do this first in a fresh clone

```
python scripts/install_hooks.py
```

**A fresh clone runs zero git hooks until you run this.** `core.hooksPath` is
local repository config; it is not part of the tree and it is not cloned. So a
tracked `.githooks/` directory looks like protection and provides none until
somebody points git at it. Nothing warns you - commits simply succeed that
should have been blocked.

Treat the hooks as the authoritative gate for the ASCII rule and for anything
else the repo enforces at commit time. Editor plugins and CI are defence in
depth, not a substitute.

Verify it actually took, rather than trusting that the script printed something:

```
git config --get core.hooksPath
```

And if you want proof, test it end to end - stage something the hook should
reject, attempt a real commit, and confirm `HEAD` did not move. A hook being
present is not evidence that it fires.

## Run the tests

```
python -m pytest
```

Run from the repo root. The suite does not require the game to be installed or
running - fixtures are committed (redacted) so that every test is runnable on a
clean machine.

Every feature starts with a failing test. If you are adding one, write the test,
watch it fail for the right reason, then implement.

## Run the pak probe

```
python scratchpad/probe_paks.py
```

Reads the container headers under
`C:\Program Files (x86)\Steam\steamapps\common\Mistfall Hunter\MistfallHunter\Content\Paks`
- 144 bytes from each `.utoc`, 221 from the end of each `.pak`. It opens no
process, loads no game module, and writes nothing.

Expected result today: 15 chunks, every one reporting
`flags=Compressed|Encrypted|Indexed`, `keyguid=ZERO`, and every legacy `.pak`
sidecar reporting `pakver=12 encrypted_index=True`.

Re-run it after any game patch. The point of keeping this probe is not to
re-confirm what we know - it is so that a patch which ships **unencrypted** paks
is detected rather than assumed away. The probe is slated to move to
`tools/probe_paks.py` with a test asserting the encrypted-flag finding, so the
check runs in the suite rather than depending on someone remembering.

## Run the frame poller

The poller captures the operator's own desktop on an interval and writes
timestamped frames. It does **not** capture the game window specifically, does
not overlay, and does not hook anything - it is a plain desktop screenshot on a
timer.

It is used to join screen-rendered text to log lines on wall clock, which is how
the class-id table in [`OBSERVED_IDS.md`](OBSERVED_IDS.md) was established. The
method matters: capture every 3 seconds with **local-time filenames**, note that
the log timestamps are UTC (local is UTC-5), and join the two streams on wall
clock.

When reading a class carousel back, remember the lag: the ROLE description panel
trails the selection by about one frame while the sidebar highlight leads it.
Read the panel for the outgoing class and the sidebar for the incoming one.

Note: the poller script is **not yet in the repo tree.** It ran from a session
scratchpad on 2026-08-09. Its intended home is `tools/frame_poller.py`, and
moving it there is unfinished business - until then, `OBSERVED_IDS.md` refers to
it as `scratchpad/frame_poller.py`.

## Find the game log

```
%LOCALAPPDATA%\MistfallHunter\Saved\Logs\MistfallHunter.log
```

The whole Saved tree, created the first time the game runs:

| Path (under `%LOCALAPPDATA%\MistfallHunter\Saved\`) | What |
|---|---|
| `Logs\MistfallHunter.log` | live-appending, the primary surface |
| `SaveGames\*.sav` | four files, plain GVAS, not encrypted |
| `Config\Windows\GameUserSettings.ini` | settings |
| `Config\Windows\Engine.ini` | plugin roster |
| `AvgPrice_937566.ini` | market / trade-price cache |

**If the directory does not exist, the game has never been run on this machine.**
That is not a negative result about the game - it was very nearly recorded as one
on 2026-08-09. Launch the game once, reach the main menu, and sweep again.

Useful greps once you have it:

```
grep "setClassGender inclassid" MistfallHunter.log
grep "server_refreshKnightFeature" MistfallHunter.log
grep "match state changed to" MistfallHunter.log
```

### Before you paste any of it anywhere

The log contains the operator's SteamID64, Steam persona, GSDK openID and userId,
an EOS ProductUserId, and an IP-resolved city, state and country.

**No log excerpt, fixture, sample or screenshot goes into a commit, an issue, or
a chat window without passing through the redactor first.** This repo is public.
See [ADR-004](adr/ADR-004-redaction-is-mandatory.md).

## Reserved local ports

None of these are built and nothing is listening on any of them. Reserved so
future services do not collide.

| Port | Service |
|---|---|
| 8810 | Dashboard |
| 8811 | Log-tail service |
| 8813 | Emberforge |

## Authoring rules enforced at commit time

- **7-bit ASCII only.** No em-dashes, no en-dashes, no smart quotes, anywhere in
  authored content. Use `" - "` for a clause break, `-` otherwise.
- **No `Co-Authored-By` trailer** on commits.

Both are checked by the hooks you installed in the first step. If you skipped
that step, neither is checked at all.
