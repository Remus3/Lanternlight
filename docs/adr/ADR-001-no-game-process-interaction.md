# ADR-001: No game-process interaction, ever

## Context

Mistfall Hunter ships **kernel-level anti-cheat**. The Steam store page discloses
"Uses Kernel Level Anti-Cheat", names it Bellring Anti-Cheat, and gates it behind
a third-party EULA.

The shipped binary set corroborates a heavy commercial anti-cheat and SDK stack:
`gpHackerProc.dll` (5.7 MB), `gpShell.dll`, `sscronet.dll`,
`tgrpdownloader.dll`, plus a publisher SDK layer under
`Binaries\Win64\GSDK_US\Steam\` (`gp.dll`, `gpm.dll`, `gpmperf.dll`, `gsdk.dll`,
`parfait.dll`, `bmf_hydra.dll`) reporting GSDK version `3.23.0.0`, package
`com.hermes.pstgame`, app_id `937566`. An embedded CEF browser ships alongside.

The precedent project (`C:\RedMoon`, V Rising) has an architecture with a
live-state half built on process integration. The question was whether that
transfers. It does not.

Measured: [`../FINDINGS.md`](../FINDINGS.md) section 2.

## Decision

Lanternlight will never interact with the game process. Specifically, and not as
a list to be argued around:

- no BepInEx or any other injected plugin
- no process memory read, no handle open, no DLL load into the game
- no packet capture or proxying of game traffic
- no overlay that hooks the game's swapchain or window
- no synthesis of keyboard or mouse input into the game window

Lanternlight reads only what the game itself writes into user-writable space, and
what is visible on the operator's own screen.

## Consequences

- The entire RedMoon live-state half is out of scope permanently. There is no
  live combat state, no in-memory entity read, no real-time damage feed.
- No in-game surface of any kind. Any UI this project grows is a separate
  top-level window owned by our own process.

  **Amended 2026-08-09, same day.** The original wording of this line read "and
  never an overlay", which conflated two different things and would have banned
  something the Decision above permits. To be exact: an **injected or hooked**
  overlay - one that hooks the swapchain, hooks Present, or uses
  SetWindowsHookEx against the game - remains forbidden by the Decision and is
  not negotiable. An **always-on-top borderless window** owned by our own
  process is an ordinary Windows window, involves no injection and no hooking,
  and is permitted. The operator accepted that distinction and its residual
  risk knowingly on 2026-08-09. See [`../OVERLAY.md`](../OVERLAY.md) section 2.
  The Decision itself is unchanged; only this consequence was over-broad.

- **Modding is closed independently of this rule.** Measured 2026-08-09: the
  Steam category list for appid 3282300 contains no Workshop entry, no level
  editor and no mod support, and every pak chunk is AES-encrypted
  ([ADR-002](ADR-002-no-asset-extraction.md)). Even without the anti-cheat
  boundary there would be no supported modding route.
- The project's data surfaces are narrowed to three: the game log, the GVAS
  saves, and passive screen capture ([ADR-003](ADR-003-log-is-primary-surface.md)).
- Some questions become permanently unanswerable by this project, and that is
  accepted rather than worked around.
- This forces every number to be measured rather than read
  ([ADR-005](ADR-005-omit-rather-than-guess.md)), which is slower and is the
  correct trade.

## Status

**Accepted, permanent.** 2026-08-09.

Not subject to revision by this project. The stake is a permanent ban on the
operator's real account, and several of the forbidden actions are plainly outside
the EULA. There is no test build, debug flag, or one-off experiment that makes
any of them acceptable. If a proposed feature requires one, the feature is
rejected, not the rule.
