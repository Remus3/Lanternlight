# Security Policy

## What this project is, in one paragraph

Lanternlight is a companion and analysis tool for a game. It runs locally, binds
no network service by default, and reads files the game writes into
user-writable space plus passive screen capture of the operator's own display.
It has no server, no accounts, no telemetry and no API keys.

## Supported versions

There are no releases yet. The `main` branch is the supported version, and the
fix for anything reported goes there.

## Reporting a vulnerability

Use GitHub's private reporting:
**Security -> Report a vulnerability** on this repository, which opens a
[private security advisory](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
visible only to the maintainer.

Please do not open a public issue for anything that would expose someone's data
before it is fixed.

Expect a first response within a week. This is a one-person project worked on
between other things, so that is a realistic figure rather than a service level.

## What is in scope

- **Anything that leaks an operator identifier.** This is the most valuable
  report you can send. The game's log and save files carry account identifiers -
  SteamID64, Steam persona, platform SDK ids, and more - and this project's
  central safety rule is that none of them crosses off the machine or into git
  history. If you find a path that publishes one, that is a real defect however
  small it looks. See
  [ADR-004](docs/adr/ADR-004-redaction-is-mandatory.md).
- Code execution or file writes outside the paths documented in the README.
- A dependency vulnerability that is actually reachable from this code.
- Anything that would cause the tool to touch the game process. That is a
  correctness AND a safety bug here, for the reason in the next section.

## What is out of scope

- **Vulnerabilities in Mistfall Hunter itself.** Report those to Bellring Games
  or Skystone Games, not here. This project has no privileged view of the game.
- **Cheats, exploits, or anti-cheat bypasses.** Not accepted, in an issue, a
  pull request, or a security report. Mistfall Hunter ships kernel-level
  anti-cheat, and this project never injects, reads process memory, captures
  traffic, hooks rendering, or synthesises input - permanently, not by default.
  See [ADR-001](docs/adr/ADR-001-no-game-process-interaction.md).
- **Extracted game assets or decryption keys.** All 15 shipped pak chunks are
  encrypted; nothing derived from breaking that is welcome here. See
  [ADR-002](docs/adr/ADR-002-no-asset-extraction.md).
- Findings from automated scanners with no demonstrated impact on this code.

## If you are reporting a leak, do not include the leaked value

Describe where it comes out and how you triggered it. A path is enough to
reproduce; a real SteamID in a public report is a second leak on top of the
first. This is the project's own standing rule for evidence, and it applies to
reports as much as to commits.
