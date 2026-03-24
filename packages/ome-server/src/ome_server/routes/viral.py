"""Viral growth routes — Soul Card sharing + Guess Who game.

These are PUBLIC routes (no auth required) designed for viral sharing:
- Soul Card: shareable personality card image
- Guess Who: game where visitors guess which answer is from AI vs human
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

from ome.core import Ome
from ome_server.deps import get_ome
from ome_server import ome_manager

router = APIRouter()

# In-memory store for guess games (lightweight, no DB needed)
_games: dict[str, dict] = {}


# ── Guess Who Game ──────────────────────────────────────────

class GuessGameCreate(BaseModel):
    question: str      # The question both user and Ome answer
    user_answer: str   # User's actual answer
    ome_answer: str    # Ome's answer (from mirror_chat)


@router.post("/guess-game/create")
async def create_guess_game(req: GuessGameCreate, ome: Ome = Depends(get_ome)):
    """Create a new Guess Who game. Returns a shareable game ID."""
    game_id = uuid.uuid4().hex[:10]

    # Randomly assign which is A and which is B (so it's not always the same order)
    import random
    user_is_a = random.choice([True, False])

    _games[game_id] = {
        "id": game_id,
        "user_name": ome.name,
        "question": req.question,
        "answer_a": req.user_answer if user_is_a else req.ome_answer,
        "answer_b": req.ome_answer if user_is_a else req.user_answer,
        "human_is": "a" if user_is_a else "b",
        "created_at": datetime.utcnow().isoformat(),
        "guesses": {"correct": 0, "wrong": 0},
    }

    return {"game_id": game_id}


@router.get("/guess-game/{game_id}")
async def get_guess_game_page(game_id: str):
    """Serve the Guess Who game as an HTML page (for sharing via WeChat/browser)."""
    game = _games.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="游戏不存在或已过期")

    html = _render_guess_page(game)
    return HTMLResponse(content=html)


@router.post("/guess-game/{game_id}/guess")
async def submit_guess(game_id: str, guess: str):
    """Submit a guess: 'a' or 'b'. Returns whether correct."""
    game = _games.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="游戏不存在")

    correct = guess == game["human_is"]
    if correct:
        game["guesses"]["correct"] += 1
    else:
        game["guesses"]["wrong"] += 1

    total = game["guesses"]["correct"] + game["guesses"]["wrong"]
    fool_rate = int(game["guesses"]["wrong"] / total * 100) if total > 0 else 0

    return {
        "correct": correct,
        "human_was": game["human_is"],
        "fool_rate": fool_rate,
        "total_guesses": total,
        "user_name": game["user_name"],
    }


def _render_guess_page(game: dict) -> str:
    """Render the Guess Who game as a self-contained HTML page.

    Design: dark theme matching Omnity brand. Works in WeChat browser.
    """
    game_json = json.dumps({
        "id": game["id"],
        "user_name": game["user_name"],
        "question": game["question"],
        "answer_a": game["answer_a"],
        "answer_b": game["answer_b"],
    }, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>猜猜哪个是AI · {game["user_name"]}的分身</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    background: #0a0a16;
    color: #f0ede6;
    font-family: -apple-system, "PingFang SC", sans-serif;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 40px 20px;
}}
.brand {{ color: #a08758; font-size: 14px; letter-spacing: 4px; margin-bottom: 8px; }}
h1 {{ font-size: 22px; margin-bottom: 6px; }}
.subtitle {{ color: #a09a90; font-size: 14px; margin-bottom: 30px; }}
.question {{
    background: #1a1a2e;
    border: 1px solid #2a2840;
    border-radius: 12px;
    padding: 16px 20px;
    width: 100%;
    max-width: 400px;
    margin-bottom: 24px;
    text-align: center;
}}
.question-label {{ color: #a08758; font-size: 12px; margin-bottom: 6px; }}
.answers {{ width: 100%; max-width: 400px; }}
.answer {{
    background: #14142a;
    border: 2px solid #2a2840;
    border-radius: 14px;
    padding: 18px 20px;
    margin-bottom: 14px;
    cursor: pointer;
    transition: all 0.2s;
    line-height: 1.6;
}}
.answer:hover {{ border-color: #c8a96e; }}
.answer:active {{ transform: scale(0.98); }}
.answer-label {{
    color: #c8a96e;
    font-size: 13px;
    font-weight: bold;
    margin-bottom: 6px;
}}
.answer.selected-correct {{
    border-color: #4ade80;
    background: rgba(74,222,128,0.1);
}}
.answer.selected-wrong {{
    border-color: #f87171;
    background: rgba(248,113,113,0.1);
}}
.answer.revealed {{
    opacity: 0.6;
}}
#result {{
    display: none;
    text-align: center;
    margin-top: 20px;
    width: 100%;
    max-width: 400px;
}}
.result-text {{ font-size: 20px; margin-bottom: 8px; }}
.result-detail {{ color: #a09a90; font-size: 14px; margin-bottom: 20px; line-height: 1.6; }}
.cta {{
    display: inline-block;
    background: #c8a96e;
    color: #0a0a16;
    padding: 12px 28px;
    border-radius: 10px;
    font-weight: bold;
    text-decoration: none;
    margin-top: 10px;
}}
.stats {{ color: #a08758; font-size: 13px; margin-top: 12px; }}
</style>
</head>
<body>
<div class="brand">✦ Ome ✦</div>
<h1>猜猜哪个是AI</h1>
<div class="subtitle">{game["user_name"]}的AI分身在其中一个回答里</div>

<div class="question">
    <div class="question-label">问题</div>
    <div id="q"></div>
</div>

<div class="answers">
    <div class="answer" id="ans-a" onclick="guess('a')">
        <div class="answer-label">回答 A</div>
        <div id="text-a"></div>
    </div>
    <div class="answer" id="ans-b" onclick="guess('b')">
        <div class="answer-label">回答 B</div>
        <div id="text-b"></div>
    </div>
</div>

<div id="result">
    <div class="result-text" id="result-text"></div>
    <div class="result-detail" id="result-detail"></div>
    <div class="stats" id="result-stats"></div>
    <a class="cta" href="#">我也要一个AI分身 →</a>
</div>

<script>
const game = {game_json};
document.getElementById('q').textContent = game.question;
document.getElementById('text-a').textContent = game.answer_a;
document.getElementById('text-b').textContent = game.answer_b;

let guessed = false;

async function guess(choice) {{
    if (guessed) return;
    guessed = true;

    try {{
        const resp = await fetch(`/api/viral/guess-game/${{game.id}}/guess?guess=${{choice}}`, {{
            method: 'POST'
        }});
        const data = await resp.json();

        const ansA = document.getElementById('ans-a');
        const ansB = document.getElementById('ans-b');

        if (data.correct) {{
            document.getElementById(choice === 'a' ? 'ans-a' : 'ans-b').classList.add('selected-correct');
            document.getElementById(choice === 'a' ? 'ans-b' : 'ans-a').classList.add('revealed');
            document.getElementById('result-text').textContent = '🎯 猜对了！';
            document.getElementById('result-detail').textContent =
                `你成功分辨出了${{game.user_name}}和TA的AI分身。不过——${{data.fool_rate}}%的人猜错了哦`;
        }} else {{
            document.getElementById(choice === 'a' ? 'ans-a' : 'ans-b').classList.add('selected-wrong');
            document.getElementById(choice === 'a' ? 'ans-b' : 'ans-a').classList.add('selected-correct');
            document.getElementById('result-text').textContent = '😱 猜错了！';
            document.getElementById('result-detail').textContent =
                `${{game.user_name}}的AI分身骗过了你！已经有${{data.fool_rate}}%的人也被骗了`;
        }}

        document.getElementById('result-stats').textContent = `共 ${{data.total_guesses}} 人参与`;
        document.getElementById('result').style.display = 'block';
    }} catch (e) {{
        console.error(e);
    }}
}}
</script>
</body>
</html>"""
