"""Minimal FastAPI inference server: /health, /generate (JSON or SSE stream).

fastapi/uvicorn are optional deps - imported here only, so the rest of lloom
never requires them. Endpoints are sync defs: FastAPI runs them in a thread
pool, which is exactly right for blocking single-GPU generation.
"""
import json
import queue
import threading

import torch

from .generate import generate

_INDEX_HTML = """<!doctype html><html><head><meta charset="utf-8"><title>Lloom</title>
<style>
 body{background:#1b1b1f;color:#e6e6e6;font-family:system-ui,sans-serif;max-width:760px;margin:40px auto;padding:0 16px}
 h1{font-weight:600;font-size:20px}
 textarea{width:100%;box-sizing:border-box;background:#26262b;color:#e6e6e6;border:1px solid #3a3a42;border-radius:8px;padding:10px;font-size:15px;resize:vertical}
 .row{display:flex;gap:12px;align-items:center;margin:10px 0}
 button{background:#6a5acd;color:#fff;border:0;border-radius:8px;padding:10px 18px;font-size:15px;cursor:pointer}
 button:disabled{opacity:.5;cursor:default}
 label{font-size:13px;color:#aaa}
 #out{white-space:pre-wrap;background:#26262b;border:1px solid #3a3a42;border-radius:8px;padding:14px;margin-top:14px;min-height:40px}
 .muted{color:#888;font-size:12px}
</style></head><body>
<h1>Lloom</h1>
<textarea id="inp" rows="3" placeholder="Ask a question, or type a prompt. Ctrl+Enter to send."></textarea>
<div class="row">
 <button id="go" onclick="ask()">Generate</button>
 <label><input type="checkbox" id="qa" checked> Q&amp;A mode</label>
 <span class="muted">min_p 0.05 / rep 1.2</span>
</div>
<div id="out"></div>
<script>
const inp=document.getElementById('inp'),out=document.getElementById('out'),go=document.getElementById('go'),qa=document.getElementById('qa');
async function ask(){
 const t=inp.value.trim(); if(!t)return;
 const prompt=qa.checked?('<|question|> '+t+' <|answer|>'):t;
 go.disabled=true; out.textContent='thinking...';
 try{
  const r=await fetch('/generate',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({prompt:prompt})});
  const j=await r.json();
  if(!r.ok){out.textContent='HTTP '+r.status+': '+JSON.stringify(j.detail||j);}
  else{out.textContent=((qa.checked?j.completion:j.text)||'').trim()||'(model produced no tokens)';}
 }catch(e){out.textContent='error: '+e}
 go.disabled=false;
}
inp.addEventListener('keydown',e=>{if(e.key==='Enter'&&(e.ctrlKey||e.metaKey))ask()});
</script></body></html>"""


def build_app(model, tokenizer, defaults: dict | None = None):
    try:
        from fastapi import FastAPI
        from fastapi.responses import StreamingResponse, HTMLResponse
        from pydantic import BaseModel
    except ImportError as e:
        raise ImportError("serving needs: pip install fastapi uvicorn") from e

    defaults = defaults or {}
    device = next(model.parameters()).device
    lock = threading.Lock()                    # one generation at a time
    app = FastAPI(title="lloom inference", version="0.1.0")

    class GenRequest(BaseModel):
        prompt: str
        max_new_tokens: int = defaults.get("max_new_tokens", 150)
        temperature: float = defaults.get("temperature", 0.7)
        top_k: int = defaults.get("top_k", 0)
        top_p: float = defaults.get("top_p", 0.9)
        min_p: float = defaults.get("min_p", 0.0)
        repetition_penalty: float = defaults.get("repetition_penalty", 1.0)
        stream: bool = False

    def _gen(req: GenRequest, on_token=None):
        idx = torch.tensor([tokenizer.encode(req.prompt)], device=device)
        with lock:
            out = generate(model, idx, req.max_new_tokens,
                           temperature=req.temperature, top_k=req.top_k,
                           top_p=req.top_p, min_p=req.min_p,
                           repetition_penalty=req.repetition_penalty,
                           eot_id=tokenizer.eot_id, on_token=on_token)
        return out[0].tolist(), idx.shape[1]

    @app.get("/health")
    def health():
        return {"status": "ok", "device": str(device),
                "params": sum(p.numel() for p in model.parameters())}

    @app.get("/")
    def index():
        return HTMLResponse(_INDEX_HTML)

    @app.post("/generate")
    def gen(req: GenRequest):
        if not req.stream:
            ids, n_prompt = _gen(req)
            return {"text": tokenizer.decode(ids),
                    "completion": tokenizer.decode(ids[n_prompt:]),
                    "n_tokens": len(ids) - n_prompt}

        q: queue.Queue = queue.Queue()

        def worker():
            try:
                _gen(req, on_token=q.put)
            finally:
                q.put(None)

        threading.Thread(target=worker, daemon=True).start()

        def events():
            pending: list[int] = []
            while (tid := q.get()) is not None:
                pending.append(tid)
                text = tokenizer.decode(pending)
                if text and not text.endswith("�"):   # whole pieces only
                    yield f"data: {json.dumps({'token': text})}\n\n"
                    pending = []
            yield "data: [DONE]\n\n"

        return StreamingResponse(events(), media_type="text/event-stream")

    return app
