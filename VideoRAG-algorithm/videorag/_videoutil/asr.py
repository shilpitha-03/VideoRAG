import os
import torch
import logging
from tqdm import tqdm
from faster_whisper import WhisperModel
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
import re

NORMALIZATION_MAP = {
    # ---- multi-word / phrases FIRST (longest-match) ----
    "bullet ethmoid elis": "bulla ethmoidalis",
    "bula admoidalis": "bulla ethmoidalis",
    "ethelite bola": "ethmoid bulla",
    "ethmoid bola": "ethmoid bulla",
    "ethmoid bula": "ethmoid bulla",

    # ---- uncinate (structure) ----
    "unsinidate": "uncinate",
    "unsinidid": "uncinate",
    "unscernet": "uncinate",
    "unsnitnet": "uncinate",
    "unsignate": "uncinate",
    "unsinite": "uncinate",
    "unsinit": "uncinate",
    "unsinid": "uncinate",
    "unsunate": "uncinate",
    "unsonet": "uncinate",
    "unsnuck": "uncinate",
    "unsnut": "uncinate",
    "unsnit": "uncinate",
    "ancillet": "uncinate",
    "ancillate": "uncinate",

    # ---- uncinectomy (procedure) ----
    "unsonectomy": "uncinectomy",
    "unsteenectomy": "uncinectomy",
    "uncynecomy": "uncinectomy",

    # ---- ethmoidectomy (procedure) ----
    "ethymidectomy": "ethmoidectomy",
    "ethymodectomy": "ethmoidectomy",
    "ethomeidectomy": "ethmoidectomy",
    "ethmidectomy": "ethmoidectomy",
    "ethmidectomies": "ethmoidectomies",
    "ethymonectomy": "ethmoidectomy",
    "admoidectomy": "ethmoidectomy",

    # ---- ethmoid (structure / adjective) ----
    "ethymite": "ethmoid",
    "ethymoid": "ethmoid",
    "admoidally": "ethmoidally",
    "admoidal": "ethmoidal",
    "admoids": "ethmoids",
    "admoid": "ethmoid",

    # ---- antrostomy ----
    "introsomy": "antrostomy",
    "enthrostomy": "antrostomy",
    "anthrostomy": "antrostomy",
    "entrostomy": "antrostomy",

    # ---- sphenoid / sphenoidotomy ----
    "swiniodotomy": "sphenoidotomy",
    "sphenodomy": "sphenoidotomy",
    "phenodotomy": "sphenoidotomy",
    "spinoid": "sphenoid",

    # ---- agger nasi ----
    "agonasey": "agger nasi",
    "agonasee": "agger nasi",
    "agonazi": "agger nasi",
    "agronazi": "agger nasi",
    "agronasi": "agger nasi",
    "aganese": "agger nasi",

    # ---- lamina papyracea ----
    "paparatia": "papyracea",
    "papricia": "papyracea",

    # ---- kerrison ----
    "carrison": "kerrison",
    "carousins": "kerrisons",
    "carousin": "kerrison",
    "kerosens": "kerrison",
    "kerosene": "kerrison",
    "kerosen": "kerrison",
    "keros": "kerrison",

    # ---- blakesley ----
    "blakeslye": "blakesley",
    "blakstey": "blakesley",
    "blakely": "blakesley",

    # ---- instruments / misc unambiguous ----
    "blexuel": "blakesley",        # see note
    "microdebriada": "microdebrider",
    "microdebreeder": "microdebrider",
    "microdebreder": "microdebrider",
    "microdebred": "microdebrider",
    "jkuret": "j-curette",
    "curet": "curette",

    # ---- anatomy misc ----
    "infunditulum": "infundibulum",
    "manxilla": "maxilla",
    "baxillary": "maxillary",
    "osteum": "ostium",
    "basalumella": "basal lamella",
    "basalamella": "basal lamella",
    "supribular": "suprabullar",
    "superbulla": "suprabullar",
    "eocynophilic": "eosinophilic",
    "eosinephylic": "eosinophilic",
    "issinifilic": "eosinophilic",
    "rhinocinocytis": "rhinosinusitis",
    "rhinocinitis": "rhinosinusitis",
    "andoscopic": "endoscopic",
}

def normalize_transcript(text, nmap=NORMALIZATION_MAP):
    for mangled in sorted(nmap, key=len, reverse=True):
        text = re.sub(rf'\b{re.escape(mangled)}\b', nmap[mangled], text, flags=re.IGNORECASE)
    return text

def speech_to_text(video_name, working_dir, segment_index2name, audio_output_format):
    # model = WhisperModel("./faster-distil-whisper-large-v3")
    model = WhisperModel("./faster-distil-whisper-large-v3", device="cpu", compute_type="int8", cpu_threads=8)
    # model = WhisperModel("./faster-distil-whisper-large-v3", device="cuda", compute_type="float16")  # float16 avoids the int8 cuDNN ops that fail
    model.logger.setLevel(logging.WARNING)
    
    cache_path = os.path.join(working_dir, '_cache', video_name)
    
    transcripts = {}
    for index in tqdm(segment_index2name, desc=f"Speech Recognition {video_name}"):
        segment_name = segment_index2name[index]
        audio_file = os.path.join(cache_path, f"{segment_name}.{audio_output_format}")

        # if the audio file does not exist, skip it
        if not os.path.exists(audio_file):
            transcripts[index] = ""
            continue
        
        segments, info = model.transcribe(audio_file)
        result = ""
        for segment in segments:
            result += "[%.2fs -> %.2fs] %s\n" % (segment.start, segment.end, segment.text)
        transcripts[index] = normalize_transcript(result)
    return transcripts