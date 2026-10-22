"""Jev-compatible HTTP server with no model download and no outbound calls.

    python -m sys1 serve --port 8765

Routes (the same surface laya-serve exposes):

* ``GET  /health``
* ``POST /v1/systemone``
* ``POST /v1/systemone/batch``

Environment variables mirror laya's where they overlap: ``SYS1_HOST``,
``SYS1_PORT``, ``SYS1_API_KEY``, ``SYS1_JEV_STRICT``, ``SYS1_MAX_CONCURRENT``.
"""

from __future__ import annotations

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional

from .decode import project_jev_strict
from .engine import DecisionEngine, VERSION
from .protocol import MAX_CHOICE_OPTIONS, QuestionError

MAX_BODY = 2 * 1024 * 1024

DEMO_PAGE = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>sys1 · 本地 System One 决策引擎</title>
<style>
:root{--bg:#0b1020;--panel:#141b2d;--line:#243049;--text:#e8eefc;--muted:#93a4c4;--acc:#6ea8fe;--ok:#45d09e}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(1200px 600px at 20% -10%,#1b2b4d,var(--bg));color:var(--text);font:15px/1.55 ui-sans-serif,system-ui,"Segoe UI","Noto Sans SC",sans-serif}
main{max-width:1040px;margin:0 auto;padding:36px 20px 60px}
header{display:flex;gap:14px;align-items:center;margin-bottom:8px}
.logo{width:38px;height:38px;border-radius:11px;background:linear-gradient(135deg,#6ea8fe,#45d09e);display:grid;place-items:center;font-weight:800;color:#08111f}
h1{font-size:22px;margin:0}p.sub{color:var(--muted);margin:6px 0 22px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}@media(max-width:820px){.grid{grid-template-columns:1fr}}
.card{background:linear-gradient(180deg,rgba(255,255,255,.03),rgba(255,255,255,0));border:1px solid var(--line);border-radius:14px;padding:16px}
label{display:block;font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin:0 0 6px}
textarea,select,input{width:100%;background:#0d1526;color:var(--text);border:1px solid var(--line);border-radius:9px;padding:10px 11px;font:inherit;outline:none}
textarea{min-height:150px;resize:vertical}
.row{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}
button{margin-top:14px;width:100%;padding:11px 14px;border:0;border-radius:10px;background:linear-gradient(135deg,#6ea8fe,#8b7bff);color:#07101f;font-weight:700;font-size:15px;cursor:pointer}
button:disabled{opacity:.6;cursor:wait}
pre{background:#0a1120;border:1px solid var(--line);border-radius:10px;padding:12px;overflow:auto;font-size:12.5px;max-height:340px}
.ans{border-top:1px dashed var(--line);padding:12px 0}.ans:first-child{border-top:0}
.name{font-weight:700}.kind{color:var(--muted);font-size:12px;margin-left:6px}
.bar{height:8px;border-radius:99px;background:#1d2740;overflow:hidden;margin:6px 0 2px}
.bar i{display:block;height:100%;background:linear-gradient(90deg,#6ea8fe,#45d09e)}
.opt{display:flex;justify-content:space-between;font-size:12.5px;color:var(--muted)}
.pill{display:inline-block;font-size:12px;padding:2px 8px;border-radius:99px;border:1px solid var(--line);color:var(--muted);margin-left:8px}
.ok{color:var(--ok)} .warn{color:#ffcf70}
small{color:var(--muted)} a{color:var(--acc)}
</style></head><body><main>
<header><div class="logo">S1</div><div><h1>sys1 — 本地 System One 决策</h1>
<p class="sub">逆向 laya 的协议与 Jev 的 <code>/v1/systemone</code> 线协议；本地打分，无 API Key，无外网。</p></div></header>
<div class="grid">
<div class="card">
<label for="state">状态（任意文本 / JSON）</label>
<textarea id="state">我这个月被重复扣款了两次，退款一直没有到账。如果今天不解决，我就要取消订阅了。</textarea>
<div class="row">
<div><label for="lang">语言提示</label><select id="lang"><option value="">自动</option><option value="zh">zh</option><option value="en">en</option><option value="es">es</option><option value="de">de</option><option value="ja">ja</option></select></div>
<div><label for="mc">最低置信度</label><input id="mc" type="number" min="0" max="1" step="0.05" placeholder="如 0.6"></div>
</div>
<button id="go">执行决策</button>
<p><small>问题集固定为 laya README 的 triage：部门（choice）、紧急度（score）、流失风险（noul）。</small></p>
</div>
<div class="card"><label>结果</label><div id="out"><small>点“执行决策”。</small></div></div>
</div>
<pre id="raw" hidden></pre>
</main><script>
const QS={department:{type:"choice",instructions:"Which department should handle this?",criteria:{billing:"invoices, payments, refunds",technical:"bugs, outages, system errors",other:"everything else"}},urgency:{type:"score",instructions:"How urgent is this?",criteria:["not urgent","soon","blocking"]},churn:{type:"noul",instructions:"Does the user threaten to cancel or leave?"}};
const fmt=(x)=>Number(x).toFixed(3);
function render(d){
  const out=document.getElementById('out'); if(!d.answers){out.innerHTML='<p class="warn">'+JSON.stringify(d)+'</p>';return;}
  let h='';
  for(const [id,a] of Object.entries(d.answers)){
    h+='<div class="ans"><span class="name">'+id+'</span><span class="kind">'+a.type+'</span>'+(a.low_confidence?'<span class="pill warn">低置信度</span>':'')+'<span class="pill">answer_conf '+fmt(a.answer_confidence)+'</span>';
    if(a.type==='choice'){
      h+='<div style="margin:8px 0 4px"><b>'+a.choice+'</b></div>';
      for(const [k,v] of Object.entries(a.probabilities)){h+='<div class="bar"><i style="width:'+(100*v).toFixed(1)+'%"></i></div><div class="opt"><span>'+k+'</span><span>'+fmt(v)+'</span></div>';}
    } else if(a.type==='score'){
      h+='<div style="margin:8px 0 4px"><b>score '+fmt(a.score)+'</b></div>';
      for(const [k,v] of Object.entries(a.probabilities)){h+='<div class="bar"><i style="width:'+(100*v).toFixed(1)+'%"></i></div><div class="opt"><span>'+k+' · '+(a.legend[k]||'')+'</span><span>'+fmt(v)+'</span></div>';}
    } else {h+='<div style="margin:8px 0 4px"><b>P(yes) = '+fmt(a.noul)+'</b></div>';}
    h+='</div>';
  }
  h+='<p><small>路由：'+d.routing.model+' · '+d.routing.reason+'<br>引擎：'+d.sys1.engine+' · '+d.sys1.latency_ms+' ms · 校准：'+d.sys1.calibration+'</small></p>';
  out.innerHTML=h;
}
document.getElementById('go').onclick=async()=>{
  const b=document.getElementById('go'); b.disabled=true; b.textContent='决策中…';
  const body={state:document.getElementById('state').value,questions:QS};
  const lg=document.getElementById('lang').value; if(lg) body.lang=lg;
  const mc=document.getElementById('mc').value; if(mc!=='') body.min_confidence=Number(mc);
  try{
    const r=await fetch('v1/systemone',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)});
    const d=await r.json(); render(d);
    const raw=document.getElementById('raw'); raw.hidden=false; raw.textContent=JSON.stringify(d,null,2);
  }catch(e){document.getElementById('out').innerHTML='<p class="warn">'+e+'</p>';}
  b.disabled=false; b.textContent='执行决策';
};
</script></body></html>
"""


class Config:
    def __init__(self, engine: Optional[DecisionEngine] = None):
        self.engine = engine or DecisionEngine()
        self.strict = os.environ.get("SYS1_JEV_STRICT", "").strip().lower() in ("1", "true", "yes", "on")
        self.api_key = os.environ.get("SYS1_API_KEY") or ""
        try:
            self.max_concurrent = max(1, int(os.environ.get("SYS1_MAX_CONCURRENT", "16")))
        except ValueError:
            self.max_concurrent = 16
        self.slots = threading.Semaphore(self.max_concurrent)


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: Any,
                   headers: Optional[Dict[str, str]] = None) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Headers", "authorization, content-type")
    for key, value in (headers or {}).items():
        handler.send_header(key, value)
    handler.end_headers()
    handler.wfile.write(body)


class BadRequest(Exception):
    """The request itself is malformed (400), not merely invalid (422)."""


def _error(handler: BaseHTTPRequestHandler, status: int, detail: str) -> None:
    _json_response(handler, status, {"detail": detail})


def _check_auth(handler: BaseHTTPRequestHandler, cfg: Config) -> bool:
    if not cfg.api_key:
        return True
    header = handler.headers.get("Authorization", "")
    return header == "Bearer " + cfg.api_key


def _read_json(handler: BaseHTTPRequestHandler) -> Any:
    length = handler.headers.get("Content-Length")
    if length is None:
        raise BadRequest("request body must be valid JSON")
    try:
        size = int(length)
    except ValueError:
        raise BadRequest("request body must be valid JSON") from None
    if size > MAX_BODY:
        raise OverflowError("request body too large")
    raw = handler.rfile.read(size)
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise BadRequest("request body must be valid JSON") from None


def _check_sizes(body: Dict[str, Any], state_count: int = 1) -> None:
    questions = body.get("questions")
    if not isinstance(questions, dict):
        raise QuestionError("'questions' must be an object")
    if len(questions) > 100:
        raise OverflowError("too many questions")
    for qid, qdef in questions.items():
        if not isinstance(qdef, dict):
            continue
        if qdef.get("type") == "choice":
            crit = qdef.get("criteria")
            if isinstance(crit, (dict, list)) and len(crit) > MAX_CHOICE_OPTIONS:
                raise OverflowError(
                    "question %r has %d options, over the %d-option amplification guard"
                    % (qid, len(crit), MAX_CHOICE_OPTIONS)
                )
    states = body.get("states") if state_count > 1 else None
    if states is not None and len(states) > 1000:
        raise OverflowError("too many states")


class Handler(BaseHTTPRequestHandler):
    server_version = "sys1/" + VERSION
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:  # quieter logs
        line = "[%s] %s\n" % (time.strftime("%H:%M:%S"), fmt % args)
        try:
            self.server.log.write(line)  # type: ignore[attr-defined]
            self.server.log.flush()
        except Exception:
            pass

    @property
    def cfg(self) -> Config:
        return self.server.cfg  # type: ignore[attr-defined]

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "authorization, content-type")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path == "/health":
            if self.cfg.api_key and not _check_auth(self, self.cfg):
                _json_response(self, 200, {"status": "ok"})
                return
            _json_response(self, 200, {
                "status": "ok",
                "loaded": ["sys1-lexical"],
                "revisions": {"sys1-lexical": VERSION},
                "device": "cpu",
                "device_is_preference": False,
                "checkpoint_devices": {"sys1-lexical": "cpu"},
                "cpu_fallbacks": {"sys1-lexical": {"count": 0, "last_reason": None}},
                "engine": "sys1",
                "calibration": self.cfg.engine.calibration_note,
            })
            return
        if path in ("/", "/index.html"):
            body = DEMO_PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        _error(self, 404, "not found")

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path not in ("/v1/systemone", "/v1/systemone/batch"):
            _error(self, 404, "not found")
            return
        if not _check_auth(self, self.cfg):
            _error(self, 401, "invalid or missing bearer token")
            return
        if not self.cfg.slots.acquire(blocking=False):
            _error(self, 503, "server busy, try again later")
            return
        try:
            body = _read_json(self)
            if not isinstance(body, dict):
                _error(self, 400, "request body must be a JSON object")
                return
            if path == "/v1/systemone":
                self._single(body)
            else:
                self._batch(body)
        except OverflowError as exc:
            _error(self, 413, str(exc))
        except BadRequest as exc:
            _error(self, 400, str(exc))
        except QuestionError as exc:
            _error(self, 422, str(exc))
        except Exception as exc:  # noqa: BLE001
            _error(self, 500, "inference failed")
            self.server.log.write("error: %r\n" % (exc,))  # type: ignore[attr-defined]
        finally:
            self.cfg.slots.release()

    # ------------------------------------------------------------------ routes
    def _single(self, body: Dict[str, Any]) -> None:
        if "questions" not in body:
            _error(self, 400, "request body must be an object with a 'questions' field")
            return
        if "state" not in body or body.get("state") is None:
            _error(self, 400, "'state' is required")
            return
        _check_sizes(body)
        options = {
            "model": body.get("model"),
            "task": body.get("task"),
            "lang": body.get("lang"),
            "lang_guess": body.get("lang_guess"),
            "max_len": body.get("max_len", 512),
            "head_max_len": body.get("head_max_len", 192),
            "min_confidence": body.get("min_confidence"),
        }
        if options["model"] is not None and not isinstance(options["model"], str):
            raise QuestionError("model must be a string")
        for key in ("max_len", "head_max_len"):
            value = options[key]
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise QuestionError("%s must be a positive integer" % key)
        for key in ("lang", "lang_guess", "task"):
            if options[key] is not None and not isinstance(options[key], str):
                raise QuestionError("%s must be a string" % key)
        started = time.perf_counter()
        result = self.cfg.engine.predict(body["state"], body["questions"], **options)
        self._finish(result, started)

    def _batch(self, body: Dict[str, Any]) -> None:
        if "questions" not in body or "states" not in body:
            _error(self, 400, "request body must be an object with 'states' and 'questions' fields")
            return
        _check_sizes(body, state_count=2)
        states = body["states"]
        if not isinstance(states, list) or not states:
            raise QuestionError("'states' must be a non-empty list")
        options = {
            "model": body.get("model"),
            "task": body.get("task"),
            "lang": body.get("lang"),
            "lang_guess": body.get("lang_guess"),
            "max_len": body.get("max_len", 512),
            "head_max_len": body.get("head_max_len", 192),
            "min_confidence": body.get("min_confidence"),
        }
        started = time.perf_counter()
        result = self.cfg.engine.predict_batch(states, body["questions"], **options)
        if self.cfg.strict:
            result["results"] = [project_jev_strict(item) for item in result["results"]]
        else:
            from .decode import add_jev_confidence
            result["results"] = [add_jev_confidence(item) for item in result["results"]]
        self._send(result, started)

    def _finish(self, result: Dict[str, Any], started: float) -> None:
        if self.cfg.strict:
            result = project_jev_strict(result)
        else:
            from .decode import add_jev_confidence
            result = add_jev_confidence(result)
        self._send(result, started)

    def _send(self, payload: Dict[str, Any], started: float) -> None:
        elapsed = (time.perf_counter() - started) * 1000.0
        _json_response(self, 200, payload, {
            "Server-Timing": "inference;dur=%.2f" % elapsed,
            "X-Inference-Time-Ms": "%.2f" % elapsed,
        })


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, cfg: Config, log_path: Optional[str] = None):
        self.cfg = cfg
        import sys
        self.log = sys.stderr
        super().__init__(address, Handler)


def create_server(host: str = "0.0.0.0", port: int = 8000,
                  engine: Optional[DecisionEngine] = None) -> Server:
    return Server((host, port), Config(engine))


def main(argv: Optional[list] = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(prog="sys1 serve")
    parser.add_argument("--host", default=os.environ.get("SYS1_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("SYS1_PORT", "8000")))
    args = parser.parse_args(argv)
    server = create_server(args.host, args.port)
    host, port = server.server_address[0], server.server_address[1]
    print("sys1 %s listening on http://%s:%d" % (VERSION, host, port))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
