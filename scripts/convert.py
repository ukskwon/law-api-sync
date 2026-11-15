# API로 받은 원문을 「산업안전 법령 학습 대시보드」 형식으로 바꾼다.
# 결과: dash/extra.json {built, docs:[대시보드에 없는 규정의 조문], revs:[95개 규정 제개정 현황], prec:[판례 요약]}
#       dash/precfull.json {판례일련번호: 판례 전문}
import json, os, re, glob
from datetime import datetime, timezone, timedelta
KST = timezone(timedelta(hours=9))
regs = {r['key']: r for r in json.load(open('regs.json', encoding='utf-8'))}
man = json.load(open('manifest.json', encoding='utf-8'))['regs']
compare = json.load(open('compare.json', encoding='utf-8')) if os.path.exists('compare.json') else {}
in_dash = None if not compare else set(regs) - set(x['key'] for x in compare.get('apiOnly', []))

def clean(s):
    s = re.sub(r'<br\s*/?>', '\n', str(s or ''), flags=re.I)
    s = re.sub(r'<[^>]+>', '', s)
    return re.sub(r'[ \t　]+', ' ', s).strip()

def dfmt(s):
    s = str(s or '')
    return '%d. %d. %d.' % (int(s[:4]), int(s[4:6]), int(s[6:8])) if re.fullmatch(r'\d{8}', s) else s

def as_list(x):
    return x if isinstance(x, list) else ([x] if x else [])

def flat_text(v):
    if isinstance(v, list): return '\n'.join(flat_text(i) for i in v)
    return clean(v)

def law_doc(key, body, info):
    L = body['법령']; arts = []; chap = []
    for u in as_list(L.get('조문', {}).get('조문단위')):
        txt = clean(u.get('조문내용'))
        if u.get('조문여부') == '전문':
            h = txt.strip()
            lvl = 0 if re.match(r'제\d+편', h) else 1 if re.match(r'제\d+장', h) else 2 if re.match(r'제\d+절', h) else 3
            chap = [c for c in chap if c[0] < lvl] + [(lvl, h)]
            continue
        no = '제%s조' % u.get('조문번호') + ('의%s' % u['조문가지번호'] if u.get('조문가지번호') else '')
        title = u.get('조문제목') or ''
        p = []
        head = re.sub(r'^' + re.escape(no) + r'(\([^)]*\))?\s*', '', txt)
        if head: p.append([0, head])
        for h in as_list(u.get('항')):
            if isinstance(h, dict) and h.get('항내용'): p.append([1, clean(flat_text(h['항내용']))])
            for ho in as_list(h.get('호') if isinstance(h, dict) else None):
                p.append([2, clean(flat_text(ho.get('호내용')))])
                for mo in as_list(ho.get('목')):
                    p.append([3, clean(flat_text(mo.get('목내용')))])
        arts.append({'n': no, 't': title, 'c': ' / '.join(c[1] for c in chap), 'p': p})
    return arts

def adm_doc(key, body, info):
    A = body['AdmRulService']; arts = []; chap = []
    for line in as_list(A.get('조문내용')):
        s = clean(flat_text(line))
        if not s: continue
        m = re.match(r'^(제\d+조(?:의\d+)?)\s*(?:\(([^)]*)\))?\s*(.*)$', s, re.S)
        if not m:
            h = s.split('\n')[0][:60]
            if re.match(r'제\d+(편|장|절|관)', h):
                lvl = {'편': 0, '장': 1, '절': 2, '관': 3}[re.match(r'제\d+(편|장|절|관)', h).group(1)]
                chap = [c for c in chap if c[0] < lvl] + [(lvl, h)]
            continue
        rest = m.group(3)
        rest = re.sub(r'(?<=[.다\)])\s*(?=(?:[①-⑳]|\d{1,2}\.\s|[가-하]\.\s))', '\n', rest)
        p = []
        for seg in [x.strip() for x in rest.split('\n') if x.strip()]:
            lvl = 1 if re.match(r'[①-⑳]', seg) else 2 if re.match(r'\d{1,2}\.', seg) else 3 if re.match(r'[가-하]\.', seg) else 0
            p.append([lvl, seg])
        arts.append({'n': m.group(1), 't': m.group(2) or '', 'c': ' / '.join(c[1] for c in chap), 'p': p})
    return arts

docs, revs = [], []
for key, info in man.items():
    reg = regs.get(key, {})
    path = 'data/%s.json' % key
    reason = ''
    try:
        body = json.load(open(path, encoding='utf-8'))
    except Exception:
        body = None
    if body:
        rz = (body.get('법령') or {}).get('제개정이유') or (body.get('AdmRulService') or {}).get('제개정이유') or {}
        reason = clean(flat_text(rz.get('제개정이유내용') if isinstance(rz, dict) else rz))[:1200]
    revs.append({'key': key, 'name': info.get('name') or reg.get('name'), 'kind': info.get('kind') or reg.get('kind'), 'promul': info.get('promul'),
                 'no': info.get('promulNo'), 'enforce': info.get('enforce'), 'rev': info.get('rev'), 'reason': reason, 'inDash': key not in [x['key'] for x in compare.get('apiOnly', [])]})
    if body and key.startswith('m_'):
        arts = law_doc(key, body, info) if reg.get('target') == 'law' else adm_doc(key, body, info)
        kind = info.get('kind') or reg.get('kind') or ''
        no = '%s 제%s호' % (kind, str(info.get('promulNo') or '').lstrip('0')) + (', %s 공포' % dfmt(info.get('promul')) if info.get('promul') else '')
        docs.append({'key': key, 'name': info.get('name') or reg['name'], 'kind': kind, 'eff': dfmt(info.get('enforce')), 'effRaw': info.get('enforce'),
                     'no': no, 'st': '국가법령정보센터 Open API 현행본', 'note': '', 'arts': arts, 'apps': [], 'g': 'api'})

prec, full = [], {}
idx = json.load(open('prec_index.json', encoding='utf-8'))['items'] if os.path.exists('prec_index.json') else {}
for pid, it in idx.items():
    f = 'data/prec/%s.json' % pid
    if not os.path.exists(f): continue
    b = json.load(open(f, encoding='utf-8'))
    g = clean(b.get('판시사항'))
    gs = [x.strip() for x in re.split(r'\[\d+\]', g) if x.strip()] if g else []
    prec.append({'id': pid, 'n': b.get('사건번호') or it.get('n'), 'c': b.get('법원명') or it.get('c'), 'd': str(b.get('선고일자') or it.get('d') or '').replace('.', ''),
                 't': b.get('사건종류명') or it.get('t'), 'm': b.get('사건명') or it.get('m'), 'g': gs, 'y': clean(b.get('판결요지')), 'r': clean(b.get('참조조문')), 'src': 'api'})
    body = clean(b.get('판례내용'))
    if body: full[pid] = body[:60000]
prec.sort(key=lambda x: str(x['d']), reverse=True)
os.makedirs('dash', exist_ok=True)
out = {'built': datetime.now(KST).strftime('%Y-%m-%d %H:%M'), 'docs': docs, 'revs': revs, 'prec': prec}
json.dump(out, open('dash/extra.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
json.dump(full, open('dash/precfull.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print('대시보드용: 추가 규정 %d개(조문 %d), 제개정 현황 %d, 판례 %d(전문 %d)' % (len(docs), sum(len(d['arts']) for d in docs), len(revs), len(prec), len(full)))
for d in docs: print(' -', d['name'], len(d['arts']))
