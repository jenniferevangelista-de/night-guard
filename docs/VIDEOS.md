# How the Night Guard videos were made

Two videos, both narrated by Snoozy, the lazy night watchman (a kawaii sloth). Every chat shown is fictional.

| Video | What it is | Length |
|---|---|---|
| Film (https://youtu.be/DFyBdn8d7xU) | Paper-style animation: the problem, the guard, what the kid and the parents get, the tools | 2:30 |
| Tour (https://youtu.be/__upiNIIlt0) | A real recording of the local app (Gemma 4 through Ollama), every feature, narrated | 3:11 |

Both exist in English and Portuguese. The English versions are the ones published.

## Pipeline

```
FILM                                          TOUR
script_<lang>.py  narration + timeline        wt_script.py   narration + timeline
        |                                             |
ng_film_<lang>.py  every scene, drawn         wt_record.py   records the real app
        |          frame by frame (Pillow)            |      (Chrome screencast)
ng_sloth.py   Snoozy, mouth follows voice     wt_build.py    paper frame, Snoozy,
        |                                             |      titles and subtitles
ng_audio_<lang>.py  voice + music + effects           |
        |                                             |
ng_render_<lang>.py  frames -> ffmpeg -> mp4  <-------+  (same ffmpeg finishing)
```

## Tools and what each one does

| Tool | Used for |
|---|---|
| Python 3.12 + Pillow | Draws every frame of the film and the tour overlay (1920x1080, 24 fps) |
| NumPy + soundfile | Mixes the audio and synthesizes the original dramatic music bed and the sound effects |
| ffmpeg | Encodes H.264 + AAC, concatenates segments, loudness-normalizes to -14 LUFS, speeds the film up |
| edge-tts | Narration voices: `en-US-BrianMultilingualNeural` (English) and `pt-BR-AntonioNeural` (Portuguese) |
| ElevenLabs | The real spoken warnings of the app (Sarah voice, `web/audio/`), played inside the film at the alert moment |
| Playwright + system Chrome | Drives the real app for the tour, with a visible cursor |
| Chrome DevTools Protocol | `Page.startScreencast` delivers the frames of the tour recording |
| Funkorama by Kevin MacLeod | Happy music once the guard appears (CC BY 4.0, https://incompetech.com) |

## The film, file by file (`video/`)

| File | What it does |
|---|---|
| `script_en.py`, `script_pt.py` | The narration text per scene. Generates one MP3 per line with edge-tts and `timeline_<lang>.json` with the start and length of every scene |
| `ng_film.py`, `ng_film_en.py`, `ng_film_pt.py` | The scenes. `render(t)` returns the image for second `t`: night room, statistics, the platforms, the alert, the hero ranks, the family view, and 10 tool cards that appear when the narrator says each tool name |
| `ng_sloth.py` | Snoozy: round body, thick outline, glossy eyes, watchman cap with a moon badge. The mouth opens with the loudness of the narration, he blinks slowly and yawns. Moods: angry in the sad part, happy once the guard arrives |
| `ng_audio_en.py`, `ng_audio_pt.py` | The mix: original drama bed (A minor, Am-F-Dm-E, string pad, low piano, heartbeat) until Night Guard appears, then a 2 s crossfade into Funkorama; the narrator; the app's own spoken warning and the "tell your family" line; alarm and thud effects |
| `ng_render_en.py`, `ng_render_pt.py` | Renders frames in 3 processes, pipes them as raw video into ffmpeg together with the mix, normalizes loudness, then a final pass makes picture and sound 20% faster (`setpts` and `atempo`, so voices keep their pitch) |

Run (from the repository root):

```
python video/script_en.py          # narration + timeline
python video/ng_film_en.py 5 20 40 # optional: preview frames at 5 s, 20 s, 40 s
python video/ng_audio_en.py        # mix
python video/ng_render_en.py       # final video/night_guard_film_en.mp4
```

## The tour, file by file (`video/walkthrough/`)

| File | What it does |
|---|---|
| `wt_script.py` | Narration for each feature segment (edge-tts, +10% rate) and `narr_<lang>.json` |
| `wt_record.py` | Opens the local app (already running; address in `NG_BASE`) in headless Chrome (1280x800), shows a fake cursor, clicks through every feature with fictional chats, and records the screen with the DevTools screencast. It also hooks the page's audio so it knows when the app speaks a warning. Writes `events_<lang>.json` and one screenshot per feature in `docs/screens/<lang>/` |
| `wt_build.py` | Puts the recording in a paper frame, Snoozy beside it, feature titles and subtitles. When the app speaks a warning, the picture holds so the warning plays in full before the narrator continues. The end is padded so the last line is never cut |

Run: `python video/walkthrough/wt_script.py en`, then `wt_record.py en`, then `wt_build.py en`. The model failure shown in the last segment is simulated by blocking the request on purpose.

## Facts shown in the film

The figures come from the sources cited in the article: more than 50,000 sextortion reports to NCMEC in 2025 (137 a day, about one every ten minutes) and the Swansea University study (first sexual request after 18 minutes).

## What is not in this repository

- Rendered videos and the mixed audio (`*.mp4`, `*.wav`) are ignored by git. The YouTube links above are the published copies.
- The scene scripts import a small drawing helper (`palito`: paper texture, stick figures, hand-drawn lines) and read `Funkorama.mp3` from the author's other project folders. They document how the videos were made; they are not meant to run from a fresh clone.
- Fonts come from Windows (Segoe UI, Impact).

## Music credit

"Funkorama" by Kevin MacLeod (incompetech.com), licensed under Creative Commons: By Attribution 4.0 (https://creativecommons.org/licenses/by/4.0/). The dramatic opening music is original and generated in code.
