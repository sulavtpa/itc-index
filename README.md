# ITC Index

A fast, searchable file index for IT Circle resources at Khwopa Engineering
College (KhEC). The site is built with SolidJS and hosted on Vercel; course
content lives in this repository under `public/content/`, and files that are
too large for GitHub are linked from external hosts (MEGA, Google Drive, â€¦).

## Sections

Files are organised by section under `public/content/`:

```
public/content/
  courses/            per-semester course tables (generated .webp images)
  past-questions/     old question papers
  syllabus/           official syllabus documents
  timetable/          class schedules
  projects/           student projects
  misc/               anything else worth keeping
```

New folders can be added anytime â€” the build treats the first folder level as
a section automatically.

### External files

When a file is too big for the repository (guideline: 25 MB), do not put it
in the repo. Create a small stub file instead:

```
public/content/misc/(external)-big-recording.mp4.txt
```

and put the download URL (one line) in the file. The build indexes it as
`big-recording.mp4` with an "Open on MEGA / Drive" button instead of a direct
download. The `contribute.py` tool does this for you.

## Building the index

After adding or changing files, always run:

```powershell
py build.py
py checks.py
```

`build.py` scans `public/content/` and writes `public/index.json` (titles,
tags, sizes, icons, external links). `checks.py` verifies everything is
consistent. The index file is committed together with the content.

## Contributing a file (no git knowledge needed)

```powershell
py contribute.py
```

The tool walks you through **add / modify / delete**, opens a file picker,
rebuilds the index, runs the checks and then:

1. creates a `contrib/â€¦` branch,
2. commits with a detailed message,
3. pushes to your fork,
4. opens a pull request â€” all automatically via the GitHub CLI (gh).

Requirements: `git`, GitHub CLI (`gh`, signed in with `gh auth login`), and
Python 3. The tool guides you through installing whichever is missing.

## Development

```powershell
npm install     # once
npm run dev     # local dev server
npm run build   # production build to dist/
py make_table.py            # regenerate course-table images (needs pillow)
```

Vercel deploys the site automatically: build command `vite build`, output
directory `dist`. `public/` is copied into the build, which is how
`index.json`, the icons and the content files ship.

## Tag colors

Tags are colored automatically â€” the color is derived from a hash of the tag
name (deterministic, low-saturation, tuned for the light theme), so there is
no color configuration file to maintain.
