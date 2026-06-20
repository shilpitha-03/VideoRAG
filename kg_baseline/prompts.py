"""
prompts.py — the extraction specification for the KG baseline.

This file holds STRINGS, not logic. It defines:
  - the entity types the graph is allowed to use
  - the instruction the model follows (system message)
  - the few-shot examples (drafted from real Mar_05 windows)
  - a small helper that assembles the final prompt for one chunk

extract.py imports build_extraction_prompt() and feeds it each chunk.
"""

# ---------------------------------------------------------------------------
# DECISION 1: entity types (locked).
# surgical_step stays defined to match run-002, but is expected near-empty
# because the proxy captions never name steps.
# ---------------------------------------------------------------------------
ENTITY_TYPES = ["anatomy", "instrument", "anatomical_landmark", "procedure", "surgical_step"]


# ---------------------------------------------------------------------------
# DECISION 2 + 3: the instruction. This is the system message.
# It encodes the canonicalization rule (offloaded to the model + op-note,
# no hand-authored vocabulary) and the action-as-edge enforcement
# (the Level-3 probe — actions/effects go in relation descriptions, never nodes).
# ---------------------------------------------------------------------------
EXTRACTION_INSTRUCTION = f"""You are a clinical expert in Functional Endoscopic Sinus Surgery (FESS).
You will be given a chunk of text describing several short clips from a FESS video.
Extract a knowledge graph of ENTITIES and RELATIONS from the text.

ENTITY TYPES — use ONLY these types:
{", ".join(ENTITY_TYPES)}

WHAT IS AN ENTITY:
- A concrete surgical object: an instrument, an anatomical structure, an
  anatomical landmark, or a named procedure.
- Do NOT create entities for actions, manipulations, movements, or effects
  (e.g. "perforation", "bleeding", "separation", "pressure"). These are NOT nodes.
- Do NOT create entities for vague phrases ("tissue", "underlying structures",
  "the area", "the field"). Only concrete, named structures.

WHAT IS A RELATION:
- A relation connects two entities (usually an instrument and an anatomical
  structure it acts on).
- Put the ACTION and its EFFECT in the relation's description, with the verb
  (e.g. "perforated", "grasped", "disarticulated") and what resulted
  (e.g. "causing slight bleeding", "exposing the cavity beneath").
- The relation description is free text — write what the instrument did to the
  structure, in past tense.

CANONICAL NAMING (critical — entities are merged by exact name match):
- Use the full clinical name of the structure or instrument as a FESS expert
  would write it in an operative note.
- lowercase, singular, no leading articles ("the", "a").
- Expand vague descriptive phrasing to the named structure
  (e.g. "uncinate tissue" -> "uncinate process").
- Be consistent: the SAME structure must get the SAME name every time.

OUTPUT FORMAT — return a single valid JSON object, nothing else (no preamble,
no markdown fences):
{{
  "entities": [
    {{"name": "<canonical name>", "type": "<one of the entity types>", "description": "<what this entity is>"}}
  ],
  "relations": [
    {{"source": "<entity name>", "target": "<entity name>", "description": "<what the source did to the target>"}}
  ]
}}
Every name used in a relation's "source" or "target" MUST also appear in "entities".
The "description" of an entity should define what it IS in general, not narrate one clip."""


# ---------------------------------------------------------------------------
# DECISION 4: the few-shots. Drafted from real Mar_05 windows.
#   A = window 40  (rich single instrument-action-anatomy)
#   B = window 18  (multi-step manipulation, canonicalization of "uncinate tissue")
#   C = window 10  (generic boilerplate -> minimal extraction, teaches restraint)
# Window 84 was deliberately EXCLUDED: it contains a one-off mangle ("1-app"),
# which is good as a test case but a bad teaching example.
# ---------------------------------------------------------------------------
FEW_SHOTS = """EXAMPLE 1
INPUT:
[w40] The sickle knife was used to perforate the bulla lamella, with the instrument moving medially and making contact with the tissue. The tissue separated and bled slightly, creating a deeper cavity and revealing more of the nasal anatomy beneath as the bulla was entered.
OUTPUT:
{
  "entities": [
    {"name": "sickle knife", "type": "instrument", "description": "Sharp endoscopic knife used to perforate and incise tissue."},
    {"name": "bulla lamella", "type": "anatomy", "description": "Ethmoid air-cell wall; perforated and entered during dissection."}
  ],
  "relations": [
    {"source": "sickle knife", "target": "bulla lamella", "description": "perforated the bulla lamella, moving medially to enter it and open a deeper cavity, causing slight bleeding"}
  ]
}

EXAMPLE 2
INPUT:
[w18] Microdebrider forceps were introduced to grasp and slightly move a piece of uncinate tissue. The instrument applied gentle pressure, causing the tissue to fold and separate slightly as it was moved medially toward the center of the nasal cavity.
OUTPUT:
{
  "entities": [
    {"name": "microdebrider forceps", "type": "instrument", "description": "Powered cutting-and-suction instrument with a grasping forceps tip, used to grasp, move, and resect tissue."},
    {"name": "uncinate process", "type": "anatomy", "description": "Thin curved bone of the lateral nasal wall; grasped and mobilized during uncinectomy."}
  ],
  "relations": [
    {"source": "microdebrider forceps", "target": "uncinate process", "description": "grasped and moved the uncinate process medially, applying gentle pressure to fold and separate the tissue"}
  ]
}

EXAMPLE 3
INPUT:
[w10] The endoscope was maneuvered within the nasal cavity, moving slightly laterally and advancing deeper into the nasal passage. The tip gently pressed against the tissue, causing slight separation and folding of the nasal mucosa, revealing more of the underlying structures.
OUTPUT:
{
  "entities": [
    {"name": "endoscope", "type": "instrument", "description": "Rigid endoscope providing the intranasal visual field; used to inspect and navigate the cavity."},
    {"name": "nasal cavity", "type": "anatomy", "description": "The intranasal space navigated and inspected during the procedure."}
  ],
  "relations": [
    {"source": "endoscope", "target": "nasal cavity", "description": "maneuvered within the nasal cavity, advancing deeper and laterally to inspect the field"}
  ]
}"""


# ---------------------------------------------------------------------------
# Helper: assemble the per-chunk user message.
# The instruction is the SYSTEM message (passed separately in extract.py);
# this builds the USER message = few-shots + the actual chunk to process.
# ---------------------------------------------------------------------------
def build_extraction_prompt(chunk_text):
    return f"""{FEW_SHOTS}

NOW EXTRACT FROM THIS INPUT:
{chunk_text}
OUTPUT:"""