"""
NIE Sri Lanka - Other Materials / Resource Books Downloader
Website: https://nie.lk/showom

Downloads PDFs, WAV and MP3 files from the Other Materials pages.
External links (e.g. FlipHTML5 viewers) are listed in the HTML index but cannot be bulk-downloaded.

Usage:
    python resource-downloader.py --medium english --output "resources -en"
    python resource-downloader.py --medium sinhala --output "resources -si"
    python resource-downloader.py --medium tamil   --output "resources -ta"
    python resource-downloader.py --medium english --output "resources -en" --check
    python resource-downloader.py --medium english --output "resources -en" --pdf-only
    python resource-downloader.py --html           --output "resources"
"""

import requests
from bs4 import BeautifulSoup
import os, re, sys, argparse, time
from urllib.parse import urljoin, unquote

sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "https://nie.lk/"

MEDIUM_MAP = {
    "english": ("showom",       "English",  "English"),
    "sinhala": ("showom2.aspx", "Sinhala",  "සිංහල"),
    "tamil":   ("showom3.aspx", "Tamil",    "தமிழ்"),
}

DOWNLOADABLE_EXTS = {'.pdf', '.wav', '.mp3'}

# ── Subject detection ──────────────────────────────────────────────────────────

SUBJECT_FOLDERS = [
    ("Biology",              ["biology"]),
    ("Physics",              ["physics"]),
    ("Chemistry",            ["chemistry"]),
    ("Combined Mathematics", ["combined math", "combined maths"]),
    ("Mathematics",          ["mathematics", "math"]),
    ("ICT",                  ["ict", "information communication technology"]),
    ("English",              ["english"]),
    ("Western Music",        ["western music"]),
    ("Agriculture",          ["agriculture"]),
    ("Tamil",                ["tamil"]),
    ("Sinhala",              ["sinhala"]),
    ("Health",               ["health"]),
    ("Geography",            ["geography"]),
    ("History",              ["history"]),
    ("Science",              ["science"]),
]

def detect_subject(name):
    """Return a subject folder name based on keywords in the file name."""
    lower = name.lower()
    for folder, keywords in SUBJECT_FOLDERS:
        if any(kw in lower for kw in keywords):
            return folder
    return "Other"

def clean_filename(name):
    name = unquote(name)
    name = re.sub(r'[<>:"/\\|?*\n\r\t]', '_', name)
    name = name.strip('. ')
    return name[:200] if name else 'unknown'

# ── File health check ──────────────────────────────────────────────────────────

def file_status(filepath):
    """
    PDFs  → 'valid' / 'partial' / 'corrupt' / 'missing'
    Audio → 'valid' / 'corrupt' / 'missing'
    """
    if not os.path.exists(filepath):
        return 'missing'
    ext = os.path.splitext(filepath)[1].lower()
    try:
        size = os.path.getsize(filepath)
        if ext == '.pdf':
            if size < 50 * 1024:
                return 'corrupt'
            with open(filepath, 'rb') as f:
                header = f.read(5)
                if header != b'%PDF-':
                    return 'corrupt'
                f.seek(max(0, size - 1024))
                tail = f.read()
            return 'valid' if b'%%EOF' in tail else 'partial'
        else:
            return 'valid' if size > 1024 else 'corrupt'
    except OSError:
        return 'missing'

# ── Fetching ──────────────────────────────────────────────────────────────────

def get_resources(page_path, session, pdf_only=False):
    """GET the page and return (downloadable, external_viewers)."""
    url = urljoin(BASE_URL, page_path)
    r = session.get(url, timeout=(10, 30))
    r.raise_for_status()

    soup = BeautifulSoup(r.text, 'html.parser')
    resources = []
    external  = []
    seen_urls = set()

    for a in soup.find_all('a', href=True):
        href = a['href']
        name = a.get_text(strip=True)
        if not name:
            continue

        ext = os.path.splitext(href.split('?')[0])[1].lower()
        is_external = href.startswith('http') and BASE_URL.rstrip('/') not in href

        # External viewer (e.g. FlipHTML5) — collect for HTML but skip download
        if is_external and ext not in DOWNLOADABLE_EXTS:
            if href not in seen_urls:
                seen_urls.add(href)
                external.append({'name': name, 'url': href})
            continue

        if ext not in DOWNLOADABLE_EXTS:
            continue
        if pdf_only and ext != '.pdf':
            continue
        if is_external:
            continue

        full_url = urljoin(BASE_URL, href)
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)

        url_filename = os.path.splitext(unquote(href.split('/')[-1]))[0]
        clean_name   = clean_filename(name) or clean_filename(url_filename)
        resources.append({'name': clean_name, 'url': full_url, 'ext': ext})

    return resources, external

# ── Downloading ───────────────────────────────────────────────────────────────

def download_file(url, filepath, session, max_retries=5):
    """HTTP Range resume + auto-retry."""
    min_size = 50 * 1024 if filepath.endswith('.pdf') else 1024

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

            if resp.status_code == 416:
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

            if done < min_size:
                os.remove(filepath)
                raise ValueError(f"Downloaded only {done} bytes — likely invalid")

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

def check_and_repair(resources, output_dir, session, delay):
    statuses = {}
    for r in resources:
        fp = os.path.join(output_dir, f"{r['name']}{r['ext']}")
        statuses[r['name']] = (file_status(fp), fp, r['url'], r['ext'])

    col = 35
    print(f"\n   {'STATUS':<{col}} FILE")
    print(f"   {'─'*col} {'─'*43}")
    for name, (status, fp, _, ext) in statuses.items():
        icon = {'valid': '✅ OK', 'partial': '⏸️  PARTIAL',
                'corrupt': '❌ CORRUPT', 'missing': '📭 MISSING'}[status]
        size = f" ({os.path.getsize(fp)/1024/1024:.1f} MB)" if status == 'valid' else ''
        label = f"{icon}{size}"
        short = name if len(name) <= 43 else name[:40] + '…'
        print(f"   {label:<{col}} {short}")

    counts = {s: sum(1 for _, (st, _, _, _) in statuses.items() if st == s)
              for s in ('valid', 'partial', 'corrupt', 'missing')}
    print(f"\n{'─'*60}")
    print(f"   ✅ Valid:    {counts['valid']}")
    print(f"   ⏸️  Partial:  {counts['partial']}")
    print(f"   ❌ Corrupt: {counts['corrupt']}")
    print(f"   📭 Missing: {counts['missing']}")
    print(f"{'─'*60}")

    to_fix = [(n, fp, url) for n, (st, fp, url, _) in statuses.items()
              if st in ('partial', 'corrupt', 'missing')]

    if not to_fix:
        print("\n✨ All files are valid — nothing to repair.")
        return 0

    resumes = sum(1 for _, fp, _ in to_fix if os.path.exists(fp))
    fresh   = len(to_fix) - resumes
    print(f"\n📥 Repairing {len(to_fix)} file(s)  ({resumes} resume, {fresh} fresh)...")

    for _, fp, _ in to_fix:
        if os.path.exists(fp) and file_status(fp) == 'corrupt':
            os.remove(fp)

    failed = 0
    for i, (name, fp, url) in enumerate(to_fix, 1):
        print(f"\n[{i}/{len(to_fix)}] {name}")
        if not download_file(url, fp, session):
            failed += 1
        if i < len(to_fix) and delay > 0:
            time.sleep(delay)

    return failed

# ── HTML index generator ───────────────────────────────────────────────────────

def generate_html(all_data, out_path):
    """
    all_data = {
      'english': (resources, external),
      'sinhala': (resources, external),
      'tamil':   (resources, external),
    }
    """
    def ext_badge(ext):
        colors = {'.pdf': '#d32f2f', '.wav': '#1565c0', '.mp3': '#6a1b9a'}
        labels = {'.pdf': 'PDF', '.wav': 'WAV', '.mp3': 'MP3'}
        c = colors.get(ext, '#555')
        l = labels.get(ext, ext.upper())
        return f'<span style="background:{c};color:#fff;padding:2px 7px;border-radius:4px;font-size:11px;font-weight:bold">{l}</span>'

    def rows_html(resources, external):
        html = ''
        if resources:
            html += '<h4 style="margin:18px 0 8px;color:#444">Downloadable Files</h4>'
            html += '<table style="width:100%;border-collapse:collapse">'
            for r in resources:
                html += (
                    f'<tr style="border-bottom:1px solid #eee">'
                    f'<td style="padding:8px 6px">{ext_badge(r["ext"])}</td>'
                    f'<td style="padding:8px 6px;width:100%">{r["name"]}</td>'
                    f'<td style="padding:8px 6px;white-space:nowrap">'
                    f'<a href="{r["url"]}" target="_blank" download '
                    f'style="background:#2e7d32;color:#fff;padding:4px 12px;border-radius:4px;text-decoration:none;font-size:13px">Download</a>'
                    f'</td></tr>\n'
                )
            html += '</table>'
        if external:
            html += '<h4 style="margin:18px 0 8px;color:#444">Online Viewers <small style="color:#888;font-weight:normal">(cannot be bulk-downloaded)</small></h4>'
            html += '<table style="width:100%;border-collapse:collapse">'
            for e in external:
                html += (
                    f'<tr style="border-bottom:1px solid #eee">'
                    f'<td style="padding:8px 6px"><span style="background:#ef6c00;color:#fff;padding:2px 7px;border-radius:4px;font-size:11px;font-weight:bold">ONLINE</span></td>'
                    f'<td style="padding:8px 6px;width:100%">{e["name"]}</td>'
                    f'<td style="padding:8px 6px;white-space:nowrap">'
                    f'<a href="{e["url"]}" target="_blank" '
                    f'style="background:#1565c0;color:#fff;padding:4px 12px;border-radius:4px;text-decoration:none;font-size:13px">View Online</a>'
                    f'</td></tr>\n'
                )
            html += '</table>'
        return html

    tabs_nav = ''
    tabs_content = ''
    for i, (key, (_, _, native)) in enumerate([(k, MEDIUM_MAP[k]) for k in ('english', 'sinhala', 'tamil')]):
        active_nav  = 'background:#1a237e;color:#fff' if i == 0 else 'background:#e8eaf6;color:#1a237e'
        display     = 'block' if i == 0 else 'none'
        resources, external = all_data.get(key, ([], []))
        total = len(resources) + len(external)
        tabs_nav += (
            f'<button onclick="showTab(\'{key}\')" id="btn-{key}" '
            f'style="{active_nav};border:none;padding:10px 22px;cursor:pointer;font-size:15px;border-radius:6px 6px 0 0;margin-right:4px">'
            f'{native} <span style="font-size:12px;opacity:.8">({total})</span></button>'
        )
        tabs_content += (
            f'<div id="tab-{key}" style="display:{display};padding:16px">'
            f'{rows_html(resources, external)}'
            f'</div>'
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>NIE Sri Lanka — Other Materials &amp; Resource Books</title>
<style>
  body {{ font-family: Segoe UI, Arial, sans-serif; margin: 0; background: #f5f5f5; }}
  .header {{ background: #1a237e; color: #fff; padding: 18px 30px; }}
  .header h1 {{ margin: 0; font-size: 22px; }}
  .header p  {{ margin: 4px 0 0; opacity: .8; font-size: 13px; }}
  .container {{ max-width: 960px; margin: 24px auto; background: #fff; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,.1); overflow: hidden; }}
  .tabs-nav {{ background: #e8eaf6; padding: 12px 16px 0; }}
  table tr:hover {{ background: #f9f9f9; }}
  a {{ color: inherit; }}
</style>
</head>
<body>
<div class="header">
  <h1>NIE Sri Lanka — Other Materials &amp; Resource Books</h1>
  <p>Source: <a href="https://nie.lk/showom" style="color:#90caf9" target="_blank">https://nie.lk/showom</a></p>
</div>
<div class="container">
  <div class="tabs-nav">
    {tabs_nav}
  </div>
  {tabs_content}
</div>
<script>
function showTab(id) {{
  ['english','sinhala','tamil'].forEach(function(k) {{
    document.getElementById('tab-'+k).style.display = (k===id) ? 'block' : 'none';
    document.getElementById('btn-'+k).style.background = (k===id) ? '#1a237e' : '#e8eaf6';
    document.getElementById('btn-'+k).style.color = (k===id) ? '#fff' : '#1a237e';
  }});
}}
</script>
</body>
</html>"""

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"   ✅ Saved: {out_path}")

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="NIE Sri Lanka Other Materials / Resource Books Downloader")
    parser.add_argument('--medium',   '-m', default='english',
                        choices=list(MEDIUM_MAP.keys()),
                        help='Medium: english / sinhala / tamil')
    parser.add_argument('--output',   '-o', default=None,
                        help='Output folder (default: "resources -<medium>")')
    parser.add_argument('--delay',    '-d', type=float, default=1.0,
                        help='Delay between downloads in seconds (default: 1)')
    parser.add_argument('--check',    '-c', action='store_true',
                        help='Audit existing downloads and repair missing/corrupt files')
    parser.add_argument('--pdf-only', '-p', action='store_true',
                        help='Skip audio files (.wav/.mp3), download PDFs only')
    parser.add_argument('--html',           action='store_true',
                        help='Generate a local HTML index for all three languages and exit')
    parser.add_argument('--by-subject',    action='store_true',
                        help='Organise downloads into subject subfolders (Biology/, Chemistry/, etc.)')
    args = parser.parse_args()

    session = requests.Session()
    session.headers.update({'User-Agent':
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})

    # ── HTML generation mode ──────────────────────────────────────────────────
    if args.html:
        out_dir = args.output or 'resources'
        out_dir = os.path.abspath(out_dir)
        os.makedirs(out_dir, exist_ok=True)
        print("=" * 60)
        print("🌐 NIE Resource Books — HTML Index Generator")
        print("=" * 60)

        all_data = {}
        for key, (page_path, en_name, native) in MEDIUM_MAP.items():
            print(f"\n🔍 Fetching {en_name} ({native})...")
            resources, external = get_resources(page_path, session)
            all_data[key] = (resources, external)
            print(f"   {len(resources)} downloadable,  {len(external)} online viewers")

        html_path = os.path.join(out_dir, 'index.html')
        print(f"\n📄 Writing HTML index...")
        generate_html(all_data, html_path)
        print(f"\nOpen in browser: {html_path}")
        return

    # ── Download / check mode ─────────────────────────────────────────────────
    page_path, medium_name, _ = MEDIUM_MAP[args.medium]
    output_dir = args.output or f"resources -{'en' if args.medium == 'english' else args.medium[:2]}"
    output_dir = os.path.abspath(output_dir)

    print("=" * 60)
    print("📚 NIE Other Materials / Resource Books Downloader")
    print("=" * 60)
    print(f"   Medium:    {medium_name}")
    print(f"   Saving to: {output_dir}")
    if args.check:
        print(f"   Mode:      CHECK + REPAIR")
    if args.pdf_only:
        print(f"   Filter:    PDFs only (audio skipped)")
    print("=" * 60)

    print(f"\n🔍 Fetching resource list ({medium_name})...")
    resources, external = get_resources(page_path, session, pdf_only=args.pdf_only)

    if not resources:
        print("   ❌ No downloadable resources found.")
        sys.exit(1)

    print(f"   Found {len(resources)} downloadable file(s).")
    if external:
        print(f"   ⏭️  {len(external)} online viewer link(s) (FlipHTML5 etc.) — not downloadable. Use --html to see them.")
    print()
    for r in resources:
        print(f"   • [{r['ext']}] {r['name']}")

    os.makedirs(output_dir, exist_ok=True)

    # ── Check mode ────────────────────────────────────────────────────────────
    if args.check:
        print(f"\n🔍 Auditing {len(resources)} file(s)...")
        failed = check_and_repair(resources, output_dir, session, args.delay)
        success = len(resources) - failed
        print(f"\n{'=' * 60}")
        print(f"📊 Final Summary")
        print(f"   ✅ Valid/Downloaded: {success}")
        print(f"   ❌ Still failed:     {failed}")
        print(f"   📁 Folder: {output_dir}")
        print(f"{'=' * 60}")
        return

    # ── Download mode ─────────────────────────────────────────────────────────
    print(f"\n📥 Downloading {len(resources)} file(s)...\n")

    success = 0
    failed  = 0
    skipped = 0

    for i, r in enumerate(resources, 1):
        if args.by_subject:
            subject = detect_subject(r['name'])
            fp = os.path.join(output_dir, subject, f"{r['name']}{r['ext']}")
        else:
            fp = os.path.join(output_dir, f"{r['name']}{r['ext']}")
        status = file_status(fp)

        print(f"[{i}/{len(resources)}] {r['name']}{r['ext']}")

        if status == 'valid':
            size = os.path.getsize(fp) / 1024 / 1024
            print(f"   ⏭️  Already valid ({size:.1f} MB) — skipping")
            skipped += 1
        else:
            if download_file(r['url'], fp, session):
                success += 1
            else:
                failed += 1

        if i < len(resources) and args.delay > 0:
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
