## LessonAI

### Part 1

#### Endpoints:

- **/assess**: Evaluates if Learning Outcomes can be formed based on the user-provided Bloom's Taxonomy Level. If not, suggests a feasible level.

- **/learning_outcomes**: Generates one terminal learning outcome and five sub-learning outcomes.

- **/flow_doc_new**: Creates an Instructional Design Document in PDF format based on the learning outcomes. Each Learning Outcome includes the following directives:
  - "Hook"
  - "Establish Relevance"
  - "Mind Map"
  - "Recall / Activate Memory"
  - "Demonstration"
  - "Practice Assessments"
  - "Summary"

### Part 2

#### Endpoints:

- **/json_script**: Generates a JSON of the PPT content and Video Script based on the Flow Document or Instructional Design Document.

- **/generate_ppt**: Creates a PPT using the selected template and the JSON of the PPT content.

### Part 3

#### Endpoints:

- **/video***: Creates a Video from the same JSON.
