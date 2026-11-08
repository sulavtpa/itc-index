#!/usr/bin/env python3
"""ITC Index contribution tool.

Lets anyone add, modify or delete files in the repository without knowing git.
It drives the whole flow: tree file browser, file pick, index rebuild,
integrity checks, a git branch + detailed commit, push to the contributor's
fork and an automatic pull request via the GitHub CLI (gh).

Requires: git, GitHub CLI (gh), Python 3 with tkinter (all default on Windows).
Usage:  py contribute.py
"""

import atexit
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTENT_DIR = ROOT / "public" / "content"
INDEX_FILE = ROOT / "public" / "index.json"
TAG_OVERRIDES_FILE = ROOT / "public" / "tag-overrides.json"
METADATA_OVERRIDES_FILE = ROOT / "public" / "metadata-overrides.json"
STUB_PREFIX = "(external)-"
STUB_SUFFIX = ".txt"
STUB_NAME = STUB_PREFIX + "{target}" + STUB_SUFFIX
REPO_UPSTREAM = "sulavtpa/itc-index"
DEFAULT_BRANCH = "main"
MAX_INLINE_SIZE = 25 * 1024 * 1024  # suggest external hosting above this

# ---------------------------------------------------------------- ANSI/UI ---

RESET = "\x1b[0m"
DIM = "\x1b[2m"
BOLD = "\x1b[1m"
GREEN = "\x1b[32m"
YELLOW = "\x1b[33m"
RED = "\x1b[31m"
ACCENT = "\x1b[38;5;202m"

if os.name == "nt":
    os.system("")  # enables ANSI escape sequences in the Windows console


def write(text=""):
    sys.stdout.write(str(text) + "\n")


def format_size(nbytes):
    result = float(nbytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(result) < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(result)} {unit}"
            return f"{result:.1f} {unit}"
        result /= 1024
    return f"{result:.1f} TB"


def size_delta_text(old, new):
    if old == new:
        return "same size"
    arrow = "->"
    if new > old:
        return (f"+{format_size(new - old)} "
                f"({format_size(old)} {arrow} {format_size(new)})")
    return (f"{format_size(new - old)} "
            f"({format_size(old)} {arrow} {format_size(new)})")


# ---------------------------------------------------------------- key read ---

if os.name == "nt":
    import msvcrt

    def read_key():
        raw = msvcrt.getwch()
        if raw in ("\x00", "\xe0"):  # prefix for arrow/function keys on Windows
            code = msvcrt.getwch()
            return {"H": "UP", "P": "DOWN", "K": "LEFT", "M": "RIGHT",
                    "G": "HOME", "O": "END"}.get(code, "")
        return {"\r": "ENTER", "\n": "ENTER", "\x1b[A": "UP",
                "\x1b": "ESC", "\x08": "BACKSPACE", "\x03": "CTRLC"
                }.get(raw, raw)
else:  # POSIX fallback so *nix contributors are not shut out
    import termios
    import tty

    def read_key():
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            raw = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        if raw == "\x1b":  # escape sequence: try to read arrow codes
            try:
                tty.setraw(fd)
                seq = sys.stdin.read(2)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)
            return {"[A": "UP", "[B": "DOWN", "[C": "RIGHT", "[D": "LEFT"
                    }.get(seq, "ESC")
        return {"\r": "ENTER", "\n": "ENTER", "\x7f": "BACKSPACE",
                "\x08": "BACKSPACE", "\x03": "CTRLC"}.get(raw, raw)

# ----------------------------------------------------------- tree browser ---


class Node:
    """One row of the file tree (folder entry or file entry)."""

    __slots__ = ("name", "path", "is_dir", "is_stub", "children", "open", "depth")

    def __init__(self, name, path, is_dir, is_stub=False, depth=0):
        self.name = name
        self.path = path  # path relative to CONTENT_DIR
        self.is_dir = is_dir
        self.is_stub = is_stub
        self.children = [] if is_dir else None
        self.open = False
        self.depth = depth


def build_tree():
    """Scan content/ into a Node tree; external stubs map to their target."""
    root = Node("", Path("."), True, depth=-1)
    folders = {".": root}

    for dirpath, dirnames, filenames in os.walk(CONTENT_DIR):
        dirnames[:] = [d for d in sorted(dirnames)
                       if not d.startswith(".") and d != "__pycache__"]
        rel_dir = Path(os.path.relpath(dirpath, CONTENT_DIR)).as_posix()
        rel_dir = "." if rel_dir == "." else rel_dir
        parent = folders[rel_dir]
        for dirname in dirnames:
            child_rel = f"{rel_dir}/{dirname}" if rel_dir != "." else dirname
            node = Node(dirname, Path(child_rel), True, depth=parent.depth + 1)
            parent.children.append(node)
            folders[child_rel] = node
        for filename in sorted(filenames):
            if filename.startswith(".") or filename.endswith("~"):
                continue
            virtual = filename
            is_stub = filename.startswith(STUB_PREFIX)
            if is_stub:
                # show the virtual file name the stub represents
                target = filename[len(STUB_PREFIX):]
                target = target[: -len(STUB_SUFFIX)]
                if target:
                    virtual = target
            node = Node(
                virtual,
                Path(f"{rel_dir}/{filename}") if rel_dir != "."
                else Path(filename),
                False, is_stub, depth=parent.depth + 1,
            )
            parent.children.append(node)
    return root


def visible_rows(root, filter_text):
    """Rows to display. While a filter is active every folder is treated as
    open so hidden files can be matched by name."""
    rows = []
    needle = filter_text.lower() if filter_text else None

    def subtree_matches(node):
        if not needle or needle in node.name.lower():
            return True
        if node.is_dir:
            return any(subtree_matches(child) for child in node.children)
        return False

    def add(node, force):
        if not force and subtree_matches(node) is False:
            return
        rows.append(node)
        if node.is_dir and (node.open or force or needle):
            for child in node.children:
                add(child, force or (needle is not None
                                     and needle in node.name.lower()))

    for child in root.children:
        add(child, False)
    return rows


VISIBILITY = 18


def tree_picker(select, title):
    """Keyboard-driven tree browser.

    select is 'dir' (pick a folder) or 'file'. Returns a Node or None.
    """
    root = build_tree()
    for child in root.children:
        child.open = True
    filter_text = ""
    cursor = 0
    scroll = 0

    while True:
        rows = visible_rows(root, filter_text)
        cursor = min(cursor, max(0, len(rows) - 1))
        if cursor < scroll:
            scroll = cursor
        if cursor >= scroll + VISIBILITY:
            scroll = cursor - VISIBILITY + 1

        sys.stdout.write("\x1b[2J\x1b[H")
        write(f"{BOLD}{ACCENT}{title}{RESET}")
        write(f"{DIM}Up/down move | Left/right collapse/expand | Enter select | "
              f"Esc cancel | type to filter: \"{filter_text}\"{RESET}")
        write("")
        for offset, row in enumerate(rows[scroll:scroll + VISIBILITY]):
            active = scroll + offset == cursor
            mark = f"{ACCENT}>{RESET}" if active else " "
            scroll_pad = "  " * row.depth
            if row.is_dir:
                marker = "[-]" if row.open else "[+]"
                text = f"{marker} {row.name}/"
            elif row.is_stub:
                text = f"{row.name}  {YELLOW}[external]{RESET}"
            else:
                text = row.name
            style = BOLD if active else ""
            write(f" {mark} {style}{scroll_pad}{text}{RESET}")
        if not rows:
            write(f" {DIM}(nothing matches this filter){RESET}")
        write("")

        key = read_key()
        if key in ("CTRLC", "ESC"):
            return None
        if key == "UP":
            cursor = max(0, cursor - 1)
        elif key == "DOWN":
            cursor = min(max(0, len(rows) - 1), cursor + 1)
        elif key == "HOME":
            cursor = 0
        elif key == "END":
            cursor = max(0, len(rows) - 1)
        elif key == "LEFT":
            row = rows[cursor] if rows else None
            if row and row.is_dir and row.open:
                row.open = False
        elif key == "RIGHT":
            row = rows[cursor] if rows else None
            if row and row.is_dir:
                row.open = True
        elif key == "BACKSPACE":
            filter_text = filter_text[:-1]
            cursor = 0
        elif key == "ENTER":
            row = rows[cursor] if rows else None
            if row is None:
                continue
            if select == "dir":
                if row.is_dir:
                    return row
                    write(f" {YELLOW}Pick a folder; use left/right to expand and "
                        f"up/down to choose.{RESET}")
                continue
            if row.is_dir:
                if row.open:
                    row.open = False
                else:
                    row.open = True
                continue
            return row
        elif isinstance(key, str) and len(key) == 1 and key.isprintable():
            filter_text += key
            cursor = 0
            scroll = 0


# ------------------------------------------------------------ subprocess ---

def run(args, *, check=True):
    result = subprocess.run(
        [str(part) for part in args], cwd=ROOT, capture_output=True,
        text=True, encoding="utf-8", errors="replace",
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(
            f"Command failed ({result.returncode}): "
            f"{' '.join(str(a) for a in args)}\n{detail}"
        )
    return result


def git(args, **kwargs):
    return run(["git", *args], **kwargs)


def gh(args, **kwargs):
    return run(["gh", *args], **kwargs)


# ------------------------------------------------------------ preflight ---

def fail_guide(missing, guide):
    write(f"{RED}Setup incomplete:{RESET} {missing} is not installed.")
    write()
    write("Install it with any one of these, then run `py contribute.py` again:")
    for command in guide:
        write(f"  - {command}")
    write()
    sys.exit(1)


def tool_present(program):
    try:
        return run([program, "--version"], check=False).returncode == 0
    except OSError:
        return False


def preflight():
    write(f"{BOLD}Preflight{RESET}")
    if not tool_present("git"):
        fail_guide("git", [
            "winget install Git.Git",
            "choco install git",
            "web download: https://git-scm.com/downloads",
        ])
    if not tool_present("gh"):
        fail_guide("gh", [
            "winget install GitHub.cli",
            "choco install gh",
            "web download: https://github.com/cli/cli/releases",
        ])

    name = run(["git", "config", "user.name"], check=False).stdout.strip()
    email = run(["git", "config", "user.email"], check=False).stdout.strip()
    if not name or not email:
        write(f"{RED}Your git identity is not configured yet.{RESET}")
        write("Run these two commands once, then start this tool again:")
        write('  git config --global user.name  "Your Name"')
        write('  git config --global user.email "you@example.com"')
        sys.exit(1)

    auth = gh(["auth", "status"], check=False)
    match = re.search(r"Logged in to github\.com(?:.|\n)*?\saccount ([^\s(]+)",
                      (auth.stdout or "") + (auth.stderr or ""))
    if auth.returncode != 0 or not match:
        write(f"{YELLOW}GitHub CLI is installed but not signed in.{RESET}")
        write("Run this once and follow its prompts (device login):")
        write("  gh auth login")
        sys.exit(1)
    username = match.group(1)
    write(f"  git identity: {name} <{email}>")
    write(f"  github account: {username}")

    if run(["git", "status", "--porcelain"], check=False).stdout.strip():
        write(f"{RED}This repository has uncommitted changes.{RESET}")
        write("Inspect them with `git status`; commit or discard them"
              " before contributing:")
        write("  git restore .        (discard edits, keep new untracked files)")
        write("  git clean -di        (delete extra files, interactive)")
        write("or commit them manually first.")
        sys.exit(1)
    return username

# ------------------------------------------------------- branch + PR flow ---


def ensure_fork(username):
    view = gh(["repo", "view", f"{username}/itc-index", "--json", "name",
               "--jq", ".name"], check=False)
    if view.returncode == 0:
        return f"{username}/itc-index"
    write(f"  creating your fork of {REPO_UPSTREAM}...")
    gh(["repo", "fork", REPO_UPSTREAM, "--clone=false"])
    return f"{username}/itc-index"


def contribute_pipeline(username, title, body, branch_suffix):
    """Everything after the file edit: branch, commit, push, PR."""
    write(f"{BOLD}Branch, commit and pull request{RESET}")
    fork_slug = ensure_fork(username)
    branch = "contrib/" + branch_suffix[:60]
    git(["fetch", "origin", DEFAULT_BRANCH])
    git(["switch", "-C", branch, f"origin/{DEFAULT_BRANCH}"])
    write(f"  branch: {branch}")

    stage_paths = ["public/content", "public/index.json"]
    tracked_tags = run(
        ["git", "ls-files", "--error-unmatch", "public/tag-overrides.json"],
        check=False,
    )
    if TAG_OVERRIDES_FILE.exists() or tracked_tags.returncode == 0:
        stage_paths.append("public/tag-overrides.json")
    tracked_metadata = run(
        ["git", "ls-files", "--error-unmatch", "public/metadata-overrides.json"],
        check=False,
    )
    if METADATA_OVERRIDES_FILE.exists() or tracked_metadata.returncode == 0:
        stage_paths.append("public/metadata-overrides.json")
    git(["add", "-A", *stage_paths])
    clean = run(["git", "diff", "--cached", "--quiet"], check=False)
    if clean.returncode == 0:
        write(f"{YELLOW}Nothing changed after all - no commit created.{RESET}")
        git(["switch", DEFAULT_BRANCH], check=False)
        git(["branch", "-D", branch], check=False)
        return None

    git(["commit", "-m", title, "-m", body])
    write("  commit created")

    write(f"  pushing to {fork_slug}...")
    remote_url = f"https://github.com/{fork_slug}.git"
    remotes = run(["git", "remote"]).stdout.split()
    if "fork" not in remotes:
        git(["remote", "add", "fork", remote_url])
    elif run(["git", "remote", "get-url", "fork"], check=False).stdout.strip() != remote_url:
        git(["remote", "set-url", "fork", remote_url])
    git(["push", "-u", "fork", branch])

    result = gh(["pr", "create", "--repo", REPO_UPSTREAM,
                 "--head", f"{username}:{branch}",
                 "--base", DEFAULT_BRANCH,
                 "--title", title, "--body", body], check=False)
    git(["switch", DEFAULT_BRANCH], check=False)
    if result.returncode != 0:
        write(f"{YELLOW}The pull request could not be opened automatically:{RESET}")
        write((result.stderr or result.stdout).strip())
        manual = (f"https://github.com/{REPO_UPSTREAM}/compare/"
                  f"{DEFAULT_BRANCH}...{username}:{branch}?expand=1")
        write(f"Open this link to finish manually:\n  {manual}")
        return branch
    write(f"{GREEN}Pull request ready: {(result.stdout or '').strip()}{RESET}")
    return branch

# ------------------------------------------------------------ index steps ---


def rebuild_and_check():
    write(f"{BOLD}Rebuilding index + running checks{RESET}")
    build = run([sys.executable, "build.py"], check=False)
    sys.stdout.write(build.stdout or "")
    if build.returncode != 0:
        sys.stdout.write(build.stderr or "")
        write(f"{RED}build.py failed. Your change is still on disk, but nothing "
              f"was committed.{RESET}")
        return False
    checks = run([sys.executable, "checks.py"], check=False)
    sys.stdout.write(checks.stdout or "")
    if checks.returncode != 0:
        write(f"{RED}checks.py failed. Nothing was committed.{RESET}")
        return False
    return True


def confirm(prompt):
    try:
        answer = input(f"{prompt} [y/N] ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        return False
    return answer in ("y", "yes")


def tkinter_pick(title):
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        write(f"{RED}tkinter is missing, so paste the full path of the file:{RESET}")
        typed = input("> ").strip().strip('"')
        if typed and Path(typed).is_file():
            return Path(typed)
        write(f"{DIM}No file chosen.{RESET}")
        return None
    tkroot = tk.Tk()
    tkroot.attributes("-topmost", True)
    tkroot.withdraw()
    chosen = filedialog.askopenfilename(
        parent=tkroot, title=title, initialdir=os.path.expanduser("~"))
    tkroot.destroy()
    if not chosen:
        write(f"{DIM}No file chosen.{RESET}")
        return None
    return Path(chosen)


def read_tag_overrides():
    if not TAG_OVERRIDES_FILE.exists():
        return {}
    try:
        with TAG_OVERRIDES_FILE.open(encoding="utf-8") as file:
            overrides = json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Could not read tag overrides: {error}") from error
    if not isinstance(overrides, dict):
        raise RuntimeError("public/tag-overrides.json must contain an object.")
    for file_id, tags in overrides.items():
        if not isinstance(file_id, str) or not isinstance(tags, list) \
                or any(not isinstance(tag, str) or not tag.strip() for tag in tags):
            raise RuntimeError("Tag overrides must map file IDs to non-empty tag lists.")
    return overrides


def save_tag_overrides(overrides):
    if not overrides:
        TAG_OVERRIDES_FILE.unlink(missing_ok=True)
        return
    TAG_OVERRIDES_FILE.write_text(
        json.dumps(overrides, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def read_metadata_overrides():
    if not METADATA_OVERRIDES_FILE.exists():
        return {}
    try:
        with METADATA_OVERRIDES_FILE.open(encoding="utf-8") as file:
            overrides = json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Could not read metadata overrides: {error}") from error
    if not isinstance(overrides, dict):
        raise RuntimeError("public/metadata-overrides.json must contain an object.")
    for file_id, metadata in overrides.items():
        if not isinstance(file_id, str) or not isinstance(metadata, dict) \
                or any(key not in ("title", "description")
                       or not isinstance(value, str) or not value.strip()
                       for key, value in metadata.items()):
            raise RuntimeError(
                "Metadata overrides must map file IDs to non-empty titles or descriptions."
            )
    return overrides


def save_metadata_overrides(overrides):
    if not overrides:
        METADATA_OVERRIDES_FILE.unlink(missing_ok=True)
        return
    METADATA_OVERRIDES_FILE.write_text(
        json.dumps(overrides, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def indexed_metadata(file_id):
    try:
        with INDEX_FILE.open(encoding="utf-8") as file:
            documents = json.load(file)
    except (OSError, json.JSONDecodeError):
        return {}
    return next(({"title": doc.get("title", ""),
                  "description": doc.get("description", "")}
                 for doc in documents if doc.get("id") == file_id), {})


def prompt_metadata(file_id, suggested_title, suggested_description):
    """Ask for index text, using prior values or generated suggestions as defaults."""
    overrides = read_metadata_overrides()
    current = {**indexed_metadata(file_id), **overrides.get(file_id, {})}
    title_default = current.get("title") or suggested_title
    description_default = current.get("description") or suggested_description
    write(f"\nTitle [{title_default}]")
    title = input("> ").strip() or title_default
    write(f"Description [{description_default}]")
    description = input("> ").strip() or description_default
    return {"title": title, "description": description}


def index_tags(file_id):
    try:
        with INDEX_FILE.open(encoding="utf-8") as file:
            documents = json.load(file)
    except (OSError, json.JSONDecodeError):
        return []
    return next((doc.get("tags", []) for doc in documents
                 if doc.get("id") == file_id), [])


def edit_tags(file_id):
    """Edit manually assigned tags; tags derived from the file path stay intact."""
    overrides = read_tag_overrides()
    selected = list(overrides.get(file_id, []))
    all_tags = {tag.casefold(): tag for doc in json.loads(
        INDEX_FILE.read_text(encoding="utf-8")) if isinstance(doc, dict)
        for tag in doc.get("tags", []) if isinstance(tag, str)}
    for tags in overrides.values():
        for tag in tags:
            all_tags.setdefault(tag.casefold(), tag)

    query = ""
    cursor = 0
    while True:
        matches = sorted(
            (tag for tag in all_tags.values()
             if query.casefold() in tag.casefold()),
            key=lambda tag: (not tag.casefold().startswith(query.casefold()),
                             tag.casefold()),
        )[:8]
        rows = [("tag", tag) for tag in matches]
        create_label = query.strip()
        if create_label and create_label.casefold() not in all_tags:
            rows.append(("create", create_label))
        rows.append(("done", "Done"))
        cursor = min(cursor, len(rows) - 1)

        sys.stdout.write("\x1b[2J\x1b[H")
        write(f"{BOLD}{ACCENT}Update tags{RESET}  {DIM}{file_id}{RESET}")
        write(f"{DIM}Type to search | Up/down choose | Enter toggle | Esc cancel{RESET}")
        automatic = [tag for tag in index_tags(file_id)
                     if tag.casefold() not in {item.casefold() for item in selected}]
        if automatic:
            write(f"Automatic tags stay: {', '.join(automatic)}")
        write(f"Selected manual tags: {', '.join(selected) if selected else '(none)'}")
        write(f"Search: {query}_")
        write("")
        if not matches and not create_label:
            write(f" {DIM}No tags yet. Type to search or create one.{RESET}")
        for row_index, (kind, value) in enumerate(rows):
            marker = ">" if row_index == cursor else " "
            if kind == "tag":
                checked = "x" if value.casefold() in {
                    item.casefold() for item in selected
                } else " "
                write(f" {marker} [{checked}] {value}")
            elif kind == "create":
                write(f" {marker} + Create new tag: {value}")
            else:
                write(f" {marker} Done")

        key = read_key()
        if key in ("CTRLC", "ESC"):
            return None
        if key == "UP":
            cursor = max(0, cursor - 1)
        elif key == "DOWN":
            cursor = min(len(rows) - 1, cursor + 1)
        elif key == "BACKSPACE":
            query = query[:-1]
            cursor = 0
        elif key == "ENTER":
            kind, value = rows[cursor]
            if kind == "done":
                return selected
            if kind == "create":
                selected.append(value)
                all_tags[value.casefold()] = value
                query = ""
                cursor = 0
                continue
            selected_key = value.casefold()
            current = next((tag for tag in selected
                            if tag.casefold() == selected_key), None)
            if current is None:
                selected.append(value)
            else:
                selected.remove(current)
        elif isinstance(key, str) and len(key) == 1 and key.isprintable():
            query += key
            cursor = 0


# Files are parked here while build/checks run, so they never land under
# public/content (which would get indexed and committed by mistake).
TEMP_DIR = Path(tempfile.mkdtemp(prefix="itc-contrib-"))
atexit.register(shutil.rmtree, TEMP_DIR, ignore_errors=True)


def park(path):
    """Move a file out of the content tree temporarily; returns its temp path."""
    spot = TEMP_DIR / path.name
    serial = 1
    while spot.exists():
        spot = TEMP_DIR / f"{serial}-{path.name}"
        serial += 1
    shutil.move(str(path), str(spot))
    return spot


def unpark(spot, destination):
    spot.replace(destination)
    if spot.parent.is_dir() and not any(spot.parent.iterdir()):
        spot.parent.rmdir()


# ---------------------------------------------------------------- actions ---


def pretty_name(filename):
    text = Path(filename).name
    text = os.path.splitext(text)[0]
    text = re.sub(r"[-_]+", " ", text).strip()
    text = text.title()
    # keep ordinals lowercase: 1St -> 1st, 3Rd -> 3rd
    return re.sub(r"(\d+)\s*(St|Nd|Rd|Th)\b",
                  lambda m: m.group(1) + m.group(2).lower(), text)


def slugify(path):
    text = str(path)
    text = text.replace("\\", "/")
    text = text.strip("/").split("/")[-1]
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:36]
    return slug or "change"


def detail_body(action, target_path, *, old_size, new_size, extra=None):
    lines = [
        "All details:",
        f"- file: {os.path.relpath(target_path, ROOT).replace(os.sep, '/')}",
        f"- action: {action}",
        f"- size: {format_size(old_size)} -> {format_size(new_size)} "
        f"({size_delta_text(old_size, new_size)})",
    ]
    if extra:
        lines.extend(extra)
    lines.append("- public/index.json rebuilt; py checks.py passed locally")
    lines.append("- submitted automatically by contribute.py")
    return "\n".join(lines)


def host_word(url):
    lowered = url.lower()
    if "mega.nz" in lowered or "mega.io" in lowered:
        return "MEGA"
    if "drive.google" in lowered or "docs.google" in lowered:
        return "Google Drive"
    if "dropbox" in lowered:
        return "Dropbox"
    return "an external host"


def suggested_description(filename, folder_rel):
    extension = Path(filename).suffix.lstrip(".").upper() or "File"
    section = Path(folder_rel).parts[0].replace("-", " ") if folder_rel else "content"
    return f"{extension} file in the {section} section."


def suggested_external_description(url):
    host = {"MEGA": "mega", "Google Drive": "drive", "Dropbox": "dropbox"}.get(
        host_word(url))
    return (f"Hosted on {host}, not in the repository." if host else
            "Hosted externally, not in the repository.")


def action_add(username):
    write(f"{BOLD}{ACCENT}Add - choose where the file belongs{RESET}")
    folder_node = tree_picker("dir", "Pick the destination folder")
    if folder_node is None:
        return
    folder_rel = folder_node.path.as_posix()
    if folder_rel == "." or not folder_rel:
        folder_rel = ""
    write("")

    write("How should students get this file?")
    write(f"  1  in the repository  (fine up to about {format_size(MAX_INLINE_SIZE)})")
    write("  2  external host (MEGA, Drive, etc.) - paste a link")
    mode = (input("1 or 2 [1]: ").strip() or "1")

    if mode == "2":
        add_external(username, folder_rel)
        return

    write("Pick the file from your computer (a window opens now).")
    source = tkinter_pick("Choose the file to add")
    if source is None:
        return
    name = source.name
    if name.startswith(STUB_PREFIX) or name.startswith(("~", ".")) \
            or name == "README.md":
        write(f"{RED}That file name is reserved by the tool/engine. Rename it "
              f"and try again.{RESET}")
        return
    destination = CONTENT_DIR / folder_rel / name
    if destination.exists():
        write(f"{RED}A file called '{name}' already exists in that folder.{RESET}")
        write("Use 'modify' to replace it, or rename the new file first.")
        return
    source_size = os.path.getsize(source)
    if source_size > MAX_INLINE_SIZE:
        write(f"{YELLOW}{format_size(source_size)} is large for the repository "
              f"(limit guide ~{format_size(MAX_INLINE_SIZE)}).{RESET}")
        if confirm("Host the file externally instead?"):
            add_external(username, folder_rel)
            return
    tag_id = destination.relative_to(ROOT).as_posix()
    metadata = prompt_metadata(
        tag_id, pretty_name(name), suggested_description(name, folder_rel))
    old_metadata = read_metadata_overrides()
    new_tags = None
    if confirm("Set tags for this file?"):
        new_tags = edit_tags(tag_id)
        if new_tags is None:
            return
    shutil.copy2(source, destination)
    updated_metadata = dict(old_metadata)
    updated_metadata[tag_id] = metadata
    save_metadata_overrides(updated_metadata)
    old_overrides = read_tag_overrides()
    if new_tags is not None:
        updated_overrides = dict(old_overrides)
        if new_tags:
            updated_overrides[tag_id] = new_tags
        else:
            updated_overrides.pop(tag_id, None)
        save_tag_overrides(updated_overrides)
    if not rebuild_and_check():
        return
    write(f"  copied to public/content/{folder_rel}/{name} "
          f"({format_size(destination.stat().st_size)})")
    if not confirm(f"Add '{name}' and submit the pull request?"):
        destination.unlink()
        save_metadata_overrides(old_metadata)
        save_tag_overrides(old_overrides)
        rebuild_and_check()
        write(f"{YELLOW}Cancelled; the copied file was removed.{RESET}")
        return
    title = f"add: {pretty_name(name)}"
    body = detail_body("add", destination, old_size=0,
                       new_size=destination.stat().st_size,
                       extra=["- section: " + folder_rel.replace("/", " / ")])
    branch_suffix = f"add-{slugify(folder_rel)}-{slugify(name)}"
    contribute_pipeline(username, title, body, branch_suffix)
    write(f"{GREEN}Done - thanks for contributing!{RESET}")


def add_external(username, folder_rel):
    target = input(
        "File name as users should see it, e.g. structural-analysis-1-solutions.pdf\n> "
    ).strip().strip("/")
    if not target or "/" in target or target.startswith(STUB_PREFIX):
        write(f"{RED}That is not a usable file name.{RESET}")
        return
    if (CONTENT_DIR / folder_rel / target).exists():
        write(f"{RED}'{target}' already exists as a real file there; external "
              f"hosting is not needed for it.{RESET}")
        return
    url = input("Paste the download URL (one line, http/https)\n> ").strip()
    if not re.fullmatch(r"https?://\S+", url):
        write(f"{RED}That does not look like a single http(s) URL.{RESET}")
        return
    stub_path = CONTENT_DIR / folder_rel / STUB_NAME.format(target=target)
    tag_id = (stub_path.parent / target).relative_to(ROOT).as_posix()
    metadata = prompt_metadata(
        tag_id, pretty_name(target), suggested_external_description(url))
    old_metadata = read_metadata_overrides()
    new_tags = None
    if confirm("Set tags for this file?"):
        new_tags = edit_tags(tag_id)
        if new_tags is None:
            return
    stub_path.parent.mkdir(parents=True, exist_ok=True)
    stub_path.write_text(url + "\n", encoding="utf-8")
    updated_metadata = dict(old_metadata)
    updated_metadata[tag_id] = metadata
    save_metadata_overrides(updated_metadata)
    old_overrides = read_tag_overrides()
    if new_tags is not None:
        updated_overrides = dict(old_overrides)
        if new_tags:
            updated_overrides[tag_id] = new_tags
        else:
            updated_overrides.pop(tag_id, None)
        save_tag_overrides(updated_overrides)
    if not rebuild_and_check():
        stub_path.unlink(missing_ok=True)
        save_metadata_overrides(old_metadata)
        save_tag_overrides(old_overrides)
        rebuild_and_check()
        return
    if not confirm(f"Link '{target}' to {url} and submit?"):
        stub_path.unlink()
        save_metadata_overrides(old_metadata)
        save_tag_overrides(old_overrides)
        rebuild_and_check()
        write(f"{YELLOW}Cancelled; the link file was removed.{RESET}")
        return
    title = f"external: {pretty_name(target)} ({host_word(url)})"
    body = detail_body(
        "external", stub_path, old_size=0, new_size=0,
        extra=[f"- link: {url}", f"- section: {folder_rel}"],
    )
    branch_suffix = f"ext-{slugify(folder_rel)}-{slugify(target)}"
    contribute_pipeline(username, title, body, branch_suffix)
    write(f"{GREEN}Done - thanks for contributing!{RESET}")


def action_modify(username):
    write(f"{BOLD}{ACCENT}Modify - choose a file{RESET}")
    node = tree_picker("file", "Pick a file to modify")
    if node is None:
        return
    write(f"\nWhat do you want to modify for '{node.name}'?")
    write("  1  replace file")
    write("  2  tags")
    write("  3  description")
    write("  4  title")
    write("  q  cancel")
    choice = input("> ").strip().lower()
    if choice in ("1", "file", "replace"):
        replace_file(username, node)
    elif choice in ("2", "tags"):
        update_tags_for_node(username, node)
    elif choice in ("3", "description", "desc"):
        update_metadata_for_node(username, node, "description")
    elif choice in ("4", "title"):
        update_metadata_for_node(username, node, "title")
    elif choice not in ("q", "quit", "cancel", ""):
        write(f"{DIM}Choose 1, 2, 3, 4 or q.{RESET}")


def replace_file(username, node):
    abs_path = CONTENT_DIR / node.path

    if node.is_stub:
        old_url = abs_path.read_text(encoding="utf-8").strip()
        write(f"Current link: {old_url}")
        new_url = input("Paste the new URL (Enter to cancel)\n> ").strip()
        if not new_url:
            return
        if not re.fullmatch(r"https?://\S+", new_url):
            write(f"{RED}That does not look like a single http(s) URL.{RESET}")
            return
        write(f"{BOLD}Do you want to update the link for {node.name}?{RESET}")
        write(f"  old: {old_url}")
        write(f"  new: {new_url}")
        if not confirm("Submit?"):
            return
        abs_path.write_text(new_url + "\n", encoding="utf-8")
        if not rebuild_and_check():
            abs_path.write_text(old_url + "\n", encoding="utf-8")
            rebuild_and_check()
            return
        title = f"link: {pretty_name(node.name)} ({host_word(new_url)})"
        body = detail_body("external", abs_path, old_size=len(old_url),
                           new_size=len(new_url),
                           extra=["- old link: " + old_url,
                                  "- new link: " + new_url])
        branch_suffix = f"link-{slugify(abs_path)}"
        contribute_pipeline(username, title, body, branch_suffix)
        write(f"{GREEN}Done - thanks for contributing!{RESET}")
        return

    old_size = abs_path.stat().st_size
    write(f"Old file: {node.name} ({format_size(old_size)})")
    write("Pick the updated file (a window opens now).")
    source = tkinter_pick("Choose the updated file")
    if source is None:
        return
    if source.resolve() == abs_path.resolve():
        write(f"{RED}That is the same file already in the repository.{RESET}")
        return
    write(f"{BOLD}Do you want to update it?{RESET}")
    write(f"  old file: {node.name}  {format_size(old_size)}")
    write(f"  new file: {source.name}  {format_size(os.path.getsize(source))}")
    write(f"  net change: {size_delta_text(old_size, os.path.getsize(source))}")
    if source.name != node.name:
        write(f"{YELLOW}Note: names differ - the renamed file will be saved as "
              f"'{node.name}'.{RESET}")
    if not confirm("Submit?"):
        return
    backup = TEMP_DIR / f"bak-{node.name}"
    if backup.exists():
        backup.unlink()
    shutil.copy2(abs_path, backup)
    shutil.copy2(source, abs_path)
    if not rebuild_and_check():
        shutil.copy2(backup, abs_path)
        backup.unlink()
        rebuild_and_check()
        return
    title = f"modify: {pretty_name(node.name)}"
    body = detail_body("modify", abs_path, old_size=old_size,
                       new_size=abs_path.stat().st_size,
                       extra=[f"- section: {abs_path.parent.relative_to(CONTENT_DIR).as_posix()}"])
    branch_suffix = f"modify-{slugify(abs_path)}"
    contribute_pipeline(username, title, body, branch_suffix)
    write(f"{GREEN}Done - thanks for contributing!{RESET}")


def action_update_tags(username):
    write(f"{BOLD}{ACCENT}Update tags - choose a file{RESET}")
    node = tree_picker("file", "Pick a file to update tags")
    if node is None:
        return
    update_tags_for_node(username, node)


def update_tags_for_node(username, node):
    abs_path = CONTENT_DIR / node.path
    target_path = abs_path.parent / node.name if node.is_stub else abs_path
    tag_id = target_path.relative_to(ROOT).as_posix()
    selected = edit_tags(tag_id)
    if selected is None:
        return

    old_overrides = read_tag_overrides()
    current = old_overrides.get(tag_id, [])
    if selected == current:
        write(f"{DIM}Tags are unchanged.{RESET}")
        return
    updated_overrides = dict(old_overrides)
    if selected:
        updated_overrides[tag_id] = selected
    else:
        updated_overrides.pop(tag_id, None)
    save_tag_overrides(updated_overrides)
    if not rebuild_and_check():
        save_tag_overrides(old_overrides)
        rebuild_and_check()
        return
    if not confirm(f"Submit tag updates for '{node.name}'?"):
        save_tag_overrides(old_overrides)
        rebuild_and_check()
        write(f"{YELLOW}Tag updates cancelled.{RESET}")
        return

    title = f"tags: {pretty_name(node.name)}"
    body = detail_body(
        "update tags", target_path, old_size=abs_path.stat().st_size,
        new_size=abs_path.stat().st_size,
        extra=["- manual tags: " + (", ".join(selected) or "none")],
    )
    contribute_pipeline(username, title, body,
                        f"tags-{slugify(target_path)}")
    write(f"{GREEN}Done - thanks for contributing!{RESET}")


def update_metadata_for_node(username, node, field):
    abs_path = CONTENT_DIR / node.path
    target_path = abs_path.parent / node.name if node.is_stub else abs_path
    file_id = target_path.relative_to(ROOT).as_posix()
    old_overrides = read_metadata_overrides()
    current = {**indexed_metadata(file_id), **old_overrides.get(file_id, {})}
    current_value = current.get(field, "")
    if not current_value:
        if field == "title":
            current_value = pretty_name(node.name)
        elif node.is_stub:
            current_value = suggested_external_description(
                abs_path.read_text(encoding="utf-8").strip())
        else:
            section = target_path.parent.relative_to(CONTENT_DIR).as_posix()
            current_value = suggested_description(node.name, section)

    write(f"Current {field}: {current_value}")
    new_value = input(f"New {field} (Enter to keep current)\n> ").strip()
    if not new_value or new_value == current_value:
        write(f"{DIM}{field.title()} unchanged.{RESET}")
        return

    updated_overrides = dict(old_overrides)
    updated_entry = dict(updated_overrides.get(file_id, {}))
    updated_entry[field] = new_value
    updated_overrides[file_id] = updated_entry
    save_metadata_overrides(updated_overrides)
    if not rebuild_and_check():
        save_metadata_overrides(old_overrides)
        rebuild_and_check()
        return
    if not confirm(f"Submit the {field} update for '{node.name}'?"):
        save_metadata_overrides(old_overrides)
        rebuild_and_check()
        write(f"{YELLOW}{field.title()} update cancelled.{RESET}")
        return

    title = f"{field}: {pretty_name(node.name)}"
    size = abs_path.stat().st_size
    body = detail_body(
        f"update {field}", abs_path, old_size=size, new_size=size,
        extra=[f"- {field}: {new_value}"],
    )
    contribute_pipeline(username, title, body,
                        f"{field}-{slugify(target_path)}")
    write(f"{GREEN}Done - thanks for contributing!{RESET}")


def action_delete(username):
    write(f"{BOLD}{ACCENT}Delete - remove a file from the index{RESET}")
    node = tree_picker("file", "Pick the file to delete")
    if node is None:
        return
    abs_path = CONTENT_DIR / node.path
    paths = [abs_path]

    if node.is_stub:
        real_file = abs_path.parent / node.name
        if real_file.exists():
            write(f"'{node.name}' has both an external link and a local copy here.")
            write("  1  remove the external link only (keep the local copy)")
            write("  2  remove both")
            mode = (input("1 or 2 [1]: ").strip() or "1")
            paths = [abs_path] + ([real_file] if mode == "2" else [])
        else:
            write(f"'{node.name}' is only an external link; the link will be removed.")
    else:
        stub_path = abs_path.parent / STUB_NAME.format(target=node.name)
        if stub_path.exists():
            write(f"'{node.name}' has a local copy and an external link.")
            write("  1  remove the local copy only (keep the external link)")
            write("  2  remove both")
            mode = (input("1 or 2 [1]: ").strip() or "1")
            paths = [abs_path] + ([stub_path] if mode == "2" else [])

    old_size = sum(p.stat().st_size for p in paths)
    write(f"{RED}Do you want to delete {node.name}?{RESET}")
    if not confirm("Confirm"):
        return
    write("This cannot be undone.")
    if not confirm("Type y to really delete"):
        return

    target_path = abs_path.parent / node.name if node.is_stub else abs_path
    tag_id = target_path.relative_to(ROOT).as_posix()
    stub_path = target_path.with_name(STUB_NAME.format(target=target_path.name))
    old_overrides = read_tag_overrides()
    updated_overrides = dict(old_overrides)
    old_metadata = read_metadata_overrides()
    updated_metadata = dict(old_metadata)
    if (target_path in paths or not target_path.exists()) \
            and (stub_path in paths or not stub_path.exists()):
        updated_overrides.pop(tag_id, None)
        updated_metadata.pop(tag_id, None)
    save_tag_overrides(updated_overrides)
    save_metadata_overrides(updated_metadata)

    parked = [park(path) for path in paths]
    if not rebuild_and_check():
        for spot, original in zip(parked, paths):
            spot.replace(original)
        save_tag_overrides(old_overrides)
        save_metadata_overrides(old_metadata)
        rebuild_and_check()
        return
    title = f"delete: {pretty_name(node.name)}"
    body = detail_body("delete", paths[0], old_size=old_size, new_size=0,
                       extra=[f"- section: {paths[0].parent.relative_to(CONTENT_DIR).as_posix()}"])
    if not confirm("Submit the pull request?"):
        for spot, original in zip(parked, paths):
            spot.replace(original)
        save_tag_overrides(old_overrides)
        save_metadata_overrides(old_metadata)
        rebuild_and_check()
        write(f"{YELLOW}Cancelled locally; nothing was committed.{RESET}")
        return
    branch_suffix = f"delete-{slugify(paths[0])}"
    contribute_pipeline(username, title, body, branch_suffix)
    write(f"{GREEN}Done - thanks for contributing!{RESET}")

# ------------------------------------------------------------------- main ---


def main():
    write(f"{BOLD}{ACCENT}ITC Index - contribution tool{RESET}")
    write(f"{DIM}You will need git and the GitHub CLI; this tool checks both.{RESET}")
    write("")
    username = preflight()
    while True:
        write("")
        write(f"{BOLD}What do you want to do?{RESET}")
        write("  1  add      - add a new file or external link")
        write("  2  modify   - replace a file with an updated version")
        write("  3  delete   - remove a file")
        write("  4  tags     - update tags for a file")
        write("  q  exit")
        choice = (input("> ").strip().lower() or "")[:12]
        if choice in ("q", "quit", "exit", "bye"):
            write("Goodbye.")
            return
        action = {"1": action_add, "add": action_add,
                  "2": action_modify, "modify": action_modify,
                  "3": action_delete, "delete": action_delete,
                "del": action_delete,
                "4": action_update_tags, "tags": action_update_tags,
                "update-tags": action_update_tags}.get(choice)
        if action is None:
            write(f"{DIM}Type 1, 2, 3, 4 or q.{RESET}")
            continue
        try:
            action(username)
        except (KeyboardInterrupt, EOFError):
            write()
            write("Stopped. Nothing was committed; your partial change may "
                "still be on disk - run `git status` to see.")
        except RuntimeError as error:
            write(f"{RED}{error}{RESET}")


if __name__ == "__main__":
    main()
