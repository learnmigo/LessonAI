import json
import time
from fastapi import FastAPI, UploadFile, File, HTTPException
from openai import OpenAI
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
import json
import requests
from io import BytesIO
from fastapi.responses import FileResponse
from mangum import Mangum
from fastapi.middleware.cors import CORSMiddleware
from urllib.parse import quote_plus
from pptx import Presentation
from pptx.util import Inches, Pt
from urllib.parse import quote_plus

app = FastAPI()
handler = Mangum(app)

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

assistant_id = 'asst_Sc75zGdT0g68oS03D3u0R47G'
api_key = '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'
query = """
"Make a PPT presentation and a script which could be said alongside the presentation based on the following Instructional Design document. The output should be in a JSON FORMAT ONLY WITHOUT ANY EXPLANATORY TEXT AROUND IT which returns the slide title, slide content in bullet points, 2-3 keywords based on the slide content and the script which could be said by the teacher when the current slide is shown. Analyse the entire instructional design document and then create concise and legible ppts.

The ppt should have the following slides:

- Hook/ Gain Attention and Establish Relevance on one slide
- Mention all the ""State Objectives"" on the next slide
- Then create a slide for individual each ""State Objective""
- Create a slide on how to ""Remember Concepts""
- Summary + Priming for Next Topic

THE SCRIPT SHOULD BE BASED ON THE CONTENT OF EACH SLIDE AND THE EXPLANATION GIVEN IN THE FLOW DOCUMENT

THE RESPONSE SHOULD BE IN THE FOLLOWING JSON FORMAT ONLY. DO NOT ADD ANY EXPLANATORY TEXT BEFORE OR AFTER IT.

{
  "slides": [
    {
      "title": "string",
      "content": [
        "string"
      ],
      "keywords": [
        "string"
      ],
      "script": "string"
    }
  ]
}
EACH SLIDE WOULD BE A LIST ITEM IN THE ABOVE JSON: 
TITLE - TITLE FOR THE SLIDE CONTENT
CONTENT - 3 TO 5 BULLET POINTS EXPLAINING THE CONTENT
KEYWORDS - 2 TO 3 SINGLE WORD KEYWORDS ABOUT THE ENTIRE SLIDE. THESE KEYWORDS WOULD BE USED TO SEARCH FOR IMAGES SO KEEP THEM APT
SCRIPT - A COMPREHENSIVE SCRIPT TO GO ALONG WITH THE SLIDE WHICH EXPLAINS THE SLIDE IN DEPTH WITH ELLUSIVE EXAMPLES

"""

client = OpenAI(api_key=api_key)

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

def write_msg(query, thread_id, file_id):
    thread_message = client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=query,
        file_ids=[file_id]
    )
    print(thread_message)

class Slide(BaseModel):
    title: str
    content: List[str]
    keywords: List[str]
    script: str
    img: str = ""  # New field for storing image URL

class Slides(BaseModel):
    slides: List[Slide]
    template: str

# Function to search Unsplash images based on keywords
def search_unsplash_images(keyword):
    query = quote_plus(keyword.lower())
    UNSPLASH_API_URL = f"https://api.unsplash.com/search/photos/?client_id=AcayKaf-dYHRjbRTrryO9Tf51Z8ann6UhfXDaAg_7rE&page=1&query={query}&per_page=1"
    response = requests.get(UNSPLASH_API_URL)
    data = json.loads(response.text)
    if "results" in data and len(data["results"]) > 0:
        return data["results"][0]["links"]["download"]
    return None

def generate_ppt_doc(slide_formatted_data, template):  
    # Fetch Images for Slides

    # slide_formatted_json = [json.loads(slide.json()) for slide in slide_formatted_data ]
    # print(slide_formatted_json)

    print("Images searching...")
    for slide in slide_formatted_data:
        if 'keywords' in slide:
            keywords = slide['keywords']
            combined_keywords = ' ,'.join(keywords)
            image_url = search_unsplash_images(combined_keywords)
            slide['image_url'] = image_url
    
    print("URLs Fetched")
    # Create Presentation Object
    prs = Presentation(f'./templates/{template}')

    print("PPT Creation Started...")
    # Iterate through JSON Slides to Create Presentation Slides
    for slide_data in slide_formatted_data:
        slide_layout = prs.slide_layouts[5]  # Use the layout suitable for content and picture
        slide = prs.slides.add_slide(slide_layout)

        # Set Title of the Slide
        title = slide.shapes.title
        title.text = slide_data['title']

        # Add Content as Bullet Points in a Text Box
        left_content = slide.shapes.add_textbox(Inches(1.5), Inches(2), Inches(5.5), Inches(4))
        left_text_frame = left_content.text_frame

        left_text_frame.word_wrap = True  # Ensure text box wraps content

        # Add content to the slide
        for text in slide_data['content']:
            p = left_text_frame.add_paragraph()
            p.text = text
            p.font.size = Pt(18)  # Set font size to 18 points
            p.space_after = Pt(12)  # Increase spacing between paragraphs
            p.level = 0  # Set content as level 0 bullet points

        # Add Image to the Slide if available
        image_url = slide_data['image_url']
        if isinstance(image_url, str) and image_url:
            image_response = requests.get(image_url)
            if image_response.status_code == 200:
                image_stream = BytesIO(image_response.content)
                left = Inches(7.5)
                top = Inches(2.2)
                width = height = Inches(4)
                slide.shapes.add_picture(image_stream, left, top, width, height)

    print("PPT Generated!!")

    ppt_file_path = '/tmp/output_new.pptx'
    prs.save(ppt_file_path)

    return FileResponse(path=ppt_file_path, media_type='application/vnd.openxmlformats-officedocument.presentationml.presentation')


@app.post("/json_script")
async def upload_file(template:str,file: UploadFile = File(...)):
    try:
        thread_id = create_thread()
        
        file_content = await file.read()
        file_id = client.files.create(file=file_content, purpose="assistants")
        
        write_msg(query, thread_id, file_id.id)

        response = run_thread(assistant_id, thread_id)
        
        i=1
        # Wait for the completion of the thread
        while response.status.lower() != "completed":
            response = client.beta.threads.runs.retrieve(run_id=response.id, thread_id=thread_id)
            time.sleep(1)
            print(i)
            i=i+1

        # Retrieve and return the response
        query_response = client.beta.threads.messages.list(thread_id=thread_id)
        print(query_response)
        for answer in query_response:
            response_text = answer.content[0].text.value
            print(response_text)
            break

        # Delete the file
        client.files.delete(file_id.id)

        # Find the index of the first '{' character
        start_index = response_text.find('{')

        # Find the index of the last '}' character
        end_index = response_text.rfind('}') + 1  # Adding 1 to include the last '}' character

        # Extract JSON string
        json_str = response_text[start_index:end_index]

        # Load JSON data
        json_data = json.loads(json_str)
        ppt_file_path = generate_ppt_doc(json_data["slides"], template)

        return json_data, ppt_file_path
        # return JSONResponse(content={"json_response": json_data}, media_type="application/json"), FileResponse(path=ppt_file_path, media_type='application/vnd.openxmlformats-officedocument.presentationml.presentation')
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate Response: {str(e)}")

@app.post("/generate_ppt")
async def generate_ppt(slides: Slides):
    try:
        print(slides.slides)
        print(slides.template)
        ppt = generate_ppt_doc(slides.slides, slides.template)
        return ppt
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate PPT: {str(e)}")
