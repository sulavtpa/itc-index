"""Validate index.json against the real files under public/content."""

import json
import re
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent
CONTENT_DIR = ROOT / "public" / "content"
INDEX_FILE = ROOT / "public" / "index.json"
STUB_PREFIX = "(external)-"
STUB_SUFFIX = ".txt"
URL_PATTERN = re.compile(r"https://\S+")
REQUIRED = {"id", "title", "tags", "description", "size", "ext", "icon", "source"}


def read_json(path):
    try:
        with path.open(encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        raise ValueError(f"Required file is missing: {path.relative_to(ROOT)}") from None
    except json.JSONDecodeError as error:
        raise ValueError(
            f"Invalid JSON in {path.relative_to(ROOT)} at line {error.lineno}, "
            f"column {error.colno}: {error.msg}"
        ) from None


def content_files():
    files = {}
    stubs = {}
    for path in CONTENT_DIR.rglob("*"):
        if not path.is_file() or path.name.startswith("."):
            continue
        if path.name == "README.md":
            continue  # empty-folder placeholder, never content
        rel = path.relative_to(ROOT).as_posix()
        if path.name.startswith(STUB_PREFIX):
            stubs[path.name] = path
        else:
            files[rel] = path
    return files, stubs


def check():
    issues = []
    files, stubs = content_files()
    index = read_json(INDEX_FILE)
    if not isinstance(index, list):
        raise ValueError("index.json must contain a list of file entries.")

    indexed = set()
    for position, entry in enumerate(index, start=1):
        label = f"index.json entry {position}"
        if not isinstance(entry, dict):
            issues.append(f"{label} must be an object.")
            continue
        for field in sorted(REQUIRED - set(entry)):
            issues.append(f"{label} is missing {field!r}.")

        file_id = entry.get("id")
        if not isinstance(file_id, str) or not file_id.strip():
            issues.append(f"{label} has an empty or invalid id.")
            continue
        parsed = PurePosixPath(file_id)
        if parsed.is_absolute() or ".." in parsed.parts or "\\" in file_id:
            issues.append(f"{label} id is not a safe relative path: {file_id}")
            continue
        if file_id in indexed:
            issues.append(f"Duplicate id: {file_id}")
        indexed.add(file_id)

        source = entry.get("source")
        if source == "repo":
            if file_id not in files:
                issues.append(f"Indexed file does not exist: {file_id}")
        elif source == "external":
            stub_name = f"{STUB_PREFIX}{Path(file_id).name}{STUB_SUFFIX}"
            stub_dir = CONTENT_DIR.joinpath(*parsed.parent.parts[2:]) \
                if len(parsed.parent.parts) > 2 else CONTENT_DIR
            stub_path = stub_dir / stub_name
            if not stub_path.is_file():
                issues.append(f"External entry has no stub file: {file_id}")
            else:
                url = stub_path.read_text(encoding="utf-8").strip()
                entry_link = entry.get("link")
                if not URL_PATTERN.fullmatch(url):
                    issues.append(f"Stub for {file_id} does not contain a valid https URL.")
                elif entry_link != url:
                    issues.append(f"Stub and index link differ for: {file_id}")
            if not isinstance(entry.get("link"), str) or not entry.get("link"):
                issues.append(f"{label} (external) has no link.")
        else:
            issues.append(f"{label} has unknown source {source!r}.")

        for field in ("title", "description"):
            value = entry.get(field)
            if not isinstance(value, str) or not value.strip():
                issues.append(f"{label} has an empty or invalid {field}.")
        tags = entry.get("tags")
        if not isinstance(tags, list) or not tags:
            issues.append(f"{label} has empty or invalid tags.")
        elif any(not isinstance(t, str) or not t.strip() for t in tags):
            issues.append(f"{label} has an invalid tag item.")
        size = entry.get("size")
        if not isinstance(size, int) or size < 0:
            if source != "external":
                issues.append(f"{label} has invalid size {size!r}.")

    for file_id in sorted(set(files) - indexed):
        issues.append(f"File has no index entry: {file_id}")
    # Orphan-stub check: a stub whose target name matches no external entry.
    externals = {Path(e["id"]).name for e in index
                 if isinstance(e, dict) and e.get("source") == "external"}
    for stub_name in sorted(stubs):
        target = stub_name[len(STUB_PREFIX):-len(STUB_SUFFIX)]
        if target not in externals:
            issues.append(f"External stub is not indexed: {stub_name} (target: {target})")

    if issues:
        print(f"Checks failed with {len(issues)} issue(s):")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print(f"All checks passed: {len(index)} entries "
          f"({len(files)} repo files, {len(stubs)} external stubs).")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(check())
    except ValueError as error:
        print(f"Checks could not run: {error}")
        sys.exit(1)
