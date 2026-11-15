# 국가법령정보센터 Open API로 regs.json 의 법령·행정규칙 현행본을 받아 data/ 에 저장한다.
# 환경변수 LAW_OC: 국가법령정보센터 Open API 인증값(OC). 저장소 Secrets 에 넣는다.
# 결과: data/<key>.json(원문 응답 그대로), manifest.json(규정별 일련번호·공포·시행일, 받은 시각), report.json(실패 목록)
import json, os, re, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta

OC = os.environ.get('LAW_OC', '').strip()
if not OC:
    sys.exit('LAW_OC 가 비어 있습니다. 저장소 Settings > Secrets and variables > Actions 에 LAW_OC 를 넣어 주세요.')
BASE = 'https://www.law.go.kr/DRF/'
KST = timezone(timedelta(hours=9))
UA = {'User-Agent': 'Mozilla/5.0 (law-api-sync; personal study)'}

def get(path, **q):
    q.update(OC=OC, type='JSON')
    url = BASE + path + '?' + urllib.parse.urlencode(q)
    last = None
    for i in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                body = r.read().decode('utf-8', 'replace')
            return json.loads(body)
        except Exception as e:  # 네트워크 오류·JSON 이 아닌 응답(오류 안내 HTML 등)
            last = e
            time.sleep(3 * (i + 1))
    raise RuntimeError('%s: %s' % (path, last))

def norm(s):
    return re.sub(r'[\s·ㆍ\-\(\)「」]', '', re.sub(r'^\((고용노동부|국토교통부|환경부)\)\s*', '', s or ''))

def as_list(x):
    return x if isinstance(x, list) else ([x] if x else [])

def find(reg):
    q = re.sub(r'^\((고용노동부|국토교통부|환경부)\)\s*', '', reg['name'])
    want = norm(reg['name'])
    if reg['target'] == 'law':
        r = get('lawSearch.do', target='law', query=q, display=100)
        rows = as_list((r.get('LawSearch') or {}).get('law'))
        rows = [x for x in rows if norm(x.get('법령명한글')) == want]
        # 같은 법령이 공포 회차별로 여러 줄(현행·연혁·시행예정) 나올 수 있다. 오늘까지 시행된 것 중 가장 최근 공포본을 고른다.
        today = datetime.now(KST).strftime('%Y%m%d')
        live = [x for x in rows if str(x.get('시행일자') or '') <= today] or rows
        if not live: return None
        rows = sorted(live, key=lambda x: (str(x.get('공포일자') or ''), int(str(x.get('법령일련번호') or 0) or 0)), reverse=True)
        nxt = sorted([x for x in rows if str(x.get('시행일자') or '') > today], key=lambda x: str(x.get('시행일자')))
        x = rows[0]
        return {'mst': x.get('법령일련번호'), 'id': x.get('법령ID'), 'name': (x.get('법령명한글') or '').strip(),
                'promul': x.get('공포일자'), 'promulNo': x.get('공포번호'), 'enforce': x.get('시행일자'), 'kind': x.get('법령구분명'), 'rev': x.get('제개정구분명'),
                'rows': [[r.get('법령일련번호'), r.get('공포일자'), r.get('공포번호'), r.get('시행일자'), r.get('현행연혁코드')] for r in rows[:6]]}
    r = get('lawSearch.do', target='admrul', query=q, display=100)
    rows = as_list((r.get('AdmRulSearch') or {}).get('admrul'))
    rows = [x for x in rows if norm(x.get('행정규칙명')) == want and x.get('현행연혁구분', '현행') == '현행']
    if not rows: return None
    rows.sort(key=lambda x: (str(x.get('발령일자') or ''), int(str(x.get('행정규칙일련번호') or 0) or 0)), reverse=True)
    x = rows[0]
    return {'mst': x.get('행정규칙일련번호'), 'id': x.get('행정규칙ID'), 'name': (x.get('행정규칙명') or '').strip(),
            'promul': x.get('발령일자'), 'promulNo': x.get('발령번호'), 'enforce': x.get('시행일자'), 'kind': x.get('행정규칙종류'), 'rev': x.get('제개정구분명')}

def main():
    regs = json.load(open('regs.json', encoding='utf-8'))
    only = set(a for a in sys.argv[1:])
    os.makedirs('data', exist_ok=True)
    old = json.load(open('manifest.json', encoding='utf-8')) if os.path.exists('manifest.json') else {'regs': {}}
    man = {'fetched': datetime.now(KST).strftime('%Y-%m-%d %H:%M'), 'regs': dict(old.get('regs') or {})}
    fails, changed = [], []
    for reg in regs:
        if only and reg['key'] not in only: continue
        try:
            info = find(reg)
            if not info:
                fails.append({'key': reg['key'], 'name': reg['name'], 'why': '검색 결과에 같은 이름의 현행 규정 없음'}); continue
            prev = old['regs'].get(reg['key']) or {}
            path = 'data/%s.json' % reg['key']
            if prev.get('mst') != info['mst'] or not os.path.exists(path):
                if reg['target'] == 'law':
                    body = get('lawService.do', target='law', MST=info['mst'])
                else:
                    body = get('lawService.do', target='admrul', ID=info['mst'])
                json.dump(body, open(path, 'w', encoding='utf-8'), ensure_ascii=False)
                bi = (body.get('법령') or {}).get('기본정보') or {}
                if bi.get('시행일자'): info['enforceBody'] = bi.get('시행일자')
                changed.append({'key': reg['key'], 'name': info['name'], 'enforce': info['enforce'], 'promul': info['promul'], 'was': prev.get('enforce')})
            info['target'] = reg['target']
            man['regs'][reg['key']] = info
        except Exception as e:
            fails.append({'key': reg['key'], 'name': reg['name'], 'why': str(e)[:300]})
        time.sleep(0.4)
    json.dump(man, open('manifest.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    json.dump({'fetched': man['fetched'], 'changed': changed, 'fails': fails}, open('report.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('받음 %d건, 바뀜 %d건, 실패 %d건' % (len(man['regs']), len(changed), len(fails)))
    for f in fails[:20]: print('실패:', f['name'], '-', f['why'])
    if fails and len(fails) == len([r for r in regs if not only or r['key'] in only]):
        sys.exit('모든 규정을 받지 못했습니다. 인증값 또는 접속 차단을 확인하세요.')

if __name__ == '__main__':
    main()
