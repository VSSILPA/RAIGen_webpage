"""
generate_demo_drive.py
======================
Scans your Google Drive raigen_checkpoints folder for minority neuron PNGs
and regenerates demo.html with direct Drive image URLs.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ONE-TIME SETUP  (takes ~5 minutes)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Go to https://console.cloud.google.com/
   - Create a new project (e.g. "RAIGen Demo")

2. Enable the Drive API:
   - In the left menu: APIs & Services → Library
   - Search "Google Drive API" → Enable

3. Create an API key:
   - APIs & Services → Credentials → Create Credentials → API key
   - Copy the key (looks like: AIzaSy...)
   - (Optional) Click "Restrict key" → API restrictions → Google Drive API

4. Make sure your Drive folder is publicly shared:
   - Right-click the top-level folder (containing prof/ and coco/)
   - Share → General access → "Anyone with the link" → Viewer
   - Do the same for ALL subfolders, or share the top folder and
     check "Apply to all items inside"

5. Get your folder ID from the sharing URL:
   - Open the folder in Drive
   - The URL looks like:
     https://drive.google.com/drive/folders/1ABC123XYZ...
   - The folder ID is everything after /folders/

6. Install dependencies:
   pip install google-api-python-client

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
USAGE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

python generate_demo_drive.py \
    --api_key  YOUR_API_KEY \
    --folder_id YOUR_TOP_FOLDER_ID \
    --out demo.html

The top folder should contain exactly two subfolders: prof/ and coco/
"""

import argparse
import json
from googleapiclient.discovery import build

# ── CLI ──────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--api_key",   required=True, help="Google API key")
parser.add_argument("--folder_id", required=True, help="Drive ID of the top-level folder (contains prof/ and coco/)")
parser.add_argument("--out",       default="demo.html")
args = parser.parse_args()

# ── Drive helpers ─────────────────────────────────────────────
service = build("drive", "v3", developerKey=args.api_key)

def list_children(parent_id, mime=None):
    """Return list of {id, name} dicts for direct children of parent_id."""
    q = f"'{parent_id}' in parents and trashed = false"
    if mime:
        q += f" and mimeType = '{mime}'"
    results = []
    page_token = None
    while True:
        resp = service.files().list(
            q=q,
            fields="nextPageToken, files(id, name)",
            pageToken=page_token,
            pageSize=1000,
        ).execute()
        results.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return results

def find_child(parent_id, name):
    """Return the Drive file/folder with the given name under parent_id, or None."""
    children = list_children(parent_id)
    for c in children:
        if c["name"] == name:
            return c
    return None

def drive_img_url(file_id):
    """Direct embeddable URL for a public Drive image."""
    return f"https://drive.google.com/uc?export=view&id={file_id}"

# ── Scan task folder (prof or coco) ──────────────────────────
def scan_task(task_folder_id, task_name):
    """
    Returns { "PromptName": {"files": [...urls...]} }
    """
    result = {}
    prompt_dirs = list_children(task_folder_id, mime="application/vnd.google-apps.folder")
    print(f"\n[{task_name}] Found {len(prompt_dirs)} prompt folders")

    for prompt in sorted(prompt_dirs, key=lambda x: x["name"]):
        prompt_name = prompt["name"]

        # find minority_neurons/ subfolder
        mn = find_child(prompt["id"], "minority_neurons")
        if mn is None:
            print(f"  [warn] no minority_neurons/ in '{prompt_name}'")
            continue

        # list PNGs sorted by filename (rank prefix ensures correct order)
        pngs = [f for f in list_children(mn["id"]) if f["name"].endswith(".png")]
        pngs.sort(key=lambda x: x["name"])

        if not pngs:
            print(f"  [warn] no PNGs in '{prompt_name}/minority_neurons/'")
            continue

        urls = [drive_img_url(f["id"]) for f in pngs]
        filenames = [f["name"] for f in pngs]

        result[prompt_name] = {"files": filenames, "urls": urls}
        print(f"  ✓  {prompt_name:30s}  {len(pngs)} images")

    return result

# ── Main ─────────────────────────────────────────────────────
print("Scanning Drive folder...")
top_children = list_children(args.folder_id, mime="application/vnd.google-apps.folder")
top_map = {c["name"]: c["id"] for c in top_children}

if "prof" not in top_map:
    raise SystemExit("ERROR: could not find 'prof/' subfolder in the top folder")
if "coco" not in top_map:
    raise SystemExit("ERROR: could not find 'coco/' subfolder in the top folder")

prof_data = scan_task(top_map["prof"], "prof")
coco_data = scan_task(top_map["coco"], "coco")

manifest = {"prof": prof_data, "coco": coco_data}
manifest_json = json.dumps(manifest, indent=2)

print(f"\nProf prompts : {sorted(prof_data.keys())}")
print(f"COCO prompts : {len(coco_data)} prompts")

# ── Generate demo.html ────────────────────────────────────────
html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>RAIGen — Minority Neuron Visualisations</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: Inter, system-ui, sans-serif; background: #fff; color: #111; line-height: 1.5; }}

  header {{
    background: #fff; border-bottom: 1px solid #e5e7eb;
    padding: 1.25rem 2rem; display: flex; align-items: baseline; gap: 1.5rem;
  }}
  header h1 {{ font-size: 1.25rem; font-weight: 700; }}
  header a  {{ font-size: 0.85rem; color: #555; text-decoration: none; }}
  header a:hover {{ text-decoration: underline; }}

  .controls {{
    display: flex; flex-wrap: wrap; gap: 1rem; align-items: flex-end;
    padding: 1rem 2rem; background: #f9f9f9; border-bottom: 1px solid #e5e7eb;
  }}
  .ctrl-group {{ display: flex; flex-direction: column; gap: 0.3rem; }}
  .ctrl-group label {{
    font-size: 0.7rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.07em; color: #888;
  }}
  select {{
    padding: 0.45rem 0.75rem; border: 1px solid #ddd;
    border-radius: 6px; font-size: 0.9rem; background: #fff;
    cursor: pointer; min-width: 200px;
  }}
  select:focus {{ outline: 2px solid #111; outline-offset: 1px; }}

  #topn-group {{ transition: opacity 0.2s; }}
  #topn-group.hidden {{ opacity: 0; pointer-events: none; }}

  main {{ padding: 1.5rem 2rem; max-width: 1200px; }}

  #status {{
    font-size: 0.82rem; color: #888; margin-bottom: 1.25rem;
    padding-bottom: 0.75rem; border-bottom: 1px solid #f0f0f0;
  }}

  .neuron-grid {{
    display: flex; flex-direction: column; gap: 1.25rem;
  }}
  .neuron-row {{
    display: flex; align-items: flex-start; gap: 1rem;
  }}
  .neuron-label {{
    min-width: 100px; text-align: right; flex-shrink: 0; padding-top: 4px;
  }}
  .neuron-label strong {{ display: block; font-size: 0.82rem; color: #111; }}
  .neuron-label span   {{ font-size: 0.72rem; color: #999; }}
  .neuron-row img {{
    width: 100%; border-radius: 8px;
    border: 1px solid #e5e7eb; display: block;
  }}
  .img-wrap {{ flex: 1; position: relative; }}
  .img-wrap .loading {{
    position: absolute; inset: 0; display: flex; align-items: center;
    justify-content: center; font-size: 0.8rem; color: #bbb;
    background: #f9f9f9; border-radius: 8px;
  }}

  #placeholder {{ color: #aaa; font-size: 0.95rem; padding: 3rem 0; }}
</style>
</head>
<body>

<header>
  <h1>RAIGen &mdash; Minority Neuron Visualisations</h1>
  <a href="../index.html">&#8592; Project Page</a>
</header>

<div class="controls">
  <div class="ctrl-group">
    <label>Task</label>
    <select id="sel-task">
      <option value="prof">Profession (WinoBias)</option>
      <option value="coco">COCO Captions</option>
    </select>
  </div>
  <div class="ctrl-group">
    <label>Prompt</label>
    <select id="sel-prompt"><option value="">— select a prompt —</option></select>
  </div>
  <div class="ctrl-group" id="topn-group">
    <label>Top-N neurons</label>
    <select id="sel-topn">
      <option value="5">Top 5</option>
      <option value="10" selected>Top 10</option>
      <option value="15">Top 15</option>
    </select>
  </div>
</div>

<main>
  <div id="status"></div>
  <div id="gallery" class="neuron-grid">
    <p id="placeholder">Select a task and prompt above to view minority neuron visualisations.</p>
  </div>
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
  selPrompt.innerHTML = '<option value="">— select a prompt —</option>';
  Object.keys(data).sort().forEach(name => {{
    const opt = document.createElement('option');
    opt.value = name;
    opt.textContent = name;
    selPrompt.appendChild(opt);
  }});
  selPrompt.value = '';
}}

function render() {{
  const task   = selTask.value;
  const prompt = selPrompt.value;
  const topN   = parseInt(selTopN.value, 10);

  topNGroup.classList.toggle('hidden', task === 'coco');

  if (!prompt) {{
    gallery.innerHTML = '<p id="placeholder">Select a task and prompt above to view minority neuron visualisations.</p>';
    status.textContent = '';
    return;
  }}

  const entry = MANIFEST[task][prompt];
  if (!entry) {{ gallery.innerHTML = '<p>No data found.</p>'; return; }}

  const n     = task === 'coco' ? entry.urls.length : topN;
  const urls  = entry.urls.slice(0, n);
  const fnames = entry.files.slice(0, n);

  status.textContent = `Showing ${{urls.length}} minority neuron${{urls.length !== 1 ? 's' : ''}} for "${{prompt}}"`;

  gallery.innerHTML = '';
  urls.forEach((url, i) => {{
    const match  = fnames[i].match(/_(neuron\\d+)\\.png$/);
    const neuron = match ? match[1] : `neuron${{i}}`;

    const row = document.createElement('div');
    row.className = 'neuron-row';

    const lbl = document.createElement('div');
    lbl.className = 'neuron-label';
    lbl.innerHTML = `<strong>rank ${{String(i+1).padStart(2,'0')}}</strong><span>${{neuron.replace('neuron','#')}}</span>`;

    const wrap = document.createElement('div');
    wrap.className = 'img-wrap';

    const loading = document.createElement('div');
    loading.className = 'loading';
    loading.textContent = 'loading…';
    wrap.appendChild(loading);

    const img = document.createElement('img');
    img.alt = neuron;
    img.loading = 'lazy';
    img.onload  = () => loading.remove();
    img.onerror = () => {{ loading.textContent = 'failed to load'; }};
    img.src = url;
    wrap.appendChild(img);

    row.appendChild(lbl);
    row.appendChild(wrap);
    gallery.appendChild(row);
  }});
}}

selTask.addEventListener('change', () => {{ populatePrompts(selTask.value); render(); }});
selPrompt.addEventListener('change', render);
selTopN.addEventListener('change', render);

populatePrompts(selTask.value);
</script>
</body>
</html>
"""

with open(args.out, "w") as f:
    f.write(html)

print(f"\nGenerated: {args.out}")
print("Commit docs/demo/demo.html — no images needed in the repo.")
