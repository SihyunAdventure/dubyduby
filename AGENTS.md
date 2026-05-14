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
