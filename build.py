"""Build the client-side index from files under public/content.

Every file in public/content is indexed. A file named like
"(external)-<real-name>.ext.txt" is an external-host pointer stub: its body
holds a download URL and it is indexed as "<real-name>.ext" with
source="external". Contributors create a stub when a file is too big for the
repository.

Output: index.json at the repo root, consumed by the site.
"""

import json
import re
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent
CONTENT_DIR = ROOT / "public" / "content"
COURSE_DATA = ROOT / "course.json"
INDEX_FILE = ROOT / "public" / "index.json"

STUB_PREFIX = "(external)-"
STUB_SUFFIX = ".txt"

# content sub-folder -> department short, resolved through course.json
FOLDER_NAMES = {
    "bit": "bit",
    "arch": "arch",
    "civil": "civil",
    "comp": "computer",
    "bca": "bca-it",
    "eca": "elx",
}
DEPARTMENT_TAGS = {
    "arch": "BE Architecture",
    "civil": "BE Civil Engineering",
    "comp": "BE Computer Engineering",
    "eca": "BE Electronics & Communication Engineering",
    "bit": "BIT",
    "bca": "BCA-IT",
}
CATEGORY_TAGS = {
    "courses": "Study Material",
    "past-questions": "Past Question",
    "syllabus": "Syllabus",
    "timetable": "Timetable",
    "projects": "Project",
    "misc": "Miscellaneous",
}
CONTENT_TAGS = {
    "Administrative": (("administrative", "administration", "admin"),),
    "Bus": (("bus",),),
    "Forum": (("forum", "forums"),),
    "Renewal": (("renewal", "renewals"),),
    "LaTeX": (("latex", "tex"),),
    "Guide": (("guide", "guides"),),
    "Note": (("note", "notes"),),
}
ORDINALS = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th", 5: "5th",
            6: "6th", 7: "7th", 8: "8th", 9: "9th", 10: "10th"}
SEMESTER_PATTERN = re.compile(r"(?<!\d)(\d+)(?:st|nd|rd|th)-sem(?:ester)?(?:-|$)", re.I)
URL_PATTERN = re.compile(r"https://\S+")
ICON_MAP = {
    ".md": "text", ".txt": "text",
    ".pdf": "pdf",
}
ICON_MAP.update({ext: "image" for ext in
                 (".avif", ".bmp", ".gif", ".jpeg", ".jpg", ".png", ".svg", ".webp")})
ICON_MAP.update({ext: "code" for ext in
                 (".css", ".html", ".js", ".json", ".py", ".ts", ".tsx",
                  ".c", ".cpp", ".h", ".java")})
ICON_MAP.update({ext: "archive" for ext in (".7z", ".rar", ".zip")})
ICON_MAP.update({ext: "video" for ext in (".mov", ".mp4", ".mkv", ".webm")})
DEFAULT_ICON = "unknown"


def read_course_data():
    with COURSE_DATA.open(encoding="utf-8") as file:
        data = json.load(file)
    departments = data.get("departments")
    if not isinstance(departments, list):
        raise ValueError("course.json must contain a departments list")
    return departments


def department_maps():
    """Build folder -> (display name, tag label) from course.json."""
    names = {dept["short"]: dept["name"] for dept in read_course_data()}
    mapping = {}

    def register(folder, short):
        label = DEPARTMENT_TAGS.get(short)
        if not label:
            # e.g. "BE Computer Engineering" missing in DEPARTMENT_TAGS
            label = names.get(short, folder.replace("-", " ").title())
        mapping[folder] = (names.get(short, label), label)

    for short, folder in FOLDER_NAMES.items():
        register(folder, short)
        register(short, short)  # allow folder to literally be the short form
    return mapping


def pretty(text):
    return re.sub(r"[-_]+", " ", text).strip().title()


def pretty_root(root):
    return root.replace("-", " ")


def semester_from(parts):
    for part in parts:
        match = SEMESTER_PATTERN.search(part)
        if match:
            return int(match.group(1))
    return None


def department_from(parts, dept_by_folder):
    for part in parts:
        if part in dept_by_folder:
            return part, dept_by_folder[part]
    return None, None


def host_for(url):
    host = PurePosixPath(url.split("://", 1)[-1].split("/", 1)[0]).parts[0] \
        if url else ""
    host = host.split(":")[0].lower().removeprefix("www.")
    if "mega.nz" in host or "mega.io" in host:
        return "mega"
    if "drive.google" in host or "docs.google" in host:
        return "drive"
    if "dropbox" in host:
        return "dropbox"
    return None


def icon_for(suffix):
    return ICON_MAP.get(suffix.lower(), DEFAULT_ICON)


def scan_real_files():
    real = {}
    for path in CONTENT_DIR.rglob("*"):
        if not path.is_file() or path.name.startswith("."):
            continue
        if path.name.startswith(STUB_PREFIX):
            continue
        real[path.relative_to(ROOT).as_posix()] = path
    return real


def describe_parts(part_path, *, name, stub_url=None, dept_by_folder, names_by_short):
    """Create an index entry for one file (real path or virtual stub target)."""
    parts = PurePosixPath(part_path.as_posix()).parts
    if len(parts) < 2:
        raise ValueError(f"'{part_path}' is a loose file directly under content/. "
                         "Put files inside one of the sections: " +
                         ", ".join(sorted(CATEGORY_TAGS)))
    section = parts[0]
    dirs = parts[:-1]
    stem = Path(name).stem
    suffix = Path(name).suffix
    semester = semester_from((*dirs, stem))
    semester_label = f"{ORDINALS.get(semester, str(semester))} Semester" \
        if semester else None
    year = (semester + 1) // 2 if semester else None
    folder, dept = department_from(dirs + (Path(name).stem,), dept_by_folder)
    dept_name, dept_tag = dept if dept else (None, None)
    if dept_tag is None:  # stub stems can carry the department short form
        token = re.sub(r"[-_]+", " ", stem).lower()
        for short, display_name in names_by_short.items():
            if f" {short} " in f" {token} ":
                dept_name, dept_tag = display_name, DEPARTMENT_TAGS.get(short, display_name)
                break

    is_table = section == "courses" and semester and bool(dept_tag)
    if is_table:
        title = f"{semester_label} Courses Table for {dept_name}"
        description = f"Course structure for the {semester_label.lower()} of {dept_name}."
    else:
        title = pretty(stem)
        description = (f"{suffix[1:].upper() if suffix else 'File'} in the "
                       f"{pretty_root(section)} section.")

    tags = []
    if section in CATEGORY_TAGS:
        tags.append(CATEGORY_TAGS[section])
    if dept_tag:
        tags.append(dept_tag)
    if semester_label:
        tags.append(semester_label)
        if year:
            tags.append(f"{ORDINALS[year]} Year")
    haystack = " ".join((*parts, stem))
    searchable = re.sub(r"[^a-z0-9]+", " ", haystack.lower())
    tokens = set(searchable.split())
    for label, phrases in CONTENT_TAGS.items():
        if any(phrase in searchable if " " in phrase else phrase in tokens
               for phrase in phrases):
            tags.append(label)
    tags = dedupe(tags)

    base = {
        "id": None,
        "title": re.sub(r"\s+", " ", title).strip(),
        "tags": tags,
        "description": description,
        "size": 0,
        "ext": suffix.lstrip(".").lower() if suffix else "",
        "icon": icon_for(suffix),
        "section": section,
    }
    return base


def build():
    dept_by_folder = {}
    names_by_short = {}
    departments = read_course_data()
    for dept in departments:
        short = dept["short"]
        names_by_short[short] = dept["name"]
        folder = FOLDER_NAMES.get(short, short)
        label = DEPARTMENT_TAGS.get(short) or dept["name"]
        dept_by_folder[folder] = (dept["name"], label)
        dept_by_folder.setdefault(short, (dept["name"], label))

    documents = []
    real_files = scan_real_files()

    for rel, path in real_files.items():
        doc = describe_parts(
            path.relative_to(CONTENT_DIR),
            name=path.name,
            dept_by_folder=dept_by_folder,
            names_by_short=names_by_short,
            stub_url=None,
        )
        doc["id"] = rel
        doc["size"] = path.stat().st_size
        doc["source"] = "repo"
        documents.append(doc)

    for path in sorted(CONTENT_DIR.rglob("*")):
        if not path.is_file() or not path.name.startswith(STUB_PREFIX):
            continue
        target_name = path.name[len(STUB_PREFIX):][:-len(STUB_SUFFIX)]
        if not target_name or "/" in target_name or "\\" in target_name \
                or target_name in (".", ".."):
            raise ValueError(
                f"External stub '{path.relative_to(ROOT)}' must be named like\n"
                f"  {STUB_PREFIX}<file-name>.<ext>{STUB_SUFFIX} (got '{path.name}')"
            )
        url = path.read_text(encoding="utf-8").strip()
        if not URL_PATTERN.fullmatch(url):
            raise ValueError(
                f"External stub '{path.relative_to(ROOT)}' must contain exactly one "
                f"https download URL and nothing else (body: {url!r})."
            )
        if (path.with_name(target_name)).exists():
            raise ValueError(
                f"External stub '{path.relative_to(ROOT)}' shadows the real file "
                f"'{target_name}'. Delete one of them."
            )
        file_id = path.relative_to(CONTENT_DIR).with_name(target_name).as_posix()
        url = path.read_text(encoding="utf-8").strip()
        doc = describe_parts(
            path.with_name(target_name).relative_to(CONTENT_DIR),
            name=target_name,
            dept_by_folder=dept_by_folder,
            names_by_short=names_by_short,
            stub_url=url,
        )
        doc["id"] = f"public/content/{file_id}"
        doc["source"] = "external"
        doc["link"] = url
        host = host_for(url)
        if host:
            doc["host"] = host
        doc["description"] = (f"Hosted on {host}, not in the repository."
                              if host else
                              "Hosted externally, not in the repository.")
        if any(d["id"] == doc["id"] for d in documents):
            raise ValueError(f"External stub '{path.relative_to(ROOT)}' duplicates id "
                             f"{doc['id']} already produced by a real file or stub.")
        documents.append(doc)

    documents.sort(key=lambda d: d["id"])
    INDEX_FILE.write_text(
        json.dumps(documents, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    external = sum(1 for d in documents if d["source"] == "external")
    print(f"Indexed {len(documents)} files ({external} external).")


def dedupe(items):
    out = []
    for item in items:
        if item and item not in out:
            out.append(item)
    return out


if __name__ == "__main__":
    build()
