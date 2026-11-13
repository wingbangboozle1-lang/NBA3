#!/usr/bin/env python3
"""Edge Lab (arena-0a016df8) static checks: pages parse, internal links resolve, data JSONs exist.

Layout: dashboard lives in edge/ (moved from site/ during integration — site/ is 7c532e8c's
generated tree). Root research-dashboard.html is an archive copy of the round-1 dashboard.
"""
import json, os, sys
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EDGE = os.path.join(ROOT, 'edge')

class P(HTMLParser):
    def __init__(self):
        super().__init__(); self.ids=set(); self.refs=[]
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if 'id' in a: self.ids.add(a['id'])
        if tag=='a' and 'href' in a: self.refs.append(a['href'])
        if tag in ('script','link') and ('src' in a or 'href' in a):
            self.refs.append(a.get('src') or a.get('href'))

def main():
    pages=[f for f in sorted(os.listdir(EDGE)) if f.endswith('.html')]
    pages+=['research-dashboard.html']
    data_json=set(os.listdir(os.path.join(EDGE,'data')))
    problems=[]; refs=0
    for fname in pages:
        base = EDGE if not fname=='research-dashboard.html' else ROOT
        path=os.path.join(base,fname)
        p=P(); p.feed(open(path,encoding='utf-8').read())
        for h in p.refs:
            refs+=1
            if h.startswith(('http://','https://','mailto:','data:')): continue
            target=os.path.normpath(os.path.join(base,h.split('#')[0])) if '#' not in h or h.count('#')==0 or not h.split('#')[0] else os.path.normpath(os.path.join(base,h.split('#')[0]))
            if h.startswith('#'):
                if h[1:] and h[1:] not in p.ids: problems.append(f"{fname}: broken anchor {h}")
            else:
                filepart=h.split('#')[0]
                if not filepart: continue
                t=os.path.normpath(os.path.join(base,filepart))
                if not os.path.exists(t): problems.append(f"{fname}: missing {h}")
    for f in sorted(data_json):
        try: json.load(open(os.path.join(EDGE,'data',f)))
        except Exception as e: problems.append(f"bad JSON {f}: {e}")
    print(f"edge/: checked {len(pages)} pages, {len(data_json)} data files, {refs} refs")
    if problems:
        print("PROBLEMS:"); [print(' -',x) for x in problems]; sys.exit(1)
    print("edge/: all internal links and data references OK")

if __name__=='__main__':
    main()
