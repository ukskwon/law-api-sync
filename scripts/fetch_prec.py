# 국가법령정보센터 Open API로 산업안전보건법·중대재해처벌법 관련 판례를 받는다.
# 새로 나온 판례만 상세를 받아 data/prec/<판례일련번호>.json 에 저장하고, prec_index.json 에 목록을 쌓는다.
import json, os, re, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta

OC = os.environ.get('LAW_OC', '').strip()
if not OC: sys.exit('LAW_OC 가 비어 있습니다.')
BASE = 'https://www.law.go.kr/DRF/'
UA = {'User-Agent': 'Mozilla/5.0 (law-api-sync; personal study)'}
KST = timezone(timedelta(hours=9))
# (검색어, search: 1=사건명, 2=본문)
QUERIES = [('산업안전보건법', 1), ('중대재해', 1), ('산업안전보건법', 2), ('중대재해 처벌 등에 관한 법률', 2)]
MAX_NEW = int(os.environ.get('PREC_MAX_NEW', '150'))

def get(path, **q):
    q.update(OC=OC, type='JSON')
    url = BASE + path + '?' + urllib.parse.urlencode(q)
    for i in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return json.loads(r.read().decode('utf-8', 'replace'))
        except Exception as e:
            last = e; time.sleep(3 * (i + 1))
    raise RuntimeError(str(last))

def as_list(x):
    return x if isinstance(x, list) else ([x] if x else [])

def main():
    os.makedirs('data/prec', exist_ok=True)
    idx = json.load(open('prec_index.json', encoding='utf-8')) if os.path.exists('prec_index.json') else {'items': {}}
    items = idx['items']
    found = {}
    for q, mode in QUERIES:
        page = 1
        while page <= 30:
            r = get('lawSearch.do', target='prec', query=q, search=mode, display=100, page=page, sort='ddes')
            ps = (r.get('PrecSearch') or {})
            rows = as_list(ps.get('prec'))
            for x in rows:
                pid = str(x.get('판례일련번호') or '')
                if pid: found[pid] = x
            total = int(ps.get('totalCnt') or 0)
            if page * 100 >= total or not rows: break
            page += 1
            time.sleep(0.3)
    new = [pid for pid in found if pid not in items]
    new.sort(key=lambda p: str(found[p].get('선고일자') or ''), reverse=True)
    got, fails = 0, []
    for pid in new[:MAX_NEW]:
        try:
            d = get('lawService.do', target='prec', ID=pid)
            body = d.get('PrecService') or d
            json.dump(body, open('data/prec/%s.json' % pid, 'w', encoding='utf-8'), ensure_ascii=False)
            x = found[pid]
            items[pid] = {'n': x.get('사건번호'), 'm': x.get('사건명'), 'c': x.get('법원명'), 'd': x.get('선고일자'), 't': x.get('사건종류명'),
                          'added': datetime.now(KST).strftime('%Y-%m-%d')}
            got += 1
        except Exception as e:
            fails.append({'id': pid, 'why': str(e)[:200]})
        time.sleep(0.4)
    idx['items'] = items
    idx['fetched'] = datetime.now(KST).strftime('%Y-%m-%d %H:%M')
    idx['found'] = len(found)
    idx['pending'] = max(0, len(new) - MAX_NEW)
    json.dump(idx, open('prec_index.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print('판례 검색 %d건, 새로 받음 %d건, 남은 대기 %d건, 실패 %d건' % (len(found), got, idx['pending'], len(fails)))

if __name__ == '__main__':
    main()
