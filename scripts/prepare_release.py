"""Validate materialized source and apply the browser timing regression fix."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def main():
    for name in ['README.md', 'project.json', 'app/service.py', 'app/indexer.py', 'localdesk/vault.py', 'run.py', 'web/app.js']:
        if not (ROOT / name).is_file():
            raise ValueError('Required source is absent: ' + name)
    path = ROOT / 'scripts/browser_check.py'
    text = path.read_text(encoding='utf-8')
    old = 'page.locator("#load-demo").click()\n                settle()'
    new = 'page.locator("#load-demo").click()\n                page.locator(".search-hit").first.wait_for(state="visible", timeout=60000)\n                page.locator("#file-tags").wait_for(state="visible", timeout=30000)\n                settle()'
    if old in text:
        if text.count(old) != 1:
            raise ValueError('The demo check changed; review the patch.')
        path.write_text(text.replace(old, new), encoding='utf-8')
    shutil.rmtree(ROOT / '_runtime', ignore_errors=True)
    print('Self-contained source validated. Browser checks await the completed search result.')


if __name__ == '__main__':
    main()
