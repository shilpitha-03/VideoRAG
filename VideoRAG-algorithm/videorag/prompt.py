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

Entity_types: [anatomy, instrument, procedure, phase, action, finding]
Text:
Caption:
The endoscopic view shows the surgeon using a sickle knife to make an incision along the uncinate process. The mucosa is scored in an anterior-to-posterior direction. A Freer elevator is then used to separate the uncinate from the lateral nasal wall. The natural maxillary ostium becomes partially visible behind the uncinate.
Transcript:
[0s -> 30s] Surgical phase: Uncinectomy. Step: Incision of uncinate process.

################
Output:
("entity"{tuple_delimiter}"SICKLE KNIFE"{tuple_delimiter}"instrument"{tuple_delimiter}"A sickle knife is a curved surgical blade used to make the initial incision along the uncinate process during endoscopic sinus surgery."){record_delimiter}
("entity"{tuple_delimiter}"UNCINATE PROCESS"{tuple_delimiter}"anatomy"{tuple_delimiter}"The uncinate process is a thin, crescent-shaped bony structure in the lateral nasal wall that partially covers the natural maxillary sinus ostium and is the first structure removed in FESS."){record_delimiter}
("entity"{tuple_delimiter}"FREER ELEVATOR"{tuple_delimiter}"instrument"{tuple_delimiter}"A Freer elevator is a flat dissecting instrument used to separate the uncinate process from the lateral nasal wall after the initial incision."){record_delimiter}
("entity"{tuple_delimiter}"MAXILLARY OSTIUM"{tuple_delimiter}"anatomy"{tuple_delimiter}"The natural maxillary ostium is the drainage opening of the maxillary sinus, which becomes visible after the uncinate process is removed."){record_delimiter}
("entity"{tuple_delimiter}"UNCINECTOMY"{tuple_delimiter}"procedure"{tuple_delimiter}"Uncinectomy is the surgical removal of the uncinate process, the first step in functional endoscopic sinus surgery to access the maxillary sinus."){record_delimiter}
("entity"{tuple_delimiter}"INCISION OF UNCINATE"{tuple_delimiter}"action"{tuple_delimiter}"The surgeon scores the mucosa along the uncinate process in an anterior-to-posterior direction using a sickle knife."){record_delimiter}
("relationship"{tuple_delimiter}"SICKLE KNIFE"{tuple_delimiter}"UNCINATE PROCESS"{tuple_delimiter}"The sickle knife is used to incise the uncinate process as the first step of its removal."{tuple_delimiter}9){record_delimiter}
("relationship"{tuple_delimiter}"FREER ELEVATOR"{tuple_delimiter}"UNCINATE PROCESS"{tuple_delimiter}"The Freer elevator separates the incised uncinate process from the lateral nasal wall."{tuple_delimiter}9){record_delimiter}
("relationship"{tuple_delimiter}"UNCINATE PROCESS"{tuple_delimiter}"MAXILLARY OSTIUM"{tuple_delimiter}"The uncinate process covers the maxillary ostium; removing it exposes the natural drainage pathway."{tuple_delimiter}8){record_delimiter}
("relationship"{tuple_delimiter}"UNCINECTOMY"{tuple_delimiter}"UNCINATE PROCESS"{tuple_delimiter}"Uncinectomy is the procedure of surgically removing the uncinate process."{tuple_delimiter}10){completion_delimiter}
#############################
Example 2:

Entity_types: [anatomy, instrument, procedure, phase, action, finding]
Text:
Caption:
The endoscope shows the inside of the maxillary sinus after the ostium has been widened. A microdebrider is being used to remove a large pale polyp from the sinus cavity. The surrounding mucosa appears edematous and inflamed. A suction irrigator clears blood from the surgical field intermittently.
Transcript:
[0s -> 30s] Surgical phase: Maxillary antrostomy. Step: Polyp removal from maxillary sinus.

################
Output:
("entity"{tuple_delimiter}"MAXILLARY SINUS"{tuple_delimiter}"anatomy"{tuple_delimiter}"The maxillary sinus is the largest paranasal sinus, located behind the cheek, accessed through the widened natural ostium during FESS."){record_delimiter}
("entity"{tuple_delimiter}"MICRODEBRIDER"{tuple_delimiter}"instrument"{tuple_delimiter}"A microdebrider is a powered rotating blade with suction used to remove polyps and diseased tissue while preserving healthy mucosa."){record_delimiter}
("entity"{tuple_delimiter}"NASAL POLYP"{tuple_delimiter}"finding"{tuple_delimiter}"A pale, benign growth protruding from the sinus mucosa, causing obstruction and being removed during the procedure."){record_delimiter}
("entity"{tuple_delimiter}"MUCOSAL EDEMA"{tuple_delimiter}"finding"{tuple_delimiter}"Swelling and inflammation of the sinus lining observed around the polyp, indicating chronic inflammatory disease."){record_delimiter}
("entity"{tuple_delimiter}"SUCTION IRRIGATOR"{tuple_delimiter}"instrument"{tuple_delimiter}"A suction irrigator is used to clear blood and debris from the surgical field to maintain visualization."){record_delimiter}
("entity"{tuple_delimiter}"MAXILLARY ANTROSTOMY"{tuple_delimiter}"procedure"{tuple_delimiter}"Maxillary antrostomy is the widening of the natural maxillary sinus ostium to improve drainage, performed after uncinectomy."){record_delimiter}
("relationship"{tuple_delimiter}"MICRODEBRIDER"{tuple_delimiter}"NASAL POLYP"{tuple_delimiter}"The microdebrider is the instrument used to excise the nasal polyp from the sinus cavity."{tuple_delimiter}9){record_delimiter}
("relationship"{tuple_delimiter}"NASAL POLYP"{tuple_delimiter}"MAXILLARY SINUS"{tuple_delimiter}"The polyp is located inside the maxillary sinus and is causing obstruction of sinus drainage."{tuple_delimiter}8){record_delimiter}
("relationship"{tuple_delimiter}"MAXILLARY ANTROSTOMY"{tuple_delimiter}"MAXILLARY SINUS"{tuple_delimiter}"Maxillary antrostomy is performed on the maxillary sinus to widen its natural drainage opening."{tuple_delimiter}10){record_delimiter}
("relationship"{tuple_delimiter}"SUCTION IRRIGATOR"{tuple_delimiter}"MICRODEBRIDER"{tuple_delimiter}"The suction irrigator works alongside the microdebrider to maintain a clear surgical field during tissue removal."{tuple_delimiter}7){completion_delimiter}
#############################
Example 3:

Entity_types: [anatomy, instrument, procedure, phase, action, finding]
Text:
Caption:
The view through the endoscope shows the posterior ethmoid cells after the basal lamella has been perforated. The surgeon uses through-cutting Blakesley forceps to carefully remove thin bony septae between ethmoid air cells. The sphenoid sinus face is visible in the background. Bleeding is minimal and the field is clear.
Transcript:
[0s -> 30s] Surgical phase: Posterior ethmoidectomy. Step: Opening posterior ethmoid cells.

################
Output:
("entity"{tuple_delimiter}"POSTERIOR ETHMOID CELLS"{tuple_delimiter}"anatomy"{tuple_delimiter}"The posterior ethmoid cells are a group of small air-filled cavities in the ethmoid bone, located between the anterior ethmoids and the sphenoid sinus."){record_delimiter}
("entity"{tuple_delimiter}"BASAL LAMELLA"{tuple_delimiter}"anatomy"{tuple_delimiter}"The basal lamella is the bony partition separating the anterior and posterior ethmoid cells, a key anatomical landmark in FESS."){record_delimiter}
("entity"{tuple_delimiter}"BLAKESLEY FORCEPS"{tuple_delimiter}"instrument"{tuple_delimiter}"Through-cutting Blakesley forceps are used to grasp and remove thin bony septae and tissue during ethmoidectomy."){record_delimiter}
("entity"{tuple_delimiter}"SPHENOID SINUS"{tuple_delimiter}"anatomy"{tuple_delimiter}"The sphenoid sinus is the most posterior paranasal sinus, its face becoming visible after posterior ethmoid cells are opened."){record_delimiter}
("entity"{tuple_delimiter}"POSTERIOR ETHMOIDECTOMY"{tuple_delimiter}"procedure"{tuple_delimiter}"Posterior ethmoidectomy is the surgical opening and clearance of the posterior ethmoid air cells, performed after perforating the basal lamella."){record_delimiter}
("relationship"{tuple_delimiter}"BLAKESLEY FORCEPS"{tuple_delimiter}"POSTERIOR ETHMOID CELLS"{tuple_delimiter}"Blakesley forceps are used to remove bony septae between the posterior ethmoid air cells."{tuple_delimiter}9){record_delimiter}
("relationship"{tuple_delimiter}"BASAL LAMELLA"{tuple_delimiter}"POSTERIOR ETHMOID CELLS"{tuple_delimiter}"The basal lamella is the anatomical boundary that must be perforated to access the posterior ethmoid cells."{tuple_delimiter}9){record_delimiter}
("relationship"{tuple_delimiter}"POSTERIOR ETHMOID CELLS"{tuple_delimiter}"SPHENOID SINUS"{tuple_delimiter}"The posterior ethmoid cells are anatomically adjacent to the sphenoid sinus, which becomes visible after ethmoidectomy."{tuple_delimiter}8){record_delimiter}
("relationship"{tuple_delimiter}"POSTERIOR ETHMOIDECTOMY"{tuple_delimiter}"BASAL LAMELLA"{tuple_delimiter}"Posterior ethmoidectomy begins by perforating the basal lamella to enter the posterior ethmoid space."{tuple_delimiter}10){completion_delimiter}
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

PROMPTS["DEFAULT_ENTITY_TYPES"] = ["anatomy", "instrument", "procedure", "phase", "action", "finding"]
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