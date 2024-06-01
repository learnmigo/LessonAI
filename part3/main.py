from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel
from typing import List
import json
import os
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from gtts import gTTS
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
from fastapi.responses import FileResponse
import tempfile
from mangum import Mangum
from fastapi.middleware.cors import CORSMiddleware
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

class Slide(BaseModel):
    title: str
    content: List[str]
    keywords: List[str]
    script: str
    img: str = ""  # New field for storing image URL

class Slides(BaseModel):
    slides: List[Slide]

# Define the temporary directory path
TEMP_DIR = "/tmp"

# Function to create the temporary directory if it doesn't exist
# def create_temp_dir():
#     if not os.path.exists(TEMP_DIR):
#         os.makedirs(TEMP_DIR)

# Function to search Unsplash images based on keywords
def search_unsplash_images(keyword):
    query = quote_plus(keyword.lower())
    UNSPLASH_API_URL = f"https://api.unsplash.com/search/photos/?client_id=AcayKaf-dYHRjbRTrryO9Tf51Z8ann6UhfXDaAg_7rE&page=1&query={query}&per_page=1"
    response = requests.get(UNSPLASH_API_URL)
    data = json.loads(response.text)
    if "results" in data and len(data["results"]) > 0:
        return data["results"][0]["links"]["download"]
    return None

# Modify the function to use the temporary directory
def create_image(slide, index):
    print("img")
    img = Image.new("RGB", (1280, 720), color="white")
    print("draw img")
    draw = ImageDraw.Draw(img)
    print("draw end")
    font_file_path = "Gidole-Regular.ttf"
    # Define font sizes
    font_title_size = 50
    font_content_size = 30

    # Create new ImageFont objects with the font file path and specified font sizes
    font_title = ImageFont.truetype(font_file_path, font_title_size)
    font_content = ImageFont.truetype(font_file_path, font_content_size)

    print("draw title")
    draw.text((100, 50), slide.title, fill="black", font=font_title)
    print("draw end")
    content_y = 150
    print("draw bullets")
    for line in slide.content:
        draw.text((100, content_y), "• " + line, fill="black", font=font_content)
        content_y += 50
    
    print("Create images")
    # Fetch image URL from Unsplash based on keywords
    image_url = search_unsplash_images(" ,".join(slide.keywords))

    print("URLS searched")
    if image_url:
        image_response = requests.get(image_url)
        if image_response.status_code == 200:
            image_data = image_response.content
            image = Image.open(BytesIO(image_data))
            image = image.resize((400, 300))
            img.paste(image, (800, 350))

    image_file_path = os.path.join(TEMP_DIR, f"temp_image_{index}.jpg")
    img.save(image_file_path)
    return image_file_path

# Modify the function to use the temporary directory
def generate_video_from_json(data: Slides):
    print("Create temp dir")
    # create_temp_dir()  # Create the temporary directory if it doesn't exist
    images = []
    script_durations = []
    i = 0
    print("Create images and scripts")
    for slide in data.slides:
        image_file_path = create_image(slide, i)
        images.append(image_file_path)
        tts = gTTS(text=slide.script, lang="en")
        tts.save(os.path.join(TEMP_DIR, f"script_{i}.mp3"))
        audio_clip = AudioFileClip(os.path.join(TEMP_DIR, f"script_{i}.mp3"))
        duration = audio_clip.duration
        script_durations.append(duration)
        audio_clip.close()
        print(i)
        i += 1
    video_clips = []
    print("COncat video and audio clips")
    for i in range(len(images)):
        img = images[i]
        image_clip = ImageClip(img).set_duration(script_durations[i])
        audio_clip = AudioFileClip(os.path.join(TEMP_DIR, f"script_{i}.mp3"))
        video_clip = image_clip.set_audio(audio_clip)
        video_clips.append(video_clip)
    final_clip = concatenate_videoclips(video_clips, method="compose")
    
    with tempfile.NamedTemporaryFile(suffix=".mp4", dir=TEMP_DIR, delete=False) as temp_file:
        temp_file_path = temp_file.name
        final_clip.write_videofile(temp_file_path, fps=1)
        temp_file.close()  # Close the file handle
        
        with open(temp_file_path, "rb") as f:
            video_data = f.read()
        
        os.remove(temp_file_path)
    
    print("Remove Temp Files")
    for i in range(len(images)):
        os.remove(images[i])
        os.remove(os.path.join(TEMP_DIR, f"script_{i}.mp3"))
    
    return video_data

@app.post("/generate_video")
async def generate_video(slides: Slides):
    temp_file_path = None
    try:
        video_data = generate_video_from_json(slides)
        print("main video returned")
        with tempfile.NamedTemporaryFile(suffix=".mp4", dir=TEMP_DIR, delete=False) as temp_file:
            temp_file.write(video_data)
            temp_file_path = temp_file.name
            print(f"File Path: {temp_file_path},\nFile Name: {temp_file.name}")
        
        return FileResponse(temp_file_path, media_type="video/mp4", filename="video_output.mp4")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate video: {str(e)}")
    # finally:
    #     # Clear the temporary MP4 video file
    #     if temp_file_path and os.path.exists(temp_file_path):
    #         os.remove(temp_file_path)
