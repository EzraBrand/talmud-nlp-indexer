#!/usr/bin/env python3
"""Discover person-reference candidates with GENERAL regexes, not gazetteer alternations.

Usage (Python 3.10+, no dependencies):
 python discover_talmud_names.py --corpus talmud_full_english.txt \
   --gold talmud_names_gazetteer.txt --bible bible_names_gazetteer.txt --out discoveries

Both lists establish known labels. The biblical list additionally supplies an
explicit known-name detection layer, including names without structural cues.
General extraction regexes do not contain gazetteer names. Coverage diagnostics
evaluate those general rules alone, before adding biblical dictionary matches.
Rules cover titled names, patronymics, names before speech verbs, 'named X',
family relationships and anonymous 'a certain ...' descriptions.
Novel candidates are unverified, not established additional true positives.
Review new_candidates.csv, then inspect all_occurrences.csv for context.
The default broad mode adds bare capitalized words and group/appellation rules.
This deliberately returns common nouns and places as well as personal names.
Use priority_candidates.csv first, then inspect broad_only_candidates.csv for
additional low-signal candidates. --mode baseline retains the previous rules.
Offsets are Unicode characters in cleaned_text.txt, end exclusive.
"""
import argparse, csv, html, json, re, unicodedata
from pathlib import Path
from collections import defaultdict, deque, Counter
from bisect import bisect_right

STOP = ('And|But|If|When|What|Who|Which|Why|How|The|This|That|These|Those|He|She|They|'
        'It|We|You|One|As|In|On|At|For|From|With|To|By|Or|Nor|Not|Now|Therefore|'
        'Rather|However|Everyone|Anyone|Someone|There|Here|Yes|No|Says|Said|'
        'Mishna|Gemara|Torah|Israel|Israelites|Shabbat|Passover|Sukkot|'
        'Rabbi|Rav|Rabban|Rebbi|Rab|King|Queen|Emperor|Caesar|Governor|'
        'Had|Has|Have|Did|Do|Does|Was|Were|Is|Are|His|Her|Their|My|Our|Your|'
        'While|Before|After|Should|Would|Could|May|Must|Let|Then|A|An|I|'
        'Even|Just|Perhaps|Granted|Know|Didn’t|Didn\x27t')
LETTER = r'[^\W\d_]'
CAP = r'[A-ZÀ-ÖØ-ÞḤṬẒṢŠ]'
WORD = rf'(?!(?:{STOP})\b){CAP}{LETTER}*(?:[’\x27](?!s\b){LETTER}+)*'
TITLE = r'(?i:rabbi|rav|rabban|rebbi|rab|r\.|king|queen|emperor|caesar|governor)'
EPITHET = rf'(?:Ha{CAP}{LETTER}*|the (?:Elder|Younger|Great)|Ish\s+{WORD})'
BASE_NAME = rf'(?:(?:Bar|Ben|Abba|Mar)\s+)?{WORD}'
PERSON = rf'(?:{TITLE}\s+)?{BASE_NAME}(?:\s+{EPITHET})?'
LINK = r'(?:ben|bar(?:\s+bar)?|son of|daughter of)'
CHAIN = rf'{PERSON}(?:\s*,?\s+{LINK}\s+{PERSON}){{0,3}}'
RULES = {
 'titled_name': rf'(?<!\w){TITLE}\s+{BASE_NAME}(?:\s+{EPITHET})?(?:\s*,?\s+{LINK}\s+{PERSON}){{0,3}}',
 'patronymic': rf'(?<!\w){PERSON}\s*,?\s+{LINK}\s+{CHAIN}',
 'named_person': rf'(?i:\bnamed\s+)(?P<entity>{CHAIN})',
 'speaker_name': rf'(?<!\w)(?P<entity>{CHAIN})(?=\s+(?:said|says|asked|asks|replied|responded|taught|teaches|objected|objects)\b)',
 'family_reference': rf'(?i:\b(?:the\s+)?(?:wife|husband|mother|father|daughter|son|brother|sister|student|disciple|servant)\s+of\s+){CHAIN}',
 'possessive_reference': rf'(?<!\w){CHAIN}[’\x27]s\s+(?:wife|husband|mother|father|daughter|son|brother|sister|student|disciple|servant)\b',
 'anonymous_person': r'(?i:\ba certain\s+(?:[a-z]+[- ]+){0,3}(?:man|woman|child|elder|doctor|merchant|heretic|apostate|butcher|priest|rabbi|disciple|student|gentile|convert|slave|eunuch|emperor|matron|officer|farmer|launderer|guarantor|porter|arab|roman|galilean))\b',
}
BASELINE_RULES = dict(RULES)
# Sentence-opening English words are a large source of weak false positives.
# Apply this only to the bare-word discovery rule, not structural name patterns.
BARE_STOP = ('Come|Blessed|Holy|Jewish|Paschal|All|According|Go|Actually|Any|Say|'
             'Alternatively|Apparently|Conclude|Give|Divine|Israelite|Learn|Until|'
             'Lest|Jews|World|Shall|Sanctuary|New|Presence|Two|Three|Universe|Him|'
             'Whose|Hebrew|High|Take|Most|Me|Please|Since|Although|Because|Hence|'
             'Indeed|Furthermore|Moreover|Nevertheless|Both|Each|Every|Some|'
             'Several|Many|Such|Only|Neither|Either|Once|Again|Without|Within|'
             'Another|First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eight|Nine|Ten')

def discovery_rules(mode):
    if mode == 'baseline':
        return dict(BASELINE_RULES)
    # These are grammatical patterns, not enumerations of gazetteer names.
    # A father may be identified only as "Rav" or "Rabbi".
    person = rf'(?:{PERSON}|(?i:Rav|Rabbi|Rabban))'
    chain = rf'{person}(?:\s*,?\s+{LINK}\s+{person}){{0,3}}'
    rules = dict(BASELINE_RULES)
    rules.update({
      'titled_name': rf'(?<!\w){TITLE}\s+{BASE_NAME}(?:\s+{EPITHET})?(?:\s*,?\s+{LINK}\s+{person}){{0,3}}',
      'patronymic': rf'(?<!\w){person}\s*,?\s+{LINK}\s+{chain}',
      'standalone_honorific': r'(?<!\w)(?:Rav|Rabbi|Rabban)(?!\w)',
      'appellation': rf'(?<!\w)(?:Mar|Reish|Beit|Bet|Beth|Ben|Bar|bar|Abba)\s+{WORD}(?:\s+{EPITHET})?(?!\w)',
      'group_reference': rf'(?i:\b(?:the\s+)?(?:school|house|household|family|sons|daughters|descendants|disciples|students|children|people|residents|elders|judges|sages|rabbis|butchers|men)\s+of\s+)(?:the\s+)?{chain}',
      'office_reference': r'(?i:\b(?:the\s+)?(?:exilarch|high priest|nasi|messiah))\b',
      'locative_reference': rf'(?<!\w){chain}\s+(?:from|of)\s+{WORD}(?!\w)',
      'expanded_family_reference': rf'(?i:\b(?:the\s+)?(?:wife|husband|mother|father|daughter|son|brother|sister|student|disciple|servant|slave|colleague|neighbor|neighbour|father-in-law|mother-in-law|son-in-law|daughter-in-law)\s+of\s+){chain}',
      'bare_capitalized_token': rf'(?<![\w’\x27])(?!(?:{BARE_STOP})\b){WORD}(?![\w’\x27])',
      'anonymous_fallback': r'(?i:\ba certain\s+[a-z]+(?:-[a-z]+)?)\b',
    })
    return rules

def cleaned(s):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFC',html.unescape(re.sub(r'<[^>]+>','',s)))).strip()

def norm(s):
    return re.sub(r'\s+',' ',s.replace('’',"'").replace('‘',"'")).strip().lower()

def folded(s):
    return ''.join(c for c in unicodedata.normalize('NFKD',norm(s)) if not unicodedata.combining(c))

def exact_gold_spans(text, names):
    edges, fail, out = [{}], [0], [[]]
    for name in names:
        p=0
        for c in name:
            if c not in edges[p]:
                edges[p][c]=len(edges); edges.append({}); fail.append(0); out.append([])
            p=edges[p][c]
        out[p].append(name)
    q=deque(edges[0].values())
    while q:
        p=q.popleft()
        for c,v in edges[p].items():
            q.append(v); f=fail[p]
            while f and c not in edges[f]: f=fail[f]
            fail[v]=edges[f].get(c,0); out[v].extend(out[fail[v]])
    candidates=[]; p=0
    for b,c in enumerate(text,1):
        while p and c not in edges[p]: p=fail[p]
        p=edges[p].get(c,0)
        for name in out[p]:
            a=b-len(name)
            if (a==0 or not (text[a-1].isalnum() or text[a-1]=='_')) and (b==len(text) or not (text[b].isalnum() or text[b]=='_')):
                candidates.append((a,b,name))
    return disjoint(candidates,len(text))

def disjoint(rows,length):
    occupied=bytearray(length); selected=[]
    for a,b,data in sorted(rows,key=lambda r:(-(r[1]-r[0]),r[0],str(r[2]))):
        if not any(occupied[a:b]):
            occupied[a:b]=b'\1'*(b-a); selected.append((a,b,data))
    return sorted(selected)

def write_csv(path,header,rows):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f); w.writerow(header); w.writerows(rows)

def concordance(text,a,b,radius=140):
    return text[max(0,a-radius):a]+' ⟦'+text[a:b]+'⟧ '+text[b:b+radius]

def main():
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--corpus',type=Path,required=True)
    p.add_argument('--gold',type=Path,required=True)
    p.add_argument('--bible',type=Path,required=True)
    p.add_argument('--mode',choices=['baseline','broad'],default='broad')
    p.add_argument('--previous-candidates',type=Path,
                   help='Optional previous new_candidates.csv for comparison only.')
    p.add_argument('--out',type=Path,default=Path('discoveries'))
    args=p.parse_args(); args.out.mkdir(parents=True,exist_ok=True)
    text=cleaned(args.corpus.read_text(encoding='utf-8-sig'))
    def load_labels(path):
        return {norm(cleaned(n)):n.strip() for n in path.read_text(encoding='utf-8-sig').splitlines() if n.strip()}
    talmud_labels=load_labels(args.gold)
    bible_labels=load_labels(args.bible)
    labels={**bible_labels,**talmud_labels}
    gold_fold={folded(n) for n in labels}
    # Apostrophe/case normalization preserves positions for this corpus.
    normalized=norm(text)
    if len(normalized)!=len(text): raise ValueError('Normalization changed offsets; inspect Unicode casing.')
    known=exact_gold_spans(normalized,labels)
    bible_mentions=exact_gold_spans(normalized,bible_labels)
    known_starts=[a for a,b,n in known]
    def inside_gold(a,b):
        i=bisect_right(known_starts,a)-1
        return i>=0 and known[i][0]<=a and b<=known[i][1]
    ruleset=discovery_rules(args.mode)
    raw=defaultdict(set)
    for rule,pattern in ruleset.items():
        # Lookahead enumerates overlapping occurrences of the same rule.
        rx=re.compile('(?=('+pattern+'))')
        for m in rx.finditer(text):
            span=m.span('entity') if 'entity' in rx.groupindex else m.span(1)
            if span[0]!=span[1]: raw[span].add(rule)
    # Keep the general-rule benchmark independent of known biblical detection.
    general_selected=disjoint([(a,b,sorted(rules)) for (a,b),rules in raw.items()],len(text))
    for a,b,name in bible_mentions:
        raw[(a,b)].add('known_bible_name')
    # Suppress nested duplicate occurrences across both detection layers.
    selected=disjoint([(a,b,sorted(rules)) for (a,b),rules in raw.items()],len(text))
    def status(a,b):
        n=norm(text[a:b])
        if n in talmud_labels and n in bible_labels: return 'known_both'
        if n in bible_labels: return 'known_bible'
        if n in talmud_labels: return 'known_talmud'
        if folded(n) in gold_fold: return 'spelling_variant_of_gold'
        if inside_gold(a,b): return 'fragment_of_gold_mention'
        return 'new_candidate'
    occ=[]; groups=defaultdict(list)
    known_tokens={folded(w) for name in labels for w in re.findall(LETTER+'+',name)}
    for a,b,rules in selected:
        s=status(a,b)
        row=[text[a:b],s,'; '.join(rules),a,b,concordance(text,a,b)]
        occ.append(row)
        if s=='new_candidate': groups[norm(text[a:b])].append((a,b,rules))
    # Do not discard weak discoveries: put them in a separate review queue.
    weak_rules={'bare_capitalized_token','anonymous_fallback'}
    # Gazetteer tokens influence review order only, never candidate extraction.
    baseline_candidates=None
    if args.previous_candidates:
        with args.previous_candidates.open(encoding='utf-8-sig',newline='') as f:
            baseline_candidates={norm(r['candidate']) for r in csv.DictReader(f)}
    # Heuristic priority is for review order, not a probability or confidence score.
    review=[]
    for n,items in groups.items():
        a,b,_=items[0]; rules=sorted({r for _,_,rs in items for r in rs})
        parts=re.findall(LETTER+'+',text[a:b])
        familiar=sum(folded(w) in known_tokens for w in parts)
        score=(3 if 'titled_name' in rules else 0)+(3 if 'patronymic' in rules else 0)+(2 if 'named_person' in rules else 0)+(1 if len(items)>1 else 0)+(1 if familiar>=2 else 0)
        structural=bool(set(rules)-weak_rules)
        transliteration=any(ord(c)>127 and c.isalpha() for c in text[a:b]) or any(c in text[a:b] for c in "’'")
        queue='priority' if structural or transliteration else 'broad_only'
        new_to_run=n not in baseline_candidates if baseline_candidates is not None else ''
        review.append([text[a:b],len(items),score,'; '.join(rules),concordance(text,a,b),a,b,queue,new_to_run])
    review.sort(key=lambda r:(-r[2],-r[1],r[0].lower()))
    review_header=['candidate','occurrences','review_priority','rules','context','example_start','example_end','review_queue','absent_from_previous_candidates']
    write_csv(args.out/'new_candidates.csv',review_header,review)
    write_csv(args.out/'priority_candidates.csv',review_header,[r for r in review if r[7]=='priority'])
    write_csv(args.out/'broad_only_candidates.csv',review_header,[r for r in review if r[7]=='broad_only'])
    write_csv(args.out/'all_occurrences.csv',['matched_text','status','rules','start','end','context'],occ)
    bible_counts=Counter(name for a,b,name in bible_mentions)
    write_csv(args.out/'bible_mentions.csv',['entry','matched_text','start','end','context'],
              ([bible_labels[name],text[a:b],a,b,concordance(text,a,b)] for a,b,name in bible_mentions))
    write_csv(args.out/'bible_counts.csv',['entry','count','name_length'],
              ([bible_labels[n],bible_counts[n],len(n)] for n in sorted(bible_labels,key=lambda n:(-len(n),n))))
    # Coverage is diagnostic for the supplied list, not ground-truth NER recall.
    starts=[a for a,b,rs in general_selected]; missed=[]; overlap=exact=0
    span_set={(a,b) for a,b,rs in general_selected}
    for a,b,name in known:
        i=bisect_right(starts,a)-1
        hit=(i>=0 and general_selected[i][1]>a) or (i+1<len(general_selected) and general_selected[i+1][0]<b)
        overlap+=hit; exact+=(a,b) in span_set
        if not hit: missed.append([labels[name],text[a:b],a,b,concordance(text,a,b)])
    write_csv(args.out/'missed_gold_mentions.csv',['entry','matched_text','start','end','context'],missed)
    summary={'talmud_entries':len(talmud_labels),'bible_entries':len(bible_labels),'combined_known_entries':len(labels),'gold_exact_nonoverlapping_mentions':len(known),'general_regex_mentions':len(general_selected),'selected_combined_mentions':len(selected),'bible_nonoverlapping_mentions':len(bible_mentions),'bible_entries_found':len(bible_counts),'gold_mentions_overlapped_by_general_rules':overlap,'gold_mentions_exact_boundaries_by_general_rules':exact,'gold_general_rule_overlap_coverage':overlap/len(known) if known else None,'new_candidate_strings':len(review),'new_candidate_occurrences':sum(r[1] for r in review),'status_counts':dict(Counter(r[1] for r in occ)),'sources':{'talmud':'https://github.com/EzraBrand/talmud-nlp-indexer/blob/main/data/talmud_names_gazetteer.txt','bible':'https://github.com/EzraBrand/talmud-nlp-indexer/blob/main/data/bible_names_gazetteer.txt'},'note':'New candidates require validation. General-rule coverage is against both lists, before adding biblical dictionary detections. Bible-only counts are a separate view of the same text; do not add them to combined totals. Matching known biblical strings does not disambiguate historical identities.'}
    gold_spans={(a,b) for a,b,n in known}
    combined_tp=sum((a,b) in gold_spans for a,b,_ in selected)
    def metrics(tp,pred):
        precision=tp/pred if pred else 0
        recall=tp/len(known) if known else 0
        return {'exact_true_positives':tp,'predicted_mentions':pred,
                'precision':precision,'recall':recall,
                'f1':2*precision*recall/(precision+recall) if precision+recall else 0}
    summary.update({'mode':args.mode,'general_exact_metrics':metrics(exact,len(general_selected)),
                    'combined_exact_metrics':metrics(combined_tp,len(selected)),
                    'priority_candidate_strings':sum(r[7]=='priority' for r in review),
                    'broad_only_candidate_strings':sum(r[7]=='broad_only' for r in review),
                    'candidate_strings_absent_from_previous':sum(r[8] is True for r in review)
                        if baseline_candidates is not None else None})
    (args.out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    (args.out/'patterns.json').write_text(json.dumps(ruleset,indent=2),encoding='utf-8')
    (args.out/'cleaned_text.txt').write_text(text,encoding='utf-8')
    print(json.dumps(summary,indent=2))
    print('First 15 review candidates:')
    for r in review[:15]: print(r[:4])

if __name__=='__main__': main()
