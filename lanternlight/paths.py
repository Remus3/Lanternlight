"""Resolve the Mistfall Hunter Saved tree.

Pure path arithmetic. Nothing in this module touches the filesystem at import
time, and nothing here requires the game to be installed - every function
returns a :class:`pathlib.Path` whether or not that path exists. That is what
makes the rest of Lanternlight testable on a machine that has never run the
game.

Layout, as measured on Windows on 2026-08-09::

    %LOCALAPPDATA%/MistfallHunter/Saved/
        Logs/MistfallHunter.log
        SaveGames/
        Config/...

Override the whole tree with the ``LH_SAVED_DIR`` environment variable. That
variable points at the ``Saved`` directory itself, not at its parent, so a
captured or redacted copy of the tree can be pointed at directly::

    set LH_SAVED_DIR=C:\\fixtures\\Saved

Every function takes an optional ``env`` mapping so callers and tests can
supply their own environment instead of the process one.
"""

import os
from collections.abc import Mapping
from pathlib import Path

#: Environment variable that overrides the resolved Saved directory.
ENV_SAVED_DIR = "LH_SAVED_DIR"

#: Environment variable holding the Windows per-user local app data root.
ENV_LOCAL_APP_DATA = "LOCALAPPDATA"

#: Publisher/game directory name under %LOCALAPPDATA%.
GAME_DIR_NAME = "MistfallHunter"

#: The Unreal "Saved" directory name.
SAVED_DIR_NAME = "Saved"

#: Unreal log directory name.
LOGS_DIR_NAME = "Logs"

#: The live-appended game log.
LOG_FILE_NAME = "MistfallHunter.log"

#: Unreal savegame directory name.
SAVE_GAMES_DIR_NAME = "SaveGames"

#: Unreal config directory name.
CONFIG_DIR_NAME = "Config"

#: Platform-flavoured config subdirectory used by a packaged UE5 Windows client.
#: UNVERIFIED against a live install - see :func:`avg_price_ini`.
CONFIG_PLATFORM_DIR_NAME = "WindowsClient"

#: Market average-price ini written alongside the other client config.
AVG_PRICE_INI_NAME = "AvgPrice.ini"

__all__ = [
    "AVG_PRICE_INI_NAME",
    "CONFIG_DIR_NAME",
    "CONFIG_PLATFORM_DIR_NAME",
    "ENV_LOCAL_APP_DATA",
    "ENV_SAVED_DIR",
    "GAME_DIR_NAME",
    "LOGS_DIR_NAME",
    "LOG_FILE_NAME",
    "SAVED_DIR_NAME",
    "SAVE_GAMES_DIR_NAME",
    "avg_price_ini",
    "config_dir",
    "find_avg_price_ini",
    "game_dir",
    "local_app_data",
    "log_file",
    "logs_dir",
    "save_games_dir",
    "saved_dir",
]

_Env = Mapping[str, str]


def _env(env: _Env | None) -> _Env:
    return os.environ if env is None else env


def local_app_data(env: _Env | None = None) -> Path:
    """Return the per-user local app data root.

    Uses ``%LOCALAPPDATA%`` when set. When it is not set - which is the normal
    case on Linux and macOS CI - falls back to ``~/AppData/Local`` so that the
    rest of the module still produces a deterministic, comparable path instead
    of raising. The fallback is a placeholder, not a claim that the game runs
    there.
    """
    raw = _env(env).get(ENV_LOCAL_APP_DATA, "")
    if raw:
        return Path(raw)
    return Path.home() / "AppData" / "Local"


def game_dir(env: _Env | None = None) -> Path:
    """Return ``%LOCALAPPDATA%/MistfallHunter``.

    Note that when ``LH_SAVED_DIR`` is set this is the *parent* of the
    overridden Saved directory, which need not be named ``MistfallHunter``.
    """
    override = _env(env).get(ENV_SAVED_DIR, "")
    if override:
        return Path(override).parent
    return local_app_data(env) / GAME_DIR_NAME


def saved_dir(env: _Env | None = None) -> Path:
    """Return the ``Saved`` directory, honouring the ``LH_SAVED_DIR`` override."""
    override = _env(env).get(ENV_SAVED_DIR, "")
    if override:
        return Path(override)
    return local_app_data(env) / GAME_DIR_NAME / SAVED_DIR_NAME


def logs_dir(env: _Env | None = None) -> Path:
    """Return ``<Saved>/Logs``."""
    return saved_dir(env) / LOGS_DIR_NAME


def log_file(env: _Env | None = None) -> Path:
    """Return ``<Saved>/Logs/MistfallHunter.log``.

    The game appends to this file while it runs, so a reader must tolerate a
    partial trailing line.
    """
    return logs_dir(env) / LOG_FILE_NAME


def save_games_dir(env: _Env | None = None) -> Path:
    """Return ``<Saved>/SaveGames``."""
    return saved_dir(env) / SAVE_GAMES_DIR_NAME


def config_dir(env: _Env | None = None) -> Path:
    """Return ``<Saved>/Config``."""
    return saved_dir(env) / CONFIG_DIR_NAME


def avg_price_ini(env: _Env | None = None) -> Path:
    """Return the expected path of ``AvgPrice.ini``.

    The filename is known. The subdirectory is the stock UE5 packaged-client
    location, ``<Saved>/Config/WindowsClient``, and is **UNVERIFIED** against a
    live Mistfall Hunter install as of 2026-08-09. If a caller needs the real
    location rather than the expected one, use :func:`find_avg_price_ini`,
    which searches the tree instead of assuming.
    """
    return config_dir(env) / CONFIG_PLATFORM_DIR_NAME / AVG_PRICE_INI_NAME


def find_avg_price_ini(env: _Env | None = None) -> Path | None:
    """Search the Saved tree for ``AvgPrice.ini`` and return the first hit.

    This is the only function in the module that touches the filesystem, and
    it does so only when called. Returns ``None`` when the Saved tree is absent
    or the file is not present anywhere under it.
    """
    root = saved_dir(env)
    try:
        if not root.is_dir():
            return None
        for candidate in sorted(root.rglob(AVG_PRICE_INI_NAME)):
            if candidate.is_file():
                return candidate
    except OSError:
        return None
    return None
