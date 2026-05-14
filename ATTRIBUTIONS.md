# Attributions

dubyduby itself is MIT-licensed (see [LICENSE](LICENSE)). It depends on the following third-party projects, fetched by `scripts/setup.sh` or invoked as external services — none are redistributed in this repository.

## Runtime dependencies

| Project | Role | License | Distributed by dubyduby? |
|---|---|---|---|
| [Supertonic](https://pypi.org/project/supertonic/) | Korean TTS engine (ONNX) | OpenRAIL-M (commercial + non-commercial OK, attribution recommended) | No — `pip install supertonic` on first setup |
| [Soniox](https://soniox.com) | Speech-to-text API + speaker diarization | Commercial SaaS, BYOK | No — user supplies `SONIOX_API_KEY` |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | YouTube video/audio download | Unlicense (public domain) | No — binary downloaded by `setup.sh` to `binaries/yt-dlp` |
| [Pretendard](https://github.com/orioncactus/pretendard) | Korean subtitle font (Bold weight) | SIL Open Font License 1.1 | No — font extracted at setup time to `fonts/` |
| [ffmpeg / ffmpeg-full](https://ffmpeg.org/) | Audio/video processing, libass subtitle render | GPL-2.0+/LGPL components | No — system package (Homebrew `ffmpeg-full` on macOS, distro package on Linux) |
| [onnxruntime](https://github.com/microsoft/onnxruntime) | TTS model inference runtime | MIT | No — transitive dep of Supertonic |
| [numpy](https://numpy.org/) / [soundfile](https://github.com/bastibe/python-soundfile) | Audio I/O for synthesis | BSD-3-Clause / BSD-3-Clause | No — transitive deps |
| [uv](https://github.com/astral-sh/uv) | Python venv + dep install | Apache-2.0 / MIT (dual) | No — user-installed prerequisite |

## Notes for redistributors

If you fork dubyduby and ship a packaged build (rather than the source repo + setup.sh pattern), the following rules become your responsibility:

- **Pretendard (SIL OFL 1.1)** — Include the OFL text alongside the font file. Reserved Font Name handling applies if you rename the font.
- **ffmpeg-full** — Contains GPL components (e.g. `libx264`, some `--enable-gpl` filters). Bundling it makes your derivative work GPL. Many filter-only flows can use plain `ffmpeg` (LGPL).
- **yt-dlp (Unlicense)** — No constraints. Note that *using* yt-dlp to download copyrighted YouTube content has its own legal considerations independent of yt-dlp's license; this tool is intended for content you have rights to translate/dub.
- **Supertonic** — Check current license on its [PyPI page](https://pypi.org/project/supertonic/) before redistributing model weights or binaries.

## Fixture / sample content

`samples/demo-karpathy-5min.mp4` includes a 5-minute excerpt from Andrej Karpathy's public talk on Claude Code, dubbed by dubyduby for demonstration purposes. Original content © Andrej Karpathy. This sample is included under fair-use / academic-demonstration grounds — if the original creator objects, open an issue and it will be removed.

Voice samples in `samples/{M1..M5,F1..F5}.mp3` are short clips synthesized by Supertonic from short neutral phrases, included as voice previews for the user.

## Reporting attribution issues

If you believe a dependency above is misattributed, or that something we use should be credited and isn't, please open an issue. Attribution corrections are merged quickly.
