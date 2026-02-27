# NIE Sri Lanka — Bulk Downloader Toolkit

Downloads textbooks, teachers' guides, and resource books from official Sri Lanka government education websites.

| Script | Source Website | What it downloads |
|--------|---------------|-------------------|
| `textbook-downloader.py` | edupub.gov.lk | Student textbooks (by grade & medium) |
| `teachers-guide-downloader.py` | nie.lk/seletguide | Teachers' guide PDFs (by grade & medium) |
| `resource-downloader.py` | nie.lk/showom | Other materials & resource books |

---

## Folder Structure

```
nie-downloader/
├── textbook-downloader.py
├── teachers-guide-downloader.py
├── resource-downloader.py
├── README.md
└── output/
    ├── textbooks/          ← textbook downloads go here
    ├── teachers-guides/    ← teachers guide downloads go here
    └── resource-books/     ← resource book downloads go here
```

---

## Prerequisites

1. **Python 3.8+** — https://www.python.org/downloads/
2. **Install dependencies** (run once):
   ```
   pip install requests beautifulsoup4
   ```

---

## 1. Textbook Downloader

**Source:** https://edupub.gov.lk

Downloads student textbooks organized by grade, medium and book/chapter.

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

Downloads teachers' guide PDFs. Each subject is one flat PDF file per grade.

### Basic usage

```bash
# Grade 10 English medium
python teachers-guide-downloader.py --grade 10 --medium english --output "output/teachers-guides/grade 10 -en"

# Grade 10 Sinhala medium
python teachers-guide-downloader.py --grade 10 --medium sinhala --output "output/teachers-guides/grade 10 -si"

# Grade 10 Tamil medium
python teachers-guide-downloader.py --grade 10 --medium tamil --output "output/teachers-guides/grade 10 -ta"
```

### All supported options

| Option | Short | Description |
|--------|-------|-------------|
| `--grade` | `-g` | Grade number 1–13 (required) |
| `--medium` | `-m` | `english` / `sinhala` / `tamil` |
| `--output` | `-o` | Output folder path |
| `--delay` | `-d` | Seconds between downloads (default: 1.0) |
| `--check` | `-c` | Audit existing downloads and repair any missing/corrupt files |

### Examples

```bash
# Download all grades 6–11 English teachers guides
python teachers-guide-downloader.py -g 6  -m english -o "output/teachers-guides/grade 6 -en"
python teachers-guide-downloader.py -g 7  -m english -o "output/teachers-guides/grade 7 -en"
python teachers-guide-downloader.py -g 8  -m english -o "output/teachers-guides/grade 8 -en"
python teachers-guide-downloader.py -g 9  -m english -o "output/teachers-guides/grade 9 -en"
python teachers-guide-downloader.py -g 10 -m english -o "output/teachers-guides/grade 10 -en"
python teachers-guide-downloader.py -g 11 -m english -o "output/teachers-guides/grade 11 -en"

# Check and repair Grade 9 teachers guides
python teachers-guide-downloader.py -g 9 -m english -o "output/teachers-guides/grade 9 -en" --check
```

---

## 3. Resource Books Downloader

**Source:** https://nie.lk/showom

Downloads other materials and resource books (A/L Biology, Chemistry, Physics, ICT, Music, Activity Books, etc.).

> **Note:** Some books (e.g. Grade 12/13 Physics and Biology resource books) are hosted on FlipHTML5 as online viewers and **cannot be bulk-downloaded**. Use `--html` to generate a clickable index page for those.

### Basic usage

```bash
# English resources
python resource-downloader.py --medium english --output "output/resource-books/resources -en"

# Sinhala resources
python resource-downloader.py --medium sinhala --output "output/resource-books/resources -si"

# Tamil resources
python resource-downloader.py --medium tamil --output "output/resource-books/resources -ta"
```

### All supported options

| Option | Short | Description |
|--------|-------|-------------|
| `--medium` | `-m` | `english` / `sinhala` / `tamil` |
| `--output` | `-o` | Output folder path |
| `--delay` | `-d` | Seconds between downloads (default: 1.0) |
| `--check` | `-c` | Audit existing downloads and repair any missing/corrupt files |
| `--pdf-only` | `-p` | Skip audio files (.wav/.mp3), download PDFs only |
| `--html` |  | Generate a local HTML index page for all 3 languages and exit |

### Examples

```bash
# PDFs only, no audio files
python resource-downloader.py -m english -o "output/resource-books/resources -en" --pdf-only

# Generate a browsable HTML index (all 3 languages, includes online-only links)
python resource-downloader.py --html --output "output/resource-books"

# Check and repair English resources
python resource-downloader.py -m english -o "output/resource-books/resources -en" --check
```

The generated `output/resource-books/index.html` opens in any browser with:
- **Download** buttons for all PDFs and audio files
- **View Online** buttons for FlipHTML5 books
- Tabs to switch between English / සිංහල / தமிழ்

---

## Using with Claude

You can run these scripts by telling Claude what you want in plain English. Claude will figure out the right command. Here are example prompts:

### Textbooks
```
Run the textbook downloader for grade 10 english medium
Download grade 11 sinhala textbooks
Run check mode on grade 9 english textbooks
Download only Mathematics and Science for grade 10 english
```

### Teachers' Guides
```
Run the teachers guide downloader for grade 10 english
Download grade 12 sinhala teachers guides
Check and repair grade 11 teachers guides english medium
```

### Resource Books
```
Run the resource downloader for english medium
Download resource books for all three languages
Generate the HTML index for resource books
Run check mode on english resource books
```

### Multiple grades at once
```
Download textbooks for grades 9, 10 and 11 english medium
Run teachers guide downloader for grades 6 through 11 english
```

---

## Resume & Retry

All three scripts support **automatic resume** if a download is interrupted:
- Partially downloaded files are resumed using HTTP Range requests
- Each file is retried up to 5 times with increasing wait times (5s, 10s, 15s…)
- Running the same command again skips already-valid files automatically

## PDF Validation

Downloaded PDFs are validated with a 3-level check:
- `valid` — correct PDF header + footer, ≥ 50 KB
- `partial` — PDF header present but incomplete (will be resumed)
- `corrupt` — wrong content or too small (will be re-downloaded)

Use `--check` on any script to audit and automatically fix partial/corrupt files.
