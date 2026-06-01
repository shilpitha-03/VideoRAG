"""
Reference:
 - Prompts are from [graphrag](https://github.com/microsoft/graphrag)
"""

GRAPH_FIELD_SEP = "<SEP>"
PROMPTS = {}

PROMPTS[
    "entity_extraction"
] = """-Goal-
Given a text document that is potentially relevant to this activity and a list of entity types, identify all entities of those types from the text and all relationships among the identified entities.

-Steps-
1. Identify all entities. For each identified entity, extract the following information:
- entity_name: Name of the entity, capitalized
- entity_type: One of the following types: [{entity_types}]
- IMPORTANT (domain guidance for surgical video transcripts):
  - This text is ASR-transcribed surgical narration and contains misspelled/mangled medical terms. Normalize each entity_name to its correct canonical surgical term. For example: "unsinit"/"unsinate"/"unscinate"/"uncernet"/"antonet" → "uncinate process"; "carrison"/"kerosene"/"keros" (when referring to the punch) → "Kerrison punch"; "ethymidectomy"/"admoidectomy" → "ethmoidectomy"; "lamina papricia"/"paparatia" → "lamina papyracea"; "agonazi"/"agronazi"/"aganese" → "agger nasi".
  - Use entity_type "anatomy" for tissues/structures being operated on (e.g. middle turbinate, maxillary sinus, ethmoid bulla).
  - Use entity_type "anatomical_landmark" for structures used as navigation boundaries or limits of dissection (e.g. skull base, lamina papyracea, basal lamella, maxillary line).
  - Use entity_type "instrument" for surgical tools (e.g. backbiter, microdebrider, Kerrison punch, ball probe, Blakesley forceps).
  - Use entity_type "procedure" for named operations (e.g. FESS, uncinectomy, maxillary antrostomy, anterior ethmoidectomy, sphenoidotomy, frontal sinusotomy).
  - Use entity_type "surgical_step" for granular intraoperative actions (e.g. reflecting the uncinate, fracturing the bulla forward, raising the axilla, widening the ostium). When a term is both a named operation and a step, prefer "procedure".
  - Use entity_type "pathology" for disease findings (e.g. chronic rhinosinusitis, eosinophilic mucin, polyps, septal spur). These are rare but clinically important — extract them whenever present.
- entity_description: Comprehensive description of the entity's attributes and activities
Format each entity as ("entity"{tuple_delimiter}<entity_name>{tuple_delimiter}<entity_type>{tuple_delimiter}<entity_description>

2. From the entities identified in step 1, identify all pairs of (source_entity, target_entity) that are *clearly related* to each other.
For each pair of related entities, extract the following information:
- source_entity: name of the source entity, as identified in step 1
- target_entity: name of the target entity, as identified in step 1
- relationship_description: explanation as to why you think the source entity and the target entity are related to each other
- relationship_strength: a numeric score indicating strength of the relationship between the source entity and target entity
 Format each relationship as ("relationship"{tuple_delimiter}<source_entity>{tuple_delimiter}<target_entity>{tuple_delimiter}<relationship_description>{tuple_delimiter}<relationship_strength>)

3. Return output in English as a single list of all the entities and relationships identified in steps 1 and 2. Use **{record_delimiter}** as the list delimiter.

4. When finished, output {completion_delimiter}

######################
-Examples-
######################
Example 1:

Entity_types: [anatomy, instrument, procedure, surgical_step, anatomical_landmark, pathology]
Text:
A backbiter is then placed in the maxillary oss at the inferior aspect of the unsinit and is used to resect the inferior aspect.
################
Output:
("entity"{tuple_delimiter}"backbiter"{tuple_delimiter}"instrument"{tuple_delimiter}"The backbiter is a surgical instrument introduced into the maxillary ostium and used to resect the inferior aspect of the uncinate process."){record_delimiter}
("entity"{tuple_delimiter}"maxillary ostium"{tuple_delimiter}"anatomy"{tuple_delimiter}"The maxillary ostium is the natural opening of the maxillary sinus and serves as the placement site for the backbiter."){record_delimiter}
("entity"{tuple_delimiter}"uncinate process"{tuple_delimiter}"anatomy"{tuple_delimiter}"The uncinate process is a thin bony structure of the lateral nasal wall whose inferior aspect is being resected in this step."){record_delimiter}
("entity"{tuple_delimiter}"resection of inferior uncinate"{tuple_delimiter}"surgical_step"{tuple_delimiter}"The intraoperative action of resecting the inferior aspect of the uncinate process with a backbiter."){record_delimiter}
("relationship"{tuple_delimiter}"backbiter"{tuple_delimiter}"uncinate process"{tuple_delimiter}"The backbiter is the instrument used to resect the inferior aspect of the uncinate process."{tuple_delimiter}9){record_delimiter}
("relationship"{tuple_delimiter}"backbiter"{tuple_delimiter}"maxillary ostium"{tuple_delimiter}"The backbiter is placed at the maxillary ostium prior to performing the resection."{tuple_delimiter}7){completion_delimiter}
#############################
Example 2:

Entity_types: [anatomy, instrument, procedure, surgical_step, anatomical_landmark, pathology]
Text:
a complete fess, which includes a maxillary introsomy, anterior ethymodectomy, posterior ethymonectomy, sphenodomy, and frontal sinusotomy.
################
Output:
("entity"{tuple_delimiter}"FESS"{tuple_delimiter}"procedure"{tuple_delimiter}"FESS (Functional Endoscopic Sinus Surgery) is the comprehensive operation composed of several sub-procedures addressing the paranasal sinuses."){record_delimiter}
("entity"{tuple_delimiter}"maxillary antrostomy"{tuple_delimiter}"procedure"{tuple_delimiter}"Maxillary antrostomy is the surgical opening of the maxillary sinus and is one of the component sub-procedures of a complete FESS."){record_delimiter}
("entity"{tuple_delimiter}"anterior ethmoidectomy"{tuple_delimiter}"procedure"{tuple_delimiter}"Anterior ethmoidectomy is the surgical removal of the anterior ethmoid air cells and is one of the component sub-procedures of a complete FESS."){record_delimiter}
("entity"{tuple_delimiter}"posterior ethmoidectomy"{tuple_delimiter}"procedure"{tuple_delimiter}"Posterior ethmoidectomy is the surgical removal of the posterior ethmoid air cells and is one of the component sub-procedures of a complete FESS."){record_delimiter}
("entity"{tuple_delimiter}"sphenoidotomy"{tuple_delimiter}"procedure"{tuple_delimiter}"Sphenoidotomy is the surgical opening of the sphenoid sinus and is one of the component sub-procedures of a complete FESS."){record_delimiter}
("entity"{tuple_delimiter}"frontal sinusotomy"{tuple_delimiter}"procedure"{tuple_delimiter}"Frontal sinusotomy is the surgical opening of the frontal sinus and is one of the component sub-procedures of a complete FESS."){record_delimiter}
("relationship"{tuple_delimiter}"maxillary antrostomy"{tuple_delimiter}"FESS"{tuple_delimiter}"Maxillary antrostomy is a component sub-procedure of a complete FESS."{tuple_delimiter}9){record_delimiter}
("relationship"{tuple_delimiter}"anterior ethmoidectomy"{tuple_delimiter}"FESS"{tuple_delimiter}"Anterior ethmoidectomy is a component sub-procedure of a complete FESS."{tuple_delimiter}9){record_delimiter}
("relationship"{tuple_delimiter}"posterior ethmoidectomy"{tuple_delimiter}"FESS"{tuple_delimiter}"Posterior ethmoidectomy is a component sub-procedure of a complete FESS."{tuple_delimiter}9){record_delimiter}
("relationship"{tuple_delimiter}"sphenoidotomy"{tuple_delimiter}"FESS"{tuple_delimiter}"Sphenoidotomy is a component sub-procedure of a complete FESS."{tuple_delimiter}9){record_delimiter}
("relationship"{tuple_delimiter}"frontal sinusotomy"{tuple_delimiter}"FESS"{tuple_delimiter}"Frontal sinusotomy is a component sub-procedure of a complete FESS."{tuple_delimiter}9){completion_delimiter}
#############################
Example 3:

Entity_types: [anatomy, instrument, procedure, surgical_step, anatomical_landmark, pathology]
Text:
one can see the lamina papricia laterally, which is the medial wall of the orbit, and the skull base superiorly. It is important not to violate either structure as they are the borders of your dissection.
################
Output:
("entity"{tuple_delimiter}"lamina papyracea"{tuple_delimiter}"anatomical_landmark"{tuple_delimiter}"The lamina papyracea is a thin bony plate seen laterally that forms the medial wall of the orbit and serves as a lateral boundary of the dissection."){record_delimiter}
("entity"{tuple_delimiter}"skull base"{tuple_delimiter}"anatomical_landmark"{tuple_delimiter}"The skull base is the superior boundary of the dissection whose integrity must not be violated."){record_delimiter}
("entity"{tuple_delimiter}"medial orbital wall"{tuple_delimiter}"anatomy"{tuple_delimiter}"The medial orbital wall is the anatomic structure separating the orbit from the ethmoid sinus and is formed by the lamina papyracea."){record_delimiter}
("relationship"{tuple_delimiter}"lamina papyracea"{tuple_delimiter}"skull base"{tuple_delimiter}"The lamina papyracea and skull base are both borders of the dissection that must not be violated."{tuple_delimiter}8){record_delimiter}
("relationship"{tuple_delimiter}"lamina papyracea"{tuple_delimiter}"medial orbital wall"{tuple_delimiter}"The lamina papyracea forms the medial wall of the orbit."{tuple_delimiter}9){completion_delimiter}
#############################
Example 4:

Entity_types: [anatomy, instrument, procedure, surgical_step, anatomical_landmark, pathology]
Text:
Once we remove that with the Housmans, we're able to use an olive tip sucker and you can see all that eocynophilic mucin in the frontal sinus.
################
Output:
("entity"{tuple_delimiter}"Housman's punch"{tuple_delimiter}"instrument"{tuple_delimiter}"Housman's punch is a surgical instrument used to remove tissue prior to suctioning the surgical field."){record_delimiter}
("entity"{tuple_delimiter}"olive tip sucker"{tuple_delimiter}"instrument"{tuple_delimiter}"The olive tip sucker is a suction instrument used to clear secretions and pathologic material from the surgical field."){record_delimiter}
("entity"{tuple_delimiter}"eosinophilic mucin"{tuple_delimiter}"pathology"{tuple_delimiter}"Eosinophilic mucin is a thick eosinophil-laden secretion found within the frontal sinus and characteristic of certain inflammatory sinus diseases."){record_delimiter}
("entity"{tuple_delimiter}"frontal sinus"{tuple_delimiter}"anatomy"{tuple_delimiter}"The frontal sinus is the paranasal sinus located in the frontal bone, here containing pathologic eosinophilic mucin."){record_delimiter}
("relationship"{tuple_delimiter}"olive tip sucker"{tuple_delimiter}"eosinophilic mucin"{tuple_delimiter}"The olive tip sucker is used to remove the eosinophilic mucin from the surgical field."{tuple_delimiter}8){record_delimiter}
("relationship"{tuple_delimiter}"eosinophilic mucin"{tuple_delimiter}"frontal sinus"{tuple_delimiter}"The eosinophilic mucin is located within the frontal sinus."{tuple_delimiter}7){completion_delimiter}
#############################
Example 5:

Entity_types: [anatomy, instrument, procedure, surgical_step, anatomical_landmark, pathology]
Text:
Next, a backbiter is used to bring the unsteenectomy to its anterior limit. The reflected unsinit is removed with an upbiting kerosene.
################
Output:
("entity"{tuple_delimiter}"backbiter"{tuple_delimiter}"instrument"{tuple_delimiter}"The backbiter is a surgical instrument used here to advance the uncinectomy to its anterior limit."){record_delimiter}
("entity"{tuple_delimiter}"uncinectomy"{tuple_delimiter}"procedure"{tuple_delimiter}"Uncinectomy is the surgical removal of the uncinate process, here advanced to its anterior limit with a backbiter."){record_delimiter}
("entity"{tuple_delimiter}"uncinate process"{tuple_delimiter}"anatomy"{tuple_delimiter}"The uncinate process is the thin bony structure being removed; the reflected remnant is taken with an upbiting Kerrison punch."){record_delimiter}
("entity"{tuple_delimiter}"Kerrison punch"{tuple_delimiter}"instrument"{tuple_delimiter}"The Kerrison punch is a bone-biting instrument used in an upbiting configuration to remove the reflected uncinate process."){record_delimiter}
("entity"{tuple_delimiter}"removal of reflected uncinate"{tuple_delimiter}"surgical_step"{tuple_delimiter}"The intraoperative step of removing the previously reflected uncinate process using a Kerrison punch."){record_delimiter}
("relationship"{tuple_delimiter}"backbiter"{tuple_delimiter}"uncinectomy"{tuple_delimiter}"The backbiter is used to advance the uncinectomy to its anterior limit."{tuple_delimiter}9){record_delimiter}
("relationship"{tuple_delimiter}"Kerrison punch"{tuple_delimiter}"uncinate process"{tuple_delimiter}"The Kerrison punch removes the reflected uncinate process."{tuple_delimiter}8){completion_delimiter}
#############################
-Real Data-
######################
Entity_types: {entity_types}
Text: {input_text}
######################
Output:
"""

PROMPTS[
    "summarize_entity_descriptions"
] = """You are a helpful assistant responsible for generating a comprehensive summary of the data provided below.
Given one or two entities, and a list of descriptions, all related to the same entity or group of entities.
Please concatenate all of these into a single, comprehensive description. Make sure to include information collected from all the descriptions.
If the provided descriptions are contradictory, please resolve the contradictions and provide a single, coherent summary.
Make sure it is written in third person, and include the entity names so we the have full context.

#######
-Data-
Entities: {entity_name}
Description List: {description_list}
#######
Output:
"""

PROMPTS[
    "entiti_continue_extraction"
] = """MANY entities were missed in the last extraction.  Add them below using the same format:
"""

PROMPTS[
    "entiti_if_loop_extraction"
] = """It appears some entities may have still been missed.  Answer YES | NO if there are still entities that need to be added.
"""

PROMPTS["DEFAULT_ENTITY_TYPES"] = ["anatomy", "instrument", "procedure", "surgical_step", "anatomical_landmark", "pathology"]
PROMPTS["DEFAULT_TUPLE_DELIMITER"] = "<|>"
PROMPTS["DEFAULT_RECORD_DELIMITER"] = "##"
PROMPTS["DEFAULT_COMPLETION_DELIMITER"] = "<|COMPLETE|>"
PROMPTS["fail_response"] = "Sorry, I'm not able to provide an answer to that question."
PROMPTS["process_tickers"] = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
PROMPTS["default_text_separator"] = [
    # Paragraph separators
    "\n\n",
    "\r\n\r\n",
    # Line breaks
    "\n",
    "\r\n",
    # Sentence ending punctuation
    "。",  # Chinese period
    "．",  # Full-width dot
    ".",  # English period
    "！",  # Chinese exclamation mark
    "!",  # English exclamation mark
    "？",  # Chinese question mark
    "?",  # English question mark
    # Whitespace characters
    " ",  # Space
    "\t",  # Tab
    "\u3000",  # Full-width space
    # Special characters
    "\u200b",  # Zero-width space (used in some Asian languages)
]


PROMPTS[
    "naive_rag_response"
] = """---Role---

You are a helpful assistant responding to a query with retrieved knowledge.

---Goal---

Generate a response of the target length and format that responds to the user's question with relevant general knowledge.
Summarize useful and relevant information from the input data tables, suitable for the specified response length and format.
If you don't know the answer or if the provided knowledge do not contain sufficient information to provide an answer, just say so. Do not make anything up.
Do not include information where the supporting evidence for it is not provided.

---Target response length and format---

{response_type}

---Data tables---

{content_data}

---Goal---

Generate a response of the target length and format that responds to the user's question with relevant general knowledge.
Summarize useful and relevant information from the input data tables appropriate for the response length and format.
If you don't know the answer or if the provided knowledge do not contain sufficient information to provide an answer, just say so. Do not make anything up.
Do not include information where the supporting evidence for it is not provided.

---Notice---
Please add sections and commentary as appropriate for the length and format if necessary. Format the response in Markdown.
"""


PROMPTS[
    "query_rewrite_for_entity_retrieval"
] = """-Goal-
For a given query, generate a declarative sentence to serve as a query for retrieving relevant knowledge.

######################
-Examples-
######################

Question: What are the main characters? \n(A) Alice\n(B) Bob\n(C) Charlie\n(D) Dana
################
Output:
The main characters. (Maybe Alice, Bob, Charlie or Dana)

Question: What locations are shown in the video?
################
Output:
The locations shown in the video.

Question: Which animals appear in the wildlife footage? \n(A) Lions\n(B) Elephants\n(C) Zebras
################
Output:
The animals that appear in the wildlife footage. (Maybe Lions, Elephants or Zebras)

#############################
-Real Data-
######################
Question: {input_text}
######################
Output:
"""



PROMPTS[
    "query_rewrite_for_visual_retrieval"
] = """-Goal-
Given a question that may include scene-related information, generate a declarative sentence to serve as a query for retrieving relevant video segments.

######################
-Examples-
######################

Question: Which animal does the protagonist encounter in the forest scene?
################
Output:
The protagonist encounters an animal in the forest.

Question: In the movie, what color is the car that chases the main character through the city?
################
Output:
A city chase scene where the main character is pursued by a car.

Question: What is the weather like during the opening scene of the film?\n(A) Sunny\n(B) Rainy\n(C) Snowy\n(D) Windy
################
Output:
The opening scene of the film featuring specific weather conditions. (Maybe Sunny, Rainy, Snowy or Windy)

#############################
-Real Data-
######################
Question: {input_text}
######################
Output:
"""



PROMPTS[
    "keywords_extraction"
] = """- Goal -
Given a query, extract the relevant keywords that can help answer the query. Please list the keywords separated by commas.

######################
- Examples -
######################

Question: Which animal does the protagonist encounter in the forest scene?
################
Output:
animal, protagonist, forest, scene

Question: In the movie, what color is the car that chases the main character through the city?
################
Output:
color, car, chases, main character, city

Question: What is the weather like during the opening scene of the film?\n(A) Sunny\n(B) Rainy\n(C) Snowy\n(D) Windy
################
Output:
weather, opening scene, film, Sunny, Rainy, Snowy, Windy

#############################
- Real Data -
######################
Question: {input_text}
######################
Output:
"""



PROMPTS[
    "filtering_segment"
] = """---Role---

You are a helpful assistant to determine whether the video may contain information relevant to the knowledge based on its rough caption.
Please note that this is a rough caption of the video segments, which means it may not directly contain the answer but may indicate that the video segment is likely to contain information relevant to answering the question. 

---Video Caption---

{caption}

---Knowledge We Need---

{knowledge}

---Answer---
Please provide an answer that begins with "yes" or "no," followed by a brief step-by-step explanation.
Answer:
"""



PROMPTS[
    "videorag_response"
] = """---Role---

You are a helpful assistant responding to a query with retrieved knowledge.

---Goal---

Generate a response of the target length and format that responds to the user's question with relevant general knowledge.
Summarize useful and relevant information from the retrieved text chunks and the information retrieved from videos, suitable for the specified response length and format.
If you don't know the answer or if the input data tables do not contain sufficient information to provide an answer, just say so. Do not make anything up.
Do not include information where the supporting evidence for it is not provided.

---Target response length and format---

{response_type}

---Retrieved Information From Videos---

{video_data}

---Retrieved Text Chunks---

{chunk_data}

---Goal---

Generate a response of the target length and format that responds to the user's question with relevant general knowledge.
Summarize useful and relevant information from the retrieved text chunks and the information retrieved from videos, suitable for the specified response length and format.
If you don't know the answer or if the input data tables do not contain sufficient information to provide an answer, just say so. Do not make anything up.
Do not include information where the supporting evidence for it is not provided.
Reference relevant video segments within the answers, specifying the video name and start & end timestamps. Use the following reference format:

---Example of Reference---

In one segment, the film highlights the devastating effects of deforestation on wildlife habitats [1]. Another part illustrates successful conservation efforts that have helped endangered species recover [2].

#### Reference:
[1] video_name_1, 05:30, 08:00  
[2] video_name_2, 25:00, 28:00 

---Notice---
Please add sections and commentary as appropriate for the length and format if necessary. Format the response in Markdown.
"""

PROMPTS[
    "videorag_response_wo_reference"
] = """---Role---

You are a helpful assistant responding to a query with retrieved knowledge.

---Goal---

Generate a response of the target length and format that responds to the user's question with relevant general knowledge.
Summarize useful and relevant information from the retrieved text chunks and the information retrieved from videos, suitable for the specified response length and format.
If you don't know the answer or if the input data tables do not contain sufficient information to provide an answer, just say so. Do not make anything up.
Do not include information where the supporting evidence for it is not provided.

---Target response length and format---

{response_type}

---Retrieved Information From Videos---

{video_data}

---Retrieved Text Chunks---

{chunk_data}

---Goal---

Generate a response of the target length and format that responds to the user's question with relevant general knowledge.
Summarize useful and relevant information from the retrieved text chunks and the information retrieved from videos, suitable for the specified response length and format.
If you don't know the answer or if the input data tables do not contain sufficient information to provide an answer, just say so. Do not make anything up.
Do not include information where the supporting evidence for it is not provided.

---Notice---
Please add sections and commentary as appropriate for the length and format if necessary. Format the response in Markdown.
"""

PROMPTS[
    "videorag_response_for_multiple_choice_question"
] = """---Role---

You are a helpful assistant responding to a multiple-choice question with retrieved knowledge.

---Goal---

Generate a concise response that addresses the user's question by summarizing relevant information derived from the retrieved text and video content. Ensure the response aligns with the specified format and length.
Please note that there is only one choice is correct.

---Target response length and format---

{response_type}

---Retrieved Information From Videos---

{video_data}

---Retrieved Text Chunks---

{chunk_data}

---Goal---

Generate a concise response that addresses the user's question by summarizing relevant information derived from the retrieved text and video content. Ensure the response aligns with the specified format and length.
Please note that there is only one choice is correct.

---Notice---
Please provide your answer in JSON format as follows:
{{
    "Answer": "The label of the answer, like A/B/C/D or 1/2/3/4 or others, depending on the given query"
    "Explanation": "Provide explanations for your choice. Use sections and commentary as needed to ensure clarity and depth. Format the response in Markdown."
}}
Key points:
1. Ensure that the "Answer" reflects the correct label format.
2. Structure the "Explanation" for clarity, using Markdown for any necessary formatting.
"""