"""
Lightweight video report generator (v2).

Reads a phase2_predictions.json, produces a self-contained HTML report
and embeds the aggregated dashboard (from aggregate_dashboard) safely.

Usage: from video.scripts.generate_video_report_v2 import generate_report
       generate_report(Path('video/results/.../phase2_predictions.json'))
"""
import json
from pathlib import Path
from datetime import datetime
from collections import Counter

from aggregate_dashboard import aggregate_dashboard, VALID_DISEASES_BY_PART

def generate_report(pred_json_path: Path) -> Path:
    pred_json_path = Path(pred_json_path)
    data = json.loads(pred_json_path.read_text(encoding='utf-8'))
    preds = data.get('predictions', [])

    # Simple status counts and timeline sample (with semantic sanity filter)
    status_counts = Counter()
    timeline = []
    formatted_predictions = []

    for p in preds:
        pred = p.get('prediction', {}) if isinstance(p, dict) else {}

        # Extract raw status prediction
        raw_status = None
        status_field = pred.get('status')
        if isinstance(status_field, dict):
            raw_status = status_field.get('prediction')
            status_conf = float(status_field.get('confidence') or 0.0)
        else:
            raw_status = status_field
            status_conf = 0.0
        raw_status = raw_status or 'Unknown'

        # Extract raw part prediction and normalize naming ('leaf' -> 'leaves')
        part_field = pred.get('part')
        if isinstance(part_field, dict):
            part = part_field.get('prediction')
            part_conf = float(part_field.get('confidence') or 0.0)
        else:
            part = part_field
            part_conf = 0.0
        if part == 'leaf':
            part = 'leaves'

        # Enforce part–disease compatibility for display and counts
        display_status = raw_status
        if part and raw_status not in (None, 'Unknown'):
            allowed = VALID_DISEASES_BY_PART.get(part, set())
            if allowed and raw_status not in allowed:
                # Logically impossible combo → treat as Unknown noise
                display_status = 'Unknown'

        # Do not count or aggregate Unknown statuses – treat them as skipped noise
        if display_status != 'Unknown':
          status_counts[display_status] += 1

        img = pred.get('image_path') or p.get('file') or ''
        timeline.append({
          'frame': p.get('frame_index'),
          'status': display_status,
          'part': part,
          'image': img
        })

        # Build formatted prediction entry for the dashboard aggregator
        # Skip frames where status becomes Unknown
        if display_status != 'Unknown' and part:
          formatted_predictions.append({
            'frame_index': p.get('frame_index'),
            'class': p.get('class'),
            'image_path': img,
            'part': {
              'prediction': part,
              'confidence': part_conf
            },
            'status': {
              'prediction': display_status,
              'confidence': status_conf
            },
            'health': pred.get('health'),
            'combined': pred.get('combined'),
            'is_out_of_distribution': pred.get('is_out_of_distribution', False),
            'ood_reason': pred.get('ood_reason'),
            'ood_signals': pred.get('ood_signals'),
            'reliability': pred.get('reliability', 0)
          })

    try:
        dashboard = aggregate_dashboard(formatted_predictions)
    except Exception:
        dashboard = None

    out_dir = pred_json_path.parent
    out_html = out_dir / 'video_report.html'

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    chart_labels = list(status_counts.keys())
    chart_data = list(status_counts.values())

    # minimal color palette
    colors = ['#4CAF50', '#FF9800', '#F44336', '#9C27B0', '#03A9F4', '#FFC107', '#9E9E9E']

    dashboard_json = json.dumps(dashboard) if dashboard is not None else 'null'

    # prepare timeline HTML safely (avoid nested f-strings inside the big template)
    timeline_html = ''.join(["<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(row.get('frame'), Path(row.get('image') or '').name, row.get('part'), row.get('status')) for row in timeline[:50]])

    chart_labels_json = json.dumps(chart_labels)
    chart_data_json = json.dumps(chart_data)
    colors_json = json.dumps(colors[:len(chart_labels)])

    html_template = """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Video Report</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>body{font-family:Arial;padding:18px;background:#f4f6f8}.card{background:#fff;padding:14px;border-radius:8px;margin-bottom:12px}.row{display:flex;gap:12px;flex-wrap:wrap}.part-card{width:260px}.badge{padding:4px 8px;border-radius:12px;color:#fff}.green{background:#4CAF50}.red{background:#F44336}.disease{margin-left:8px}</style>
</head>
<body>
  <h1>Video Report</h1>
  <div class="card"><strong>Generated:</strong> __NOW__ &nbsp; <strong>Predictions:</strong> __TOTAL__</div>

  <div id="embedded-dashboard"></div>

  <div class="card"><h3>Status Distribution</h3><canvas id="statusChart"></canvas></div>

  <div class="card"><h3>Timeline (sample)</h3><table border="0" cellpadding="6"><tr><th>Frame</th><th>Image</th><th>Part</th><th>Status</th></tr>__TIMELINE_HTML__</table></div>

  <script>
    const ctx = document.getElementById('statusChart').getContext('2d');
    new Chart(ctx, {type:'doughnut', data:{labels:__CHART_LABELS__, datasets:[{data:__CHART_DATA__, backgroundColor:__COLORS__}]}});
  </script>

  <script>
    // Render embedded dashboard (safe)
    const EMBEDDED = __DASHBOARD_JSON__;
    if (EMBEDDED) {
      const c = document.getElementById('embedded-dashboard');
      let out = '';
      const t = EMBEDDED.tree || {};
      out += `<div class="card"><h2>Overall Tree Status</h2><div class="status">${(t.health||'unknown').toUpperCase()}</div><div class="score">${t.score||0}%</div>${(t.health === 'unhealthy' && t.primary_disease)?`<p>Primary issue: <b>${t.primary_disease}</b></p>`:`<p>No dominant disease</p>`}</div>`;
      out += '<div class="row">';
      for (const p of Object.keys(EMBEDDED.parts||{})){
        const info = EMBEDDED.parts[p];
        let diseases = '';
        if (info.health === 'unhealthy'){
          for (const d of Object.keys(info.diseases||{})){
            diseases += `<div class="disease">• ${d} – ${info.diseases[d]}%</div>`;
          }
        }
        out += `<div class="card part-card"><h3>${p.toUpperCase()}</h3><span class="badge ${info.health==='healthy'?'green':'red'}">${(info.health||'UNKNOWN').toUpperCase()}</span><p>Score: <b>${info.score||0}%</b></p><p>Frames: ${info.frames||0}</p>${diseases}</div>`;
      }
      out += '</div>';
      c.innerHTML = out;
    }
  </script>
</body>
</html>
"""

    final_html = html_template.replace('__NOW__', now).replace('__TOTAL__', str(len(timeline))).replace('__TIMELINE_HTML__', timeline_html).replace('__CHART_LABELS__', chart_labels_json).replace('__CHART_DATA__', chart_data_json).replace('__COLORS__', colors_json).replace('__DASHBOARD_JSON__', dashboard_json)

    out_html.write_text(final_html, encoding='utf-8')
    print(f"✅ Report generated: {out_html}")
    return out_html

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--pred', required=True)
    args = parser.parse_args()
    generate_report(Path(args.pred))
