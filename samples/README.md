# Samples

Two kinds of samples live in this folder:

1. **`demo-karpathy-5min.mp4`** — full end-to-end demo. A 5-minute excerpt of Andrej Karpathy's Claude Code talk, dubbed into Korean by dubyduby. Two-voice speaker separation (F1 host + M1 Karpathy), per-utterance placement, ASS subtitle burn-in. Best single-file demonstration of what the tool produces. Original content © Andrej Karpathy; included for demonstration only — see [../ATTRIBUTIONS.md](../ATTRIBUTIONS.md).
2. **Voice previews (`M1`-`M5`, `F1`-`F5`)** — short per-voice synthesized clips so you can pick `DUBYDUBY_VOICE` before dubbing.

## Voice previews

Supertonic ONNX 10 voices에서 같은 한국어 문장 합성. 사용자가 dub 시 voice 선택 참고.

**Sample text**:
> "여러분 안녕하세요. 이건 더비더비 한국어 음성 샘플인데요. Opus 사 점 칠 같은 영문 brand도 자연스럽게 처리됩니다."

(자막체 톤 + 영문 brand mix + 숫자 한글 표기 — 실제 dub guideline 패턴)

**Note**: brand name (`Opus`)은 영문 그대로, 숫자 (`4.7`)는 한글 표기 (`사 점 칠`)로. 한국어 voice가 영문+숫자 mix를 자연스럽게 phoneme switching 못해서, AGENTS.md 가이드라인에 명시.

## Voices

| Voice | Sample | Type |
|-------|--------|------|
| M1 | [M1.mp3](M1.mp3) | Male 1 |
| M2 | [M2.mp3](M2.mp3) | Male 2 |
| M3 | [M3.mp3](M3.mp3) | Male 3 |
| M4 | [M4.mp3](M4.mp3) | Male 4 |
| M5 | [M5.mp3](M5.mp3) | Male 5 |
| F1 | [F1.mp3](F1.mp3) | Female 1 |
| F2 | [F2.mp3](F2.mp3) | Female 2 |
| F3 | [F3.mp3](F3.mp3) | Female 3 |
| F4 | [F4.mp3](F4.mp3) | Female 4 |
| F5 | [F5.mp3](F5.mp3) | Female 5 |

GitHub raw url로 직접 stream 가능 — 클릭하면 브라우저 player에서 재생.

## Default

dubyduby의 default voice = **M1** (`dub.sh` 기본값).

영상별로 voice 바꾸려면 환경변수:
```bash
DUBYDUBY_VOICE=F3 ./scripts/dub.sh <URL>
```

## Generation

이 sample들은 Supertonic ONNX local TTS (`./models/`)에서 생성됨. License: OpenRAIL-M (Supertonic), 비상업 + 상업 모두 사용 가능 (`Supertone` attribution 권장).

CPU 합성 시간 ~1.6초/voice (M-series Mac). Free + local + offline.
