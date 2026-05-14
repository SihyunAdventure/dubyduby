# dubyduby — Agent instructions

You're an AI agent (Claude, Codex, Cursor, etc.) helping a user dub YouTube videos into Korean.

## Trigger

User says any of:
- "이 URL dub해줘"
- "dub this URL"
- "dub this video"
- "이 영상 한국어로"
- Pastes a YouTube URL with intent to translate

## Two-phase workflow

`bash scripts/dub.sh <URL>` orchestrates everything. It runs in **two phases** with a pause between them where **you** (the agent) write the translation.

### Phase 1 — download + transcribe (automatic)

```bash
bash scripts/dub.sh https://youtu.be/EXAMPLE
```

This:
1. Downloads video + audio via yt-dlp → `output/<video_id>/1_source/{video.mp4, audio.mp3}`
2. Calls Soniox STT batch → `output/<video_id>/2_transcript/{tokens.json, transcript.md}`
3. **Pauses** — prints instructions and exits.

If user wants only the first N seconds: `bash scripts/dub.sh <URL> 120` (cuts at 120s).

### Phase 2 — agent writes translation

**Before translating: read `glossary.json` at repo root.** It maps known STT misreads → canonical brand/term names, plus Korean phonetic spellings used in TTS. Apply during transcript cleanup before writing `sentences.json`.

Read `output/<video_id>/2_transcript/transcript.md` (full EN text from Soniox).

Write `output/<video_id>/3_translation/sentences.json` as an array of `{en, ko}`:

```json
[
  { "en": "Hey everybody,", "ko": "여러분 안녕하세요." },
  { "en": "Opus 4.7 just dropped a few minutes ago,", "ko": "Opus 사 점 칠이 방금 출시됐는데요." }
]
```

Then re-run the same orchestrator command:

```bash
bash scripts/dub.sh https://youtu.be/EXAMPLE
```

This time it detects `sentences.json` and proceeds: match_timing → synthesize → finalize → `output/<video_id>/6_final/dubbed_video.mp4`.

## Glossary — STT misread fix + Korean phonetic

`glossary.json` (repo root) is the source of truth for brand names and recurring terms. Each entry:

```json
{
  "canonical": "Claude Code",
  "stt_misreads": ["Cloth Code", "Cloud Code"],
  "korean_phonetic": "클로드 코드",
  "category": "ai-product"
}
```

### How to use it

1. **Before writing sentences.json**, scan transcript for any `stt_misreads` strings and replace with `canonical`. Soniox commonly mishears `Claude` as `Cloth`, `Karpathy` as `Carpathy`, etc.
2. For the Korean column (`ko`), use `korean_phonetic` when the term appears (or keep Latin brand per [Brand names](#brand-names--latin-script) rule below — both forms are valid; pick whichever sounds natural in context).
3. If you encounter a new recurring term (proper noun, product name, technical term) that isn't in `glossary.json`:
   - Add it inline during this translation pass.
   - **Surface it to the user** in your end-of-turn summary so they can confirm.
   - On confirmation, append a new entry to `glossary.json`. Keep entries sorted by category, then by canonical name.

### Categories

- `ai-product` (Claude, GPT, ChatGPT, Gemini, Mythos, …)
- `ai-concept` (LLM, RAG, agentic, vibe coding, …)
- `company` (OpenAI, Anthropic, Tesla, …)
- `person` (Andrej Karpathy, …)
- `tech` (Bash, Autopilot, …)
- `social` (Twitter, X, …)
- `product` (dubyduby itself, user products, …)

## Translation guidelines (lock-in)

User-validated patterns (2026-05-14). Apply consistently for every utterance.

### Tone

- **자막체 polite endings**: `-어요`, `-이에요`, `-예요`, `-네요`, `-죠`
- **NEVER formal**: `-입니다`, `-합니다`, `-답니다`, `-ㅂ니다`
- Subjects **explicit** (Korean usually drops them — keep them here):
  - `we` → 우리는
  - `I` → 저는
  - `they` → 그들은
  - `these guys` → 이 친구들은
  - `you` → 여러분은

### Numbers in Korean phonetic

- `4.7` → "사 점 칠"
- `53.4%` → "오십삼 점 사 퍼센트"
- `2020` → "이천이십 년"
- Model versions like `GPT-5.4` → "GPT 오 점 사" (brand keeps Latin)

### Brand names — Latin script

- `Opus`, `GPT`, `Gemini`, `Mythos`, `Anthropic`, `Claude`, `dubyduby` (in writing — TTS will pronounce "더비더비")
- Do NOT romanize Korean phonetics into Latin

### Discourse markers — preserved (not omitted)

- `All right` → "좋아요" or "자"
- `so` → "그래서"
- `well` → "글쎄요"
- `you know` → "있잖아요"
- Filler ONLY when meaningless: omit `uh`, `um`, `ah`, `er`

### Sentence boundaries

- **Do NOT split inside brand names** with periods: `Opus 4.7` is ONE token, never "Opus 4." + "7..." (Soniox auto-segmentation makes this mistake; fix it).
- One sentence per array entry. Multiple sentences per entry → Supertonic inserts 0.3s silence between chunks (sounds bad).
- Max ~120 Korean chars per entry (Supertonic ko chunk limit).
- Korean commas (`,`) → omit. Supertonic adds micro-pauses on commas, which compound across many sentences.

### Repetition — preserved

- `really, really, really long` → "정말, 정말, 정말 긴"
- `that's, that's cool` → "그건, 그건 멋져요"

### Idiom override (when literal sounds stiff)

- `All there is to say` → "더 할 말은 없네요" (NOT "그게 전부예요")
- `here we are in front of X` → "우리는 X 앞에 있어요" (literal works)
- `pretty much` → "거의" or "딱히"

## Long-form videos — chunked linear workflow

For videos longer than ~10 minutes (= >150 sentences), don't try to write `sentences.json` in one shot. Append in linear chunks and let the **accumulated reference** do the consistency work for you.

### Why linear, not parallel

The video is **not split**. yt-dlp downloads it once, Soniox transcribes it once, synthesis runs over the full `sentences.json`. The only thing chunked is **your translation work**.

Going linear (chunk N reads chunks 1..N-1 as context) gives you:
- **Style propagation** — the tone (자막체 endings, subject explicitness, discourse marker handling) set in chunk 1 carries through. New chunks self-correct against earlier ones.
- **Implicit consistency for things glossary.json can't capture** — idiom interpretation, speaker personality (Karpathy 톤 vs interviewer 톤), comma/period split rhythm, repetition handling.
- **Growing glossary** — when you discover a new proper noun mid-transcript, surface it, append to `glossary.json`, and from that chunk on it's a hard rule.

Parallel chunking *can* keep glossary terms consistent (it's a lookup table), but it loses the soft-reference layer. For short videos (≤30min), linear is fast enough that the trade-off doesn't matter.

### Chunk sizing — empirical

| Video length | Approx sentences | Recommended chunks |
|---|---|---|
| 5 min | ~75 | 1 (single pass) |
| 30 min | ~450 | 6–8 (50–60 per chunk) |
| 1 h | ~900 | 12–15 |
| 2 h | ~1800 | 25–30 |

Chunk size sweet spot is **~50–60 sentences**. Smaller = more orchestration overhead. Larger = harder to keep coherent in one pass.

### First chunk is the style seed — slow down here

The first chunk (especially the first ~30 entries) locks in:
- The polite-ending palette you'll use (`-어요/-네요/-죠/-이에요` — pick a balance)
- How you handle each speaker's voice (host vs guest 톤)
- Discourse marker translations
- Subject explicitness pattern

Once locked in, chunks 2..N can move much faster — most decisions are already made. Spend disproportionate care on chunk 1.

### Append pattern

Don't rewrite the whole file each chunk. Read existing, append, write back:

```python
import json
from pathlib import Path
TARGET = Path("output/<video_id>/3_translation/sentences.json")

existing = json.loads(TARGET.read_text()) if TARGET.exists() else []
new = [
  {"en": "...", "ko": "...", "ko_tts": "..."},  # ko_tts only when Latin brand → 한글 음역 needed
  ...
]
combined = existing + new
TARGET.write_text(json.dumps(combined, ensure_ascii=False, indent=2) + "\n")
print(f"appended {len(new)} → total {len(combined)}")
```

Save this as a tiny helper and reuse across chunks. **Sentence order in the final array must follow the transcript** — appending preserves that automatically as long as you proceed left-to-right through the transcript.

### New-term protocol

When you encounter a proper noun, product name, or technical term not in `glossary.json`:
1. Translate it inline in the current chunk using your best guess.
2. At the **end of that chunk's turn**, surface it to the user in your reply: *"새로 등장한 term: `Nanobanana` → '나노바나나'로 처리했어요. glossary에 추가할까요?"*
3. On confirmation, append to `glossary.json` (sorted by category then canonical name).
4. From the next chunk onward, the term is a hard reference — no more interpretation needed.

This way the glossary **grows during the dub**, and later chunks benefit from earlier discoveries.

### Audit before Phase 3

After the last chunk, before running `dub.sh` again for Phase 3:
- Scan for new proper nouns you handled inconsistently across chunks (`grep -i "<term>"` over `sentences.json`).
- Check that any added glossary terms are applied retroactively where they appeared in earlier chunks.
- Spot-check 3–5 random sentences from each major section for tone consistency.

5 minutes of audit catches issues that would otherwise show up as awkward 자막 mid-watch.

## Output structure

```
output/<video_id>/
├── 1_source/        video.mp4, audio.mp3       (yt-dlp)
├── 2_transcript/    tokens.json, transcript.md (Soniox)
├── 3_translation/   sentences.json, sentences.md, utterances.json (agent + match_timing)
├── 4_synth/         utt-NNN.wav                (Supertonic per-utterance)
├── 5_intermediate/  dub_raw.wav, dub_clean.wav (concat, silenceremove)
└── 6_final/         dubbed_audio.wav, dubbed_video.mp4 (atempo fit + mux)
```

## Voice

Default = M1. Override per dub:

```bash
DUBYDUBY_VOICE=F3 bash scripts/dub.sh <URL>
```

Voices: M1-M5, F1-F5. Preview: `samples/*.mp3` in this repo.

## Environment

- `SONIOX_API_KEY` in `.env` (required; sign up at https://soniox.com — 200min/month free)
- No LLM API key needed — you (the agent) handle translation directly.

## First-time setup

If `.venv/` or `binaries/yt-dlp` missing: run `bash scripts/setup.sh`. It installs uv venv + supertonic + yt-dlp. Supertonic model (~260MB) auto-downloads on first synth.

## Translation length tip

Korean tends to be ~20-30% verbose vs English in this style guide (explicit subjects + Korean phonetic numbers). atempo will scale to fit video (typically 1.1-1.3x). If user reports unnatural audio, try shortening verbose Korean entries.
