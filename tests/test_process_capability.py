"""Capability ALLOWLIST over the two modules that can hold a process handle.

ROADMAP ``OPS-16``, opened by the refutation pass of ledger ``LL-0122`` and
widened by a second refutation pass over this file's own first version, which
found eleven laundering spellings it let through while its docstring claimed
otherwise. See THE SECOND BUG below.

WHY THIS EXISTS. ``tests/test_loop_watch.py`` already carries
``test_watch_exposes_no_termination_path``. It collects call NAMES out of the
AST and forbids a set of them. A DENYLIST of names reads as exhaustive and is
not, and ``OPS-16`` names three spellings it cannot see:

1. ``subprocess.run(["taskkill", "/F", "/PID", pid])``, and the same through
   ``Popen``. ``taskkill`` is banned as a call NAME, so the same word as a
   STRING IN AN ARGUMENT LIST sails past - and ``Popen`` cannot simply be
   banned, because the module's own detached spawn needs it and an anchor
   assertion in that very test requires it to be present.
2. ``getattr(kernel32, "Open" + "Process")``, and any dynamically assembled
   attribute name. This defeats every name-based AST check BY CONSTRUCTION.
3. ``ntdll.NtSuspendProcess`` and the other undocumented NT entry points, none
   of which appear in the forbidden set.

THE BUG THIS IS WRITTEN AGAINST, and the reason nothing below is a denylist.
``OPS-13`` shipped a source-register checker that filtered bare domains through
a HARDCODED TLD ALLOWLIST. ``.gl`` was not in it, so ``th.gl`` was cited twice
in ``docs/ECOSYSTEM.md``, was invisible to the check, and the check reported a
confident "62 of 62, 0 missing" while a cited source was absent. Widening a
DENY list one string at a time is that same defect wearing the other hat: both
are enumerated lists that read as complete and are not. So this file asks the
opposite question. Not "is this call one of the bad ones", but "is every
capability these modules reach for on a list a human vetted".

THE SECOND BUG, and the reason every sentence below has a test above it. This
file's FIRST version shipped with eleven undeclared holes and, worse, a
docstring that ASSERTED coverage it did not have. It claimed a literal-name
``getattr`` "cannot launder an entry point the attribute form would have
failed on" and named ``os.system``, ``os.killpg`` and ``os.abort`` as caught
through that path. Both claims were false and each fell to one command:
``getattr(os, "system")("taskkill /F /PID 1")`` scanned CLEAN while the same
call spelled ``os.system(...)`` was correctly refused. One design decision
caused all eleven - library handles were tracked in a set of NAMES, and a
literal-name ``getattr`` was routed through the Win32 allowlist only when its
target was a Name in that set, so ``os``, ``subprocess``, ``ctypes``, an
aliased handle and every name a from-import introduced laundered whatever they
were asked to reach. ``OPS-16``'s acceptance asks for the blindness to be
stated in the ARTIFACT; a guard that MIS-states its coverage is worse than one
that merely reads as exhaustive.

HOW IT WORKS. :func:`scan_source` parses one module with ``ast``, builds a
SYMBOL TABLE out of the module's own bindings, and reports a
:class:`Violation` for anything it can reach that is not on a vetted set.

The symbol table maps a bound NAME - dotted, so ``self.k32`` is one name - to
what it refers to: the ``os`` module, the ``subprocess`` module, ``ctypes``, a
ctypes LOADER, a ctypes loader NAMESPACE, a loaded library HANDLE, or one
named attribute of ``os`` or ``subprocess``. It is populated from ``import``
and ``from X import Y`` with or without an alias, from plain assignment and
tuple unpacking, and from ``with ... as`` and ``for ... in`` over a literal
container. It is flow-insensitive and iterated to a fixed point, so
``alias = kernel32`` binds a handle wherever the two statements sit relative to
each other. EVERY access is then routed through the same checks, whether it is
spelled as an attribute (``os.system``), as a literal-name ``getattr``
(``getattr(os, "system")``), or as a bare name a from-import introduced
(``system(...)`` after ``from os import system``):

* :data:`ALLOWED_LIBRARIES` - every ``WinDLL`` / ``CDLL`` / ``OleDLL`` /
  ``PyDLL`` / ``LoadLibrary`` load, every ``windll.<lib>`` / ``cdll.<lib>``
  namespace reach, and every ``LibraryLoader`` namespace, must name a vetted
  library. This is what catches ``ntdll``.
* :data:`ALLOWED_WIN32_FUNCTIONS` - every function reached on a loaded library
  handle. ``kernel32.OpenProcess.restype`` is an attribute ON the function
  rather than a second function, so the chain is split: the first segment is
  the entry point and the rest must be in
  :data:`ALLOWED_WIN32_FUNCTION_ATTRS`.
* :data:`ALLOWED_OS_ATTRS` - every attribute reached on the ``os`` module,
  whether ``os`` arrives as ``import os``, ``import os as o``, or through the
  attribute name in a ``from os import ...``, which is refused at the IMPORT
  because that is where the capability is acquired. Without this,
  ``os.killpg``, ``os.system`` and ``os.abort`` would each be a fourth blind
  spelling, reachable because ``os`` is a legitimate import.
* ``os.kill`` is permitted ONLY with a literal ``0`` as its second argument.
  Signal 0 is different in kind from every other signal: it asks the kernel
  whether the pid exists and delivers NOTHING. ``os.kill(pid, 9)`` is a
  termination path spelled with the same four letters, and a signal passed as
  a name or an expression cannot be read statically, so it is refused.
* Dynamic attribute access - ``eval``, ``exec``, ``__import__`` and
  ``import_module`` are banned outright, including under a from-import alias:
  their presence is the violation and there is no safe spelling. ``getattr``
  and ``setattr`` are constrained to a STRING LITERAL attribute name, and the
  TARGET is then resolved through the symbol table and the literal put through
  whichever allowlist that target answers to. ``vars()`` on a tracked name is
  refused, because a mapping lookup assembles the name at run time.
  **Not banning ``getattr`` outright is the one place this file deviates from
  the ``OPS-16`` slice brief.** It cannot: HEAD's ``ops/loop/watch.py`` calls
  ``getattr(plan, "name", None)`` and ``getattr(plan, "poll_seconds", None)``
  in ``_plan_poll_intervals``, this item is forbidden from changing production
  code, and a guard that fails on the shipped tree is not a guard. A
  literal-name ``getattr`` on a target the table resolves is exactly as
  readable as the attribute form; a COMPUTED name, and a literal name on a
  target the table cannot resolve, are the cases static analysis cannot read.
  The first is refused. The second is ALLOWED, and it is what ``plan`` is -
  see the blind list below, because that is the price of not banning it.
* :data:`ALLOWED_ARGV0` - every ``subprocess`` spawn must be handed a LIST
  LITERAL whose first element is ``sys.executable``. That admits the one
  legitimate detached spawn and refuses ``["taskkill", ...]``,
  ``["powershell", ...]`` and ``["wmic", ...]`` WITHOUT enumerating any of
  them. A non-literal argv, a missing positional argv, an EMPTY argv, or
  ``shell=`` anything other than a literal ``False`` also fails - a static
  check cannot see through those, and the rule is REFUSE WHAT YOU CANNOT READ,
  never assume it is safe. The ``executable=`` keyword is refused OUTRIGHT: it
  names the program to run and overrides argv[0] entirely, so the argv
  allowlist is worthless while a caller may pass it, and nothing in this repo
  has a use for it.
* :data:`ALLOWED_IMPORTS` - the modules imported at module scope AND inside
  function bodies. This is what stops ``import psutil`` or a fresh
  ``import signal`` arriving unnoticed.
* A tracked name REBOUND by an expression the table cannot read is refused
  unread. ``kernel32 = supplied`` after ``kernel32 = ctypes.WinDLL(...)``
  means every later ``kernel32.X`` is a claim this file cannot make, so it
  makes none and reports the rebinding instead.

WHAT THIS GUARD IS BLIND TO. Stated here, in the artifact, because a caveat
that lives only in a chat log or a commit message is a lie in the artifact -
and because the FIRST version of this docstring asserted three coverages it
did not have. Nothing below is claimed without a test above it.

* **It reads SOURCE. It runs nothing.** Every statement it makes is about what
  the text says, never about what the process did.
* **It is scoped to the two files in :data:`SCOPE`.** A call into any OTHER
  module that does the killing is invisible to it. Adding a third module that
  can acquire a handle to another process means adding it to :data:`SCOPE`
  here; nothing detects that omission for you.
* A subprocess that runs a SCRIPT which kills is invisible. The argv allowlist
  proves the interpreter is ours; it proves nothing about what that interpreter
  is asked to run.
* **A literal-name ``getattr`` on a target the symbol table does not resolve
  is allowed.** ``getattr(plan, "name", None)`` is the shape that forces this,
  and ``getattr(anything_untracked, "TerminateProcess")`` rides along with it.
  Banning it needs a production change this item may not make.
* **The symbol table follows only the binding forms listed above.** A tracked
  value that flows through a CALL (``contextlib.nullcontext(kernel32)``), a
  conditional (``k = kernel32 if win else None``), a ``or``/``and``, a
  container element (``handles[0]``), a dict value, a default argument, or a
  RETURN from a helper function is not followed - there is no inter-procedural
  analysis and no scoping, and a name is one name for the whole file.
* A C extension is invisible, and so is ``ctypes`` reaching a function pointer
  through a non-attribute expression - ``loaded["Terminate" + "Process"]``,
  any SUBSCRIPT of a handle, a ``CFUNCTYPE`` cast, ``operator.attrgetter``, or
  a function pointer bound to a name and called later. ``vars()`` is refused
  on a TRACKED name only; ``vars(alias_we_could_not_follow)`` is not.
* A METHOD call on an object this file cannot type - ``child.terminate()`` on a
  ``Popen`` result - is invisible here. That case belongs to the name denylist
  in ``tests/test_loop_watch.py``, which this guard COMPLEMENTS and does not
  replace. Neither is sufficient alone.
* **A ``**kwargs`` splat on a spawn is not read.** ``ops/loop/watch.py`` builds
  its platform flags into an ``extra`` dict and passes ``**extra`` to
  ``Popen``, so ``shell=`` OR ``executable=`` arriving through a splat would
  pass this check. The argv allowlist still holds - argv[0] must be
  ``sys.executable`` - but a splat that carried ``executable=`` would defeat
  even that, which is the sharpest edge on this list.
* Scoping is not modelled, and the error is deliberately toward MORE
  violations: a parameter or local that merely shares a name with a tracked
  module is read as a rebinding of it and refused unread. Neither module in
  :data:`SCOPE` does that today.
* **The vetted sets are the trusted part.** A dangerous entry added to
  :data:`ALLOWED_WIN32_FUNCTIONS`, :data:`ALLOWED_LIBRARIES`,
  :data:`ALLOWED_OS_ATTRS` or :data:`ALLOWED_IMPORTS` is hidden from this check
  exactly the way ``.gl`` was hidden by the old TLD allowlist. Review belongs
  on the SETS, not on the walking logic - exactly as
  ``tests/test_source_register.py`` says of its denylist.
* It says nothing about the RIGHT an ``OpenProcess`` asks for.
  ``PROCESS_QUERY_LIMITED_INFORMATION`` versus ``PROCESS_TERMINATE`` is checked
  separately, in ``tests/test_loop_watch.py``.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

#: The modules in scope: the only two in this repo that can acquire a handle to
#: another process. See "WHAT THIS GUARD IS BLIND TO" - a third such module is
#: unchecked until it is added HERE.
SCOPE = ("ops/loop/guard.py", "ops/loop/watch.py")

# ---------------------------------------------------------------------------
# The vetted sets. THIS is the part that gets reviewed. Every member below was
# read in the shipped modules before it was added; nothing is here on the
# strength of "it is probably fine".
# ---------------------------------------------------------------------------

#: Native libraries these modules may load. ``kernel32`` supplies the whole
#: liveness probe. ``ntdll`` is the one this set exists to refuse.
ALLOWED_LIBRARIES = frozenset({"kernel32"})

#: Win32 entry points reachable on a loaded library handle. Every one of these
#: only ASKS - none can affect the process it names.
ALLOWED_WIN32_FUNCTIONS = frozenset(
    {
        "OpenProcess",
        "GetProcessTimes",
        "GetExitCodeProcess",
        "CloseHandle",
    }
)

#: Attributes set ON a ctypes function object. These configure marshalling and
#: reach no further entry point.
ALLOWED_WIN32_FUNCTION_ATTRS = frozenset({"restype", "argtypes"})

#: Attributes reachable on the ``os`` module. ``kill`` is here only because
#: :func:`_check_kill_signal` constrains it to signal 0; the name alone is not
#: what makes it safe.
ALLOWED_OS_ATTRS = frozenset(
    {
        "O_CREAT",
        "O_EXCL",
        "O_WRONLY",
        "fdopen",
        "fsync",
        "getpid",
        "kill",
        "open",
    }
)

#: Modules these two files may import, at module scope or inside a function.
ALLOWED_IMPORTS = frozenset(
    {
        "__future__",
        "collections.abc",
        "contextlib",
        "ctypes",
        "dataclasses",
        "datetime",
        "json",
        "lanternlight.armwatch",
        "math",
        "ops.loop",
        "os",
        "pathlib",
        "subprocess",
        "sys",
        "tempfile",
    }
)

#: The only permitted ``argv[0]`` for a subprocess spawn, as source text.
ALLOWED_ARGV0 = "sys.executable"

# ---------------------------------------------------------------------------
# Recognisers. These are not allowlists - they are how a construct is SPOTTED
# so an allowlist can be applied to it. Widening one of these widens what is
# CHECKED, never what is permitted.
# ---------------------------------------------------------------------------

#: ctypes library-loader callables.
DLL_LOADERS = frozenset({"WinDLL", "CDLL", "OleDLL", "PyDLL", "LoadLibrary"})

#: ctypes loader NAMESPACES, where the next chain segment is a library name.
DLL_NAMESPACES = frozenset({"windll", "cdll", "oledll", "pydll"})

#: The ctypes helper that MAKES a loader namespace. ``LibraryLoader(WinDLL)``
#: behaves as ``windll`` does, so its result is treated as one.
LIBRARY_LOADER = "LibraryLoader"

#: The one namespace member that is a LOADER rather than a library: in
#: ``cdll.LoadLibrary("ntdll")`` the library is named in the call, not here.
LOAD_LIBRARY = "LoadLibrary"

#: Dynamic access with no safe spelling here: presence is the violation.
BANNED_DYNAMIC = frozenset({"eval", "exec", "__import__", "import_module"})

#: Dynamic access constrained to a string-literal attribute name.
LITERAL_ONLY_DYNAMIC = frozenset({"getattr", "setattr"})

#: Callables that hand back a namespace MAPPING, where the attribute name
#: becomes a dict key and stops being readable statically.
NAMESPACE_OPENERS = frozenset({"vars"})

#: ``subprocess`` callables that start an external program.
SUBPROCESS_SPAWNERS = frozenset(
    {
        "Popen",
        "run",
        "call",
        "check_call",
        "check_output",
        "getoutput",
        "getstatusoutput",
    }
)

# Violation kinds, so a test names what it expects rather than matching prose
# that will be reworded.
KIND_LIBRARY = "library"
KIND_WIN32 = "win32-function"
KIND_OS_ATTR = "os-attribute"
KIND_KILL_SIGNAL = "os-kill-signal"
KIND_DYNAMIC = "dynamic-access"
KIND_ARGV = "subprocess-argv"
KIND_IMPORT = "import"
KIND_REBIND = "unreadable-rebinding"

# ---------------------------------------------------------------------------
# What a bound NAME can refer to. These are the symbol table's value type -
# not an allowlist, not a denylist, just the vocabulary the walker needs so
# that ``os``, ``o``, ``getattr(os, ...)`` and ``from os import ...`` all end
# up at the same check.
# ---------------------------------------------------------------------------

REF_OS = "os-module"
REF_SUBPROCESS = "subprocess-module"
REF_CTYPES = "ctypes-module"
REF_LOADER = "ctypes-loader"
REF_NAMESPACE = "ctypes-loader-namespace"
REF_HANDLE = "library-handle"
REF_OS_ATTR = "os-attribute-ref"
REF_SUBPROCESS_ATTR = "subprocess-attribute-ref"
REF_BANNED = "banned-dynamic-ref"


class _Ref(NamedTuple):
    """One thing a name can refer to: a kind, and the name of the thing."""

    kind: str
    name: str


#: Top-level modules worth tracking by name.
_MODULE_REFS = {
    "os": _Ref(REF_OS, "os"),
    "subprocess": _Ref(REF_SUBPROCESS, "subprocess"),
    "ctypes": _Ref(REF_CTYPES, "ctypes"),
}

#: Fixed-point bound for binding propagation. ``a = b`` chains in real source
#: are one or two links deep; six passes is slack, and the bound exists only
#: so a pathological file cannot spin.
_BINDING_PASSES = 6


@dataclass(frozen=True)
class Violation:
    """One capability a scanned module reaches for that is not vetted."""

    kind: str
    detail: str
    lineno: int

    def __str__(self) -> str:
        return f"line {self.lineno}: [{self.kind}] {self.detail}"


def _attr_chain(node: ast.expr) -> tuple[ast.expr, list[str]]:
    """Peel an attribute chain, returning its base expression and the names.

    ``kernel32.OpenProcess.restype`` yields ``(Name('kernel32'),
    ['OpenProcess', 'restype'])``. Splitting the chain this way is what keeps
    ``.restype`` from being mis-flagged as a second Win32 entry point.
    """
    parts: list[str] = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    parts.reverse()
    return cur, parts


def _terminal_name(func: ast.expr) -> str | None:
    """Return the last name in a callable expression, or ``None``."""
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _normalise_library(raw: str) -> str:
    """Fold ``KERNEL32.DLL`` and ``C:/windows/kernel32.dll`` onto ``kernel32``."""
    name = raw.strip().lower().replace("\\", "/").rsplit("/", 1)[-1]
    if name.endswith(".dll"):
        name = name[: -len(".dll")]
    return name


def _namespace_index(chain: list[str]) -> int | None:
    """Return the index of a ctypes loader namespace in ``chain``."""
    for index, part in enumerate(chain):
        if part in DLL_NAMESPACES:
            return index
    return None


def _is_literal_str(node: ast.expr) -> bool:
    """Return True if ``node`` is a plain string literal."""
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def _is_literal_zero(node: ast.expr) -> bool:
    """Return True if ``node`` is the integer literal ``0`` and not ``False``."""
    if not isinstance(node, ast.Constant):
        return False
    value = node.value
    return isinstance(value, int) and not isinstance(value, bool) and value == 0


def _imported_modules(tree: ast.AST) -> list[tuple[str, int]]:
    """Return every module name imported anywhere in ``tree``, with its line."""
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((alias.name, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            prefix = "." * (node.level or 0)
            found.append((prefix + (node.module or ""), node.lineno))
    return found


def _dotted_name(node: ast.expr) -> str | None:
    """Return ``a.b.c`` for a pure Name/Attribute chain, else ``None``.

    Dotted keys are what let ``self.k32 = ctypes.WinDLL(...)`` bind a handle.
    A chain rooted at anything but a Name - a call, a subscript - has no
    stable name to key on and is not tracked. See the blind list.
    """
    parts: list[str] = []
    cur: ast.expr = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if not isinstance(cur, ast.Name):
        return None
    parts.append(cur.id)
    parts.reverse()
    return ".".join(parts)


def _target_names(target: ast.expr) -> list[str]:
    """Return every dotted name one assignment target binds."""
    if isinstance(target, ast.Tuple | ast.List):
        names: list[str] = []
        for element in target.elts:
            names.extend(_target_names(element))
        return names
    if isinstance(target, ast.Starred):
        return _target_names(target.value)
    dotted = _dotted_name(target)
    return [dotted] if dotted is not None else []


def _binding_sites(tree: ast.AST) -> list[tuple[str, ast.expr | None, int]]:
    """Return every ``(name, value expression or None, line)`` binding.

    ``None`` for the value means "bound by something this file does not
    model" - a parameter, an ``except ... as``, an augmented assignment, a
    loop over an expression rather than a literal container. That is not a
    violation on its own; it becomes one only when the name is ALSO bound to a
    capability somewhere else, which is the ``kernel32 = supplied`` case.
    """
    sites: list[tuple[str, ast.expr | None, int]] = []

    def bind(target: ast.expr, value: ast.expr | None, lineno: int) -> None:
        if (
            isinstance(target, ast.Tuple | ast.List)
            and isinstance(value, ast.Tuple | ast.List)
            and len(target.elts) == len(value.elts)
        ):
            for one_target, one_value in zip(target.elts, value.elts, strict=True):
                bind(one_target, one_value, lineno)
            return
        for name in _target_names(target):
            sites.append((name, value, lineno))

    def bind_iteration(target: ast.expr, iterable: ast.expr, lineno: int) -> None:
        if isinstance(iterable, ast.Tuple | ast.List | ast.Set):
            if not iterable.elts:
                bind(target, None, lineno)
            for element in iterable.elts:
                bind(target, element, lineno)
            return
        bind(target, None, lineno)

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                bind(target, node.value, node.lineno)
        elif isinstance(node, ast.AnnAssign):
            bind(node.target, node.value, node.lineno)
        elif isinstance(node, ast.AugAssign):
            bind(node.target, None, node.lineno)
        elif isinstance(node, ast.NamedExpr):
            bind(node.target, node.value, node.lineno)
        elif isinstance(node, ast.With | ast.AsyncWith):
            for item in node.items:
                if item.optional_vars is not None:
                    bind(item.optional_vars, item.context_expr, node.lineno)
        elif isinstance(node, ast.For | ast.AsyncFor):
            bind_iteration(node.target, node.iter, node.lineno)
        elif isinstance(node, ast.comprehension):
            bind_iteration(node.target, node.iter, getattr(node.target, "lineno", 0))
        elif isinstance(node, ast.ExceptHandler) and node.name:
            sites.append((node.name, None, node.lineno))
        elif isinstance(node, ast.arguments):
            every = [
                *node.posonlyargs,
                *node.args,
                *node.kwonlyargs,
                node.vararg,
                node.kwarg,
            ]
            sites.extend((arg.arg, None, arg.lineno) for arg in every if arg is not None)
    return sites


def _from_import_ref(module: str | None, name: str) -> _Ref | None:
    """Return what ``from <module> import <name>`` binds, if anything."""
    if name in BANNED_DYNAMIC:
        return _Ref(REF_BANNED, name)
    if module == "os":
        return _Ref(REF_OS_ATTR, name)
    if module == "subprocess":
        return _Ref(REF_SUBPROCESS_ATTR, name)
    if module == "ctypes":
        if name in DLL_LOADERS:
            return _Ref(REF_LOADER, name)
        if name in DLL_NAMESPACES:
            return _Ref(REF_NAMESPACE, name)
    return None


def _import_refs(node: ast.AST) -> list[tuple[str, _Ref | None, int]]:
    """Return the ``(local name, ref or None, line)`` an import statement binds."""
    out: list[tuple[str, _Ref | None, int]] = []
    if isinstance(node, ast.Import):
        for alias in node.names:
            if alias.asname:
                out.append((alias.asname, _MODULE_REFS.get(alias.name), node.lineno))
            else:
                # ``import ctypes.wintypes`` binds ``ctypes``, not the submodule.
                head = alias.name.split(".")[0]
                out.append((head, _MODULE_REFS.get(head), node.lineno))
    elif isinstance(node, ast.ImportFrom):
        for alias in node.names:
            local = alias.asname or alias.name
            out.append((local, _from_import_ref(node.module, alias.name), node.lineno))
    return out


class _Scanner(ast.NodeVisitor):
    """Walk one parsed module and record every unvetted capability.

    The visitor overrides :meth:`visit_Attribute` so an attribute CHAIN is
    resolved once, at its outermost node, and the inner nodes are not visited
    again. Without that, ``kernel32.OpenProcess.restype`` would be reported
    twice and ``restype`` would be read as an entry point.

    :attr:`symbols` is the whole of the widening described in the module
    docstring: one dotted name to the set of things it can refer to. Every
    check below asks the table what it is looking at rather than pattern
    matching the spelling in front of it.
    """

    def __init__(self, tree: ast.AST) -> None:
        self.violations: list[Violation] = []
        self.seen: dict[str, set[str]] = {
            "libraries": set(),
            "win32": set(),
            "os": set(),
            "dynamic": set(),
            "subprocess": set(),
            "imports": set(),
            "tracked": set(),
        }
        self.symbols: dict[str, set[_Ref]] = {}
        self.unreadable: dict[str, int] = {}
        self._collect_bindings(tree)
        self.seen["tracked"] = set(self.symbols)
        self._flag_unreadable_rebindings()
        self._check_from_imports(tree)

    # -- pre-pass ----------------------------------------------------------

    def _collect_bindings(self, tree: ast.AST) -> None:
        """Build the symbol table, then record what it could not read.

        Flow-insensitive and deliberately so: a handle assigned in one function
        and used in another is still a handle, and this guard would rather
        over-attribute a name than lose one. Iterated to a fixed point because
        ``alias = kernel32`` needs ``kernel32`` known first, and nothing
        guarantees the two statements arrive in that order.
        """
        imports: list[tuple[str, _Ref | None, int]] = []
        for node in ast.walk(tree):
            imports.extend(_import_refs(node))
        for name, ref, _lineno in imports:
            if ref is not None:
                self.symbols.setdefault(name, set()).add(ref)

        sites = _binding_sites(tree)
        for _pass in range(_BINDING_PASSES):
            changed = False
            for name, value, _lineno in sites:
                refs = self._classify(value)
                if refs and not refs <= self.symbols.get(name, set()):
                    self.symbols.setdefault(name, set()).update(refs)
                    changed = True
            if not changed:
                break

        # Only now, with the table stable, is "this binding is unreadable" a
        # statement worth making: a site read as unreadable on pass one may be
        # perfectly readable once the name it copies from is known.
        for name, value, lineno in [*sites, *((n, None, ln) for n, r, ln in imports if r is None)]:
            if name in self.symbols and not self._classify(value):
                self.unreadable[name] = min(self.unreadable.get(name, lineno), lineno)

    def _flag_unreadable_rebindings(self) -> None:
        """Refuse a tracked name that is also bound by something unreadable."""
        for name in sorted(self.unreadable):
            kinds = sorted({ref.kind for ref in self.symbols[name]})
            self._flag_at(
                KIND_REBIND,
                f"{name} is bound elsewhere to {' and '.join(kinds)} and is also "
                f"rebound by an expression this check cannot read, so nothing it "
                f"reaches for afterwards can be judged; refused unread",
                self.unreadable[name],
            )

    def _check_from_imports(self, tree: ast.AST) -> None:
        """Refuse ``from os import <not vetted>`` where the name is BOUND.

        The import IS the acquisition. Checking here rather than at the call
        site is what makes ``from os import system`` fail even in a module
        that never calls it, and it is what closes the spelling
        ``system(...)`` with no ``os.`` in front of it anywhere.
        """
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.module != "os":
                continue
            for alias in node.names:
                self._check_os_attr(alias.name, node)

    # -- symbol table ------------------------------------------------------

    def _classify(self, value: ast.expr | None) -> set[_Ref]:
        """Return what an expression evaluates to, as far as this file can tell."""
        if value is None:
            return set()
        return self._resolve_expr_refs(value)

    def _resolve_expr_refs(self, expr: ast.expr) -> set[_Ref]:
        """Resolve any expression to the set of things it can refer to."""
        if isinstance(expr, ast.Call):
            return self._call_result_refs(expr)
        resolved = self._resolve_prefix(expr)
        if resolved is None:
            return set()
        refs, rest = resolved
        return self._walk_rest(refs, rest)

    def _resolve_prefix(self, expr: ast.expr) -> tuple[set[_Ref], list[str]] | None:
        """Match the LONGEST tracked dotted prefix of ``expr``.

        ``self.k32.TerminateProcess`` matches ``self.k32`` and leaves
        ``['TerminateProcess']``; ``ctypes.windll.ntdll.X`` matches ``ctypes``
        and leaves the rest for :meth:`_step` to walk.
        """
        if not isinstance(expr, ast.Name | ast.Attribute):
            return None
        base, chain = _attr_chain(expr)
        if not isinstance(base, ast.Name):
            return None
        parts = [base.id, *chain]
        for cut in range(len(parts), 0, -1):
            refs = self.symbols.get(".".join(parts[:cut]))
            if refs:
                return set(refs), parts[cut:]
        return None

    def _step(self, refs: set[_Ref], attribute: str) -> set[_Ref]:
        """Take one attribute step from every ref in ``refs``."""
        out: set[_Ref] = set()
        for ref in refs:
            if ref.kind == REF_CTYPES:
                if attribute in DLL_NAMESPACES:
                    out.add(_Ref(REF_NAMESPACE, attribute))
                elif attribute in DLL_LOADERS:
                    out.add(_Ref(REF_LOADER, attribute))
            elif ref.kind == REF_NAMESPACE:
                out.add(_Ref(REF_HANDLE, attribute))
            elif ref.kind == REF_OS:
                out.add(_Ref(REF_OS_ATTR, attribute))
            elif ref.kind == REF_SUBPROCESS:
                out.add(_Ref(REF_SUBPROCESS_ATTR, attribute))
        return out

    def _walk_rest(self, refs: set[_Ref], rest: list[str]) -> set[_Ref]:
        """Apply every attribute in ``rest``, in order."""
        current = refs
        for attribute in rest:
            current = self._step(current, attribute)
            if not current:
                break
        return current

    def _call_result_refs(self, call: ast.Call) -> set[_Ref]:
        """Return what a CALL evaluates to - a handle, a namespace, or nothing."""
        loader = self._resolve_loader(call.func)
        if loader is not None:
            first = call.args[0] if call.args else None
            library = (
                _normalise_library(first.value)
                if first is not None and _is_literal_str(first)
                else loader
            )
            return {_Ref(REF_HANDLE, library)}
        terminal = _terminal_name(call.func)
        if terminal == LIBRARY_LOADER:
            return {_Ref(REF_NAMESPACE, LIBRARY_LOADER)}
        if (
            terminal in LITERAL_ONLY_DYNAMIC
            and len(call.args) >= 2
            and _is_literal_str(call.args[1])
        ):
            return self._step(self._resolve_expr_refs(call.args[0]), call.args[1].value)
        return set()

    def _resolve_loader(self, func: ast.expr) -> str | None:
        """Return the loader a callable expression names, or ``None``."""
        for ref in self._resolve_expr_refs(func):
            if ref.kind == REF_LOADER:
                return ref.name
        terminal = _terminal_name(func)
        if terminal in DLL_LOADERS:
            return terminal
        return None

    # -- reporting ---------------------------------------------------------

    def _flag(self, kind: str, detail: str, node: ast.AST) -> None:
        self._flag_at(kind, detail, getattr(node, "lineno", 0))

    def _flag_at(self, kind: str, detail: str, lineno: int) -> None:
        self.violations.append(Violation(kind, detail, lineno))

    # -- checks ------------------------------------------------------------

    def _check_library_name(self, raw: str, node: ast.AST) -> None:
        name = _normalise_library(raw)
        self.seen["libraries"].add(name)
        if name not in ALLOWED_LIBRARIES:
            self._flag(
                KIND_LIBRARY,
                f"loads library {name!r}, which is not in ALLOWED_LIBRARIES "
                f"{sorted(ALLOWED_LIBRARIES)}",
                node,
            )

    def _check_win32(self, parts: list[str], node: ast.AST) -> None:
        if not parts:
            return
        entry = parts[0]
        self.seen["win32"].add(entry)
        if entry not in ALLOWED_WIN32_FUNCTIONS:
            self._flag(
                KIND_WIN32,
                f"reaches Win32 entry point {entry!r} on a loaded library handle, "
                f"which is not in ALLOWED_WIN32_FUNCTIONS "
                f"{sorted(ALLOWED_WIN32_FUNCTIONS)}",
                node,
            )
        for attr in parts[1:]:
            if attr not in ALLOWED_WIN32_FUNCTION_ATTRS:
                self._flag(
                    KIND_WIN32,
                    f"sets {entry}.{attr}, which is not in "
                    f"ALLOWED_WIN32_FUNCTION_ATTRS "
                    f"{sorted(ALLOWED_WIN32_FUNCTION_ATTRS)}",
                    node,
                )

    def _check_os_attr(self, attr: str, node: ast.AST) -> None:
        self.seen["os"].add(attr)
        if attr not in ALLOWED_OS_ATTRS:
            self._flag(
                KIND_OS_ATTR,
                f"reaches os.{attr}, which is not in ALLOWED_OS_ATTRS "
                f"{sorted(ALLOWED_OS_ATTRS)}",
                node,
            )

    def _check_kill_signal(self, node: ast.Call) -> None:
        """``os.kill`` is permitted ONLY with a literal ``0``.

        Signal 0 delivers nothing - it asks whether the pid exists. Every other
        signal, and every signal this checker cannot read, is a termination
        path spelled with the same four letters.
        """
        if len(node.args) != 2 or any(isinstance(arg, ast.Starred) for arg in node.args):
            self._flag(
                KIND_KILL_SIGNAL,
                "os.kill(...) call shape is unreadable; refused unread",
                node,
            )
            return
        signal_arg = node.args[1]
        if _is_literal_zero(signal_arg):
            return
        self._flag(
            KIND_KILL_SIGNAL,
            f"os.kill(..., {ast.unparse(signal_arg)}) - permitted only with a "
            f"literal 0, which delivers no signal and only asks whether the pid "
            f"exists",
            node,
        )

    def _check_loader_args(self, node: ast.Call, terminal: str) -> None:
        if not node.args or isinstance(node.args[0], ast.Starred):
            self._flag(
                KIND_LIBRARY,
                f"{terminal}(...) names no readable library; refused unread",
                node,
            )
            return
        arg = node.args[0]
        if not _is_literal_str(arg):
            self._flag(
                KIND_LIBRARY,
                f"{terminal}({ast.unparse(arg)}) - the library name is not a "
                f"string literal, so it cannot be read; refused unread",
                node,
            )
            return
        self._check_library_name(arg.value, node)

    def _check_dynamic_literal(self, node: ast.Call, terminal: str) -> None:
        self.seen["dynamic"].add(terminal)
        if len(node.args) < 2 or any(isinstance(arg, ast.Starred) for arg in node.args):
            self._flag(
                KIND_DYNAMIC,
                f"{terminal}(...) argument list is unreadable; refused unread",
                node,
            )
            return
        name_arg = node.args[1]
        if not _is_literal_str(name_arg):
            self._flag(
                KIND_DYNAMIC,
                f"{terminal}(..., {ast.unparse(name_arg)}) assembles an attribute "
                f"name at run time, which defeats every static check by "
                f"construction",
                node,
            )
            return
        # A literal name is as readable as the attribute form, so put it
        # through whatever allowlist the TARGET answers to. This is the hole
        # the first version's docstring claimed was closed and was not.
        attribute = name_arg.value
        for ref in self._resolve_expr_refs(node.args[0]):
            if ref.kind == REF_HANDLE:
                self._check_win32([attribute], node)
            elif ref.kind == REF_OS:
                self._check_os_attr(attribute, node)
            elif ref.kind == REF_NAMESPACE:
                self._check_library_name(attribute, node)

    def _check_namespace_opener(self, node: ast.Call, terminal: str) -> None:
        """``vars(os)`` turns attribute access into a mapping lookup."""
        if not node.args:
            return
        target = node.args[0]
        if not self._resolve_expr_refs(target):
            return
        self.seen["dynamic"].add(terminal)
        self._flag(
            KIND_DYNAMIC,
            f"{terminal}({ast.unparse(target)}) opens a tracked namespace as a "
            f"mapping, and a mapping key is assembled at run time, which defeats "
            f"every static check by construction",
            node,
        )

    def _check_argv(self, node: ast.Call, terminal: str) -> None:
        for keyword in node.keywords:
            if keyword.arg == "executable":
                self._flag(
                    KIND_ARGV,
                    f"{terminal}(..., executable={ast.unparse(keyword.value)}) - "
                    f"executable= names the program to run and overrides argv[0] "
                    f"entirely, so the argv allowlist is worthless beside it; "
                    f"nothing in this repo has a use for it",
                    node,
                )
            if keyword.arg != "shell":
                continue
            value = keyword.value
            if not (isinstance(value, ast.Constant) and value.value is False):
                self._flag(
                    KIND_ARGV,
                    f"{terminal}(..., shell={ast.unparse(value)}) - a shell hides "
                    f"the real argv from this check; only a literal False passes",
                    node,
                )
        if not node.args or isinstance(node.args[0], ast.Starred):
            self._flag(
                KIND_ARGV,
                f"{terminal}(...) has no readable positional argv; refused unread",
                node,
            )
            return
        argv = node.args[0]
        if not isinstance(argv, ast.List | ast.Tuple):
            self._flag(
                KIND_ARGV,
                f"{terminal}({ast.unparse(argv)}) - argv is not a list literal, so "
                f"this check cannot read it; refused unread",
                node,
            )
            return
        if not argv.elts:
            self._flag(KIND_ARGV, f"{terminal}([]) - empty argv is unreadable", node)
            return
        first = argv.elts[0]
        rendered = ast.unparse(first)
        if rendered != ALLOWED_ARGV0:
            self._flag(
                KIND_ARGV,
                f"{terminal} argv[0] is {rendered}, but the only permitted "
                f"argv[0] is {ALLOWED_ARGV0} - an external program is not a "
                f"capability these modules have",
                node,
            )

    # -- dispatch ----------------------------------------------------------

    def _os_attrs_of(self, func: ast.expr) -> set[str]:
        """Return every ``os`` attribute a callable expression can name."""
        return {
            ref.name
            for ref in self._resolve_expr_refs(func)
            if ref.kind == REF_OS_ATTR
        }

    def _is_subprocess_spawn(self, func: ast.expr) -> str | None:
        """Return the spawner name if ``func`` starts an external program."""
        for ref in self._resolve_expr_refs(func):
            if ref.kind == REF_SUBPROCESS_ATTR and ref.name in SUBPROCESS_SPAWNERS:
                return ref.name
        return None

    def _banned_dynamic_of(self, func: ast.expr, terminal: str | None) -> str | None:
        """Return the banned callable this expression reaches, or ``None``."""
        if terminal in BANNED_DYNAMIC:
            return terminal
        for ref in self._resolve_expr_refs(func):
            if ref.kind == REF_BANNED:
                return ref.name
        return None

    # ``visit_Call`` and ``visit_Attribute`` are ast.NodeVisitor's own naming
    # convention, not this project's.
    def visit_Call(self, node: ast.Call) -> None:
        terminal = _terminal_name(node.func)

        loader = self._resolve_loader(node.func)
        if loader is not None:
            self._check_loader_args(node, loader)

        banned = self._banned_dynamic_of(node.func, terminal)
        if banned is not None:
            self.seen["dynamic"].add(banned)
            spelling = "" if banned == terminal else f" (spelled here as {terminal})"
            self._flag(
                KIND_DYNAMIC,
                f"{banned}(...) has no safe spelling in this scope{spelling} - its "
                f"presence is the violation, because it defeats a static check "
                f"by construction",
                node,
            )
        elif terminal in LITERAL_ONLY_DYNAMIC:
            self._check_dynamic_literal(node, terminal)
        elif terminal in NAMESPACE_OPENERS:
            self._check_namespace_opener(node, terminal)

        if "kill" in self._os_attrs_of(node.func):
            self._check_kill_signal(node)

        spawner = self._is_subprocess_spawn(node.func)
        if spawner is not None:
            self.seen["subprocess"].add(spawner)
            self._check_argv(node, spawner)

        self.generic_visit(node)

    def _check_chain(self, refs: set[_Ref], rest: list[str], node: ast.AST) -> None:
        """Apply the capability checks to ``rest`` reached from ``refs``."""
        for ref in refs:
            if ref.kind == REF_HANDLE:
                self._check_win32(rest, node)
            elif ref.kind == REF_OS and rest:
                self._check_os_attr(rest[0], node)
            elif ref.kind == REF_NAMESPACE and rest:
                self._check_namespace_reach(rest, node)
            elif ref.kind == REF_CTYPES and len(rest) > 1 and rest[0] in DLL_NAMESPACES:
                self._check_namespace_reach(rest[1:], node)

    def _check_namespace_reach(self, rest: list[str], node: ast.AST) -> None:
        """``windll.<library>.<entry point>`` - check the library, then the entry.

        ``cdll.LoadLibrary("ntdll")`` names its library in the CALL, so leave
        it to :meth:`_check_loader_args` rather than reading the loader's own
        name as a library.
        """
        if rest[0] == LOAD_LIBRARY:
            return
        self._check_library_name(rest[0], node)
        self._check_win32(rest[1:], node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        base, chain = _attr_chain(node)
        resolved = self._resolve_prefix(node)
        if resolved is not None:
            refs, rest = resolved
            self._check_chain(refs, rest, node)
        elif isinstance(base, ast.Call):
            # ``WinDLL("ntdll").NtSuspendProcess`` - a handle that was never
            # bound to a name, so the prefix walk has nothing to match on.
            self._check_chain(self._call_result_refs(base), chain, node)
        else:
            # An untracked base with a loader namespace somewhere in the chain.
            # Kept as a fallback so a module that reaches ``windll`` without an
            # import this file recognised is still checked.
            namespace = _namespace_index(chain)
            if namespace is not None and chain[namespace + 1 :]:
                self._check_namespace_reach(chain[namespace + 1 :], node)
        # Only the non-attribute base is walked further: the inner Attribute
        # nodes of this chain were consumed above and must not be re-reported.
        self.visit(base)


def scan_source(source: str) -> list[Violation]:
    """Return every unvetted capability :data:`SCOPE`-style source reaches for.

    Args:
        source: Python source text.

    Returns:
        A list of :class:`Violation`, empty when the source reaches only for
        capabilities on the vetted sets above.
    """
    tree = ast.parse(source)
    scanner = _Scanner(tree)
    scanner.visit(tree)
    for module, lineno in _imported_modules(tree):
        scanner.seen["imports"].add(module)
        if module not in ALLOWED_IMPORTS:
            scanner.violations.append(
                Violation(
                    KIND_IMPORT,
                    f"imports {module!r}, which is not in ALLOWED_IMPORTS",
                    lineno,
                )
            )
    # De-duplicated: one construct can now be reached by two routes - the
    # attribute walk and the getattr walk both land on the same entry point -
    # and reporting it twice is noise, not evidence.
    unique = set(scanner.violations)
    return sorted(unique, key=lambda v: (v.lineno, v.kind, v.detail))


def observed_capabilities(source: str) -> dict[str, set[str]]:
    """Return what the scanner SAW, independent of what it judged.

    This exists so the mirror test over the real modules cannot pass
    vacuously. A checker that parsed nothing - wrong path, wrong recogniser,
    a visitor that never fires - reports zero violations, which looks exactly
    like a clean bill of health.
    """
    tree = ast.parse(source)
    scanner = _Scanner(tree)
    scanner.visit(tree)
    scanner.seen["imports"] = {module for module, _ in _imported_modules(tree)}
    return scanner.seen


def _scope_source(relative: str) -> str:
    """Read one in-scope module from disk."""
    return (REPO_ROOT / relative).read_text(encoding="utf-8")


def _kinds(violations: list[Violation]) -> set[str]:
    return {violation.kind for violation in violations}


def _rendered(violations: list[Violation]) -> str:
    return "\n".join(str(violation) for violation in violations)


# ---------------------------------------------------------------------------
# The three spellings ``OPS-16`` names. Each gets its own test, because the
# item's acceptance asks for a test watched going red for each spelling the
# approach claims to catch.
# ---------------------------------------------------------------------------

TASKKILL_THROUGH_SUBPROCESS = '''\
import subprocess
import sys


def stop(pid):
    subprocess.run(["taskkill", "/F", "/PID", str(pid)])
'''

GETATTR_ASSEMBLED_NAME = '''\
import ctypes


def probe(pid):
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    opener = getattr(kernel32, "Open" + "Process")
    return opener(0x0001, False, pid)
'''

NTDLL_SUSPEND = '''\
import ctypes


def freeze(handle):
    ntdll = ctypes.WinDLL("ntdll")
    return ntdll.NtSuspendProcess(handle)
'''


def test_ops16_spelling_1_taskkill_as_a_string_in_an_argv() -> None:
    """``taskkill`` as a STRING, which the name denylist cannot see.

    The old guard forbids ``taskkill`` as a call NAME. Here it is argv[0] of a
    perfectly ordinary ``subprocess.run``, so no forbidden name appears
    anywhere in the AST. The allowlist does not look for it: it requires
    argv[0] to BE ``sys.executable`` and this one is not.
    """
    violations = scan_source(TASKKILL_THROUGH_SUBPROCESS)
    assert KIND_ARGV in _kinds(violations), _rendered(violations)
    assert "'taskkill'" in _rendered(violations)
    assert ALLOWED_ARGV0 in _rendered(violations)


def test_ops16_spelling_2_getattr_with_an_assembled_attribute_name() -> None:
    """A computed attribute name defeats every name-based check by construction.

    ``"Open" + "Process"`` is an ``ast.BinOp``, so no AST node anywhere in this
    module carries the string ``OpenProcess``. The allowlist refuses it for
    being UNREADABLE rather than for being dangerous, which is the only stance
    a static check can honestly take.
    """
    violations = scan_source(GETATTR_ASSEMBLED_NAME)
    assert KIND_DYNAMIC in _kinds(violations), _rendered(violations)
    assert "defeats every static check" in _rendered(violations)


def test_ops16_spelling_3_ntdll_undocumented_entry_point() -> None:
    """``ntdll.NtSuspendProcess`` - absent from any denylist, and always will be.

    Caught twice over, and both are worth having: the LIBRARY is not
    ``kernel32``, and the ENTRY POINT is not one of the four vetted calls. Each
    would have caught it alone.
    """
    violations = scan_source(NTDLL_SUSPEND)
    kinds = _kinds(violations)
    assert KIND_LIBRARY in kinds, _rendered(violations)
    assert KIND_WIN32 in kinds, _rendered(violations)
    assert "'ntdll'" in _rendered(violations)
    assert "'NtSuspendProcess'" in _rendered(violations)


# ---------------------------------------------------------------------------
# The wider table. Every entry is a spelling a human wrote down as something
# these two modules must never grow.
# ---------------------------------------------------------------------------

FORBIDDEN_SPELLINGS: tuple[tuple[str, str, str, str], ...] = (
    (
        "windll-namespace-ntdll",
        "import ctypes\n\n\ndef f(h):\n    return ctypes.windll.ntdll.NtSuspendProcess(h)\n",
        KIND_LIBRARY,
        "'ntdll'",
    ),
    (
        "loadlibrary-ntdll",
        'import ctypes\n\n\ndef f():\n    return ctypes.cdll.LoadLibrary("ntdll.dll")\n',
        KIND_LIBRARY,
        "'ntdll'",
    ),
    (
        "kernel32-terminateprocess",
        'import ctypes\n\n\ndef f(h):\n'
        '    kernel32 = ctypes.WinDLL("kernel32")\n'
        "    return kernel32.TerminateProcess(h, 1)\n",
        KIND_WIN32,
        "'TerminateProcess'",
    ),
    (
        "getattr-literal-launders-terminateprocess",
        'import ctypes\n\n\ndef f(h):\n'
        '    kernel32 = ctypes.WinDLL("kernel32")\n'
        '    return getattr(kernel32, "TerminateProcess")(h, 1)\n',
        KIND_WIN32,
        "'TerminateProcess'",
    ),
    (
        "popen-taskkill",
        'import subprocess\n\n\ndef f(pid):\n'
        '    subprocess.Popen(["taskkill", "/F", "/PID", str(pid)])\n',
        KIND_ARGV,
        "'taskkill'",
    ),
    (
        "popen-taskkill-with-shell",
        'import subprocess\n\n\ndef f():\n'
        '    subprocess.Popen(["taskkill"], shell=True)\n',
        KIND_ARGV,
        "shell=True",
    ),
    (
        "popen-argv-from-a-variable",
        "import subprocess\n\n\ndef f(argv):\n    subprocess.Popen(argv)\n",
        KIND_ARGV,
        "not a list literal",
    ),
    (
        "popen-argv-from-an-fstring",
        'import subprocess\n\n\ndef f(pid):\n'
        '    subprocess.Popen(f"taskkill /F /PID {pid}")\n',
        KIND_ARGV,
        "not a list literal",
    ),
    (
        "run-powershell",
        'import subprocess\n\n\ndef f():\n'
        '    subprocess.run(["powershell", "-Command", "Stop-Process -Id 1"])\n',
        KIND_ARGV,
        "'powershell'",
    ),
    (
        "run-wmic",
        'import subprocess\n\n\ndef f():\n'
        '    subprocess.check_call(["wmic", "process", "delete"])\n',
        KIND_ARGV,
        "'wmic'",
    ),
    (
        "os-kill-sigkill-literal-9",
        "import os\n\n\ndef f(pid):\n    os.kill(pid, 9)\n",
        KIND_KILL_SIGNAL,
        "literal 0",
    ),
    (
        "os-kill-signal-by-name",
        "import os\nimport signal\n\n\ndef f(pid):\n    os.kill(pid, signal.SIGKILL)\n",
        KIND_KILL_SIGNAL,
        "literal 0",
    ),
    (
        "os-kill-signal-from-a-variable",
        "import os\n\n\ndef f(pid, sig):\n    os.kill(pid, sig)\n",
        KIND_KILL_SIGNAL,
        "literal 0",
    ),
    (
        "os-killpg",
        "import os\n\n\ndef f(pgid):\n    os.killpg(pgid, 9)\n",
        KIND_OS_ATTR,
        "os.killpg",
    ),
    (
        "os-system-taskkill",
        'import os\n\n\ndef f(pid):\n    os.system(f"taskkill /F /PID {pid}")\n',
        KIND_OS_ATTR,
        "os.system",
    ),
    (
        # Named in the docstring beside killpg and system, so it needs a test
        # of its own rather than the reader's trust that it behaves the same.
        "os-abort",
        "import os\n\n\ndef f():\n    os.abort()\n",
        KIND_OS_ATTR,
        "os.abort",
    ),
    (
        "import-psutil",
        "import psutil\n\n\ndef f(pid):\n    return psutil.Process(pid)\n",
        KIND_IMPORT,
        "'psutil'",
    ),
    (
        "import-signal",
        "import signal\n\n\ndef f():\n    return signal.SIGTERM\n",
        KIND_IMPORT,
        "'signal'",
    ),
    (
        "importlib-import-module",
        'import importlib\n\n\ndef f():\n    return importlib.import_module("psutil")\n',
        KIND_DYNAMIC,
        "no safe spelling",
    ),
    (
        "dunder-import",
        'def f():\n    return __import__("psutil")\n',
        KIND_DYNAMIC,
        "no safe spelling",
    ),
    (
        "eval",
        'def f(src):\n    return eval(src)\n',
        KIND_DYNAMIC,
        "no safe spelling",
    ),
    (
        "exec",
        'def f(src):\n    exec(src)\n',
        KIND_DYNAMIC,
        "no safe spelling",
    ),
    (
        "windll-from-a-variable-library-name",
        "import ctypes\n\n\ndef f(name):\n    return ctypes.WinDLL(name)\n",
        KIND_LIBRARY,
        "not a string literal",
    ),
    (
        "kernel32-unvetted-function-attribute",
        'import ctypes\n\n\ndef f():\n'
        '    kernel32 = ctypes.WinDLL("kernel32")\n'
        "    kernel32.CloseHandle.errcheck = None\n",
        KIND_WIN32,
        "CloseHandle.errcheck",
    ),
)


@pytest.mark.parametrize(
    ("label", "source", "expected_kind", "expected_fragment"),
    FORBIDDEN_SPELLINGS,
    ids=[entry[0] for entry in FORBIDDEN_SPELLINGS],
)
def test_a_forbidden_spelling_is_caught_and_named(
    label: str, source: str, expected_kind: str, expected_fragment: str
) -> None:
    """Each spelling is refused, and the report NAMES what it refused.

    A guard that merely returns "violation" is unactionable, and worse, it is
    indistinguishable from a guard that has stopped discriminating. Asserting
    the fragment pins the message to the construct.
    """
    violations = scan_source(source)
    rendered = _rendered(violations)
    assert violations, f"{label}: expected a violation, got none"
    assert expected_kind in _kinds(violations), f"{label}: {rendered}"
    assert expected_fragment in rendered, f"{label}: {rendered}"


# ---------------------------------------------------------------------------
# The mirror. Without this, every assertion above would still pass if
# scan_source were replaced by ``return [Violation("x", "x", 0)]`` - and a
# guard that rejects everything is not a guard.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("relative", SCOPE)
def test_the_real_module_reaches_for_nothing_unvetted(relative: str) -> None:
    """The shipped modules produce ZERO violations.

    This is the half that stops the checker from degenerating into "reject
    everything". It is also the half that will break first when a real change
    lands - and when it does, the question to ask is whether the new capability
    belongs on a vetted set, not whether the check should be relaxed.
    """
    violations = scan_source(_scope_source(relative))
    assert violations == [], f"{relative}:\n{_rendered(violations)}"


@pytest.mark.parametrize("relative", SCOPE)
def test_the_scanner_actually_saw_the_module(relative: str) -> None:
    """The zero above is a clean bill, not an empty parse.

    A scanner that walks nothing reports no violations, which reads exactly
    like a module that reaches for nothing. So assert the capabilities the two
    modules DO have were observed: both load ``kernel32`` and both open a
    process handle to ask a question about it.
    """
    seen = observed_capabilities(_scope_source(relative))
    assert "kernel32" in seen["libraries"], seen
    assert "OpenProcess" in seen["win32"], seen
    assert "CloseHandle" in seen["win32"], seen
    assert seen["imports"], seen


def test_the_guard_module_and_the_watch_module_differ_where_expected() -> None:
    """Pin the two inventories apart, so a copy-paste scan is visible.

    If both files were scanned through the same stale path - or if
    :func:`_scope_source` silently read one file twice - these two inventories
    would be identical. They are not: only ``guard`` probes with
    ``GetExitCodeProcess`` and ``os.kill``, and only ``watch`` spawns.
    """
    guard_seen = observed_capabilities(_scope_source("ops/loop/guard.py"))
    watch_seen = observed_capabilities(_scope_source("ops/loop/watch.py"))

    assert "GetExitCodeProcess" in guard_seen["win32"]
    assert "kill" in guard_seen["os"]
    assert guard_seen["subprocess"] == set()

    assert "GetProcessTimes" in watch_seen["win32"]
    assert watch_seen["subprocess"] == {"Popen"}
    assert "subprocess" in watch_seen["imports"]


def test_the_one_permitted_spawn_and_the_one_permitted_signal_still_pass() -> None:
    """The allowlist admits the legitimate constructs, spelled minimally.

    Stated as its own test rather than left implicit in the mirror, because the
    mirror would also pass if the checker only ever tolerated the exact text of
    the two shipped modules.
    """
    spawn = (
        "import subprocess\nimport sys\n\n\ndef f(dest):\n"
        '    subprocess.Popen([sys.executable, "-m", "lanternlight.armwatch", dest])\n'
    )
    probe = "import os\n\n\ndef f(pid):\n    os.kill(pid, 0)\n"
    handle = (
        "import ctypes\n\n\ndef f(pid):\n"
        '    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)\n'
        "    kernel32.OpenProcess.restype = None\n"
        "    kernel32.OpenProcess.argtypes = ()\n"
        "    handle = kernel32.OpenProcess(0x1000, False, pid)\n"
        "    kernel32.CloseHandle(handle)\n"
    )

    for source in (spawn, probe, handle):
        assert scan_source(source) == [], _rendered(scan_source(source))


def test_scope_names_files_that_exist() -> None:
    """A typo in :data:`SCOPE` would silently check nothing at all."""
    for relative in SCOPE:
        path = REPO_ROOT / relative
        assert path.is_file(), f"{path} is in SCOPE but is not a file"
        assert path.read_text(encoding="utf-8").strip(), f"{path} is empty"


def test_a_restype_assignment_is_not_read_as_an_entry_point() -> None:
    """``kernel32.OpenProcess.restype`` is one entry point, not two.

    The nested-``Attribute`` shape is the specific thing that makes a naive
    chain walk mis-flag configuration as a call. Assert the shape is handled
    rather than trusting the mirror to have covered it.
    """
    source = (
        "import ctypes\n\n\ndef f():\n"
        '    kernel32 = ctypes.WinDLL("kernel32")\n'
        "    kernel32.OpenProcess.restype = None\n"
    )
    assert scan_source(source) == []
    seen = observed_capabilities(source)
    assert seen["win32"] == {"OpenProcess"}, seen


# ---------------------------------------------------------------------------
# The LAUNDERED spellings. Every entry below except the two marked inline
# scanned CLEAN under the first version of this file, and each was reproduced
# by hand against a positive control - ``os.system("taskkill /F /PID 1")``
# spelled directly, which was correctly refused. The exceptions are stated
# rather than quietly included, because "all of these were holes" would be the
# same kind of over-claim this file exists to stop.
#
# They share ONE cause: the scanner tracked library handles
# in a set of names and routed a literal-name ``getattr`` through the Win32
# allowlist only when the target was a Name in that set. Everything else -
# ``os``, ``subprocess``, ``ctypes``, an aliased handle, and any name a
# from-import introduced - was laundered.
#
# The docstring made it worse than a gap. It ASSERTED that a literal-name
# ``getattr`` "cannot launder an entry point the attribute form would have
# failed on" and named ``os.system``, ``os.killpg`` and ``os.abort`` as caught
# through that path. Both claims were false and each fell to one command. A
# guard that mis-states its coverage is worse than one that says what it
# misses, which is what ``OPS-16`` exists to end.
# ---------------------------------------------------------------------------

LAUNDERED_SPELLINGS: tuple[tuple[str, str, str, str], ...] = (
    (
        "from-os-import-system",
        'from os import system\n\n\ndef f(pid):\n    system(f"taskkill /F /PID {pid}")\n',
        KIND_OS_ATTR,
        "os.system",
    ),
    (
        "from-os-import-system-under-an-alias",
        "from os import system as s\n\n\ndef f(pid):\n"
        '    s(f"taskkill /F /PID {pid}")\n',
        KIND_OS_ATTR,
        "os.system",
    ),
    (
        "subprocess-executable-keyword-names-another-program",
        "import subprocess\nimport sys\n\n\ndef f():\n"
        '    subprocess.Popen([sys.executable], executable="C:/Windows/taskkill.exe")\n',
        KIND_ARGV,
        "executable=",
    ),
    (
        "getattr-launders-os-system",
        'import os\n\n\ndef f(pid):\n'
        '    getattr(os, "system")(f"taskkill /F /PID {pid}")\n',
        KIND_OS_ATTR,
        "os.system",
    ),
    (
        "getattr-launders-os-kill",
        'import os\n\n\ndef f(pid):\n    getattr(os, "kill")(pid, 9)\n',
        KIND_KILL_SIGNAL,
        "literal 0",
    ),
    (
        "getattr-launders-a-subprocess-spawner",
        'import subprocess\n\n\ndef f():\n'
        '    getattr(subprocess, "run")(["taskkill", "/F"])\n',
        KIND_ARGV,
        "'taskkill'",
    ),
    (
        "getattr-launders-a-windll-namespace-library",
        'import ctypes\n\n\ndef f(h):\n'
        '    return getattr(ctypes.windll, "ntdll").NtSuspendProcess(h)\n',
        KIND_LIBRARY,
        "'ntdll'",
    ),
    (
        "handle-reached-through-a-plain-alias",
        'import ctypes\n\n\ndef f(h):\n'
        '    kernel32 = ctypes.WinDLL("kernel32")\n'
        "    alias = kernel32\n"
        "    return alias.TerminateProcess(h, 1)\n",
        KIND_WIN32,
        "'TerminateProcess'",
    ),
    (
        "handle-reached-through-a-with-as-binding",
        'import ctypes\n\n\ndef f(h):\n'
        '    kernel32 = ctypes.WinDLL("kernel32")\n'
        "    with kernel32 as lib:\n"
        "        return lib.TerminateProcess(h, 1)\n",
        KIND_WIN32,
        "'TerminateProcess'",
    ),
    (
        "handle-reached-through-a-for-in-binding",
        'import ctypes\n\n\ndef f(h):\n'
        '    kernel32 = ctypes.WinDLL("kernel32")\n'
        "    for lib in (kernel32,):\n"
        "        lib.TerminateProcess(h, 1)\n",
        KIND_WIN32,
        "'TerminateProcess'",
    ),
    (
        "handle-reached-through-tuple-unpacking",
        'import ctypes\n\n\ndef f(h):\n'
        '    kernel32 = ctypes.WinDLL("kernel32")\n'
        "    alias, spare = kernel32, None\n"
        "    return alias.TerminateProcess(h, 1)\n",
        KIND_WIN32,
        "'TerminateProcess'",
    ),
    (
        # EXCEPTION 1 of 2: this one was not silent before, it was WRONG. The
        # old pre-pass walked every Name inside an assignment target, so
        # ``self.k32 = WinDLL(...)`` bound ``self`` as the handle and the
        # report read "reaches Win32 entry point 'k32'" and never named
        # TerminateProcess at all. A guard that flags the right line for the
        # wrong reason is not evidence that it understood the line.
        "handle-reached-through-an-instance-attribute",
        "import ctypes\n\n\nclass Probe:\n"
        "    def start(self):\n"
        '        self.k32 = ctypes.WinDLL("kernel32")\n\n'
        "    def stop(self, h):\n"
        "        return self.k32.TerminateProcess(h, 1)\n",
        KIND_WIN32,
        "'TerminateProcess'",
    ),
    (
        "loader-aliased-out-of-ctypes-by-a-from-import",
        'from ctypes import WinDLL as W\n\n\ndef f(h):\n'
        '    return W("ntdll").NtSuspendProcess(h)\n',
        KIND_LIBRARY,
        "'ntdll'",
    ),
    (
        "namespace-aliased-out-of-ctypes-by-a-from-import",
        "from ctypes import windll\n\n\ndef f(h):\n"
        "    return windll.ntdll.NtSuspendProcess(h)\n",
        KIND_LIBRARY,
        "'ntdll'",
    ),
    (
        "os-module-under-an-import-alias",
        'import os as o\n\n\ndef f(pid):\n    o.system(f"taskkill /F /PID {pid}")\n',
        KIND_OS_ATTR,
        "os.system",
    ),
    (
        "subprocess-module-under-an-import-alias",
        'import subprocess as sp\n\n\ndef f():\n    sp.run(["taskkill", "/F"])\n',
        KIND_ARGV,
        "'taskkill'",
    ),
    (
        # EXCEPTION 2 of 2: this one already passed before the widening. The
        # old walk looked for a loader namespace ANYWHERE in the chain and did
        # not care what the base was called, so the alias was irrelevant to
        # it. Kept because the symbol table now owns this path and a
        # regression here would otherwise be silent.
        "ctypes-module-under-an-import-alias",
        "import ctypes as c\n\n\ndef f(h):\n"
        "    return c.windll.ntdll.NtSuspendProcess(h)\n",
        KIND_LIBRARY,
        "'ntdll'",
    ),
    (
        "import-module-aliased-out-of-importlib",
        "from importlib import import_module as im\n\n\ndef f():\n"
        '    return im("psutil")\n',
        KIND_DYNAMIC,
        "no safe spelling",
    ),
    (
        "ctypes-libraryloader-reaches-ntdll",
        "import ctypes\n\n\ndef f(h):\n"
        "    loader = ctypes.LibraryLoader(ctypes.WinDLL)\n"
        "    return loader.ntdll.NtSuspendProcess(h)\n",
        KIND_LIBRARY,
        "'ntdll'",
    ),
    (
        "vars-opens-the-os-namespace-as-a-mapping",
        'import os\n\n\ndef f(pid):\n'
        '    vars(os)["system"](f"taskkill /F /PID {pid}")\n',
        KIND_DYNAMIC,
        "vars(os)",
    ),
    (
        "a-tracked-name-rebound-by-something-unreadable",
        'import ctypes\n\n\ndef f(h, supplied):\n'
        '    kernel32 = ctypes.WinDLL("kernel32")\n'
        "    kernel32 = supplied\n"
        "    return kernel32.CloseHandle(h)\n",
        KIND_REBIND,
        "refused unread",
    ),
)


@pytest.mark.parametrize(
    ("label", "source", "expected_kind", "expected_fragment"),
    LAUNDERED_SPELLINGS,
    ids=[entry[0] for entry in LAUNDERED_SPELLINGS],
)
def test_a_laundered_spelling_is_caught_and_named(
    label: str, source: str, expected_kind: str, expected_fragment: str
) -> None:
    """Each launder is refused, and the report NAMES what it refused.

    The point of the fragment assertion is the same as in
    :func:`test_a_forbidden_spelling_is_caught_and_named`: a guard that returns
    a bare "violation" is indistinguishable from one that has stopped
    discriminating, and every one of these WAS returning nothing at all.
    """
    violations = scan_source(source)
    rendered = _rendered(violations)
    assert violations, f"{label}: expected a violation, got none"
    assert expected_kind in _kinds(violations), f"{label}: {rendered}"
    assert expected_fragment in rendered, f"{label}: {rendered}"


# ---------------------------------------------------------------------------
# The refusal branches. A 36-mutation pass over the first version of this file
# found 7 survivors and every one of them was in a branch no test reached: the
# four "refused unread" paths, the empty-argv refusal, and the two from-import
# alias trackers. A branch no test reaches is decoration - it can be deleted
# without a single test noticing, which is exactly what the mutation pass did.
# ---------------------------------------------------------------------------

UNREADABLE_SHAPES: tuple[tuple[str, str, str, str], ...] = (
    (
        "os-kill-with-one-argument",
        "import os\n\n\ndef f(pid):\n    os.kill(pid)\n",
        KIND_KILL_SIGNAL,
        "unreadable",
    ),
    (
        "os-kill-with-a-starred-argument-list",
        "import os\n\n\ndef f(args):\n    os.kill(*args)\n",
        KIND_KILL_SIGNAL,
        "unreadable",
    ),
    (
        "windll-with-no-arguments",
        "import ctypes\n\n\ndef f():\n    return ctypes.WinDLL()\n",
        KIND_LIBRARY,
        "names no readable library",
    ),
    (
        "windll-with-a-starred-argument-list",
        "import ctypes\n\n\ndef f(a):\n    return ctypes.WinDLL(*a)\n",
        KIND_LIBRARY,
        "names no readable library",
    ),
    (
        "getattr-with-one-argument",
        "def f(obj):\n    return getattr(obj)\n",
        KIND_DYNAMIC,
        "argument list is unreadable",
    ),
    (
        "getattr-with-a-starred-argument-list",
        "def f(a):\n    return getattr(*a)\n",
        KIND_DYNAMIC,
        "argument list is unreadable",
    ),
    (
        "popen-with-no-positional-argv",
        "import subprocess\n\n\ndef f():\n    subprocess.Popen(stdin=None)\n",
        KIND_ARGV,
        "no readable positional argv",
    ),
    (
        "popen-with-a-starred-argv",
        "import subprocess\n\n\ndef f(a):\n    subprocess.Popen(*a)\n",
        KIND_ARGV,
        "no readable positional argv",
    ),
    (
        "popen-with-an-empty-argv",
        "import subprocess\n\n\ndef f():\n    subprocess.Popen([])\n",
        KIND_ARGV,
        "empty argv is unreadable",
    ),
)


@pytest.mark.parametrize(
    ("label", "source", "expected_kind", "expected_fragment"),
    UNREADABLE_SHAPES,
    ids=[entry[0] for entry in UNREADABLE_SHAPES],
)
def test_an_unreadable_call_shape_is_refused_rather_than_assumed_safe(
    label: str, source: str, expected_kind: str, expected_fragment: str
) -> None:
    """REFUSE WHAT YOU CANNOT READ, stated as a test rather than a comment.

    None of these shapes is dangerous on its face. Each one is refused because
    a static check cannot see what it does, and treating unreadable as safe is
    the assumption that makes a guard decorative.
    """
    violations = scan_source(source)
    rendered = _rendered(violations)
    assert violations, f"{label}: expected a violation, got none"
    assert expected_kind in _kinds(violations), f"{label}: {rendered}"
    assert expected_fragment in rendered, f"{label}: {rendered}"


def test_a_handle_that_is_never_bound_to_a_name_is_still_checked() -> None:
    """Two shapes where the handle exists only as an expression.

    Both survived a mutation pass with every other assertion in this file
    green, which is what an untested branch looks like from the outside: the
    LIBRARY was named by the loader call and asserted, and the ENTRY POINT
    reached on the loader's RESULT was checked by nobody. Each of these is
    caught twice over, and this test says so rather than settling for the
    first half.
    """
    loader_call = (
        "from ctypes import WinDLL as W\n\n\ndef f(h):\n"
        '    return W("ntdll").NtSuspendProcess(h)\n'
    )
    getattr_on_a_namespace = (
        "import ctypes\n\n\ndef f(h):\n"
        '    return getattr(ctypes.windll, "ntdll").NtSuspendProcess(h)\n'
    )
    for source in (loader_call, getattr_on_a_namespace):
        violations = scan_source(source)
        rendered = _rendered(violations)
        assert KIND_LIBRARY in _kinds(violations), rendered
        assert KIND_WIN32 in _kinds(violations), rendered
        assert "'NtSuspendProcess'" in rendered, rendered


def test_the_symbol_table_does_not_depend_on_statement_order() -> None:
    """``alias = LIB`` before ``LIB = WinDLL(...)`` still binds a handle.

    The docstring claims the table is iterated to a fixed point. That claim is
    only worth making if a source where the copy PRECEDES the thing it copies
    still resolves - one pass over this module in source order learns nothing
    about ``ALIAS``, and a guard that depended on the author's statement order
    would be trivial to sidestep by moving a line.
    """
    source = (
        "import ctypes\n\n\n"
        "def alias_it():\n"
        "    global ALIAS\n"
        "    ALIAS = LIB\n\n\n"
        "def setup():\n"
        "    global LIB\n"
        '    LIB = ctypes.WinDLL("kernel32")\n\n\n'
        "def use(h):\n"
        "    return ALIAS.TerminateProcess(h, 1)\n"
    )
    violations = scan_source(source)
    assert KIND_WIN32 in _kinds(violations), _rendered(violations)
    assert "'TerminateProcess'" in _rendered(violations)


def test_a_handle_reached_through_a_loader_namespace_is_tracked() -> None:
    """``k = ctypes.windll.kernel32`` binds a HANDLE, so ``k.X`` is checked.

    The namespace reach itself is clean here - ``kernel32`` is vetted - so
    every other namespace assertion in this file is satisfied without the
    resolution step that turns ``windll.<lib>`` into a handle. That step
    survived a mutation until this test existed.
    """
    source = (
        "import ctypes\n\n\ndef f(h):\n"
        "    k = ctypes.windll.kernel32\n"
        "    return k.TerminateProcess(h, 1)\n"
    )
    violations = scan_source(source)
    assert KIND_WIN32 in _kinds(violations), _rendered(violations)
    assert "'TerminateProcess'" in _rendered(violations)


def test_a_from_import_alias_of_a_subprocess_spawner_is_still_a_spawner() -> None:
    """``from subprocess import run as r`` - one of the two survivors.

    The alias tracker existed and no test reached it, so a mutation that
    emptied it survived. The spawner is the CAPABILITY; the local name it
    arrives under is decoration.
    """
    source = 'from subprocess import run as r\n\n\ndef f():\n    r(["taskkill", "/F"])\n'
    violations = scan_source(source)
    assert KIND_ARGV in _kinds(violations), _rendered(violations)
    assert "'taskkill'" in _rendered(violations)


def test_a_from_import_alias_of_os_kill_is_still_os_kill() -> None:
    """``from os import kill as k`` - the other survivor.

    ``os.kill`` is on the attribute allowlist ONLY because the signal check
    constrains it to a literal 0. If the alias were not tracked, the signal
    check would never run on ``k(pid, 9)`` and the name alone would be doing
    the work the docstring says it does not do.
    """
    source = "from os import kill as k\n\n\ndef f(pid):\n    k(pid, 9)\n"
    violations = scan_source(source)
    assert KIND_KILL_SIGNAL in _kinds(violations), _rendered(violations)
    assert "literal 0" in _rendered(violations)


# ---------------------------------------------------------------------------
# The other half of every check above: the shapes the real modules use must
# stay clean. A checker that flags everything passes every assertion in this
# file except these.
# ---------------------------------------------------------------------------


def test_the_shapes_the_real_modules_use_are_not_flagged() -> None:
    """The symbol table must not turn legitimate stdlib use into a violation.

    ``wintypes`` is from-imported out of ``ctypes`` and is not a loader, a
    namespace or a handle; ``guard`` is from-imported out of ``ops.loop``; and
    ``getattr`` on an object that is not a tracked module or handle is how
    ``ops/loop/watch.py`` reads a plan. Each of these is a shape the widened
    checks could plausibly have started flagging.
    """
    wintypes_use = (
        "import ctypes\nfrom ctypes import wintypes\n\n\ndef f():\n"
        '    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)\n'
        "    kernel32.OpenProcess.restype = wintypes.HANDLE\n"
        "    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL)\n"
    )
    plain_getattr = (
        "def f(plans):\n"
        "    for plan in plans:\n"
        '        name = getattr(plan, "name", None)\n'
        '        seconds = getattr(plan, "poll_seconds", None)\n'
        "        yield name, seconds\n"
    )
    sibling_import = (
        "from ops.loop import guard\n\n\ndef f():\n    return guard.REPO_ROOT\n"
    )
    structure = (
        "import ctypes\nfrom ctypes import wintypes\n\n\n"
        "class _FILETIME(ctypes.Structure):\n"
        '    _fields_ = (("dwLowDateTime", wintypes.DWORD),)\n\n\n'
        "def f():\n    return ctypes.byref(_FILETIME())\n"
    )

    for source in (wintypes_use, plain_getattr, sibling_import, structure):
        assert scan_source(source) == [], _rendered(scan_source(source))


def test_the_two_legitimate_getattr_calls_in_watch_stay_clean() -> None:
    """``getattr(plan, ...)`` in ``_plan_poll_intervals`` is not a launder.

    Asserted on the SHIPPED text with the anchors named, because this is the
    exact pair that stops ``getattr`` being banned outright - and a check that
    started flagging them would fail the mirror in a way that reads as "the
    guard got stricter" rather than "the guard got wrong".
    """
    source = _scope_source("ops/loop/watch.py")
    assert 'getattr(plan, "name", None)' in source, "anchor moved; re-read watch.py"
    assert 'getattr(plan, "poll_seconds", None)' in source, "anchor moved"
    dynamic = [v for v in scan_source(source) if v.kind == KIND_DYNAMIC]
    assert dynamic == [], _rendered(dynamic)


@pytest.mark.parametrize("relative", SCOPE)
def test_the_symbol_table_binds_the_real_modules_names(relative: str) -> None:
    """The zero above is a clean bill, not an empty symbol table.

    The whole widening rests on the table being populated. A table that bound
    nothing would route nothing through the capability checks and report a
    confident zero - the same shape of failure as a visitor that never fires,
    which :func:`test_the_scanner_actually_saw_the_module` already guards.
    """
    seen = observed_capabilities(_scope_source(relative))
    assert "os" in seen["tracked"], seen["tracked"]
    assert "ctypes" in seen["tracked"], seen["tracked"]
    assert "kernel32" in seen["tracked"], seen["tracked"]
