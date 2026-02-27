"""
Sri Lanka Educational Publications Department - Bulk Textbook Downloader
Website: http://www.edupub.gov.lk/BooksDownload.php

Flow:
  1. POST SelectSyllabuss.php  → list of books (.SelectSyllabuss elements)
  2. POST SelectChapter.php    → chapter PDF links (class="SelectChapter")
  3. Download PDFs with HTTP Range resume support

Folder structure:
  <output>/
    <Book Title>/
      <Chapter Name>.pdf
      <Chapter Name>.pdf
      ...

Usage:
    python textbook-downloader.py --grade 10 --medium english --output "grade 10 -en"
    python textbook-downloader.py --grade 10 --medium english --books "Mathematics,Science"
    python textbook-downloader.py --grade 10 --medium english --output "grade 10 -en" --check

Requirements:
    pip install requests beautifulsoup4
"""

import requests
from bs4 import BeautifulSoup
import os
import re
import sys
import argparse
import time
from urllib.parse import urljoin, unquote

sys.stdout.reconfigure(encoding='utf-8')

BASE_URL     = "http://www.edupub.gov.lk/"
DOWNLOAD_URL = "http://www.edupub.gov.lk/BooksDownload.php"
SYLLABUS_URL = "http://www.edupub.gov.lk/SelectSyllabuss.php"
CHAPTER_URL  = "http://www.edupub.gov.lk/SelectChapter.php"

MEDIUM_MAP = {
    "english": ("1", "English"),
    "sinhala": ("2", "Sinhala"),
    "tamil":   ("3", "Tamil"),
}


def grade_to_value(grade_str):
    g = int(grade_str)
    return "17" if g in (12, 13) else str(g)


def clean_filename(name):
    """Remove characters invalid in Windows filenames/folder names."""
    name = unquote(name)
    name = re.sub(r'[<>:"/\\|?*\n\r\t]', '_', name)
    name = name.strip('. ')
    return name[:200] if name else 'unknown'


def pdf_status(filepath):
    """
    Classify a file:
      'valid'   — complete PDF (%PDF- header + %%EOF footer, ≥ 50 KB)
      'partial' — has %PDF- header but no %%EOF (mid-download, resumable)
      'corrupt' — wrong/tiny content
      'missing' — does not exist
    """
    if not os.path.exists(filepath):
        return 'missing'
    try:
        size = os.path.getsize(filepath)
        if size < 50 * 1024:
            return 'corrupt'
        with open(filepath, 'rb') as f:
            header = f.read(5)
            if header != b'%PDF-':
                return 'corrupt'
            f.seek(max(0, size - 1024))
            tail = f.read()
            return 'valid' if b'%%EOF' in tail else 'partial'
    except OSError:
        return 'missing'


# ── Site interaction ──────────────────────────────────────────────────────────

def get_book_list(grade_val, medium_id, medium_name, session):
    print(f"\n📚 Fetching book list (BookLanguage={medium_id}, BookGrade={grade_val})...")
    resp = session.post(SYLLABUS_URL,
                        data={'BookLanguage': medium_id, 'BookGrade': grade_val},
                        timeout=30)
    resp.encoding = 'utf-8'
    soup = BeautifulSoup(resp.text, 'html.parser')
    books, seen = [], set()
    for el in soup.find_all(True, {'class': 'SelectSyllabuss'}):
        book_id   = el.get('bookid')   or el.get('bookId')
        book_name = el.get('bookname') or el.get('bookName') or el.get_text(strip=True)
        if book_id and book_id not in seen:
            seen.add(book_id)
            title = el.get_text(strip=True) or book_name
            books.append({'bookId': book_id, 'bookName': book_name, 'title': title})
    print(f"   Found {len(books)} books.")
    if not books:
        debug = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'debug_syllabus.html')
        with open(debug, 'w', encoding='utf-8') as f:
            f.write(resp.text)
        print(f"   ⚠️  No books found. Debug HTML saved to: {debug}")
    return books


def filter_books(books, patterns):
    lower = [p.strip().lower() for p in patterns if p.strip()]
    return [b for b in books if any(p in (b['title'] or b['bookName']).lower()
                                    for p in lower)]


def get_chapter_pdfs(book, grade_val, medium_name, session, save_debug=False):
    """
    Returns list of dicts: {'url', 'book_title', 'chapter_name'}
    book_title  → used as the subfolder name
    chapter_name → used as the filename inside the subfolder
    """
    resp = session.post(CHAPTER_URL, data={
        'bookId':           book['bookId'],
        'BookGrade':        grade_val,
        'BookLanguageView': medium_name,
        'bookName':         book['bookName'],
    }, timeout=30)
    resp.encoding = 'utf-8'

    if save_debug:
        debug = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'debug_chapter.html')
        with open(debug, 'w', encoding='utf-8') as f:
            f.write(resp.text)

    soup       = BeautifulSoup(resp.text, 'html.parser')
    book_title = clean_filename(book['title'] or book['bookName'])
    PLACEHOLDER = 'downloads/pdf.pdf'
    pdfs, seen = [], set()

    for a in soup.find_all('a', class_='SelectChapter', href=True):
        href = a['href']
        if '.pdf' not in href.lower() or PLACEHOLDER in href.lower():
            continue
        full_url = urljoin(BASE_URL, href)
        if full_url in seen:
            continue
        seen.add(full_url)
        label        = a.get_text(strip=True)
        chapter_name = clean_filename(label) if label else clean_filename(os.path.basename(href))
        pdfs.append({'url': full_url, 'book_title': book_title, 'chapter_name': chapter_name})

    # Fallback: any Administrator/ PDF not found above
    if not pdfs:
        for a in soup.find_all('a', href=True):
            href = a['href']
            if PLACEHOLDER in href.lower():
                continue
            if 'administrator' in href.lower() and '.pdf' in href.lower():
                full_url = urljoin(BASE_URL, href)
                if full_url not in seen:
                    seen.add(full_url)
                    label        = a.get_text(strip=True) or clean_filename(os.path.basename(href))
                    chapter_name = clean_filename(label)
                    pdfs.append({'url': full_url, 'book_title': book_title,
                                 'chapter_name': chapter_name})
    return pdfs


def collect_all_pdfs(books, grade_val, medium_name, session):
    print(f"\n🔍 Collecting chapter PDFs for {len(books)} book(s)...")
    all_pdfs = []
    for i, book in enumerate(books):
        label = book['title'] or book['bookName']
        print(f"   [{i+1}/{len(books)}] {label}")
        chapters = get_chapter_pdfs(book, grade_val, medium_name, session, save_debug=(i == 0))
        if chapters:
            print(f"     → {len(chapters)} chapter(s) found")
            all_pdfs.extend(chapters)
        else:
            print(f"     ✘ No PDFs found (bookId={book['bookId']})")
        time.sleep(0.5)
    return all_pdfs


# ── File path helper ──────────────────────────────────────────────────────────

def get_filepath(pdf, output_dir):
    """
    Returns the full path for a PDF and ensures its book subfolder exists.
    Structure: <output_dir>/<book_title>/<chapter_name>.pdf
    """
    book_dir = os.path.join(output_dir, pdf['book_title'])
    os.makedirs(book_dir, exist_ok=True)
    return os.path.join(book_dir, f"{pdf['chapter_name']}.pdf")


# ── Download with Range resume ────────────────────────────────────────────────

def download_file(url, filepath, session, max_retries=5):
    """
    Download a PDF with:
      - HTTP Range resume: if a partial file exists, continue from the last byte
      - Automatic retry (up to max_retries) with growing wait (5 / 10 / 15 / 20 s)
      - Timeout tuple (10 s connect, 300 s between-bytes) to handle slow servers
      - Partial files are KEPT on failure so the next run can resume
    """
    for attempt in range(1, max_retries + 1):
        try:
            # ── Resume support ────────────────────────────────────────────────
            resume_from = 0
            req_headers = {}
            if os.path.exists(filepath):
                size = os.path.getsize(filepath)
                if size > 0:
                    resume_from = size
                    req_headers['Range'] = f'bytes={resume_from}-'

            resp = session.get(url, stream=True,
                               timeout=(10, 300),
                               headers=req_headers)

            # 416 = Range Not Satisfiable (server doesn't support it, or we're past EOF)
            if resp.status_code == 416:
                resume_from = 0
                req_headers  = {}
                resp.close()
                resp = session.get(url, stream=True, timeout=(10, 300))
                resp.raise_for_status()
            elif resp.status_code not in (200, 206):
                resp.raise_for_status()

            resuming = (resp.status_code == 206)
            if not resuming:
                resume_from = 0
                # Only honour Content-Disposition on a fresh (non-resume) response
                content_disp = resp.headers.get('Content-Disposition', '')
                if 'filename=' in content_disp:
                    server_name = re.findall(r'filename="?([^";\n]+)"?', content_disp)
                    if server_name:
                        filepath = os.path.join(os.path.dirname(filepath),
                                                clean_filename(server_name[0]))
                if not filepath.lower().endswith('.pdf'):
                    if 'pdf' in resp.headers.get('Content-Type', '').lower():
                        filepath += '.pdf'

            # content-length in a 206 response = remaining bytes, not total
            remaining = int(resp.headers.get('content-length', 0))
            total     = resume_from + remaining
            done      = resume_from

            write_mode = 'ab' if resuming else 'wb'
            with open(filepath, write_mode) as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        done += len(chunk)
                        if total > 0:
                            pct = done / total * 100
                            print(f"\r   ⬇️  {pct:.1f}% of {total/1024/1024:.1f} MB",
                                  end='', flush=True)

            # Reject suspiciously small files
            if done < 50 * 1024:
                os.remove(filepath)
                print(f"\r   ⚠️  Skipped (too small: {done} bytes — not a real textbook)")
                return False

            print(f"\r   ✅ Saved: {os.path.basename(filepath)} ({done/1024/1024:.1f} MB)")
            return True

        except requests.exceptions.RequestException as e:
            current = os.path.getsize(filepath) if os.path.exists(filepath) else 0
            if attempt < max_retries:
                wait = 5 * attempt
                print(f"\r   ⚠️  Attempt {attempt}/{max_retries} failed "
                      f"({current/1024/1024:.1f} MB so far): {e}")
                verb = "Resuming" if current > 0 else "Retrying"
                print(f"      {verb} in {wait}s...", flush=True)
                time.sleep(wait)
            else:
                # Keep partial file so future --check run can resume it
                if current == 0 and os.path.exists(filepath):
                    os.remove(filepath)
                print(f"\r   ❌ Failed after {max_retries} attempts: {e}")
                return False


# ── Check + repair ────────────────────────────────────────────────────────────

def check_and_repair(all_pdfs, output_dir, session, delay):
    """
    Audit every expected PDF:
      ✅ valid   — skip
      ⏸  partial — resume download from current size
      ❌ corrupt — delete and re-download
      📭 missing — download fresh
    """
    valid_list   = []
    partial_list = []
    corrupt_list = []
    missing_list = []

    print(f"\n🔍 Auditing {len(all_pdfs)} expected PDF(s)...\n")
    print(f"   {'STATUS':<34} FILE")
    print(f"   {'─'*32} {'─'*43}")

    for pdf in all_pdfs:
        filepath = get_filepath(pdf, output_dir)
        status   = pdf_status(filepath)
        label    = f"{pdf['book_title']} / {pdf['chapter_name']}"
        display  = label[:52] + ('…' if len(label) > 52 else '')

        if status == 'valid':
            mb  = os.path.getsize(filepath) / 1024 / 1024
            tag = f"✅ OK ({mb:.1f} MB)"
            valid_list.append(pdf)
        elif status == 'partial':
            kb  = os.path.getsize(filepath) / 1024
            tag = f"⏸️  PARTIAL ({kb:.0f} KB — resuming)"
            partial_list.append(pdf)
        elif status == 'corrupt':
            kb  = os.path.getsize(filepath) / 1024 if os.path.exists(filepath) else 0
            tag = f"❌ CORRUPT ({kb:.0f} KB)" if kb else "❌ CORRUPT"
            corrupt_list.append(pdf)
        else:
            tag = "📭 MISSING"
            missing_list.append(pdf)

        print(f"   {tag:<34} {display}")

    print(f"\n{'─'*60}")
    print(f"   ✅ Valid:    {len(valid_list)}")
    print(f"   ⏸️  Partial:  {len(partial_list)}")
    print(f"   ❌ Corrupt: {len(corrupt_list)}")
    print(f"   📭 Missing: {len(missing_list)}")
    print(f"{'─'*60}")

    # Delete corrupt files (partial files are kept for resume)
    for pdf in corrupt_list:
        fp = get_filepath(pdf, output_dir)
        if os.path.exists(fp):
            os.remove(fp)
            print(f"   🗑️  Deleted: {pdf['book_title']} / {pdf['chapter_name']}")

    to_fix = partial_list + corrupt_list + missing_list
    if not to_fix:
        print("\n✨ All files are valid — nothing to repair.")
        return len(valid_list), 0

    n_resume = len(partial_list)
    n_fresh  = len(corrupt_list) + len(missing_list)
    print(f"\n📥 Repairing {len(to_fix)} file(s)  "
          f"({n_resume} resume, {n_fresh} fresh)...\n")

    success = failed = 0
    for i, pdf in enumerate(to_fix, 1):
        print(f"[{i}/{len(to_fix)}] {pdf['book_title']} / {pdf['chapter_name']}")
        filepath = get_filepath(pdf, output_dir)
        if download_file(pdf['url'], filepath, session):
            success += 1
        else:
            failed += 1
        if i < len(to_fix):
            time.sleep(delay)

    return len(valid_list) + success, failed


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Bulk download Sri Lanka textbooks from edupub.gov.lk"
    )
    parser.add_argument('--grade',  '-g', required=True,
                        help='Grade number (1-13)')
    parser.add_argument('--medium', '-m', required=True,
                        choices=['sinhala', 'tamil', 'english'],
                        help='Medium of instruction')
    parser.add_argument('--output', '-o', default=None,
                        help='Root folder for downloads.  '
                             'Defaults to Grade_<grade>_<medium>/')
    parser.add_argument('--delay',  '-d', type=float, default=1.5,
                        help='Seconds between downloads (default 1.5)')
    parser.add_argument('--books',  '-b', default=None,
                        help='Comma-separated book name substrings, '
                             'e.g. "Mathematics,Science"  (case-insensitive)')
    parser.add_argument('--check',  '-c', action='store_true',
                        help='Audit downloaded files and repair bad/missing ones')

    args = parser.parse_args()

    grade_val          = grade_to_value(args.grade)
    medium_id, medium_name = MEDIUM_MAP[args.medium.lower()]

    output_dir = os.path.abspath(args.output) if args.output \
                 else os.path.abspath(f"Grade_{args.grade}_{medium_name}")
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 60)
    print("📖 Sri Lanka Textbook Bulk Downloader")
    print("=" * 60)
    print(f"   Grade:     {args.grade}  (site value: {grade_val})")
    print(f"   Medium:    {medium_name}  (site value: {medium_id})")
    print(f"   Saving to: {output_dir}")
    if args.books:
        print(f"   Filter:    {args.books}")
    if args.check:
        print(f"   Mode:      CHECK + REPAIR")
    print("=" * 60)

    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer':    DOWNLOAD_URL,
    })

    # Step 1 — book list
    books = get_book_list(grade_val, medium_id, medium_name, session)
    if not books:
        return

    # Optional filter
    if args.books:
        books = filter_books(books, args.books.split(','))
        if not books:
            print(f"\n⚠️  No books matched the filter: {args.books}")
            return
        print(f"   Filtered to {len(books)} book(s) matching: {args.books}")

    # Step 2 — chapter PDF links
    all_pdfs = collect_all_pdfs(books, grade_val, medium_name, session)
    if not all_pdfs:
        print("\n⚠️  Could not find any PDF download links.")
        return

    # Step 3a — CHECK + REPAIR mode
    if args.check:
        success, failed = check_and_repair(all_pdfs, output_dir, session, args.delay)
        print(f"\n{'=' * 60}")
        print(f"📊 Final Summary")
        print(f"   ✅ Valid/Downloaded: {success}")
        print(f"   ❌ Still failed:     {failed}")
        print(f"   📁 Folder: {output_dir}")
        print(f"{'=' * 60}")
        return

    # Step 3b — normal download (skip complete files, resume partial ones)
    print(f"\n📥 Downloading {len(all_pdfs)} PDF file(s)...\n")
    success = failed = 0

    for i, pdf in enumerate(all_pdfs, 1):
        print(f"[{i}/{len(all_pdfs)}] {pdf['book_title']} / {pdf['chapter_name']}")
        filepath = get_filepath(pdf, output_dir)

        st = pdf_status(filepath)
        if st == 'valid':
            print(f"   ⏭️  Already complete, skipping.")
            success += 1
            continue
        if st == 'partial':
            kb = os.path.getsize(filepath) / 1024
            print(f"   ⏩  Resuming from {kb:.0f} KB...")

        if download_file(pdf['url'], filepath, session):
            success += 1
        else:
            failed += 1

        if i < len(all_pdfs):
            time.sleep(args.delay)

    print(f"\n{'=' * 60}")
    print(f"📊 Download Summary")
    print(f"   ✅ Success: {success}")
    print(f"   ❌ Failed:  {failed}")
    print(f"   📁 Saved to: {output_dir}")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    main()
