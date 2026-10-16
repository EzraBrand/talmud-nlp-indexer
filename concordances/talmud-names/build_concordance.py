import argparse, csv, html, json, re, hashlib
from urllib.parse import quote, urlencode
from pathlib import Path
from html.parser import HTMLParser
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description="Build the bold-translation Talmud names concordance")
parser.add_argument('--gazetteer', type=Path, default=ROOT/'data/talmud_names_gazetteer.txt')
parser.add_argument('--corpus', type=Path, default=ROOT/'data/archive/steinsaltz_talmud_combined_richHTML.csv')
parser.add_argument('--output-dir', type=Path, default=HERE)
args = parser.parse_args()
OUT = args.output_dir
OUT.mkdir(parents=True, exist_ok=True)
csv.field_size_limit(2**31-1)
class Plain(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True); self.parts=[]
    def handle_data(self, data): self.parts.append(data)
    def handle_starttag(self,tag,attrs):
        if tag in ('br','p','div','li'): self.parts.append(' ')
    def handle_endtag(self,tag):
        if tag in ('p','div','li'): self.parts.append(' ')
def plain(s):
    p=Plain(); p.feed(s); return ''.join(p.parts)
def normalize(s, legacy=False):
    s=plain(s).replace('\u2019', "'").replace('\u2018', "'")
    if legacy:
        s=re.sub(r'(?<=[A-Za-z])\?(?=[A-Za-z])','ḥ',s)
        s=re.sub(r'(?<![A-Za-z])\?(?=[a-z])','Ḥ',s)
    return s.casefold()
def tokens(s): return re.findall(r"[^\W_]+(?:['-][^\W_]+)*",s)
def repair_display(rich):
    parts=re.split(r'(<[^>]+>)',rich)
    for j in range(0,len(parts),2):
        parts[j]=re.sub(r'(?<=[A-Za-z])\?(?=[A-Za-z])','ḥ',parts[j])
        parts[j]=re.sub(r'(?<![A-Za-z])\?(?=[a-z])','Ḥ',parts[j])
    return ''.join(parts)
def bekiut_url(loc):
    match=re.fullmatch(r'(.+?)\s+(\d+[ab]):(\d+)',loc)
    if not match: raise ValueError('Unrecognized citation: '+loc)
    tractate,daf,section=match.groups()
    return f'https://bekiut.com/talmud/{quote(tractate,safe="")}/{daf}#{section}'
assert repair_display('<b>Rav ?isda</b> said: Yo?anan?')=='<b>Rav Ḥisda</b> said: Yoḥanan?'
assert bekiut_url('Berakhot 2a:2')=='https://bekiut.com/talmud/Berakhot/2a#2'
def bold_matches(rich, trie):
    # Keep source tags intact. Each run is uninterrupted bold text, allowing
    # only whitespace outside bold tags between adjacent translation spans.
    parts=re.split(r'(<[^>]+>)',rich)
    runs=[]; run=[]; depth=0
    for j,part in enumerate(parts):
        if j%2:
            if re.match(r'<(?:b|strong)(?:\s|>)',part,re.I): depth+=1
            elif re.match(r'</(?:b|strong)\s*>',part,re.I): depth=max(0,depth-1)
            elif re.match(r'<br\b',part,re.I) and run: run.append((None,'\n',False))
            continue
        text=html.unescape(part)
        if depth: run.append((j,text,True))
        elif not text.strip() and run: run.append((j,text,False))
        elif run: runs.append(run); run=[]
    if run: runs.append(run)
    found=defaultdict(list)
    for run in runs:
        text=''.join(s for _,s,_ in run)
        normalized=text.replace('\u2019',"'").replace('\u2018',"'")
        normalized=re.sub(r'(?<=[A-Za-z])\?(?=[A-Za-z])','ḥ',normalized)
        normalized=re.sub(r'(?<![A-Za-z])\?(?=[a-z])','Ḥ',normalized)
        words=list(re.finditer(r"[^\W_]+(?:['-][^\W_]+)*",normalized))
        candidates=[]
        for start in range(len(words)):
            node=trie
            for end in range(start,len(words)):
                word=words[end].group().casefold()
                if word not in node: break
                node=node[word]
                for i in node.get(None,[]):
                    candidates.append((words[start].start(),words[end].end(),i))
        # Resolve against the entire gazetteer before excluding titled names.
        # The longest overlapping phrase owns that occurrence.
        accepted=[]
        for left,right,i in sorted(candidates,key=lambda c:(-(c[1]-c[0]),c[0],c[2])):
            if any(left<b and right>a for a,b,_ in accepted): continue
            accepted.append((left,right,i))
        for left,right,i in accepted:
            if i<0: continue  # excluded entries still block shorter matches
            pos=0
            for j,s,bold in run:
                a,b=max(left,pos),min(right,pos+len(s))
                if bold and a<b: found[i].append((j,a-pos,b-pos))
                pos+=len(s)
    return parts,found
def highlight(parts,spans):
    edits=defaultdict(list)
    for j,a,b in spans: edits[j].append((a,b))
    out=parts.copy()
    for j,ranges in edits.items():
        text=html.unescape(parts[j]); merged=[]
        for a,b in sorted(ranges):
            if merged and a<=merged[-1][1]: merged[-1]=(merged[-1][0],max(b,merged[-1][1]))
            else: merged.append((a,b))
        pos=0; segments=[]
        for a,b in merged:
            segments.extend([html.escape(text[pos:a]),'<mark>',html.escape(text[a:b]),'</mark>']); pos=b
        segments.append(html.escape(text[pos:])); out[j]=''.join(segments)
    result=''.join(out)
    assert plain(result)==plain(''.join(parts)), 'Highlight changed source text'
    return result

# Check nested formatting, phrase boundaries, and commentary exclusion.
test_trie={'abaye':{'bar':{'abba':{None:[0]}}}}
p,m=bold_matches('<b>Abaye <i>bar</i></b> <strong>Abba</strong> commentary Abaye bar Abba',test_trie)
assert 0 in m and highlight(p,m[0]).count('<mark>')==3
assert not bold_matches('<b>Abaye</b> commentary <b>bar Abba</b>',test_trie)[1]
assert not bold_matches('Abaye bar Abba',test_trie)[1]
assert not bold_matches('<b>Abaye bar Abbas</b>',test_trie)[1]
honorific=re.compile(r'^(?:rabbi|rav|mar|abba|ravin|rava|rabba|rabban|abaye|avimi|avin|avuh|mareimar|mari)(?=$|\W)',re.I)
source_names=args.gazetteer.read_text(encoding='utf-8').splitlines()
names=[]; excluded=[]; seen=set()
for s in source_names:
    s=s.strip()
    if not s: continue
    if honorific.match(s): excluded.append(s); continue
    if s.casefold() not in seen: names.append(s); seen.add(s.casefold())
names.sort(key=str.casefold)
trie={}
for i,n in enumerate(names):
    node=trie
    for word in tokens(normalize(n)): node=node.setdefault(word,{})
    node.setdefault(None,[]).append(i)
for i,n in enumerate(excluded):
    node=trie
    for word in tokens(normalize(n)): node=node.setdefault(word,{})
    node.setdefault(None,[]).append(-i-1)
# A titled occurrence must not leak into the shorter entry, but a separate
# standalone occurrence in the same section must still match.
overlap_trie={'bar':{'giyorei':{None:[0]}},'rav':{'yitzḥak':{'bar':{'giyorei':{None:[-1]}}}}}
assert not bold_matches('<b>Rav Yitzḥak bar Giyorei</b>',overlap_trie)[1]
p,m=bold_matches('<b>Rav Yitzḥak bar Giyorei and bar Giyorei</b>',overlap_trie)
assert len(m[0])==1 and highlight(p,m[0]).count('<mark>')==1
assert not bold_matches('<b>Rav Yitzḥak</b> <b>bar Giyorei</b>',overlap_trie)[1]
hits=defaultdict(list); counts=defaultdict(int); seen_sections=defaultdict(set)
rows=0
with args.corpus.open(encoding='cp1252',newline='') as f:
    for row in csv.reader(f):
        if len(row)<2 or not re.search(r'\d+[ab]:\d+$',row[0]): continue
        loc,rich=row[:2]; rich=repair_display(rich); rows+=1
        source_parts,found=bold_matches(rich,trie)
        for i in found:
            if loc in seen_sections[i]: continue
            seen_sections[i].add(loc); counts[i]+=1
            if len(hits[i])<3: hits[i].append((loc,highlight(source_parts,found[i])))
        if rows%10000==0: print('Processed',rows,flush=True)
summary=dict(gazetteer_rows=len(source_names),excluded_rows=len(excluded),eligible_names=len(names),names_with_matches=len(hits),names_without_matches=len(names)-len(hits),sections_searched=rows,sections_displayed=sum(map(len,hits.values())),csv_sha256=hashlib.sha256(args.corpus.read_bytes()).hexdigest())
head='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Concordance of Names and References to Commoners in the Talmud</title>
<style>mark{background:#ffe76b;color:inherit;border-radius:2px;padding:0 .08em}body{margin:0;background:#f8f6f0;color:#252822;font:18px/1.65 Georgia,serif}main{max-width:1000px;margin:auto;padding:24px}h1{line-height:1.2}h2{font-size:1.4rem;margin-bottom:.3rem}a{color:#245a66}header,article{border-bottom:1px solid #c8cec5;padding-bottom:24px;margin-bottom:28px}.context{background:white;border:1px solid #d7d9d1;padding:20px;margin:12px 0;overflow-wrap:anywhere}.citation{font:600 15px/1.5 system-ui;margin-bottom:10px}.toolbar{position:sticky;top:0;background:#f8f6f0;padding:12px 0;z-index:1}input{box-sizing:border-box;width:100%;padding:12px;font:16px system-ui}small,.meta{font:14px/1.6 system-ui;color:#4a554c}nav{max-height:240px;overflow:auto;columns:3;column-width:230px}nav a{display:block}article{scroll-margin-top:80px}[hidden]{display:none!important}@media(max-width:600px){main{padding:14px}.context{padding:14px}body{font-size:16px}}@media print{.toolbar,nav{display:none}}</style><main><header><h1>Concordance of Names and References to Commoners in the Talmud</h1><p>Entries without an initial honorific · up to three full sections per name</p>'''
parts=[head, '<p class="meta">'+html.escape(f"{len(names):,} eligible names · {len(hits):,} with matches · {rows:,} sections searched")+'</p>', '''<p class="meta">Source: <a href="https://github.com/EzraBrand/talmud-nlp-indexer/blob/main/data/talmud_names_gazetteer.txt">names gazetteer</a> and <a href="https://github.com/EzraBrand/talmud-nlp-indexer/blob/main/data/archive/steinsaltz_talmud_combined_richHTML.csv">archived Steinsaltz CSV</a>. Generated October 16, 2026. Excludes names beginning with Rabbi, Rav, Mar, Abba, Ravin, Rava, Rabba, Rabban, Abaye, Avimi, Avin, Avuh, Mareimar, or Mari as a complete word, ignoring case. Matches whole token sequences only within bold translation text (b/strong tags); overlapping matches are assigned to the longest matching entry in the full gazetteer, including excluded entries. Shorter names inside an excluded longer name do not count. Separate standalone occurrences still count. Commentary cannot trigger a match. Matching translation text is highlighted in yellow; each result includes the full section. Apostrophe variants and whitespace are normalized for matching. The legacy CSV is Windows-1252; its question-mark placeholders are interpreted as ḥ/Ḥ for matching using the archived builder's rule. Displayed HTML restores these ḥ/Ḥ placeholders while retaining source wording and formatting. Each citation links to its passage on Bekiut. Results are the first three distinct sections in CSV order; counts cover all matching sections. All eligible names, including those without a match, are listed.</p></header><div class="toolbar"><label for="search">Find a gazetteer entry</label><input id="search" type="search" placeholder="Filter names…"><small id="visible"></small></div><nav aria-label="Names">''']
for i,n in enumerate(names): parts.append(f'<a data-name="{html.escape(n.casefold(),quote=True)}" href="#n{i}">{html.escape(n)}</a>')
parts.append('</nav>')
for i,n in enumerate(names):
    search_url='https://bekiut.com/search?'+urlencode({'q':plain(n),'type':'talmud'})
    parts.append(f'<article id="n{i}" data-name="{html.escape(n.casefold(),quote=True)}"><h2><a href="{html.escape(search_url,quote=True)}" target="_blank" rel="noopener noreferrer">{html.escape(n)}</a></h2><p class="meta">{counts[i]:,} matching sections · showing {len(hits[i])}</p>')
    if not hits[i]: parts.append('<p>No matching section found.</p>')
    for loc,rich in hits[i]:
        parts.append(f'<section class="context"><div class="citation"><a href="{html.escape(bekiut_url(loc),quote=True)}" target="_blank" rel="noopener noreferrer">{html.escape(loc)}</a></div><div class="source-html">{rich}</div></section>')
    parts.append('</article>')
parts.append('''</main><script>const input=document.querySelector('#search');const items=[...document.querySelectorAll('article')];function filter(){const q=input.value.toLocaleLowerCase().trim();let count=0;for(const el of document.querySelectorAll('[data-name]')){el.hidden=!el.dataset.name.includes(q);if(el.tagName==='ARTICLE'&&!el.hidden)count++}document.querySelector('#visible').textContent=count+' entries shown'}input.addEventListener('input',filter);filter();</script></html>''')
result=''.join(parts)
assert all(len(v)<=3 for v in hits.values())
assert not any(honorific.match(n) for n in names)
assert result.count('<article ')==len(names)
assert result.count('class="source-html"')==summary['sections_displayed']
for v in hits.values():
    for loc,rich in v: assert rich in result
(OUT/'index.html').write_text(result,encoding='utf-8')
(OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps(summary,indent=2))
