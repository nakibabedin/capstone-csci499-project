"""Benchmark LLM lab-result extraction on Modal GPUs against the local rule parser.

Measures, for one PDF on one GPU type:
  - cold start: container start + model load, as seen from your machine
  - whole document in a single request
  - every page as its own request, all sent in one batch (vLLM runs them in parallel)
and scores each against the rule parser's results.

Setup (once):
    pip install modal pymupdf
    modal setup                       # opens a browser to log in

Run from this directory:
    BENCH_GPU=A10G modal run bench_modal.py --pdf /path/to/report.pdf
    BENCH_GPU=H100 modal run bench_modal.py --pdf report.pdf --model Qwen/Qwen2.5-7B-Instruct

The GPU is chosen with an environment variable rather than a flag because Modal
checks the GPU a class declares when the app starts, so it must be set at import.
H100s require a payment method on the Modal account.

Page text is uploaded to Modal, so only use sample or synthetic reports.
The first run also builds the image and downloads the model (~16 GB) to a
Modal volume, so its cold start isn't representative; run it twice.
"""

import json
import os
import re
import sys
import time
from pathlib import Path

import modal

# Same model as the local Ollama `qwen2.5vl:7b`, for an apples-to-apples comparison.
DEFAULT_MODEL = "Qwen/Qwen2.5-VL-7B-Instruct"
MAX_MODEL_LEN = 16384
GPU = os.environ.get("BENCH_GPU", "A10G")

SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "test": {"type": "string"},
                    "value": {"type": "string"},
                    "unit": {"type": "string"},
                    "reference_range": {"type": "string"},
                    "flag": {"type": "string"},
                },
                "required": ["test", "value", "unit", "reference_range", "flag"],
            },
        }
    },
    "required": ["results"],
}
PROMPT = (
    "Extract every lab test result from this lab report text. Include only tests with a measured "
    "result from the results tables; ignore explanatory notes, interpretation tables, and patient "
    "details. Copy the value, unit, reference range and flag (H/L) exactly as printed; use an empty "
    "string when a field is missing."
)

image = (
    modal.Image.debian_slim(python_version="3.12")
    .uv_pip_install("vllm==0.9.2", "hf_transfer")
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
)
hf_cache = modal.Volume.from_name("lab-bench-hf-cache", create_if_missing=True)
vllm_cache = modal.Volume.from_name("lab-bench-vllm-cache", create_if_missing=True)
volumes = {"/root/.cache/huggingface": hf_cache, "/root/.cache/vllm": vllm_cache}

app = modal.App("lab-report-llm-bench", image=image)


@app.function(volumes=volumes, timeout=30 * 60)
def download(model: str):
    """Fetch the weights on a CPU container so GPU time isn't spent downloading."""
    from huggingface_hub import snapshot_download

    snapshot_download(model)
    hf_cache.commit()


@app.cls(gpu=GPU, volumes=volumes, timeout=20 * 60, scaledown_window=60)
class Extractor:
    model: str = modal.parameter(default=DEFAULT_MODEL)

    @modal.enter()
    def load(self):
        from vllm import LLM

        start = time.perf_counter()
        self.llm = LLM(model=self.model, max_model_len=MAX_MODEL_LEN, gpu_memory_utilization=0.90)
        self.load_seconds = time.perf_counter() - start

    @modal.method()
    def extract(self, texts: list[str]) -> dict:
        """Run one extraction request per text, batched together."""
        from vllm import SamplingParams
        from vllm.sampling_params import GuidedDecodingParams

        conversations = [
            [{"role": "system", "content": PROMPT}, {"role": "user", "content": text}]
            for text in texts
        ]
        # Let each request generate up to the context limit, like the local run.
        tokenizer = self.llm.get_tokenizer()
        params = [
            SamplingParams(
                temperature=0,
                max_tokens=MAX_MODEL_LEN - len(tokenizer.apply_chat_template(c, add_generation_prompt=True)),
                guided_decoding=GuidedDecodingParams(json=SCHEMA),
            )
            for c in conversations
        ]
        start = time.perf_counter()
        outputs = self.llm.chat(conversations, params, use_tqdm=False)
        return {
            "seconds": time.perf_counter() - start,
            "load_seconds": self.load_seconds,
            "outputs": [
                {
                    "text": o.outputs[0].text,
                    "finish": o.outputs[0].finish_reason,
                    "tokens_in": len(o.prompt_token_ids),
                    "tokens_out": len(o.outputs[0].token_ids),
                }
                for o in outputs
            ],
        }


# --- scoring (same checks as the local Ollama benchmark) ---

def _first_num(s):
    m = re.search(r"\d[\d,]*\.?\d*", s or "")
    return float(m.group().replace(",", "")) if m else None


def _nums(s):
    return sorted(float(x) for x in re.findall(r"\d+\.?\d*", (s or "").replace(",", "")))


def _words(s):
    return set(re.findall(r"[a-z0-9]+", (s or "").lower()))


def _parse(outputs):
    results, failures = [], []
    for i, o in enumerate(outputs):
        try:
            results += json.loads(o["text"])["results"]
        except (json.JSONDecodeError, KeyError):
            failures.append(f"request {i + 1}: invalid JSON (stop={o['finish']})")
    return results, failures


def _score(results, reference, source_text):
    compact = re.sub(r"\s+", "", source_text)
    ungrounded = [r for r in results if re.sub(r"\s+", "", r["value"]) not in compact]
    unused, matched = list(results), []
    for want in reference:
        hit = next(
            (r for r in unused
             if _first_num(r["value"]) == want["value"] and _words(r["test"]) & _words(want["test"])),
            None,
        )
        if hit:
            unused.remove(hit)
            matched.append((want, hit))
    return {
        "found": len(results),
        "matched": len(matched),
        "unit_ok": sum((w["unit"] or "").lower() == (h["unit"] or "").lower().replace(" ", "") for w, h in matched),
        "range_ok": sum(_nums(w["reference_range"]) == _nums(h["reference_range"]) for w, h in matched),
        "ungrounded": len(ungrounded),
        "unmatched": [(r["test"], r["value"]) for r in unused],
    }


def _print_run(label, wall, run, reference, source_text):
    results, failures = _parse(run["outputs"])
    s = _score(results, reference, source_text)
    tokens_out = sum(o["tokens_out"] for o in run["outputs"])
    print(f"\n### {label}")
    print(f"  wall {wall:.1f}s (GPU generation {run['seconds']:.1f}s), "
          f"{sum(o['tokens_in'] for o in run['outputs'])} tokens in, {tokens_out} out, "
          f"{tokens_out / run['seconds']:.0f} tokens/s overall")
    print(f"  matched {s['matched']}/{len(reference)} reference results "
          f"(recall {s['matched'] / max(1, len(reference)):.0%}, precision {s['matched'] / max(1, s['found']):.0%}); "
          f"of matched: unit ok {s['unit_ok']}, range ok {s['range_ok']}")
    print(f"  values not in source text: {s['ungrounded']}; invalid outputs: {failures or 'none'}")
    print(f"  unmatched LLM results: {s['unmatched']}")


@app.local_entrypoint()
def main(pdf: str, model: str = DEFAULT_MODEL):
    import pymupdf

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
    from lab_parser import parse_lab_report

    data = Path(pdf).read_bytes()
    pages = [page.get_text() for page in pymupdf.open(stream=data)]
    source_text = "".join(pages)
    start = time.perf_counter()
    reference = parse_lab_report(data, 50)[0]["results"]
    print(f"{Path(pdf).name}: {len(pages)} pages; rule parser {(time.perf_counter() - start) * 1000:.0f}ms, "
          f"{len(reference)} results. GPU {GPU}, model {model}")

    download.remote(model)
    extractor = Extractor(model=model)

    start = time.perf_counter()
    warmup = extractor.extract.remote(["Hemoglobin 13.2 g/dL 12.0 - 16.0"])
    print(f"\n### Cold start: {time.perf_counter() - start:.1f}s wall "
          f"(of which model load {warmup['load_seconds']:.1f}s)")

    start = time.perf_counter()
    run = extractor.extract.remote(["\n\n".join(pages)])
    _print_run("Whole document, one request", time.perf_counter() - start, run, reference, source_text)

    start = time.perf_counter()
    run = extractor.extract.remote(pages)
    _print_run(f"One request per page, {len(pages)} in parallel", time.perf_counter() - start,
               run, reference, source_text)
