# 국가법령정보센터 API로 받은 현행 시행일(manifest.json)과 대시보드 자료 원천(산안법 검색기 공개 저장소)의 수록 시행일을 대조한다.
# 사용: python3 scripts/compare.py <sanan-search 저장소 폴더>
# 결과: compare.json {checked, same, diffs:[{key, name, api_enforce, api_promul, api_no, sanan_enforce, sanan_no, note}], apiOnly:[...]}
import json, re, sys
from datetime import datetime, timezone, timedelta

repo = sys.argv[1]
h = open(repo + '/index.html', encoding='utf-8').read()
S = json.loads(re.search(r'<script type="application/json" id="lawdata">([\s\S]*?)</script>', h).group(1))
man = json.load(open('manifest.json', encoding='utf-8'))['regs']
norm = lambda s: re.sub(r'[\s·ㆍ\-\(\)]', '', re.sub(r'^\((고용노동부|국토교통부|환경부)\)\s*', '', s or ''))
by = {norm(L['name']): (k, L) for k, L in S['laws'].items()}
diffs, api_only, same = [], [], 0
for key, v in man.items():
    hit = by.get(norm(v.get('name')))
    if not hit:
        api_only.append({'key': key, 'name': v.get('name'), 'api_enforce': v.get('enforce')}); continue
    _, L = hit
    a, b = str(v.get('enforce') or ''), str(L.get('enforce') or '')
    if a == b:
        same += 1; continue
    diffs.append({'key': key, 'name': v.get('name'), 'api_enforce': a, 'api_promul': v.get('promul'), 'api_no': v.get('promulNo'),
                  'sanan_enforce': b, 'sanan_no': str(L.get('promulNo') or ''), 'sanan_promul': str(L.get('promul') or ''),
                  'note': '국가법령정보센터 현행이 더 최근 시행' if a > b else '수록본이 더 최근(시행 예정 개정 선반영 가능성)'})
out = {'checked': datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M'), 'sananBuilt': S.get('built'), 'same': same, 'diffs': diffs, 'apiOnly': api_only}
json.dump(out, open('compare.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('일치 %d, 차이 %d, API에만 %d' % (same, len(diffs), len(api_only)))
for d in diffs: print('차이:', d['name'], 'API', d['api_enforce'], '/ 수록본', d['sanan_enforce'], '-', d['note'])
