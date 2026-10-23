"""Render the Night Guard film: frames (3 processes) piped to ffmpeg with the mix, loudness -14 LUFS."""
import subprocess
import time
from multiprocessing import Pool
from pathlib import Path

from ng_film_pt import DUR, FPS, H, W, render

HERE = Path(__file__).resolve().parent


def job(i): return render(i / FPS).tobytes()


if __name__ == "__main__":
    n = int(DUR * FPS); t0 = time.time()
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                           "-i", str(HERE / "mix_filme_pt.wav"), "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                           "-pix_fmt", "yuv420p", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "192k", "-shortest",
                           str(HERE / "_normal_night_guard_filme_pt.mp4")], stdin=subprocess.PIPE)
    with Pool(3) as p:
        for b in p.imap(job, range(n), chunksize=8): ff.stdin.write(b)
    ff.stdin.close(); ff.wait()
    # 20% faster (requested): picture and sound together, voices keep their pitch
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(HERE / "_normal_night_guard_filme_pt.mp4"), "-filter_complex",
                    "[0:v]setpts=PTS/1.2[v];[0:a]atempo=1.2,loudnorm=I=-14:TP=-1.5:LRA=11[a]", "-map", "[v]", "-map", "[a]", "-r", str(FPS),
                    "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", str(HERE / "night_guard_filme_pt.mp4")], check=True)
    (HERE / "_normal_night_guard_filme_pt.mp4").unlink()
    print("done", round(time.time() - t0), "s")
