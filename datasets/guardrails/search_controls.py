#!/usr/bin/env python3
"""A local lexical retrieval baseline over reference controls; scores are not probabilities."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import re
import time


def tokens(text):
    return re.findall(r'[a-z0-9_]+', text.lower())


def search(rows, query, engine=None, limit=5):
    rows = [row for row in rows if row.get('role') != 'fixture' and (engine is None or row['engine'] == engine)]
    texts = [' '.join(str(row.get(key, '')) for key in ('name', 'title', 'description', 'category'))+' '+
             str(row['document'].get('desc', ''))+' '+' '.join(row['document'].get('tags', [])) for row in rows]
    terms = [Counter(tokens(text)) for text in texts]
    frequencies = Counter(term for document in terms for term in document)
    average = sum(sum(document.values()) for document in terms)/max(1, len(terms))
    ranked = []
    for row, document in zip(rows, terms):
        score = 0.0
        length = sum(document.values())
        for term in set(tokens(query)):
            count = document[term]
            if count:
                idf = math.log(1+(len(rows)-frequencies[term]+0.5)/(frequencies[term]+0.5))
                score += idf*count*2.2/(count+1.2*(0.25+0.75*length/max(average, 1)))
        if score:
            ranked.append({'id': row['id'], 'name': row['name'], 'engine': row['engine'], 'kind': row['kind'],
                           'score': round(score, 6), 'purpose': row.get('description') or row['document'].get('desc', ''),
                           'source': row['source']})
    return sorted(ranked, key=lambda row: (-row['score'], row['id']))[:limit]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', type=Path, default=Path(__file__).with_name('corpus')/'catalog.jsonl')
    parser.add_argument('--query', required=True)
    parser.add_argument('--engine', choices=('kyverno', 'falco'))
    parser.add_argument('--limit', type=int, default=5)
    args = parser.parse_args()
    if not 1 <= args.limit <= 20:
        parser.error('Use a limit of 1–20')
    start = time.monotonic()
    rows = [json.loads(line) for line in args.catalog.read_text().splitlines()]
    matches = search(rows, args.query, args.engine, args.limit)
    print(json.dumps({'authority': 'review candidates only', 'method': 'BM25 lexical baseline',
                      'elapsed_ms': round((time.monotonic()-start)*1000, 3), 'api_calls': 0,
                      'local_compute_cost': 'unpriced', 'matches': matches}, indent=2))
