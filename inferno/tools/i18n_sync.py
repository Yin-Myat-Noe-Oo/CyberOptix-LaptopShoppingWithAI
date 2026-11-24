#!/usr/bin/env python
"""
i18n_sync.py - keep locale/my/LC_MESSAGES/django.po in sync without GNU gettext.

Run from the ``inferno/`` project directory:

    ..\\.venv\\Scripts\\python.exe tools/i18n_sync.py            # sync + fill + compile
    ..\\.venv\\Scripts\\python.exe tools/i18n_sync.py --check    # report only, write nothing
    ..\\.venv\\Scripts\\python.exe tools/i18n_sync.py --dump-untranslated todo.json
    ..\\.venv\\Scripts\\python.exe tools/i18n_sync.py --show-english   # list msgstrs that look English

What it does
  1. Extracts msgids exactly the way ``makemessages`` would:
       * templates/**/*.html - uses Django's own ``templatize()`` so {% trans %},
         {% translate %}, {% blocktrans[late] [trimmed] %} ... {% endblocktrans %}
         ({{ var }} -> %(var)s, ``%`` -> ``%%``, plural/context) and _("...")
         constants are handled identically to Django.
       * <app>/**/*.py (flame, verasChatbot, userauths, kbzpay_mock, api) - AST scan
         of _(), gettext(), gettext_lazy(), gettext_noop(), ngettext*(), pgettext*(),
         npgettext*() (and the legacy u* aliases) with literal string arguments.
  2. Adds any msgid missing from locale/my/LC_MESSAGES/django.po (obsolete entries
     are revived).
  3. Fills msgstr from locale/my/extra_translations.json  {msgid: burmese}.
       * key "context\\u0004msgid" targets a pgettext entry;
       * the value for a plural entry may be a string or a list (msgstr[0..]).
     An existing non-empty msgstr is only replaced when the JSON has an entry for it.
     Entries filled from the JSON lose their ``fuzzy`` flag.
     The optional list ``"_dynamic": [msgid, ...]`` declares msgids that only exist
     at runtime (e.g. {% trans order.get_status_display %}, model choice labels);
     they are added to the PO so the JSON can translate them.  Keys starting with
     ``_comment`` are ignored.
  4. Reports remaining untranslated (empty or fuzzy) msgids and compiles django.mo
     with polib's save_as_mofile.  locale/en is never touched.
"""
import argparse
import ast
import json
import os
import re
import sys
import warnings

import polib

HERE = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(HERE)  # .../inferno
sys.path.insert(0, BASE_DIR)

LANG = "my"
PO_PATH = os.path.join(BASE_DIR, "locale", LANG, "LC_MESSAGES", "django.po")
MO_PATH = os.path.join(BASE_DIR, "locale", LANG, "LC_MESSAGES", "django.mo")
JSON_PATH = os.path.join(BASE_DIR, "locale", LANG, "extra_translations.json")
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
PY_APPS = ["flame", "verasChatbot", "userauths", "kbzpay_mock", "api"]
SKIP_DIRS = {"migrations", "__pycache__", "tests", "node_modules"}

CTX_SEP = "\x04"
MYANMAR_RE = re.compile(r"[က-႟ꩠ-ꩿꧠ-꧿]")

# --------------------------------------------------------------------------- #
# Extraction
# --------------------------------------------------------------------------- #
# keyword -> (context arg index or None, singular index, plural index or None)
PY_KEYWORDS = {
    "_": (None, 0, None),
    "gettext": (None, 0, None),
    "gettext_lazy": (None, 0, None),
    "gettext_noop": (None, 0, None),
    "ugettext": (None, 0, None),
    "ugettext_lazy": (None, 0, None),
    "ugettext_noop": (None, 0, None),
    "_lazy": (None, 0, None),
    "ngettext": (None, 0, 1),
    "ngettext_lazy": (None, 0, 1),
    "ungettext": (None, 0, 1),
    "ungettext_lazy": (None, 0, 1),
    "pgettext": (0, 1, None),
    "pgettext_lazy": (0, 1, None),
    "npgettext": (0, 1, 2),
    "npgettext_lazy": (0, 1, 2),
}

_STR = r"""u?(?:'(?:[^'\\\n]|\\.)*'|"(?:[^"\\\n]|\\.)*")"""
_CALL_RE = re.compile(
    r"(?<![\w.])(npgettext|pgettext|ngettext|gettext|_)\(\s*("
    + _STR + r"(?:\s*,\s*" + _STR + r")*)"
)
_STR_RE = re.compile(_STR)


class Msg:
    __slots__ = ("msgid", "plural", "ctx", "refs", "pyformat")

    def __init__(self, msgid, plural=None, ctx=None):
        self.msgid, self.plural, self.ctx = msgid, plural, ctx
        self.refs = []
        self.pyformat = False

    @property
    def key(self):
        return (self.ctx or "") + CTX_SEP + self.msgid if self.ctx else self.msgid


def _add(found, msgid, plural, ctx, ref, pyformat=False):
    if not msgid:
        return
    k = (ctx, msgid)
    m = found.get(k)
    if m is None:
        m = found[k] = Msg(msgid, plural, ctx)
    if plural and not m.plural:
        m.plural = plural
    if ref not in m.refs:
        m.refs.append(ref)
    m.pyformat = m.pyformat or pyformat


_ESCAPED_TRANS_RE = re.compile(
    r"""{%\s*(trans(?:late)?\s+(?:"(?:[^"\\\n]|\\.)*\\.(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*\\.(?:[^'\\\n]|\\.)*')[^%]*?)\s*%}"""
)


def smart_split_contents(contents):
    from django.template.base import Token, TokenType
    return Token(TokenType.BLOCK, contents).split_contents()


def unescape_string_literal(s):
    from django.utils.text import unescape_string_literal as _u
    return _u(s)


def extract_templates(found):
    from django.utils.translation.template import templatize

    for root, dirs, files in os.walk(TEMPLATE_DIR):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in sorted(files):
            if not fn.endswith((".html", ".txt", ".htm")):
                continue
            path = os.path.join(root, fn)
            rel = os.path.relpath(path, BASE_DIR).replace(os.sep, "/")
            with open(path, encoding="utf-8") as fh:
                src = fh.read()
            # templatize()/xgettext mangle {% trans "a \"b\" c" %}; Django's runtime
            # unescapes the literal, so extract that exact msgid ourselves.
            for m in _ESCAPED_TRANS_RE.finditer(src):
                try:
                    bits = smart_split_contents(m.group(1))
                    msgid = unescape_string_literal(bits[1]).replace("%", "%%")
                except (ValueError, IndexError):
                    continue
                ctx = None
                if "context" in bits[2:]:
                    i = bits.index("context", 2)
                    if i + 1 < len(bits) and bits[i + 1][:1] in "\"'":
                        ctx = unescape_string_literal(bits[i + 1])
                line = src.count("\n", 0, m.start()) + 1
                _add(found, msgid, None, ctx, "%s:%d" % (rel, line), False)
            src = _ESCAPED_TRANS_RE.sub(lambda m: " " * len(m.group(0)), src)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                try:
                    out = templatize(src, origin=rel)
                except SyntaxError as exc:  # broken blocktrans etc.
                    print("  ! %s: %s" % (rel, exc))
                    continue
            for m in _CALL_RE.finditer(out):
                func = m.group(1)
                args = [ast.literal_eval(s) for s in _STR_RE.findall(m.group(2))]
                line = out.count("\n", 0, m.start()) + 1
                ref = "%s:%d" % (rel, line)
                pyfmt = "%(" in "".join(args)
                try:
                    if func in ("gettext", "_"):
                        _add(found, args[0], None, None, ref, pyfmt)
                    elif func == "ngettext":
                        _add(found, args[0], args[1], None, ref, pyfmt)
                    elif func == "pgettext":
                        _add(found, args[1], None, args[0], ref, pyfmt)
                    elif func == "npgettext":
                        _add(found, args[1], args[2], args[0], ref, pyfmt)
                except IndexError:
                    pass


def _const_str(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def extract_python(found):
    for app in PY_APPS:
        app_dir = os.path.join(BASE_DIR, app)
        if not os.path.isdir(app_dir):
            continue
        for root, dirs, files in os.walk(app_dir):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for fn in sorted(files):
                if not fn.endswith(".py"):
                    continue
                path = os.path.join(root, fn)
                rel = os.path.relpath(path, BASE_DIR).replace(os.sep, "/")
                try:
                    with open(path, encoding="utf-8") as fh:
                        tree = ast.parse(fh.read(), filename=rel)
                except (SyntaxError, UnicodeDecodeError) as exc:
                    print("  ! skip %s: %s" % (rel, exc))
                    continue
                for node in ast.walk(tree):
                    if not isinstance(node, ast.Call):
                        continue
                    f = node.func
                    name = f.id if isinstance(f, ast.Name) else (
                        f.attr if isinstance(f, ast.Attribute) else None)
                    spec = PY_KEYWORDS.get(name)
                    if not spec:
                        continue
                    ci, si, pi = spec
                    a = node.args
                    if len(a) <= si:
                        continue
                    msgid = _const_str(a[si])
                    if msgid is None:
                        continue
                    ctx = _const_str(a[ci]) if ci is not None else None
                    if ci is not None and ctx is None:
                        continue
                    plural = _const_str(a[pi]) if pi is not None and len(a) > pi else None
                    pyfmt = bool(re.search(r"%(\(\w+\))?[sdif]", msgid))
                    _add(found, msgid, plural, ctx, "%s:%d" % (rel, node.lineno), pyfmt)


# --------------------------------------------------------------------------- #
# PO handling
# --------------------------------------------------------------------------- #
def entry_key(e):
    return (e.msgctxt + CTX_SEP + e.msgid) if e.msgctxt else e.msgid


def is_translated(e):
    if e.fuzzy or e.obsolete:
        return False
    if e.msgid_plural:
        return bool(e.msgstr_plural) and all(v for v in e.msgstr_plural.values())
    return bool(e.msgstr)


def looks_english(e):
    text = " ".join(e.msgstr_plural.values()) if e.msgid_plural else e.msgstr
    if not text or MYANMAR_RE.search(text):
        return False
    stripped = re.sub(r"%\(\w+\)[sd]|%[sd]|\{\w*\}|<[^>]+>|&\w+;", " ", text)
    return bool(re.search(r"[A-Za-z]{3,}", stripped))


def apply_translation(e, value):
    """Set msgstr from JSON value. Returns True if something changed."""
    if e.msgid_plural:
        vals = value if isinstance(value, list) else [value]
        new = {i: v for i, v in enumerate(vals)}
        changed = dict(e.msgstr_plural) != new
        e.msgstr_plural = new
    else:
        if isinstance(value, list):
            value = value[0]
        changed = e.msgstr != value
        e.msgstr = value
    if e.fuzzy:
        e.flags.remove("fuzzy")
        e.previous_msgid = e.previous_msgid_plural = e.previous_msgctxt = None
        changed = True
    return changed


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="report only; write nothing")
    ap.add_argument("--dump-untranslated", metavar="FILE",
                    help="write a JSON skeleton {msgid: ''} of untranslated msgids")
    ap.add_argument("--show-english", action="store_true",
                    help="list entries whose msgstr has no Myanmar characters")
    ap.add_argument("-q", "--quiet", action="store_true",
                    help="don't print every untranslated msgid")
    args = ap.parse_args()

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:
            pass

    # templatize() only needs Django's Lexer, but it reads settings lazily.
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "inferno.settings")
    from django.conf import settings
    try:
        settings.INSTALLED_APPS  # noqa: B018 - force settings import
    except Exception:
        settings.configure()

    found = {}
    extract_templates(found)
    extract_python(found)

    po = polib.pofile(PO_PATH, wrapwidth=0)
    before = len([e for e in po if not e.obsolete])

    index = {}
    for e in po:
        index.setdefault((e.msgctxt, e.msgid), e)

    added = revived = 0
    for (ctx, msgid), m in found.items():
        e = index.get((ctx, msgid))
        if e is None:
            e = polib.POEntry(msgid=msgid, msgctxt=ctx, msgstr="")
            if m.plural:
                e.msgid_plural = m.plural
                e.msgstr_plural = {0: ""}
            if m.pyformat:
                e.flags.append("python-format")
            e.occurrences = [tuple(r.rsplit(":", 1)) for r in m.refs[:5]]
            po.append(e)
            index[(ctx, msgid)] = e
            added += 1
        elif e.obsolete:
            e.obsolete = False
            revived += 1
        if m.plural and not e.msgid_plural:
            e.msgid_plural = m.plural
            e.msgstr_plural = {0: e.msgstr or ""}
            e.msgstr = ""

    extra = {}
    if os.path.exists(JSON_PATH):
        with open(JSON_PATH, encoding="utf-8") as fh:
            extra = json.load(fh)
    filled = 0
    unknown_json = []
    dynamic = extra.get("_dynamic", [])  # msgids only known at runtime ({% trans var %})
    keyed = {entry_key(e): e for e in po if not e.obsolete}
    for k in dynamic:
        if k in keyed:
            continue
        ctx, _, mid = k.rpartition(CTX_SEP)
        e = polib.POEntry(msgid=mid, msgctxt=ctx or None, msgstr="",
                          comment="dynamic msgid (listed in extra_translations.json _dynamic)")
        obsolete = index.get((e.msgctxt, mid))
        if obsolete is not None:
            obsolete.obsolete = False
            e = obsolete
            revived += 1
        else:
            po.append(e)
            added += 1
        keyed[k] = e
    for k, v in extra.items():
        if k == "_dynamic" or k.startswith("_comment"):
            continue
        e = keyed.get(k)
        if e is None:
            unknown_json.append(k)
            continue
        if v in ("", None, []):
            continue
        if apply_translation(e, v):
            filled += 1

    active = [e for e in po if not e.obsolete]
    untranslated = [e for e in active if not is_translated(e)]
    english = [e for e in active if is_translated(e) and looks_english(e)]

    print("Source msgids found     : %d" % len(found))
    print("PO entries before/after : %d -> %d (added %d, revived %d)"
          % (before, len(active), added, revived))
    print("Filled/updated from JSON: %d (JSON keys: %d, not in PO: %d)"
          % (filled, len(extra), len(unknown_json)))
    print("Untranslated remaining  : %d" % len(untranslated))
    print("msgstr looks English    : %d" % len(english))
    in_src = {(m.ctx, m.msgid) for m in found.values()}
    if not args.quiet:
        for e in untranslated:
            flag = "" if (e.msgctxt, e.msgid) in in_src else "  (not in sources)"
            print("  - %r%s" % (entry_key(e), flag))
    if args.show_english:
        for e in english:
            print("  EN %r -> %r" % (e.msgid, e.msgstr or e.msgstr_plural))
    if unknown_json and not args.quiet:
        print("JSON keys with no PO entry (ignored):")
        for k in unknown_json[:50]:
            print("  ? %r" % k)

    if args.dump_untranslated:
        with open(args.dump_untranslated, "w", encoding="utf-8") as fh:
            json.dump({entry_key(e): "" for e in untranslated}, fh,
                      ensure_ascii=False, indent=2)
        print("Wrote %s" % args.dump_untranslated)

    if args.check:
        print("(--check: nothing written)")
        return 1 if untranslated else 0

    po.metadata["Content-Type"] = "text/plain; charset=UTF-8"
    po.save(PO_PATH)
    po.save_as_mofile(MO_PATH)
    print("Saved %s and compiled %s" % (os.path.relpath(PO_PATH, BASE_DIR),
                                         os.path.relpath(MO_PATH, BASE_DIR)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
