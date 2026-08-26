from html.parser import HTMLParser
from pathlib import Path

class VisibleCheck(HTMLParser):
    def __init__(self):
        super().__init__()
        self.regions = {r: [] for r in ['drop-zone','file-queue','settings','log','actions']}
    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        dr = d.get('data-region')
        if dr in self.regions:
            self.regions[dr].append((tag, d.get('style',''), d.get('hidden'), d.get('aria-hidden')))

html = Path('c:/Syncthing/Trae Workspace/win98-asf-converter-ui.design/pages/index.html').read_text(encoding='utf-8')
vc = VisibleCheck()
vc.feed(html)
for k,v in vc.regions.items():
    print(k, v)
