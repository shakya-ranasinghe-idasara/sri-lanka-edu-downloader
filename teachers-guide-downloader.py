"""
NIE Sri Lanka - Teachers' Guide Bulk Downloader
Website: https://nie.lk/seletguide

Usage:
    python teachers-guide-downloader.py --grade 10 --medium english --output "grade 10 -en"
    python teachers-guide-downloader.py --grade 10 --medium english --output "grade 10 -en" --check
    python teachers-guide-downloader.py --grade 10 --medium sinhala --output "grade 10 -si"
    python teachers-guide-downloader.py --grade 10 --medium tamil  --output "grade 10 -ta"
"""

import requests
from bs4 import BeautifulSoup
import os, re, sys, argparse, time
from urllib.parse import urljoin, unquote

sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "https://nie.lk/"

MEDIUM_MAP = {
    "english": ("seletguide",  "English"),
    "sinhala": ("seletguide2", "Sinhala"),
    "tamil":   ("seletguide3", "Tamil"),
}

def grade_to_value(grade):
    return f"GR{int(grade)}"

def clean_filename(name):
    name = unquote(name)
    name = re.sub(r'[<>:"/\\|?*\n\r\t]', '_', name)
    name = name.strip('. ')
    return name[:200] if name else 'unknown'

# ── PDF health check ──────────────────────────────────────────────────────────

def pdf_status(filepath):
    """
    'valid'   — %PDF- header + %%EOF footer, >= 50 KB
    'partial' — %PDF- header, no %%EOF (resumable)
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

# ── Fetching ──────────────────────────────────────────────────────────────────

def get_guides(grade_val, page_path, session):
    """POST to the guide selection page and return list of {name, url}."""
    url = urljoin(BASE_URL, page_path)

    # Step 1: GET to grab ASP.NET hidden fields
    r = session.get(url, timeout=(10, 30))
    r.raise_for_status()

    def extract(field):
        m = re.search(rf'id="{re.escape(field)}" value="(.*?)"', r.text)
        return m.group(1) if m else ''

    data = {
        '__VIEWSTATE':          extract('__VIEWSTATE'),
        '__VIEWSTATEGENERATOR': extract('__VIEWSTATEGENERATOR'),
        '__EVENTVALIDATION':    extract('__EVENTVALIDATION'),
        'ctl00$MainContent$DropDownList1': grade_val,
        'ctl00$MainContent$Button1': "Find Teachers' Guide",
    }

    # Step 2: POST with selected grade
    r2 = session.post(url, data=data, timeout=(10, 30))
    r2.raise_for_status()

    soup = BeautifulSoup(r2.text, 'html.parser')
    guides = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        if '.pdf' in href.lower():
            name = a.get_text(strip=True)
            full_url = urljoin(BASE_URL, href)
            guides.append({'name': clean_filename(name) or clean_filename(href.split('/')[-1]),
                           'url':  full_url})
    return guides

# ── Downloading ───────────────────────────────────────────────────────────────

def download_file(url, filepath, session, max_retries=5):
    """HTTP Range resume + auto-retry. timeout=(10, 300)."""
    for attempt in range(1, max_retries + 1):
        try:
            resume_from = 0
            req_headers = {}
            if os.path.exists(filepath):
                size = os.path.getsize(filepath)
                if size > 0:
                    resume_from = size
                    req_headers['Range'] = f'bytes={resume_from}-'

            resp = session.get(url, stream=True, timeout=(10, 300),
                               headers=req_headers)

            if resp.status_code == 416:          # Range Not Satisfiable
                resume_from = 0
                resp.close()
                resp = session.get(url, stream=True, timeout=(10, 300))
                resp.raise_for_status()
            elif resp.status_code not in (200, 206):
                resp.raise_for_status()

            resuming   = (resp.status_code == 206)
            remaining  = int(resp.headers.get('content-length', 0))
            total      = resume_from + remaining
            done       = resume_from
            write_mode = 'ab' if resuming else 'wb'

            if not resuming:
                resume_from = 0

            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, write_mode) as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        done += len(chunk)
                        if total > 0:
                            pct = done / total * 100
                            print(f"\r   ⬇️  {pct:.1f}% of {total/1024/1024:.1f} MB",
                                  end='', flush=True)

            if done < 50 * 1024:
                os.remove(filepath)
                raise ValueError(f"Downloaded only {done} bytes — likely not a real PDF")

            print(f"\r   ✅ Saved: {os.path.basename(filepath)} ({done/1024/1024:.1f} MB)")
            return True

        except Exception as e:
            current = os.path.getsize(filepath) if os.path.exists(filepath) else 0
            if attempt < max_retries:
                wait = 5 * attempt
                print(f"\r   ⚠️  Attempt {attempt}/{max_retries} failed "
                      f"({current/1024/1024:.1f} MB so far): {e}")
                print(f"      {'Resuming' if current > 0 else 'Retrying'} in {wait}s...")
                time.sleep(wait)
            else:
                if current == 0 and os.path.exists(filepath):
                    os.remove(filepath)
                print(f"\r   ❌ Failed after {max_retries} attempts: {e}")
                return False

# ── Check / repair ────────────────────────────────────────────────────────────

def check_and_repair(guides, output_dir, session, delay):
    statuses = {}
    for g in guides:
        fp = os.path.join(output_dir, f"{g['name']}.pdf")
        statuses[g['name']] = (pdf_status(fp), fp, g['url'])

    # Print audit table
    col = 35
    print(f"\n   {'STATUS':<{col}} FILE")
    print(f"   {'─'*col} {'─'*43}")
    for name, (status, fp, _) in statuses.items():
        icon = {'valid':'✅ OK', 'partial':'⏸️  PARTIAL', 'corrupt':'❌ CORRUPT',
                'missing':'📭 MISSING'}[status]
        size = f" ({os.path.getsize(fp)/1024/1024:.1f} MB)" if status == 'valid' else ''
        label = f"{icon}{size}"
        short = name if len(name) <= 43 else name[:40] + '…'
        print(f"   {label:<{col}} {short}")

    counts = {s: sum(1 for _,( st,_,__) in statuses.items() if st == s)
              for s in ('valid','partial','corrupt','missing')}
    print(f"\n{'─'*60}")
    print(f"   ✅ Valid:    {counts['valid']}")
    print(f"   ⏸️  Partial:  {counts['partial']}")
    print(f"   ❌ Corrupt: {counts['corrupt']}")
    print(f"   📭 Missing: {counts['missing']}")
    print(f"{'─'*60}")

    to_fix = [(n, fp, url) for n, (st, fp, url) in statuses.items()
              if st in ('partial', 'corrupt', 'missing')]

    if not to_fix:
        print("\n✨ All files are valid — nothing to repair.")
        return 0

    resumes = sum(1 for n, fp, _ in to_fix if os.path.exists(fp))
    fresh   = len(to_fix) - resumes
    print(f"\n📥 Repairing {len(to_fix)} file(s)  ({resumes} resume, {fresh} fresh)...")

    # Delete corrupt files before re-downloading
    for n, fp, _ in to_fix:
        if os.path.exists(fp) and pdf_status(fp) == 'corrupt':
            os.remove(fp)

    failed = 0
    for i, (name, fp, url) in enumerate(to_fix, 1):
        print(f"\n[{i}/{len(to_fix)}] {name}")
        if not download_file(url, fp, session):
            failed += 1
        if i < len(to_fix) and delay > 0:
            time.sleep(delay)

    return failed

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="NIE Sri Lanka Teachers' Guide Downloader")
    parser.add_argument('--grade',  '-g', required=True,
                        help='Grade number (1-13)')
    parser.add_argument('--medium', '-m', default='english',
                        choices=list(MEDIUM_MAP.keys()),
                        help='Medium: english / sinhala / tamil')
    parser.add_argument('--output', '-o', default=None,
                        help='Output folder (default: "grade <N> -<medium>")')
    parser.add_argument('--delay',  '-d', type=float, default=1.0,
                        help='Delay between downloads in seconds (default: 1)')
    parser.add_argument('--check',  '-c', action='store_true',
                        help='Audit existing downloads and repair missing/corrupt files')
    args = parser.parse_args()

    grade_val   = grade_to_value(args.grade)
    page_path, medium_name = MEDIUM_MAP[args.medium]
    output_dir  = args.output or f"grade {args.grade} -{'en' if args.medium == 'english' else args.medium[:2]}"
    output_dir  = os.path.abspath(output_dir)

    mode_label  = "CHECK + REPAIR" if args.check else "DOWNLOAD"

    print("=" * 60)
    print("📚 NIE Teachers' Guide Downloader")
    print("=" * 60)
    print(f"   Grade:     {args.grade}  (value: {grade_val})")
    print(f"   Medium:    {medium_name}")
    print(f"   Saving to: {output_dir}")
    if args.check:
        print(f"   Mode:      {mode_label}")
    print("=" * 60)

    session = requests.Session()
    session.headers.update({'User-Agent':
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})

    print(f"\n🔍 Fetching guide list for Grade {args.grade} ({medium_name})...")
    guides = get_guides(grade_val, page_path, session)

    if not guides:
        print("   ❌ No guides found. Check grade/medium or try again.")
        sys.exit(1)

    print(f"   Found {len(guides)} guide(s).\n")
    for g in guides:
        print(f"   • {g['name']}")

    os.makedirs(output_dir, exist_ok=True)

    # ── Check mode ────────────────────────────────────────────────────────────
    if args.check:
        print(f"\n🔍 Auditing {len(guides)} PDF(s)...")
        failed = check_and_repair(guides, output_dir, session, args.delay)
        success = len(guides) - failed
        print(f"\n{'=' * 60}")
        print(f"📊 Final Summary")
        print(f"   ✅ Valid/Downloaded: {success}")
        print(f"   ❌ Still failed:     {failed}")
        print(f"   📁 Folder: {output_dir}")
        print(f"{'=' * 60}")
        return

    # ── Download mode ─────────────────────────────────────────────────────────
    print(f"\n📥 Downloading {len(guides)} PDF(s)...\n")

    success = 0
    failed  = 0
    skipped = 0

    for i, g in enumerate(guides, 1):
        fp     = os.path.join(output_dir, f"{g['name']}.pdf")
        status = pdf_status(fp)

        print(f"[{i}/{len(guides)}] {g['name']}")

        if status == 'valid':
            size = os.path.getsize(fp) / 1024 / 1024
            print(f"   ⏭️  Already valid ({size:.1f} MB) — skipping")
            skipped += 1
        else:
            if download_file(g['url'], fp, session):
                success += 1
            else:
                failed += 1

        if i < len(guides) and args.delay > 0:
            time.sleep(args.delay)

    print(f"\n{'=' * 60}")
    print(f"📊 Download Summary")
    print(f"   ✅ Success: {success}")
    print(f"   ⏭️  Skipped: {skipped}")
    print(f"   ❌ Failed:  {failed}")
    print(f"   📁 Saved to: {output_dir}")
    print(f"{'=' * 60}")

if __name__ == '__main__':
    main()
