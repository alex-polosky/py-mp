import json
import os
from elasticsearch import Elasticsearch

es = Elasticsearch('http://localhost:9200')

for fn in os.listdir(os.path.dirname(__file__)):
    if not (fn.startswith('data') and fn.endswith('ndjson')):
        continue
    if fn == 'data.0.001.ndjson':
        continue
    fn = os.path.join(os.path.dirname(__file__), fn)
    with open(fn) as f:
        data = f.read()
    for line in data.split('\n'):
        if not line:
            continue
        x = json.loads(line)
        # print(fn, x)
        es.index(index='py-run-time', document=x)
