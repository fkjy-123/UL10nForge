# 一次性诊断脚本：Flabby Pizza 场景文件字节串 vs 提取池 差异
import re, os, sqlite3, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

base = r'C:/Users/mingming/Downloads/games/Flabby Pizza/Flabby Pizza_Data'
files = ['level%d' % i for i in range(10)]
pat = re.compile(rb'[\x20-\x7e]{4,}')

def wordlike(s):
    if len(s) < 4: return False
    a = sum(c.isalpha() for c in s)
    if a < 3 or a/len(s) < 0.5: return False
    if len(set(s)) < 3: return False
    return True

def display_plausible(s):
    if '/' in s or '\\' in s: return False
    if s.count('.') > 1: return False
    if any(c in s for c in '<>{}()=:;'): return False
    return True

allstr = {}
for f in files:
    data = open(os.path.join(base, f), 'rb').read()
    for m in pat.findall(data):
        s = m.decode('ascii', 'replace').strip()
        if wordlike(s):
            allstr.setdefault(s, 0)
            allstr[s] += 1

db = sqlite3.connect('C:/Users/mingming/.hanhua/projects/651ca14afb/project.db')
cur = db.cursor()
pool = set()
for (o,) in cur.execute('SELECT original FROM entries'):
    pool.add(o.strip())
    for line in o.split('\n'):
        pool.add(line.strip())

missing = sorted([(c, s) for s, c in allstr.items() if s not in pool and display_plausible(s)],
                 key=lambda x: -len(x[1]))
print('level files wordlike strings:', len(allstr))
print('missing display-plausible strings:', len(missing))
print()
for c, s in missing[:150]:
    print('[%d] %s' % (c, s))
