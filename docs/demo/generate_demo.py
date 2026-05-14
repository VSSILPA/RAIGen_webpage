"""
Scans raigen_checkpoints/prof/ and raigen_checkpoints/coco/ for minority neuron
PNG strips and generates a self-contained demo.html.

Usage:
    python generate_demo.py \
        --prof_root  /path/to/raigen_checkpoints/prof \
        --coco_root  /path/to/raigen_checkpoints/coco \
        --out        demo.html
"""

import os
import json
import argparse
from pathlib import Path

# ── CLI ──────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--prof_root", default="/vol/research/Anjan_Cloud_Storage/results_raigen/checkpoints_sdxl/raigen_checkpoints/prof")
parser.add_argument("--coco_root", default="/vol/research/Anjan_Cloud_Storage/results_raigen/checkpoints_sdxl/raigen_checkpoints/coco")
parser.add_argument("--out",       default="demo.html")
args = parser.parse_args()

# ── Helpers ──────────────────────────────────────────────────────────────────

def find_minority_neurons_dir(prompt_dir: Path):
    """Return the minority_neurons/ folder inside a prompt directory (any depth)."""
    for mn in prompt_dir.rglob("minority_neurons"):
        if mn.is_dir():
            return mn
    return None


def collect_pngs(root: str) -> dict:
    """
    Returns  { "PromptName": ["0000_neuron0638.png", ...], ... }
    PNG lists are sorted by rank (filename already encodes rank as 4-digit prefix).
    """
    result = {}
    root_path = Path(root)
    if not root_path.exists():
        print(f"[warn] path not found: {root}")
        return result

    for prompt_dir in sorted(root_path.iterdir()):
        if not prompt_dir.is_dir():
            continue
        mn_dir = find_minority_neurons_dir(prompt_dir)
        if mn_dir is None:
            print(f"[warn] no minority_neurons/ found under {prompt_dir.name}")
            continue
        pngs = sorted(p.name for p in mn_dir.glob("*.png"))
        if pngs:
            # store relative path from demo.html root
            rel = str(mn_dir.relative_to(root_path.parent))
            result[prompt_dir.name] = {"rel_dir": rel, "files": pngs}

    return result


prof_data = collect_pngs(args.prof_root)
coco_data = collect_pngs(args.coco_root)

manifest = {"prof": prof_data, "coco": coco_data}
manifest_json = json.dumps(manifest, indent=2)

print(f"Prof prompts : {sorted(prof_data.keys())}")
print(f"COCO prompts : {sorted(coco_data.keys())}")

# ── HTML template ────────────────────────────────────────────────────────────
html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>RAIGen — Minority Neurons</title>
<style>
  :root {{
    --accent: #4f46e5;
    --bg: #f9fafb;
    --card: #ffffff;
    --border: #e5e7eb;
    --text: #111827;
    --muted: #6b7280;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: system-ui, sans-serif; background: var(--bg); color: var(--text); }}

  header {{
    background: var(--card);
    border-bottom: 1px solid var(--border);
    padding: 1.5rem 2rem;
  }}
  header h1 {{ font-size: 1.4rem; font-weight: 700; letter-spacing: -0.01em; }}
  header p  {{ font-size: 0.85rem; color: var(--muted); margin-top: 0.3rem; }}

  .controls {{
    display: flex;
    flex-wrap: wrap;
    gap: 1rem;
    align-items: flex-end;
    padding: 1.25rem 2rem;
    background: var(--card);
    border-bottom: 1px solid var(--border);
  }}
  .ctrl-group {{ display: flex; flex-direction: column; gap: 0.3rem; }}
  .ctrl-group label {{ font-size: 0.75rem; font-weight: 600; text-transform: uppercase;
                       letter-spacing: 0.05em; color: var(--muted); }}
  select {{
    padding: 0.45rem 0.75rem;
    border: 1px solid var(--border);
    border-radius: 6px;
    font-size: 0.9rem;
    background: white;
    cursor: pointer;
    min-width: 160px;
  }}
  select:focus {{ outline: 2px solid var(--accent); outline-offset: 1px; }}

  #topn-group {{ transition: opacity 0.2s; }}
  #topn-group.hidden {{ opacity: 0; pointer-events: none; }}

  main {{
    padding: 1.5rem 2rem;
    max-width: 1400px;
  }}

  #status {{
    font-size: 0.85rem;
    color: var(--muted);
    margin-bottom: 1rem;
  }}

  .neuron-row {{
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-bottom: 0.75rem;
  }}
  .neuron-label {{
    min-width: 90px;
    text-align: right;
    font-size: 0.75rem;
    color: var(--muted);
    line-height: 1.4;
    flex-shrink: 0;
  }}
  .neuron-label strong {{ display: block; color: var(--text); font-size: 0.8rem; }}
  .neuron-row img {{
    max-width: 100%;
    border-radius: 6px;
    border: 1px solid var(--border);
    display: block;
  }}

  #placeholder {{
    color: var(--muted);
    font-size: 0.9rem;
    padding: 2rem 0;
  }}
</style>
</head>
<body>

<header>
  <h1>RAIGen &mdash; Minority Neuron Visualisation</h1>
  <p>Top-activating images for minority neurons identified by the RAIGen pipeline.</p>
</header>

<div class="controls">
  <div class="ctrl-group">
    <label>Task</label>
    <select id="sel-task">
      <option value="prof">Profession</option>
      <option value="coco">COCO</option>
    </select>
  </div>
  <div class="ctrl-group">
    <label>Prompt</label>
    <select id="sel-prompt"><option value="">— select —</option></select>
  </div>
  <div class="ctrl-group" id="topn-group">
    <label>Top-N neurons</label>
    <select id="sel-topn">
      <option value="5">Top 5</option>
      <option value="10" selected>Top 10</option>
      <option value="20">Top 20</option>
    </select>
  </div>
</div>

<main>
  <div id="status"></div>
  <div id="gallery"><p id="placeholder">Select a task and prompt to view minority neurons.</p></div>
</main>

<script>
const MANIFEST = {manifest_json};

const selTask   = document.getElementById('sel-task');
const selPrompt = document.getElementById('sel-prompt');
const selTopN   = document.getElementById('sel-topn');
const topNGroup = document.getElementById('topn-group');
const gallery   = document.getElementById('gallery');
const status    = document.getElementById('status');

function populatePrompts(task) {{
  const data = MANIFEST[task] || {{}};
  selPrompt.innerHTML = '<option value="">— select —</option>';
  Object.keys(data).sort().forEach(name => {{
    const opt = document.createElement('option');
    opt.value = name;
    opt.textContent = name;
    selPrompt.appendChild(opt);
  }});
}}

function render() {{
  const task   = selTask.value;
  const prompt = selPrompt.value;
  const topN   = task === 'coco' ? 5 : parseInt(selTopN.value, 10);

  // show/hide top-N selector
  topNGroup.classList.toggle('hidden', task === 'coco');

  if (!prompt) {{
    gallery.innerHTML = '<p id="placeholder">Select a task and prompt to view minority neurons.</p>';
    status.textContent = '';
    return;
  }}

  const entry = MANIFEST[task][prompt];
  if (!entry) {{ gallery.innerHTML = '<p>No data found.</p>'; return; }}

  const files = entry.files.slice(0, topN);
  const relDir = entry.rel_dir;

  status.textContent = `Showing ${{files.length}} minority neuron${{files.length !== 1 ? 's' : ''}} for "${{prompt}}"`;

  gallery.innerHTML = '';
  files.forEach((fname, i) => {{
    // parse neuron index from filename e.g. "0003_neuron0279.png"
    const match = fname.match(/_(neuron\\d+)\\.png$/);
    const label = match ? match[1].replace('neuron', '#') : `rank ${{i}}`;

    const row = document.createElement('div');
    row.className = 'neuron-row';

    const lbl = document.createElement('div');
    lbl.className = 'neuron-label';
    lbl.innerHTML = `<strong>rank ${{String(i+1).padStart(2,'0')}}</strong>neuron ${{label}}`;

    const img = document.createElement('img');
    img.src = relDir + '/' + fname;
    img.alt = label;
    img.loading = 'lazy';

    row.appendChild(lbl);
    row.appendChild(img);
    gallery.appendChild(row);
  }});
}}

selTask.addEventListener('change', () => {{
  populatePrompts(selTask.value);
  render();
}});
selPrompt.addEventListener('change', render);
selTopN.addEventListener('change', render);

// init
populatePrompts(selTask.value);
</script>
</body>
</html>
"""

with open(args.out, "w") as f:
    f.write(html)

print(f"\nGenerated: {args.out}")
print("Put demo.html alongside the raigen_checkpoints/ folder and open in a browser.")
