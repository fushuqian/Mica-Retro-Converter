from pathlib import Path
from html.parser import HTMLParser

class AttrParser(HTMLParser):
    def __init__(self, target_attrs):
        super().__init__()
        self.target_attrs = target_attrs
        self.found = {k: [] for k in target_attrs}

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        for attr_name in self.target_attrs:
            if attr_name in attr_dict:
                self.found[attr_name].append((tag, attr_dict[attr_name]))

html = Path('c:/Syncthing/Trae Workspace/win98-asf-converter-ui.design/pages/index.html').read_text(encoding='utf-8')
parser = AttrParser(['data-region'])
parser.feed(html)
for tag, vals in parser.found.items():
    print(tag, vals)
