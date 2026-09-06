"""CANONFLOW review console. Human-in-the-loop control plane."""
from __future__ import annotations

import gradio as gr

from ..flow.nodes.render import TIERS
from . import data

CSS = """
.gradio-container {max-width:1500px !important}
footer {display:none !important}
#hdr h1 {font:600 22px/1.2 system-ui;margin:0}
#hdr p {color:#8b94a7;margin:4px 0 0;font-size:13px}
"""

HEADERS = ["beat", "segment", "shots", "sec", "verdict",
           "ctx_state", "media", "run"]
IMG_EXT = (".png", ".jpg", ".jpeg", ".webp")
VID_EXT = (".mp4", ".webm", ".mov")


THEME = gr.themes.Base(primary_hue="indigo", neutral_hue="slate")


def build() -> gr.Blocks:
    idx0 = data.scan()

    with gr.Blocks(title="CANONFLOW") as ui:
        state = gr.State(idx0)

        with gr.Row(elem_id="hdr"):
            gr.HTML("<h1>CANONFLOW - Agentic Film Control Plane</h1>"
                    "<p>yd-when-paradise-glitches &middot; packet-bound shot "
                    "contracts &middot; canon validation &middot; gated "
                    "rendering</p>")

        with gr.Tab("Timeline"):
            tl = gr.HTML(data.timeline_html(idx0))
            tbl = gr.Dataframe(value=data.overview_rows(idx0),
                               headers=HEADERS, interactive=False, wrap=True)
            refresh = gr.Button("Reload runs", variant="secondary")

        with gr.Tab("Shot Review"):
            with gr.Row():
                beat_dd = gr.Dropdown(sorted(idx0), label="Beat")
                shot_dd = gr.Dropdown([], label="Shot")
            with gr.Row():
                with gr.Column(scale=1):
                    verdict = gr.Textbox(label="Canon verdict",
                                         interactive=False)
                    contract = gr.JSON(label="Packet contract")
                with gr.Column(scale=2):
                    prompt_box = gr.Code(label="Render prompt", lines=18)
            with gr.Row():
                gallery = gr.Gallery(label="Rendered stills", columns=4,
                                     height=280)
                video = gr.Video(label="Rendered clip")

        with gr.Tab("Render (gated)"):
            with gr.Row():
                tier = gr.Radio(list(TIERS), value="draft", label="Tier")
                nshots = gr.Number(value=1, precision=0, label="Shots")
                secs = gr.Number(value=10, precision=0, label="Seconds/shot")
            cost = gr.Markdown()
            gr.Markdown("Tiers above `draft` require `CF_TIER_OK=<batch_id>` "
                        "in the server environment. This console never "
                        "bypasses that gate.")

        def on_refresh():
            idx = data.scan()
            return (idx, data.timeline_html(idx), data.overview_rows(idx),
                    gr.update(choices=sorted(idx)))

        refresh.click(on_refresh, None, [state, tl, tbl, beat_dd])

        def on_beat(idx, b):
            if not b or b not in idx:
                return gr.update(choices=[]), "", None, "", [], None
            r = idx[b]
            keys = ["{}.{}".format(s.get("scene_no"), s.get("shot_no"))
                    for s in r["shots"]]
            imgs = [str(p) for p in r["media"]
                    if p.suffix.lower() in IMG_EXT]
            vids = [str(p) for p in r["media"]
                    if p.suffix.lower() in VID_EXT]
            return (gr.update(choices=keys, value=keys[0] if keys else None),
                    r["verdict"], None, "", imgs,
                    vids[0] if vids else None)

        beat_dd.change(on_beat, [state, beat_dd],
                       [shot_dd, verdict, contract, prompt_box, gallery, video])

        def on_shot(idx, b, key):
            if not (b and key and b in idx):
                return None, ""
            r = idx[b]
            sc, sh = (int(x) for x in key.split("."))
            shot = next((s for s in r["shots"]
                         if s.get("scene_no") == sc
                         and s.get("shot_no") == sh), {})
            view = {k: shot.get(k) for k in
                    ("duration_s", "hero_render", "intent", "subject",
                     "characters_present", "location", "time_of_day")}
            pr = r["prompts"]
            items = pr.get("prompts", pr) if isinstance(pr, dict) else pr
            text = ""
            if isinstance(items, list):
                hit = next((p for p in items
                            if isinstance(p, dict)
                            and p.get("scene_no") == sc
                            and p.get("shot_no") == sh), None)
                if hit:
                    text = hit.get("prompt") or hit.get("text") or str(hit)
            elif items:
                text = str(items)
            return view, text

        shot_dd.change(on_shot, [state, beat_dd, shot_dd],
                       [contract, prompt_box])

        def on_cost(t, n, s):
            spec = TIERS[t]
            img = spec["usd_image"] * int(n or 0)
            vid = spec["usd_video_per_s"] * int(n or 0) * int(s or 0)
            return ("**Estimate - tier `{}`**  \n"
                    "image `{}` @ {}: `${:.2f}`  \n"
                    "video `{}` @ {}: `${:.2f}`  \n"
                    "**total `${:.2f}`**").format(
                        t, spec["image"], spec["image_res"], img,
                        spec["video"], spec["video_res"], vid, img + vid)

        for comp in (tier, nshots, secs):
            comp.change(on_cost, [tier, nshots, secs], cost)
        ui.load(on_cost, [tier, nshots, secs], cost)

    return ui
