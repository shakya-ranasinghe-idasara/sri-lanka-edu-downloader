# NIE Sri Lanka — Bulk Downloader & Study Tools Toolkit

Downloads textbooks, teachers' guides, and resource books from official Sri Lanka government education websites, and generates structured short notes from teacher's guides using AI.

| Script | Source / Tool | What it does |
|--------|--------------|--------------|
| `textbook-downloader.py` | edupub.gov.lk | Downloads student textbooks (by grade & medium) |
| `teachers-guide-downloader.py` | nie.lk/seletguide | Downloads teachers' guide PDFs (by grade & medium) |
| `resource-downloader.py` | nie.lk/showom | Downloads other materials & resource books |
| `short-notes-generator.py` | DeepSeek AI | Generates per-lesson short notes from teacher's guides |

---

## Folder Structure

```
nie-downloader/
├── textbook-downloader.py
├── teachers-guide-downloader.py
├── resource-downloader.py
├── short-notes-generator.py
├── README.md
└── output/
    ├── textbooks/                    ← textbook downloads
    │   ├── grade 10 -en/
    │   │   ├── Mathematics I/
    │   │   └── Science/
    │   └── grade 10 -si/
    ├── teachers-guides/              ← teachers guide downloads
    │   ├── grade 10 -en/
    │   └── grade 10 -si/
    ├── resource-books/               ← resource book downloads
    │   ├── resources -en/
    │   └── resources -si/
    └── short-notes/                  ← AI-generated short notes
        ├── english-medium/
        │   ├── grade 9/
        │   │   └── History/
        │   │       ├── Lesson 01 - ....docx
        │   │       └── Lesson 02 - ....docx
        │   └── grade 10/
        │       └── Science/
        └── sinhala-medium/
```

---

## Prerequisites

1. **Python 3.8+** — https://www.python.org/downloads/
2. **Install dependencies** (run once):
   ```bash
   # For downloaders
   pip install requests beautifulsoup4

   # For short notes generator (additional)
   pip install openai pdfplumber python-docx
   ```
3. **DeepSeek API key** (for short notes generator only) — https://platform.deepseek.com

---

## 1. Textbook Downloader

**Source:** https://edupub.gov.lk

Downloads student textbooks organized by grade, medium, book and chapter.

### Basic usage

```bash
# Grade 10 English medium
python textbook-downloader.py --grade 10 --medium english --output "output/textbooks/grade 10 -en"

# Grade 10 Sinhala medium
python textbook-downloader.py --grade 10 --medium sinhala --output "output/textbooks/grade 10 -si"

# Grade 10 Tamil medium
python textbook-downloader.py --grade 10 --medium tamil --output "output/textbooks/grade 10 -ta"
```

### All supported options

| Option | Short | Description |
|--------|-------|-------------|
| `--grade` | `-g` | Grade number 1–13 (required) |
| `--medium` | `-m` | `english` / `sinhala` / `tamil` |
| `--output` | `-o` | Output folder path |
| `--delay` | `-d` | Seconds between downloads (default: 1.5) |
| `--books` | `-b` | Download specific books only, e.g. `"Mathematics,Science"` |
| `--check` | `-c` | Audit existing downloads and repair any missing/corrupt files |

### Examples

```bash
# Download only Mathematics and Science for Grade 11
python textbook-downloader.py -g 11 -m english -o "output/textbooks/grade 11 -en" --books "Mathematics,Science"

# Check and repair Grade 10 downloads
python textbook-downloader.py -g 10 -m english -o "output/textbooks/grade 10 -en" --check
```

---

## 2. Teachers' Guide Downloader

**Source:** https://nie.lk/seletguide

Downloads teachers' guide PDFs. Optionally organises them into per-subject subfolders.

### Basic usage

```bash
# Grade 10 English medium
python teachers-guide-downloader.py --grade 10 --medium english --output "output/teachers-guides/grade 10 -en"

# Grade 10 Sinhala medium
python teachers-guide-downloader.py --grade 10 --medium sinhala --output "output/teachers-guides/grade 10 -si"

# Save each guide in its own subject subfolder
python teachers-guide-downloader.py --grade 10 --medium english \
    --output "output/teachers-guides/grade 10 -en" --by-subject
```

### All supported options

| Option | Short | Description |
|--------|-------|-------------|
| `--grade` | `-g` | Grade number 1–13 (required) |
| `--medium` | `-m` | `english` / `sinhala` / `tamil` |
| `--output` | `-o` | Output folder path |
| `--delay` | `-d` | Seconds between downloads (default: 1.0) |
| `--check` | `-c` | Audit existing downloads and repair any missing/corrupt files |
| `--by-subject` | | Save each guide in its own subject subfolder |

### Examples

```bash
# Download all grades 6–11 English teachers guides
for g in 6 7 8 9 10 11; do
  python teachers-guide-downloader.py -g $g -m english -o "output/teachers-guides/grade $g -en"
done

# Download Grade 12 & 13 into per-subject folders
python teachers-guide-downloader.py -g 12 -m english \
    -o "output/teachers-guides/grade 12 -en" --by-subject
python teachers-guide-downloader.py -g 13 -m english \
    -o "output/teachers-guides/grade 13 -en" --by-subject

# Check and repair Grade 9 teachers guides
python teachers-guide-downloader.py -g 9 -m english -o "output/teachers-guides/grade 9 -en" --check
```

---

## 3. Resource Books Downloader

**Source:** https://nie.lk/showom

Downloads other materials and resource books (A/L Biology, Chemistry, Physics, ICT, Music, Activity Books, etc.).

> **Note:** Some books are hosted on FlipHTML5 as online viewers and **cannot be bulk-downloaded**. Use `--html` to generate a clickable index page for those.

### Basic usage

```bash
# English resources
python resource-downloader.py --medium english --output "output/resource-books/resources -en"

# Sinhala resources
python resource-downloader.py --medium sinhala --output "output/resource-books/resources -si"

# Organised into subject subfolders (Biology/, Chemistry/, etc.)
python resource-downloader.py --medium english \
    --output "output/resource-books/resources -en" --by-subject
```

### All supported options

| Option | Short | Description |
|--------|-------|-------------|
| `--medium` | `-m` | `english` / `sinhala` / `tamil` |
| `--output` | `-o` | Output folder path |
| `--delay` | `-d` | Seconds between downloads (default: 1.0) |
| `--check` | `-c` | Audit existing downloads and repair any missing/corrupt files |
| `--pdf-only` | `-p` | Skip audio files (.wav/.mp3), download PDFs only |
| `--by-subject` | | Organise downloads into subject subfolders |
| `--html` | | Generate a local HTML index page for all 3 languages and exit |

### Examples

```bash
# PDFs only, no audio files
python resource-downloader.py -m english -o "output/resource-books/resources -en" --pdf-only

# Generate a browsable HTML index (all 3 languages, includes online-only links)
python resource-downloader.py --html --output "output/resource-books"

# Check and repair English resources
python resource-downloader.py -m english -o "output/resource-books/resources -en" --check
```

---

## 4. Short Notes Generator

**Requires:** DeepSeek API key — set via `--api-key` or `DEEPSEEK_API_KEY` environment variable.

Reads a NIE teacher's guide PDF and uses DeepSeek AI to generate structured short notes for every lesson, saved as individual Word (`.docx`) files.

**Lesson divisions come from the teacher's guide** — the AI uses the guide's lesson numbers and titles as the authoritative structure, then builds detailed notes from the guide content. A textbook PDF can optionally be added to enrich the notes.

### Output structure

```
output/short-notes/<medium>-medium/grade <N>/<Subject>/
    Lesson 01 - Title.docx
    Lesson 02 - Title.docx
    ...
    Grade N - Subject - notes.json
```

### Each lesson note contains 6 sections

| Section | Content |
|---------|---------|
| 1. Core Concepts | Definition, plain-language explanation, real-world analogy, diagram reference, links to other concepts |
| 2. Key Formulas / Definitions / Rules | Split into Revision and New — each with a step-by-step worked example |
| 3. Worked Examples | 2–4 fully solved exam-style problems with numbered steps, tricky parts highlighted, common mistakes |
| 4. Diagrams & Visual Descriptions | Every diagram described: what it shows, labels, relationships, key learning |
| 5. Tips & Tricks for Exams | Practical tips with mark allocation and frequency information |
| 6. Important Points to Remember | Must-know facts and an exam checklist |

### Basic usage

```bash
# Teacher's guide only (lesson structure + content from guide)
python short-notes-generator.py \
    --guide "output/teachers-guides/grade 9 -en/History (2018).pdf" \
    --grade 9 --medium english

# Teacher's guide + textbook for richer notes
python short-notes-generator.py \
    --guide  "output/teachers-guides/grade 10 -en/Science/Science (2018).pdf" \
    --pdf    "output/textbooks/grade 10 -en/Science Part I/Science.pdf" \
    --grade 10 --medium english

# Teacher's guide folder (multiple PDFs)
python short-notes-generator.py \
    --guide-folder "output/teachers-guides/grade 10 -en/Mathematics/" \
    --grade 10 --medium english

# Set API key as environment variable
export DEEPSEEK_API_KEY="sk-..."
python short-notes-generator.py --guide "..." --grade 10
```

### All supported options

| Option | Short | Description |
|--------|-------|-------------|
| `--guide` | `-G` | Teacher's guide single PDF (primary lesson source) |
| `--guide-folder` | `-GF` | Folder of teacher's guide PDFs |
| `--pdf` | `-f` | Textbook single PDF (supplementary, optional) |
| `--folder` | `-F` | Textbook folder (supplementary, optional) |
| `--grade` | `-g` | Grade number (required) |
| `--medium` | `-m` | `english` / `sinhala` / `tamil` (default: `english`) |
| `--subject` | `-s` | Subject name hint (auto-detected if omitted) |
| `--output` | `-o` | Base output root folder |
| `--api-key` | `-k` | DeepSeek API key |
| `--max-pages` | | Limit pages extracted per PDF |
| `--lesson` | | Retry/generate a single lesson number only |
| `--lesson-title` | | Title for `--lesson` (required with `--lesson`) |

### Retrying a failed lesson

If a lesson fails due to a network or parsing error, retry just that one:

```bash
python short-notes-generator.py \
    --guide "output/teachers-guides/grade 9 -en/History (2018).pdf" \
    --grade 9 --medium english \
    --lesson 5 \
    --lesson-title "Constitutional Reforms and National Independence Movement"
```

---

## Using with Claude

You can run these scripts by telling Claude what you want in plain English:

### Downloading
```
Download grade 10 english medium textbooks
Download grade 9 sinhala medium textbooks
Download teachers guides for grade 12 english in separate subject folders
Download english resource books organised by subject
Run check mode on grade 10 sinhala textbooks
```

### Short Notes
```
Create short notes for grade 9 History
Generate short notes for grade 10 Science english medium
Retry lesson 5 for grade 9 History short notes
```

---

## Resume & Retry

All downloader scripts support **automatic resume** if a download is interrupted:
- Partially downloaded files are resumed using HTTP Range requests
- Each file is retried up to 5 times with increasing wait times (5s, 10s, 15s…)
- Running the same command again skips already-valid files automatically

## PDF Validation

Downloaded PDFs are validated with a 3-level check:

| Status | Meaning |
|--------|---------|
| `valid` | Correct PDF header + footer, ≥ 50 KB |
| `partial` | PDF header present but file is incomplete (will be resumed) |
| `corrupt` | Wrong content or too small (will be re-downloaded) |

Use `--check` on any downloader script to audit and automatically fix partial/corrupt files.
