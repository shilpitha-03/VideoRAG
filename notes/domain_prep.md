Domain Prep: Surgical Videos\n\nGoal: adapt VideoRAG pipeline to surgical clip data\nwith no audio, using phase/step annotations as text context.
Edits:
- caption.py-> segment_caption() -> "# query = f"The transcript of the current video:\n{segment_transcript}.\nNow provide a description (caption) of the video in English."
                query = f"Surgical context: {segment_transcript}.\nProvide a detailed caption of this surgical video clip. Describe the visible instruments, anatomical structures, surgical actions being performed, and any notable findings or complications visible in the frames.""
- prompt.py-> line33-100  switched for in domain examples
- asr.py -> completely changed to include 