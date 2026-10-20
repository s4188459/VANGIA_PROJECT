"""English local reports: evidence scope stays visible in every export."""
import html
from pathlib import Path
from .common import read_json, write_json


def report(path, formats=('md', 'json', 'html')):
    path = Path(path)
    manifest = read_json(path/'manifest.json')
    metrics = read_json(path/'metrics.json') if (path/'metrics.json').exists() else {}
    status = read_json(path/'state.json') if (path/'state.json').exists() else {'status': manifest['status']}
    lines = ['# Vangia English ASR evidence report', '',
             f"Run: {manifest['run_id']} | Input: {manifest['input_mode']} | Split: {manifest['dataset_split']}",
             f"Execution: {status['status']} | Scientific decision: INSUFFICIENT EVIDENCE", '',
             '[E] observed evidence; [I] derived inference; [P] provisional proposal; [G] missing measurement.',
             '[P] WER 15% and P95 3 seconds are PROVISIONAL, not universal standards or validation.',
             '[G] A UI update or paint callback does not verify physical screen presentation.', '']
    if manifest['input_mode'] == 'historical_whole_file':
        lines += ['[E-LOCAL] Historical whole-file final / full-file-v1; development/selection evidence.',
                  f"100 recordings; {metrics['duration_s']} seconds; 5024 reference words; 27 configurations, 25 completed, 2 failed.",
                  '[G] Original waveforms, verified weight revisions and live lag measurements are missing.',
                  'RTF describes whole-file processing throughput, not live caption lag. Historical chunk_seconds=3 did not measure streaming.', '',
                  '| Historical configuration | WER | Whole-file RTF | Status | Candidate role |',
                  '|---|---:|---:|---|---|']
        for c in metrics['configurations']:
            wer = 'null' if c['wer'] is None else f"{c['wer']:.8f}"
            rtf = 'null' if c['rtf'] is None else f"{c['rtf']:.6f}"
            lines.append(f"| {c['label']} | {wer} | {rtf} | {c['status']} | {', '.join(c['roles'])} |")
            if c['error']:
                lines.append(f"\nFailure ({c['label']}): {c['error']}\n")
    else:
        lines += ['```json', __import__('json').dumps(metrics, indent=2, ensure_ascii=False), '```']
    lines += ['', 'Source traceability:'] + [f'- {url}' for url in manifest.get('source_urls', [])]
    lines += ['', 'No human sign-off or held-out validation is implied by this report.']
    content = '\n'.join(lines) + '\n'
    if 'md' in formats:
        (path/'report.md').write_text(content, encoding='utf-8')
    if 'json' in formats:
        write_json(path/'report.json', {'manifest': manifest, 'execution': status, 'metrics': metrics,
                                      'scientific_status': 'INSUFFICIENT EVIDENCE'})
    if 'html' in formats:
        body = '<!doctype html><html lang="en"><meta charset="utf-8"><title>Vangia ASR evidence</title><style>body{background:#101c2c;color:#e8eff7;font:15px system-ui;margin:40px}pre{white-space:pre-wrap;line-height:1.7}h1{color:#66dac5}</style><h1>Vangia ASR Lab</h1><pre>' + html.escape(content) + '</pre></html>'
        (path/'report.html').write_text(body, encoding='utf-8')
    return content
