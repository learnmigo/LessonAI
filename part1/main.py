from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from fastapi.responses import FileResponse
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

from openai import OpenAI
import time
import re
import os

from mangum import Mangum

app = FastAPI()
handler = Mangum(app)

# Replace these values with your actual OpenAI credentials
api_key = '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'
assistant_id = 'asst_Sc75zGdT0g68oS03D3u0R47G'
client = OpenAI(api_key=api_key)

class LearningOutcomeInput(BaseModel):
    topic: str
    time: str
    target_type: str
    target_subtype: str
    taxonomy_level: str

class FlowDocInput(BaseModel):
    no_of_assessments: str
    type_of_assessments: str
    learning_outcomes: dict

def create_thread():
    # Create a thread
    thread = client.beta.threads.create()

    # Add the thread_id to the list
    thread_id = thread.id
    print("THREAD CREATED!!!")

    return thread_id

def run_thread(assistant_id, thread_id):
    # Run the thread
    response = client.beta.threads.runs.create(assistant_id=assistant_id, thread_id=thread_id)
    print("THREAD RUN!!!")
    return response

def write_msg(query, thread_id):
    thread_message = client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=query
    )
    print(thread_message)

def format_text(input_text):
    # Make text bold between **<text>**
    formatted_text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', input_text)
    
    return formatted_text

def generate_pdf(input_text, output_path='/tmp/output.pdf'):
    formatted_text = format_text(input_text)
    
    # Get the directory where the script is located
    script_dir = os.path.dirname(os.path.realpath(__file__))
    
    # Create PDF path relative to the script directory
    pdf_path = os.path.join(script_dir, output_path)
    
    # Create PDF using ReportLab
    doc = SimpleDocTemplate(pdf_path, pagesize=letter)
    styles = getSampleStyleSheet()
    
    # Split the formatted text into paragraphs
    paragraphs = [Paragraph(paragraph, styles['BodyText']) for paragraph in formatted_text.split('\n')]
    
    # Add paragraphs to the document
    doc.build(paragraphs)
    
    return pdf_path

@app.post("/assess")
async def assess_outcomes(outcome_input: LearningOutcomeInput):
    # Create a thread
    thread_id = create_thread()

    prompt = f"""Assess if the Bloom's taxonomy level - {outcome_input.taxonomy_level} can be achieved or not for the topic -{outcome_input.topic} for the target students of type - {outcome_input.target_type} and subtype - {outcome_input.target_subtype} in the time period of {outcome_input.time} minute lecture. If not, then suggest which level can be achieved. Answer in bullet points. If the topic is not found in the documents uploaded then Answer based on your knowldege and do not mention this in your response"""

    # Write a single message with instructions, questions, and answers
    write_msg(prompt, thread_id)

    # Run the thread
    response = run_thread(assistant_id, thread_id)

    i = 0
    while response.status.lower() != "completed":
        time.sleep(3)
        i = i + 1
        print(i, "...")
        response = client.beta.threads.runs.retrieve(run_id=response.id, thread_id=thread_id)

    query_response = client.beta.threads.messages.list(thread_id=thread_id)
    for answer in query_response:
        print(answer.content[0].text.value)
        return answer.content[0].text.value
    
    # answers = [answer.content[0].text.value for answer in query_response]
    # thread_info = {"thread_id": thread_id, "answers": answers}

    # return JSONResponse(content=thread_info)


@app.post("/learning_outcomes")
async def learning_outcomes(outcome_input: LearningOutcomeInput):
    # Create a thread
    thread_id = create_thread()

    json_format= {
  "learningOutcomes": [
    {
      "terminalOutcome": "",
      "subLearningOutcomes": [
        {
          "id": 1,
          "outcome": "",
          "examples": [
            "",
            ""
          ],
          "modeOfDelivery": "",
          "timeRequired": ""
        },
        {
          "id": 2,
          "outcome": "",
          "examples": [
            "",
            ""
          ],
          "modeOfDelivery": "",
          "timeRequired": ""
        },
        {
          "id": 3,
          "outcome": "",
          "examples": [
            "",
            ""
          ],
          "modeOfDelivery": "",
          "timeRequired": ""
        },
        {
          "id": 4,
          "outcome": "",
          "examples": [
            "",
            ""
          ],
          "modeOfDelivery": "",
          "timeRequired": ""
        },
        {
          "id": 5,
          "outcome": "",
          "examples": [
            "",
            ""
          ],
          "modeOfDelivery": "",
          "timeRequired": ""
        }
      ]
    }
  ]
}

    # Concatenate instructions, questions, and answers
    prompt = f"""Create Learning Outcomes for the topic - {outcome_input.topic} based on Bloom's taxonomy level -{outcome_input.taxonomy_level} for the target students of type - {outcome_input.target_type} and subtype - {outcome_input.target_subtype}. Create outcomes for a {outcome_input.time} minute lecture. 

Create 1 terminal learning outcomes and for each terminal learning outcome create 5 other sub-learning outcomes. For each sub-learning outcome, create specific examples for delivering the outcome which is relevant and relatable to the learners of type - {outcome_input.target_type} and subtype - {outcome_input.target_subtype} and also mention the mode of delivery such as demonstrations, presentations and experimentations and the time required for delivering. Keep in mind, all terminal outcomes has to be taught within the time period of {outcome_input.time} minutes. 

Give the output only in the following JSON format

{json_format}
"""

    # Write a single message with instructions, questions, and answers
    write_msg(prompt, thread_id)

    # Run the thread
    response = run_thread(assistant_id, thread_id)

    i = 0
    while response.status.lower() != "completed":
        i = i + 1
        print(i, "...")
        response = client.beta.threads.runs.retrieve(run_id=response.id, thread_id=thread_id)
        time.sleep(1)

    query_response = client.beta.threads.messages.list(thread_id=thread_id)
    for answer in query_response:
        print(answer.content[0].text.value)
        return answer.content[0].text.value
    
    answers = [answer.content[0].text.value for answer in query_response]
    thread_info = {"thread_id": thread_id, "answers": answers}
    
    return JSONResponse(content=thread_info)


@app.post("/flow_doc_new")
def create_flow_document_new(flow_input: FlowDocInput):
    # Create a thread for each sub-learning outcome
    thread_ids = []
    responses = []

    learning_outcomes_data = flow_input.learning_outcomes.get("learningOutcomes", {})
    total_sub_learning_outcomes = len(learning_outcomes_data[0]["subLearningOutcomes"])

    for i, sub_learning_outcome in enumerate(learning_outcomes_data[0]["subLearningOutcomes"]):
        # Create a thread
        thread_id = create_thread()

        # Extract relevant information from the sub-learning outcome
        sub_learning_outcome_text = sub_learning_outcome["outcome"]
        # sub_learning_outcome_mode = sub_learning_outcome["modeOfDelivery"]
        # sub_learning_outcome_time = sub_learning_outcome["timeRequired"]

        # Extract information about the next sub-learning outcome
        next_sub_learning_outcome = learning_outcomes_data[0]["subLearningOutcomes"][(i + 1) % total_sub_learning_outcomes]
        next_sub_learning_outcome_text = next_sub_learning_outcome["outcome"]

        # Construct prompt for the current sub-learning outcome
        prompt = f"""Create a instructional design document for each of the sub-learning outcomes which are primarily based upon Gagne's levels of instructional design.

For each sub-learning objective create a 
"Hook" - to Gain Attention of the Learner and Arouse Curiosity, 
"Establish Relevance" - to explain when / how the learner will use and benefit from learning the topic, 
"Mind Map" - give a bullet list to understand the main concept at a glance
"Recall / Activate Memory", 
"Demonstration" of a simple and real problem, 
"Practice Assessments" - Create {flow_input.no_of_assessments} assesments which are of {flow_input.type_of_assessments} type. Also, give the answers to these assesements in one word or one line.
"Summary" for the sub-learning outcome and priming for next sub-learning outcome.
FOCUS ON THE CURRENT SUB-LEARNING OUTCOME ONLY FOR ALL OF PARAMETER EXCEPT FOR THE SUMMARY AND PRIMING FOR NEXT LEARNING OUTCOME. BOLD ALL THESE HEADINGS LIKE HOOK, MIND MAP ETC. IN THE RESPONSE.


The Learning Outcomes and their Sub-learning outcomes are mentioned within the delimiters (<quotes></quotes>)
<quotes>
Terminal Learning Outcome - {learning_outcomes_data[0]['terminalOutcome']}
Current Sub-Learning Outcome - {sub_learning_outcome_text}
Next Sub-Learning Outcome - {next_sub_learning_outcome_text}
</quotes>

FOR THE INPUT 
Terminal Learning Outcome - Understanding Neural Networks 
Sub-Learning Outcome - Applications of Neural Network
Next Sub-Learning Outcome - The analogy with Human brain

THE OUTPUT IS EXPECTED IN THE FOLLOWING FORMAT
Hook / Gain Attention:
Engage learners by presenting a captivating scenario where they interact with SIRI, ALEXA, or Google Lens in their daily lives, highlighting the remarkable capabilities enabled by Neural Networks.

Recall / Activate Memory:
Prompt learners to recall instances where they have utilized SIRI, ALEXA, or Google Lens, encouraging them to reflect on how these technologies have impacted their daily routines.

State Objectives:
Identify the key objectives for this session, specifying what learners should accomplish:
Remember: List use cases of Speech and text recognition (SIRI, ALEXA, Google Assistant).
Understand: Describe use cases of Computer Vision (Google Lens, Object recognition).

Demonstration:
Demonstrate: Showcase the working mechanisms of ALEXA, SIRI, or Google Assistant to deepen understanding.
For instance: "Observe how ALEXA responds to voice commands and recognize the underlying neural network processes."

Summary + Priming for Next Topic:
Summarize: Review the applications of Neural Networks in daily life.
Priming: Introduce the analogy between Neural Networks and the human brain, preparing learners for the next topic.
For example: "As we wrap up our discussion on Neural Networks, consider how these technologies emulate the complexities of our own brain. This will be our focus in the upcoming topic."
Practice Assessments:

Assessment: Pose questions to assess comprehension.
"List other applications of Neural Networks you encounter in your daily life."
Encourage: Stimulate critical thinking by having learners apply knowledge.
"Think about a real-life problem you could solve using Neural Networks and outline your approach."

"""
        # Write the prompt to the thread
        write_msg(prompt, thread_id)

        response = run_thread(assistant_id, thread_id)
        responses.append(response)

        # Add the thread_id to the list
        thread_ids.append(thread_id)

    # Wait for completion of each thread
    for i, response in enumerate(responses):
        j = 0
        while response.status.lower() != "completed":
            j = j + 1
            print(f"Thread {i + 1} - {j}...")
            response = client.beta.threads.runs.retrieve(run_id=response.id, thread_id=thread_ids[i])
            time.sleep(1)

    # Retrieve responses for each thread
    thread_responses = []
    answers_list = []
    answers=""
    final_answer = ""
    for i, thread_id in enumerate(thread_ids):
        query_response = client.beta.threads.messages.list(thread_id=thread_id)
        for answer in query_response:
            answers+=answer.content[0].text.value
            answers_list.append(answer.content[0].text.value)
            final_answer += "**TERMINAL LEARNING OUTCOME:**\n"
            print("TERMINAL LEARNING OUTCOME \n")
            final_answer += f"{learning_outcomes_data[0]['terminalOutcome']}"
            print(learning_outcomes_data[0]['terminalOutcome'])
            final_answer += f"\n **SUB LEARNING OUTCOME-{i+1}:** \n"
            print("SUB LEARNING OUTCOME -", i,"\n")
            final_answer += f"{learning_outcomes_data[0]['subLearningOutcomes'][i]['outcome']}"
            print(learning_outcomes_data[0]['subLearningOutcomes'][i]['outcome'])
            final_answer += "\n **FLOW DOCUMENT:** \n"
            print("FLOW DOCUMENT \n")
            final_answer += f"{answer.content[0].text.value}"
            print(answer.content[0].text.value)
            final_answer +="\n\n\n\n"
            final_answer +="________________________________________________________________________________"
            final_answer +="\n\n\n\n"
            break
            
        # answers = [answer.content[0].text.value for answer in query_response]
        thread_responses.append({"thread_id": thread_id, "answers": answers})

    pdf_path = generate_pdf(final_answer)
    return FileResponse(pdf_path, filename='output.pdf', media_type='application/pdf')


@app.get("/")
def home():
    return {"message":"hello"}
