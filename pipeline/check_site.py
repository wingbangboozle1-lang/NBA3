#!/usr/bin/env python3
"""Static site checks: every .html parses, internal links resolve, data JSONs exist."""
import json, os, re, sys
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class P(HTMLParser):
    def __init__(self):
        super().__init__(); self.ids=set(); self.hrefs=[]; self.srcs=[]
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if 'id' in a: self.ids.add(a['id'])
        if tag=='a' and 'href' in a: self.hrefs.append(a['href'])
        if tag=='script' and 'src' in a: self.srcs.append(a['src'])
        if tag=='link' and 'href' in a: self.srcs.append(a['href'])

def main():
    site=os.path.join(ROOT,'site'); root_files=['index.html','research-dashboard.html']
    pages=[('index.html',ROOT)]+[(f,ROOT) for f in root_files[1:]]+[(f,site) for f in sorted(os.listdir(site)) if f.endswith('.html')]
    data_json=set(os.listdir(os.path.join(site,'data')))
    referenced=set()
    problems=[]
    checked=0
    for fname,base in pages:
        path=os.path.join(base,fname)
        p=P(); p.feed(open(path,encoding='utf-8').read()); checked+=1
        hrefs=p.hrefs+p.srcs
        for h in hrefs:
            if h.startswith('#'):
                if h[1:] and h[1:] not in p.ids and fname=='index.html':
                    problems.append(f"{fname}: broken anchor {h}")
            elif h.startswith('data/'):
                referenced.add(h.split('/')[1])
                if not os.path.exists(os.path.join(site,h)):
                    problems.append(f"{fname}: missing {h}")
            elif h.startswith('site/'):
                target=os.path.join(ROOT,h)
                if not os.path.exists(target):
                    problems.append(f"{fname}: missing {h}")
            elif h.startswith('assets/'):
                if not os.path.exists(os.path.join(site,h)):
                    problems.append(f"{fname}: missing {h}")
            elif h.startswith(('http://','https://','mailto:')) or h.endswith('.html'):
                if h.endswith('.html') and not h.startswith('http'):
                    base_dir = site if not fname.startswith('site/') or True else site
                    # links between root and site are relative to the file's dir
                    d = site if base==site else ROOT
                    if not os.path.exists(os.path.join(d,h)):
                        problems.append(f"{fname}: missing local page {h}")
    missing=referenced-data_json
    if missing: problems.append(f"referenced data files missing: {missing}")
    # JSON parse check
    for f in data_json:
        try: json.load(open(os.path.join(site,'data',f)))
        except Exception as e: problems.append(f"bad JSON {f}: {e}")
    print(f"checked {checked} pages, {len(data_json)} data files")
    if problems:
        print("PROBLEMS:"); [print(' -',x) for x in problems]; sys.exit(1)
    print("all internal links and data references OK")

if __name__=='__main__':
    main()
