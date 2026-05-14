# dubyduby

> 어떤 YouTube 영상이든 한국어로 더빙해주는 도구 — 에이전트 기반, 2인 보이스, 자막 포함.

YouTube URL을 붙여넣으면 `dubyduby`가 영상을 받아오고, 음성을 Soniox로 받아쓰고, **사용자가 평소 쓰는 AI 에이전트** (Claude Code, Codex, Cursor 등)가 한국어 번역을 직접 작성합니다. 그 다음 Supertonic으로 한국어 음성을 합성하고, 각 발화를 원본 시작 시각에 배치하고, ASS 자막을 입힌 뒤 다시 `.mp4`로 묶어줍니다.

**LLM API key는 필요 없습니다** — 번역은 이미 쓰고 있는 AI 에이전트가 [`AGENTS.md`](AGENTS.md)의 스타일 가이드를 따라 직접 처리하니까요.

**데모**: [`samples/demo-karpathy-5min.mp4`](samples/demo-karpathy-5min.mp4) — Karpathy 5분 발췌 (진행자 F1 + Karpathy M1 2인 보이스, Pretendard Bold 자막, 발화 단위 배치).

## 빠른 시작

```bash
git clone git@github.com:SihyunAdventure/dubyduby.git
cd dubyduby
bash scripts/setup.sh          # uv venv + supertonic + yt-dlp + Pretendard + ffmpeg 체크
cp .env.example .env           # SONIOX_API_KEY 입력
bash scripts/dub.sh "https://www.youtube.com/watch?v=..."
```

`dub.sh`는 **2단계로 끊어서** 동작합니다. 중간에 에이전트가 끼어드는 구조예요.

1. **Phase 1 (자동)** — yt-dlp로 다운로드, Soniox로 받아쓰기. 끝나면 안내 메시지 출력하고 종료.
2. **Phase 2 (에이전트)** — AI 에이전트가 `output/<video_id>/2_transcript/transcript.md`를 읽고, [`AGENTS.md`](AGENTS.md) 가이드대로 `output/<video_id>/3_translation/sentences.json`을 `[{en, ko}, ...]` 형태로 작성.
3. **Phase 3 (자동)** — 같은 `dub.sh` 명령을 다시 실행하면 `sentences.json`을 감지하고 이어서 진행: match_timing → synthesize → place → finalize.

영상 앞부분만 잘라서 더빙: `bash scripts/dub.sh <URL> 120` (앞 120초만).

보이스 바꾸기: `DUBYDUBY_VOICE=F3 bash scripts/dub.sh <URL>` (M1-M5, F1-F5 중 선택. 미리듣기는 [`samples/`](samples/)).

## 동작 흐름

```
YouTube URL
  │
  ▼ yt-dlp                       1_source/{video.mp4, audio.mp3}
  ▼ Soniox STT + 화자 분리        2_transcript/{tokens.json, transcript.md}
  │
  ▼ ─── 일시 정지: 에이전트가 sentences.json 작성 ───
  │       (Claude Code, Codex, Cursor… AGENTS.md + glossary.json 참고)
  │
  ▼ match_timing.py              3_translation/utterances.json
  ▼ analyze_speakers.py          피치(f0) → 성별 → 보이스 자동 매핑
  ▼ Supertonic ONNX              4_synth/utt-NNN.wav      (발화별 합성)
  ▼ place_timeline.py            5_intermediate/dub_clean.wav
  ▼ subtitle.py + ffmpeg libass  6_final/dubbed_video.mp4
```

발화마다 `atempo`를 1.0~1.6 범위로 따로 적용해서, 전체 타임라인을 늘이지 않고도 각 줄이 자기 자리에 맞도록 합니다.

## 왜 에이전트 기반인가

대부분의 더빙 도구는 특정 LLM 하나에 묶여 있습니다. dubyduby는 번역 단계를 바깥으로 빼서 다음을 가능하게 합니다.

- 프로젝트 컨텍스트·고유 용어집·말투를 이미 알고 있는 평소의 AI 에이전트를 그대로 활용
- 별도 API key 발급 불필요
- 번역 수정은 다음 메시지로 자연스럽게 — 처음부터 다시 돌릴 필요 없음

[`AGENTS.md`](AGENTS.md)가 번역 계약서입니다 — 자막체 톤 (`-어요`, `-입니다` 금지), 한글 음성 숫자 표기, 영문 브랜드 처리, 문장 경계 규칙. [`glossary.json`](glossary.json)은 STT 오인식 → 고유명사 매핑 (예: Soniox가 `Claude`를 `Cloth`로 받아쓰는 케이스를 번역 시점에 보정).

## 환경 요구사항

- macOS (arm64) 또는 Linux
- Python 3.12 (`uv` 권장 — `scripts/setup.sh`가 venv 자동 구성)
- `libass` 포함된 `ffmpeg` (macOS는 setup.sh가 필요시 `brew install ffmpeg-full` 자동 실행)
- [Soniox](https://soniox.com) 계정 — 월 200분 무료, 이후 유료. `.env`로 BYOK.
- transcript 읽고 구조화된 JSON 출력할 수 있는 AI 에이전트. Claude Code 기준으로 검증됐고, `AGENTS.md`를 따를 수 있는 에이전트면 무엇이든 OK.

LLM API key 불필요, GPU 불필요.

## 보이스

Supertonic 한국어 보이스 10종 — 남성 M1~M5, 여성 F1~F5. 사용 모델은 `supertonic-3` (다국어 multilingual, 44.1kHz).

선택 전에 [`samples/`](samples/)의 미리듣기 파일들로 비교해보세요. 화자가 둘 이상인 영상 (토크쇼, 인터뷰, 팟캐스트 등)은 피치(f0) 분석 (`scripts/analyze_speakers.py`)으로 성별을 자동 판별해서 보이스를 매핑합니다.

## 프로젝트 구조

```
dubyduby/
├── scripts/             # 파이프라인: setup, dub, transcribe, synthesize, place, subtitle, finalize
├── samples/             # 보이스 미리듣기 + 풀 데모 .mp4
├── output/              # 영상별 파이프라인 산출물 (gitignored)
├── AGENTS.md            # AI 에이전트용 번역 스타일 가이드 (← 톤 조정은 여기를 수정)
├── glossary.json        # STT 오인식 → 고유명사 + 한글 음역 레지스트리
├── ATTRIBUTIONS.md      # 외부 의존성 크레딧
├── LICENSE              # MIT
└── README.md
```

`CLAUDE.md`는 `AGENTS.md`로 가는 심볼릭 링크라서 Claude Code가 자동으로 인식합니다.

## 라이센스 및 크레딧

dubyduby 자체는 [MIT 라이센스](LICENSE)입니다. 외부 의존성 (Supertonic, Soniox, yt-dlp, Pretendard, ffmpeg, onnxruntime) 라이센스 및 재배포 시 주의사항은 [ATTRIBUTIONS.md](ATTRIBUTIONS.md)에 정리되어 있습니다.

감사:
- [Supertone Inc.](https://supertone.ai) — Supertonic TTS 엔진
- [Soniox](https://soniox.com) — STT + 화자 분리 API
- [orioncactus](https://github.com/orioncactus/pretendard) — Pretendard 폰트
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) 메인테이너
- [Andrej Karpathy](https://x.com/karpathy) — 데모 원본 영상

## 기여

이슈와 PR 환영합니다. 특히:
- 잘못 처리된 브랜드/고유명사를 `glossary.json`에 추가
- 피치 외에 다른 보이스 선택 휴리스틱
- 한국어 외 다른 타겟 언어 지원 (구조 자체는 언어 중립적 — AGENTS.md, glossary, 보이스 리스트만 바꾸면 됨)

이 위에 뭔가 만들어주시면 어트리뷰션 링크 걸어주시면 감사하겠지만, 강제는 아닙니다.
