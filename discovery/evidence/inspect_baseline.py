"""Read-only discovery probes; render only into a temporary directory."""
import ast
import contextlib
import io
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from collections import Counter
from itertools import combinations

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / 'src/mvp_news_aggregator'))
from curator import ArticleCurator
from quiz_data import QuizGenerator
from web_newsletter import NewsletterGenerator
from foreign_exchange_data import _fetch_historical_rates_alternative

result = {'source_files': {}, 'archives': {}, 'probes': {}}
for path in sorted((root / 'src').rglob('*.py')):
    tree = ast.parse(path.read_text())
    result['source_files'][str(path.relative_to(root))] = {
        'lines': len(path.read_text().splitlines()),
        'definitions': [n.name for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef))],
    }
news = json.loads((root / 'data/loading/newsletter_curated.json').read_text())
result['news_schema'] = {category: {tier: {'count': len(rows), 'fields': sorted(set().union(*(r.keys() for r in rows))) if rows else []} for tier, rows in data.items()} for category, data in news.items()}
quizzes = {}
for path in sorted((root / 'data/staging/quiz_data').glob('*.json')):
    data = json.loads(path.read_text())
    questions = {q['question'].strip().casefold() for q in data['questions']}
    quizzes[path.name] = questions
    result['archives'][path.name] = {'question_count': len(data['questions']), 'unique_questions': len(questions), 'metadata': data['metadata']}
result['quiz_pair_overlap'] = [{'a': a, 'b': b, 'shared': len(quizzes[a] & quizzes[b])} for a,b in combinations(quizzes,2)]
conn = sqlite3.connect(f'file:{root / "data/newsletter.db"}?mode=ro', uri=True)
result['legacy_database'] = {}
for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table'"):
    if name in ('articles','subscribers'):
        result['legacy_database'][name] = {'rows': conn.execute(f'SELECT count(*) FROM {name}').fetchone()[0], 'columns': [r[1] for r in conn.execute(f'PRAGMA table_info({name})')]}
conn.close()
with contextlib.redirect_stdout(io.StringIO()):
    quiz = QuizGenerator(use_llm=False)
    first = quiz.generate_daily_quiz(topics=None)
    second = quiz.generate_daily_quiz(topics=None)
    result['probes']['quiz_fallback'] = {'requested': 25, 'first_count': len(first['questions']), 'second_count': len(second['questions']), 'overlap': len({q['question'] for q in first['questions']} & {q['question'] for q in second['questions']})}
    curator = ArticleCurator(use_llm=False)
    a = {'id':'a','title':'Example A','description':'A sufficiently long description with specific facts.','url':'https://example.com/a','source':'Example','published':'2026-10-16T00:00:00+00:00','category':'tech'}
    b = {**a, 'id':'b','title':'Example B','url':'https://example.com/b'}
    result['probes']['no_llm_dedup_count'] = len(curator.deduplicate_articles([a,a.copy()]))
    class Response:
        text = '{"top_stories":[{"id":"a","score":8,"reason":"Useful reason"}],"quick_reads":[]}'
    class FakeModel:
        def generate_content(self,prompt): return Response()
    curator.use_llm = True
    curator.model = FakeModel()
    mapped = curator.curate_one_category([a,b], 'tech')['top_stories'][0]
    result['probes']['selection_reason_lost'] = {'llm_summary': mapped.get('llm_summary'), 'has_reason': 'reason' in mapped, 'importance_score': mapped.get('importance_score')}
    generator = NewsletterGenerator()
    rendered = generator.generate_html()
    with tempfile.TemporaryDirectory(prefix='newsletter-discovery-') as tmp:
        output = Path(tmp) / 'newsletter.html'
        output.write_text(rendered)
        result['probes']['cached_render'] = {'bytes': output.stat().st_size, 'article_blocks': rendered.count('class="article '), 'quiz_buttons': rendered.count('onclick="revealAnswer('), 'why_matters_blocks': rendered.count('class="why-matters"'), 'output': 'temporary directory, removed automatically'}
    unsafe = generator.generate_mixed_article_html({**a, 'title':'<b>unescaped title</b>'}, 'critical')
    result['probes']['raw_html_interpolation'] = '<b>unescaped title</b>' in unsafe
    from datetime import date
    result['probes']['synthetic_fx_example'] = _fetch_historical_rates_alternative(date(2026,10,16), {'NZD/USD':0.562,'NZD/AUD':0.812,'NZD/INR':53.36,'NZD/CNY':3.75,'NZD/THB':18.81})
result['test_files'] = [str(p.relative_to(root)) for p in root.rglob('test*.py') if 'daily_news_letter_venv' not in str(p) and '.git' not in str(p)]
print(json.dumps(result, indent=2))
