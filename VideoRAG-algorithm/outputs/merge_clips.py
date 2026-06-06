from moviepy import VideoFileClip, concatenate_videoclips
from pathlib import Path
import csv
import re


VIDEO_FOLDER = Path(r"C:/Users/Shilpitha/Desktop/SETIENT/Surgical data/mar_12")

OUTPUT_VIDEO = VIDEO_FOLDER / "final_video.mp4"
OUTPUT_CSV = VIDEO_FOLDER / "annotations.csv"

# --------------------------------------------------

def parse_filename(filename):

    stem = Path(filename).stem

    match = re.match(r"(\d+)__(.+?)__(.+)", stem)

    if not match:
        raise ValueError(f"Bad filename: {filename}")

    number = int(match.group(1))
    phase = match.group(2)
    step = match.group(3)

    return number, phase, step

# --------------------------------------------------

video_files = sorted(
    [f for f in VIDEO_FOLDER.iterdir() if f.suffix == ".mp4"],
    key=lambda x: parse_filename(x.name)[0]
)

clips = []

running_time = 0.0

with open(OUTPUT_CSV, "w", newline="") as csvfile:

    writer = csv.writer(csvfile)

    writer.writerow([
        "clip_index",
        "start_time",
        "end_time",
        "phase",
        "step",
        "source_file"
    ])

    for idx, video_path in enumerate(video_files):

        number, phase, step = parse_filename(video_path.name)

        clip = VideoFileClip(str(video_path))

        start_time = running_time
        end_time = running_time + clip.duration

        writer.writerow([
            idx,
            round(start_time, 3),
            round(end_time, 3),
            phase,
            step,
            video_path.name
        ])

        running_time = end_time

        clips.append(clip)

final = concatenate_videoclips(clips)

final.write_videofile(
    str(OUTPUT_VIDEO),
    codec="libx264"
)


# #!/usr/bin/env python3

# import csv
# import json
# import re
# import subprocess
# from pathlib import Path

# # ============================================================
# # CONFIG
# # ============================================================

# VIDEO_FOLDER = Path(r"C:/Users/Shilpitha/Desktop/SETIENT/Surgical data/jan_15")

# # OUTPUT_VIDEO = "final_video.mp4"
# # OUTPUT_CSV = "annotations.csv"
# OUTPUT_VIDEO = VIDEO_FOLDER / "final_video.mp4"
# OUTPUT_CSV = VIDEO_FOLDER / "annotations.csv"

# VIDEO_EXTENSIONS = [".mp4", ".mov", ".avi", ".mkv"]

# # ============================================================
# # HELPERS
# # ============================================================

# def parse_filename(filename):
#     """
#     Expected format:
#     1__PhaseName__StepName.mp4
#     """

#     stem = Path(filename).stem

#     match = re.match(r"(\d+)__(.+?)__(.+)", stem)

#     if not match:
#         raise ValueError(f"Invalid filename format: {filename}")

#     number = int(match.group(1))
#     phase = match.group(2).replace("_", " ")
#     step = match.group(3).replace("_", " ")

#     return number, phase, step


# def get_duration(video_path):
#     """
#     Get video duration using ffprobe.
#     """

#     cmd = [
#         "ffprobe",
#         "-v", "error",
#         "-show_entries", "format=duration",
#         "-of", "json",
#         str(video_path)
#     ]

#     result = subprocess.run(
#         cmd,
#         capture_output=True,
#         text=True,
#         check=True
#     )

#     data = json.loads(result.stdout)

#     return float(data["format"]["duration"])


# # ============================================================
# # FIND + SORT CLIPS
# # ============================================================

# video_files = [
#     f for f in VIDEO_FOLDER.iterdir()
#     if f.suffix.lower() in VIDEO_EXTENSIONS
# ]

# video_files.sort(key=lambda x: parse_filename(x.name)[0])

# # ============================================================
# # BUILD CSV + CONCAT LIST
# # ============================================================

# running_time = 0.0

# concat_file = VIDEO_FOLDER / "concat_list.txt"

# with open(OUTPUT_CSV, "w", newline="") as csvfile, \
#      open(concat_file, "w") as concat:

#     writer = csv.writer(csvfile)

#     writer.writerow([
#         "clip_index",
#         "start_time",
#         "end_time",
#         "phase",
#         "step",
#         "source_file"
#     ])

#     for idx, video_path in enumerate(video_files):

#         number, phase, step = parse_filename(video_path.name)

#         duration = get_duration(video_path)

#         start_time = running_time
#         end_time = running_time + duration

#         # CSV row
#         writer.writerow([
#             idx,
#             round(start_time, 3),
#             round(end_time, 3),
#             phase,
#             step,
#             video_path.name
#         ])

#         # ffmpeg concat list
#         concat.write(f"file '{video_path.resolve()}'\n")

#         running_time = end_time

#         print(
#             f"[{idx}] "
#             f"{phase} | {step} | "
#             f"{duration:.2f}s"
#         )

# # ============================================================
# # MERGE VIDEOS
# # ============================================================

# ffmpeg_cmd = [
#     "ffmpeg",
#     "-y",
#     "-f", "concat",
#     "-safe", "0",
#     "-i", str(concat_file),
#     "-c:v", "libx264",
#     "-preset", "medium",
#     "-crf", "23",
#     "-pix_fmt", "yuv420p",
#     "-an",
#     OUTPUT_VIDEO
# ]

# print("\nMerging videos...")

# subprocess.run(ffmpeg_cmd, check=True)

# print("\nDone.")
# print(f"Video: {OUTPUT_VIDEO}")
# print(f"CSV:   {OUTPUT_CSV}")

# # cleanup
# concat_file.unlink()