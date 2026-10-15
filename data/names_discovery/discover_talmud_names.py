#!/usr/bin/env python3
"""Discover person-reference candidates with GENERAL regexes, not gazetteer alternations.

Usage (Python 3.10+, no dependencies):
 python discover_talmud_names.py --corpus talmud_full_english.txt \
   --gold talmud_names_gazetteer.txt --bible bible_names_gazetteer.txt \
   --toponyms talmud_toponyms_gazetteer.txt bible_places_gazetteer.txt \
   --nations nations_and_demonyms_gazetteer.txt --out discoveries

Both name lists establish known labels. The biblical list additionally supplies an
explicit known-name detection layer, including names without structural cues.
The toponym lists (and the optional nations/demonyms list) supply a separate
known-place detection layer. Known places are labelled, never reported as new
person candidates, and are excluded from the name predictions in the metrics.
General extraction regexes do not contain gazetteer names. Coverage diagnostics
evaluate those general rules alone, before adding dictionary matches.
Rules cover titled names, patronymics, names before speech verbs, 'named X',
family relationships and anonymous 'a certain ...' descriptions.
Novel candidates are unverified, not established additional true positives.
Review new_candidates.csv, then inspect all_occurrences.csv for context.
The default recall mode extends broad mode with surnames and epithets after a
name, possessives, lowercase 'ben', 'the X' expressions, generic descriptions of
people ('an old man', 'this woman') and multi-word places in locative phrases.
It deliberately trades precision for recall; rule_metrics.csv shows the cost of
each rule. --mode broad and --mode baseline retain the previous rule sets.
Offsets are Unicode characters in cleaned_text.txt, end exclusive.
"""
import argparse, csv, html, json, re, sys, unicodedata
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
APOS = r'(?:[’\x27](?!s\b){LETTER}+)*'.replace('{LETTER}', LETTER)
WORD = rf'(?!(?:{STOP})\b){CAP}{LETTER}*{APOS}'
TITLE = r'(?i:rabbi|rav|rabban|rebbi|rab|r\.|king|queen|emperor|caesar|governor)'
EPITHET = rf'(?:Ha{CAP}{LETTER}*|the (?:Elder|Younger|Great)|Ish\s+{WORD})'
BASE_NAME = rf'(?:(?:Bar|Ben|Abba|Mar)\s+)?{WORD}'
PERSON = rf'(?:{TITLE}\s+)?{BASE_NAME}(?:\s+{EPITHET})?'
LINK = r'(?:ben|bar(?:\s+bar)?|son of|daughter of)'
CHAIN = rf'{PERSON}(?:\s*,?\s+{LINK}\s+{PERSON}){{0,3}}'
SPEECH = 'said|says|asked|asks|replied|responded|taught|teaches|objected|objects'
RULES = {
 'titled_name': rf'(?<!\w){TITLE}\s+{BASE_NAME}(?:\s+{EPITHET})?(?:\s*,?\s+{LINK}\s+{PERSON}){{0,3}}',
 'patronymic': rf'(?<!\w){PERSON}\s*,?\s+{LINK}\s+{CHAIN}',
 'named_person': rf'(?i:\bnamed\s+)(?P<entity>{CHAIN})',
 'speaker_name': rf'(?<!\w)(?P<entity>{CHAIN})(?=\s+(?:{SPEECH})\b)',
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
# Common nouns for people. Used only after a determiner, in recall mode.
PERSON_NOUNS = ('man|men|woman|women|girl|girls|boy|boys|youth|youths|child|children|person|'
                'people|elder|elders|bandit|bandits|emperor|governor|king|queen|prince|'
                'princess|spies|spy|prophet|prophets|prophetess|matron|heretic|heretics|'
                'apostate|gentile|gentiles|idolater|idolaters|sadducee|sadducees|'
                'samaritan|priest|priests|maidservant|maidservants|servant|servants|slave|'
                'slaves|widow|orphan|judge|judges|officer|officers|minister|ministers|'
                'officials?|general|sage|scholar|scholars|student|students|disciple|disciples|'
                'host|guest|guests|merchant|merchants|doctor|sorcerer|sorceress|magician|'
                'magus|demon|angel|angels|eunuch|convert|harlot|prostitute|thief|thieves|'
                'robber|robbers|sailor|sailors|shepherd|shepherds|butcher|launderer|'
                'tanner|innkeeper|nobleman|noblewoman|lady|maiden|infant|baby|son|daughter|'
                'sons|daughters|wife|husband|father|mother|brother|sister|bride|groom|'
                'heir|heirs|neighbor|neighbors|kingdom|nation|nations|generation|'
                'scribe|scribes|teacher|teachers|tanna|tannaim|amora|amoraim|exilarch|nasi')
DETERMINER = r'(?:a|an|the|this|that|these|those|one|some|another|certain)'
LOWER_EPITHETS = ('priest|scribe|elder|younger|great|small|pious|righteous|wicked|'
                  'babylonian|galilean|tanner|smith|physician|doctor|hasid|tzaddik|'
                  'distinguished|first|second|wise|blind|lame|short|tall')
# Roles and groups often written with a bare 'the'. Generic English nouns only.
ROLE_NOUNS = ('emperor|governor|king|queen|prince|princess|nasi|exilarch|spies|prophet|'
              'matron|heretic|heretics|sadducees?|wicked kingdom|evil kingdom|wicked one|'
              'elders|judges|sages|rabbis|scribes|patriarchs|matriarchs|priests|levites|'
              'prophets|kings|nations|gentiles|idolaters|samaritans|romans|persians|'
              'magi|amora[’\x27]?im|tanna[’\x27]?im|students|disciples|servants|slaves|'
              'members|residents|inhabitants|people of the [a-z]+')
# English function words and sentence openers only: never names, places or groups.
EXTRA_STOP = ('So|Where|Like|Bring|Initially|Due|Ultimately|Anything|Be|Whether|Whoever|'
              'Its|Write|Evidently|Can|Since|During|Wherever|Bless|Whatever|Tell|'
              'Between|Afterward|Afterwards|Accordingly|Consequently|Thus|Otherwise|'
              'Nowadays|Today|Tomorrow|Yesterday|Behold|See|Look|Listen|Leave|Here|'
              'Everything|Nothing|Something|Will|Might|Upon|Among|Through|Toward|'
              'Towards|About|Above|Below|Under|Over|Into|Onto|Out|Up|Down|Off|Very|Too|'
              'Also|Still|Yet|Already|Always|Never|Sometimes|Usually|Generally|'
              'Certainly|Clearly|Obviously|Similarly|Likewise|Instead|Unless|Though|'
              'Whenever|Wherever|Whereas|Where|Whom|Whose|Yours|Mine|Ours|Theirs|'
              'Hers|Himself|Herself|Themselves|Itself|Oneself|Ourselves|Yourself|'
              'Did|Can|Cannot|Will|Won|Why|Ok|Okay|Well|Oh|Woe|Alas|Rise|Stand|Sit|'
              'Eat|Drink|Bring|Put|Make|Do|Get|Let|Keep|Hold|Turn|Open|Close|Teach|'
              'Read|Write|Tell|Ask|Answer|Return|Remove|Place|Send|Show|Note|Consider|'
              'Explain|Infer|Derive|Rule|Prohibit|Permit|Wait|Hear|Remember|Forget|'
              'Four|Five|Six|Seven|Eleven|Twelve|Hundred|Thousand')

def discovery_rules(mode, surnames=()):
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
    if mode == 'broad':
        return rules
    # Recall mode: wider name shapes and more cue words. Lower precision is accepted.
    word2 = rf'{WORD}(?:-{WORD})?'
    epithet = (rf'(?:Ha{CAP}{LETTER}*{APOS}|the\s+{WORD}|the\s+(?i:{LOWER_EPITHETS})(?!\w)'
               rf'|Ish\s+{WORD})')
    # A name may carry a second capitalized word: a surname or nickname (Yitzḥak Nappaḥa).
    # The surname is not taken when a patronymic link follows (Rav Huna Ḥiyya bar Rav)
    # and is not taken inside a patronymic chain, where it mostly absorbs the next sentence.
    prefix = r'(?:(?:Bar|Ben|ben|Abba|Mar)\s+)?'
    # Surnames come from corpus statistics (see surname_candidates), never from a gazetteer.
    sur = '|'.join(sorted(map(re.escape, surnames), key=len, reverse=True)) or '(?!)'
    base = rf'{prefix}{word2}(?:\s+(?:{sur})(?![\w’\x27])(?!\s*,?\s+{LINK}\b))?'
    base_link = rf'{prefix}{word2}'
    person_r = rf'(?:(?:{TITLE}\s+)?{base_link}(?:\s+{epithet})?|(?i:Rav|Rabbi|Rabban))'
    chain_r = rf'{person_r}(?:\s*,?\s+{LINK}\s+{person_r}){{0,3}}'
    speech = (SPEECH + '|say|stated|states|related|relates|raised|raises|challenged|'
              'explained|explains|interpreted|interprets|expounded|expounds|ruled|rules|'
              'holds|held|maintains|maintained|disagrees|disagreed|inquired|sent|'
              'answered|answers|cited|cites|transmitted|reported|reports|would|also|'
              'came|went|heard|saw|told|tells|deems|deemed|concedes|conceded|agrees|'
              'agreed|permits|permitted|prohibits|prohibited|did|was|is|had|has')
    rules.update({
      'titled_name': rf'(?<!\w){TITLE}\s+{base}(?:\s+{epithet})?(?:\s*,?\s+{LINK}\s+{person_r}){{0,3}}',
      'titled_surname': rf'(?<!\w){TITLE}\s+{base}(?:\s+{epithet})?(?!\w)',
      'patronymic': rf'(?<!\w){person_r}\s*,?\s+{LINK}\s+{chain_r}',
      'speaker_name': rf'(?<!\w)(?!(?:{BARE_STOP}|{EXTRA_STOP})\b)(?P<entity>{chain_r})(?=[’\x27]?\s*,?\s+(?:{speech})\b)',
      'named_person': rf'(?i:\b(?:named|called|known as)\s+)(?P<entity>{chain_r})',
      'standalone_honorific': r'(?<!\w)(?i:rav|rabbi|rabban|rabbis|sages)(?!\w)',
      # Lowercase 'ben' and a doubled name (ben Bag Bag).
      'appellation': rf'(?<!\w)(?:Mar|Reish|Beit|Bet|Beth|Bei|Ben|ben|Bar|bar|Abba|Imma|Ima)\s+{word2}(?:\s+{WORD})?(?:\s+{epithet})?(?!\w)',
      'name_with_epithet': rf'(?<!\w)(?!(?:{BARE_STOP}|{EXTRA_STOP})\b)(?!{LETTER}*n[’\x27]t\b){word2}\s+{epithet}(?!\w)',
      'locative_reference': rf'(?<!\w){chain_r}\s*,?\s+(?:from|of)\s+(?:the\s+)?{WORD}(?:\s+{WORD})?(?!\w)',
      'group_reference': rf'(?i:\b(?:the\s+)?(?:school|house|household|family|sons|daughters|descendants|disciples|students|children|people|residents|inhabitants|members|elders|judges|court|sages|rabbis|butchers|men|women|servants|slaves|generation)\s+of\s+)(?:the\s+)?{chain_r}',
      'expanded_family_reference': rf'(?i:\b(?:the\s+)?(?:wife|husband|mother|father|daughter|son|brother|sister|student|disciple|servant|slave|maidservant|colleague|neighbor|neighbour|host|attendant|scribe|teacher|father-in-law|mother-in-law|son-in-law|daughter-in-law|brother-in-law|sister-in-law|grandson|granddaughter|grandfather|grandmother|nephew|uncle|aunt|widow)\s+of\s+){chain_r}',
      'possessive_reference': rf'(?<!\w){chain_r}[’\x27]s\s+(?:wife|husband|mother|father|daughter|son|brother|sister|student|disciple|servant|slave|maidservant|colleague|neighbor|host|attendant|scribe|teacher|father-in-law|mother-in-law|son-in-law|daughter-in-law|sons|daughters|household|family|school|house)\b',
      # Bare capitalized words may now carry a possessive ’s (Rava’s).
      'bare_capitalized_token': rf'(?<![\w’\x27])(?!(?:{BARE_STOP}|{EXTRA_STOP})\b)(?!{LETTER}*n[’\x27]t\b){word2}(?!\w)(?![’\x27](?!s\b))',
      'the_capitalized': rf'(?<!\w)(?i:the)\s+{WORD}(?!\w)',
      # Generic people: a qualifying word or a pointing determiner is required
      # ('an old man', 'this woman'), so bare 'a person' or 'the father' is not taken.
      'descriptive_person': rf'(?<!\w)(?i:(?:(?:a|an|the|one|some|another)\s+(?!certain\b)(?:[a-z]+[- ]+){{1,2}}|(?:this|that|these|those|one)\s+)(?:{PERSON_NOUNS}))(?!\w)',
      # Roles and groups that are often written with a bare 'the'.
      'role_title': rf'(?<!\w)(?i:the\s+(?:{ROLE_NOUNS}))(?!\w)',
      'generation_reference': r'(?<!\w)(?i:the\s+generation\s+of\s+(?:the\s+)?[a-z]+)(?!\w)',
      'one_of_group': rf'(?<!\w)(?i:one\s+of\s+the\s+(?:[a-z]+\s+)?(?:{PERSON_NOUNS}|sages|rabbis|amora[’\x27]?im|tanna[’\x27]?im))(?!\w)',
    })
    return rules

def surname_candidates(text):
    '''Corpus statistics, not gazetteer content. A surname or nickname is a word that
    follows a titled name at least twice (Rabbi Yitzḥak Nappaḥa) and that the
    corpus does not itself use as a first name (after a title) or as a bare speaker.'''
    after_title=Counter(re.findall(rf'(?<!\w){TITLE}\s+({WORD})',text))
    # A bare speaker is a word before a speech verb that does not follow another name.
    speakers=Counter()
    for m in re.finditer(rf'(?<![\w’\x27])({WORD})\s+(?:{SPEECH})\b',text):
        before=text[max(0,m.start()-40):m.start()].split()
        if not (before and before[-1][:1].isupper() and before[-1][-1:].isalpha()):
            speakers[m.group(1)]+=1
    pairs=Counter(re.findall(rf'(?<!\w){TITLE}\s+(?:(?:Bar|Ben|ben|Abba|Mar)\s+)?{WORD}\s+({WORD})(?![\w’\x27])',text))
    stop=set(BARE_STOP.split('|'))|set(EXTRA_STOP.split('|'))|{'Bar','Ben','Mar','Reish','Ish','Abba','Beit','Bei'}
    return sorted(w for w,c in pairs.items()
                  if c>=2 and after_title[w]<3 and speakers[w]<3 and w not in stop
                  and not w.startswith('Ha'))

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
    sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--corpus',type=Path,required=True)
    p.add_argument('--gold',type=Path,required=True)
    p.add_argument('--bible',type=Path,required=True)
    p.add_argument('--toponyms',type=Path,nargs='*',default=[],
                   help='One or more place-name gazetteers (known toponym layer).')
    p.add_argument('--nations',type=Path,
                   help='Optional nations/demonyms gazetteer, labelled like toponyms.')
    p.add_argument('--mode',choices=['baseline','broad','recall'],default='recall')
    p.add_argument('--previous-candidates',type=Path,
                   help='Optional previous new_candidates.csv for comparison only.')
    p.add_argument('--out',type=Path,default=Path('discoveries'))
    args=p.parse_args(); args.out.mkdir(parents=True,exist_ok=True)
    text=cleaned(args.corpus.read_text(encoding='utf-8-sig'))
    def load_labels(paths):
        labels={}
        for path in paths:
            for n in path.read_text(encoding='utf-8-sig').splitlines():
                if n.strip(): labels.setdefault(norm(cleaned(n)),cleaned(n))
        return labels
    talmud_labels=load_labels([args.gold])
    bible_labels=load_labels([args.bible])
    place_labels=load_labels(args.toponyms)
    nation_labels=load_labels([args.nations]) if args.nations else {}
    labels={**bible_labels,**talmud_labels}
    gold_fold={folded(n) for n in labels}
    # Apostrophe/case normalization preserves positions for this corpus.
    normalized=norm(text)
    if len(normalized)!=len(text): raise ValueError('Normalization changed offsets; inspect Unicode casing.')
    known=exact_gold_spans(normalized,labels)
    bible_mentions=exact_gold_spans(normalized,bible_labels)
    # Places and nations form one known-place layer; a nation entry is tagged separately.
    place_layer={**nation_labels,**place_labels}
    place_mentions=exact_gold_spans(normalized,place_layer) if place_layer else []
    known_starts=[a for a,b,n in known]
    def inside_gold(a,b):
        i=bisect_right(known_starts,a)-1
        return i>=0 and known[i][0]<=a and b<=known[i][1]
    place_starts=[a for a,b,n in place_mentions]
    def places_within(a,b):
        i=bisect_right(place_starts,a-1)
        found=[]
        while i<len(place_mentions) and place_mentions[i][0]<b:
            pa,pb,pn=place_mentions[i]
            if a<=pa and pb<=b: found.append(place_layer[pn])
            i+=1
        return found
    ruleset=discovery_rules(args.mode,surname_candidates(text))
    raw=defaultdict(set)
    for rule,pattern in ruleset.items():
        # Lookahead enumerates overlapping occurrences of the same rule.
        rx=re.compile('(?=('+pattern+'))')
        for m in rx.finditer(text):
            span=m.span('entity') if 'entity' in rx.groupindex else m.span(1)
            if span[0]!=span[1]: raw[span].add(rule)
    # Keep the general-rule benchmark independent of known dictionary detection.
    general_selected=disjoint([(a,b,sorted(rules)) for (a,b),rules in raw.items()],len(text))
    for a,b,name in bible_mentions:
        raw[(a,b)].add('known_bible_name')
    for a,b,name in place_mentions:
        raw[(a,b)].add('known_nation' if name in nation_labels and name not in place_labels else 'known_toponym')
    # Suppress nested duplicate occurrences across all detection layers.
    selected=disjoint([(a,b,sorted(rules)) for (a,b),rules in raw.items()],len(text))
    def status(a,b):
        n=norm(text[a:b])
        is_place=n in place_labels; is_nation=n in nation_labels
        if n in labels and (is_place or is_nation): return 'known_name_and_place'
        if n in talmud_labels and n in bible_labels: return 'known_both'
        if n in bible_labels: return 'known_bible'
        if n in talmud_labels: return 'known_talmud'
        if is_place: return 'known_toponym'
        if is_nation: return 'known_nation'
        if folded(n) in gold_fold: return 'spelling_variant_of_gold'
        if inside_gold(a,b): return 'fragment_of_gold_mention'
        return 'new_candidate'
    occ=[]; groups=defaultdict(list); statuses={}
    known_tokens={folded(w) for name in labels for w in re.findall(LETTER+'+',name)}
    for a,b,rules in selected:
        s=status(a,b); statuses[(a,b)]=s
        inner='; '.join(places_within(a,b)) if s not in ('known_toponym','known_nation') else ''
        row=[text[a:b],s,'; '.join(rules),inner,a,b,concordance(text,a,b)]
        occ.append(row)
        if s=='new_candidate': groups[norm(text[a:b])].append((a,b,rules))
    # Do not discard weak discoveries: put them in a separate review queue.
    weak_rules={'bare_capitalized_token','anonymous_fallback','the_capitalized','name_with_epithet',
                'descriptive_person','standalone_honorific','one_of_group'}
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
        inner=places_within(a,b)
        score=(3 if 'titled_name' in rules else 0)+(3 if 'patronymic' in rules else 0)+(2 if 'named_person' in rules else 0)+(1 if len(items)>1 else 0)+(1 if familiar>=2 else 0)+(1 if inner and set(rules)&{'locative_reference','titled_name','patronymic'} else 0)
        structural=bool(set(rules)-weak_rules)
        transliteration=any(ord(c)>127 and c.isalpha() for c in text[a:b]) or any(c in text[a:b] for c in "’'")
        queue='priority' if structural or transliteration else 'broad_only'
        new_to_run=n not in baseline_candidates if baseline_candidates is not None else ''
        review.append([text[a:b],len(items),score,'; '.join(rules),'; '.join(inner),concordance(text,a,b),a,b,queue,new_to_run])
    review.sort(key=lambda r:(-r[2],-r[1],r[0].lower()))
    review_header=['candidate','occurrences','review_priority','rules','known_places_in_span','context','example_start','example_end','review_queue','absent_from_previous_candidates']
    write_csv(args.out/'new_candidates.csv',review_header,review)
    write_csv(args.out/'priority_candidates.csv',review_header,[r for r in review if r[8]=='priority'])
    write_csv(args.out/'broad_only_candidates.csv',review_header,[r for r in review if r[8]=='broad_only'])
    write_csv(args.out/'all_occurrences.csv',['matched_text','status','rules','known_places_in_span','start','end','context'],occ)
    bible_counts=Counter(name for a,b,name in bible_mentions)
    write_csv(args.out/'bible_mentions.csv',['entry','matched_text','start','end','context'],
              ([bible_labels[name],text[a:b],a,b,concordance(text,a,b)] for a,b,name in bible_mentions))
    write_csv(args.out/'bible_counts.csv',['entry','count','name_length'],
              ([bible_labels[n],bible_counts[n],len(n)] for n in sorted(bible_labels,key=lambda n:(-len(n),n))))
    # Toponym views: every dictionary hit, and whether it survived as its own span.
    sel_status={(a,b):statuses[(a,b)] for a,b,_ in selected}
    place_counts=Counter(name for a,b,name in place_mentions)
    def place_source(n):
        return '; '.join(s for s,d in (('toponym',place_labels),('nation',nation_labels),('talmud_name',talmud_labels),('bible_name',bible_labels)) if n in d)
    write_csv(args.out/'toponym_mentions.csv',['entry','matched_text','sources','selected_as','start','end','context'],
              ([place_layer[n],text[a:b],place_source(n),sel_status.get((a,b),'inside_longer_span'),a,b,concordance(text,a,b)] for a,b,n in place_mentions))
    write_csv(args.out/'toponym_counts.csv',['entry','count','sources'],
              ([place_layer[n],place_counts[n],place_source(n)] for n in sorted(place_layer,key=lambda n:(-place_counts[n],n))))
    # Places named in locative phrases that are not in any list: candidate toponyms.
    topo_cands=defaultdict(list)
    for (a,b),rules in raw.items():
        if 'locative_reference' not in rules: continue
        m=re.search(rf'\s(?:from|of)\s+(?:the\s+)?({WORD}(?:\s+{WORD})?)$',text[a:b])
        if not m: continue
        pa,pb=a+m.start(1),a+m.end(1); n=norm(text[pa:pb])
        if n not in place_layer and n not in labels: topo_cands[n].append((pa,pb,a,b))
    write_csv(args.out/'toponym_candidates.csv',['candidate','occurrences','example_phrase','context'],
              sorted(([text[v[0][0]:v[0][1]],len(v),text[v[0][2]:v[0][3]],concordance(text,v[0][0],v[0][1])] for n,v in topo_cands.items()),key=lambda r:(-r[1],r[0].lower())))
    # Coverage is diagnostic for the supplied list, not ground-truth NER recall.
    starts=[a for a,b,rs in general_selected]; missed=[]; overlap=exact=0
    span_set={(a,b) for a,b,rs in general_selected}
    for a,b,name in known:
        i=bisect_right(starts,a)-1
        hit=(i>=0 and general_selected[i][1]>a) or (i+1<len(general_selected) and general_selected[i+1][0]<b)
        overlap+=hit; exact+=(a,b) in span_set
        if not hit: missed.append([labels[name],text[a:b],a,b,concordance(text,a,b)])
    write_csv(args.out/'missed_gold_mentions.csv',['entry','matched_text','start','end','context'],missed)
    gold_spans={(a,b) for a,b,n in known}
    # Per-rule cost: how many selected spans each rule supports, and how many are exact gold.
    rule_tp=Counter(); rule_n=Counter()
    for a,b,rules in general_selected:
        for r in rules:
            rule_n[r]+=1; rule_tp[r]+=(a,b) in gold_spans
    write_csv(args.out/'rule_metrics.csv',['rule','selected_spans','exact_gold','precision'],
              sorted(([r,rule_n[r],rule_tp[r],round(rule_tp[r]/rule_n[r],4)] for r in rule_n),key=lambda r:-r[1]))
    summary={'talmud_entries':len(talmud_labels),'bible_entries':len(bible_labels),'toponym_entries':len(place_labels),'nation_entries':len(nation_labels),'combined_known_entries':len(labels),'gold_exact_nonoverlapping_mentions':len(known),'general_regex_mentions':len(general_selected),'selected_combined_mentions':len(selected),'bible_nonoverlapping_mentions':len(bible_mentions),'bible_entries_found':len(bible_counts),'place_nonoverlapping_mentions':len(place_mentions),'place_entries_found':len(place_counts),'gold_mentions_overlapped_by_general_rules':overlap,'gold_mentions_exact_boundaries_by_general_rules':exact,'gold_general_rule_overlap_coverage':overlap/len(known) if known else None,'new_candidate_strings':len(review),'new_candidate_occurrences':sum(r[1] for r in review),'toponym_candidate_strings':len(topo_cands),'status_counts':dict(Counter(r[1] for r in occ)),'sources':{'talmud':'https://github.com/EzraBrand/talmud-nlp-indexer/blob/main/data/talmud_names_gazetteer.txt','bible':'https://github.com/EzraBrand/talmud-nlp-indexer/blob/main/data/bible_names_gazetteer.txt','toponyms':[str(t.name) for t in args.toponyms],'nations':args.nations.name if args.nations else None},'note':'New candidates require validation. General-rule coverage is against both name lists, before adding dictionary detections. Bible-only and place counts are separate views of the same text; do not add them to combined totals. Matching known strings does not disambiguate historical identities. Name metrics exclude spans labelled only as known places.'}
    def metrics(tp,pred):
        precision=tp/pred if pred else 0
        recall=tp/len(known) if known else 0
        return {'exact_true_positives':tp,'predicted_mentions':pred,
                'precision':precision,'recall':recall,
                'f1':2*precision*recall/(precision+recall) if precision+recall else 0}
    combined_tp=sum((a,b) in gold_spans for a,b,_ in selected)
    # A span labelled only as a known place is not a person prediction.
    name_preds=[(a,b) for a,b,_ in selected if statuses[(a,b)] not in ('known_toponym','known_nation')]
    name_tp=sum(s in gold_spans for s in name_preds)
    summary.update({'mode':args.mode,'general_exact_metrics':metrics(exact,len(general_selected)),
                    'combined_exact_metrics':metrics(combined_tp,len(selected)),
                    'combined_name_metrics_excluding_known_places':metrics(name_tp,len(name_preds)),
                    'priority_candidate_strings':sum(r[8]=='priority' for r in review),
                    'broad_only_candidate_strings':sum(r[8]=='broad_only' for r in review),
                    'candidate_strings_absent_from_previous':sum(r[9] is True for r in review)
                        if baseline_candidates is not None else None})
    (args.out/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
    (args.out/'patterns.json').write_text(json.dumps(ruleset,indent=2,ensure_ascii=False),encoding='utf-8')
    (args.out/'cleaned_text.txt').write_text(text,encoding='utf-8')
    print(json.dumps(summary,indent=2,ensure_ascii=False))
    print('First 15 review candidates:')
    for r in review[:15]: print(r[:4])

if __name__=='__main__': main()
