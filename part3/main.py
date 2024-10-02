import asyncio
import base64
from uuid import uuid4
import aiofiles
import boto3
import json
import os
import requests
import tempfile

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel
from typing import List
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
from mangum import Mangum
from fastapi.middleware.cors import CORSMiddleware
from urllib.parse import quote_plus
from loguru import logger

app = FastAPI()
handler = Mangum(app)

origins = ["*"]

# Replace these values with your actual OpenAI credentials
ACCESS_KEY = os.getenv("S3_ACCESS_KEY")
SECRET_KEY = os.getenv("S3_SECRET_KEY")
SARVAMAI_KEY = os.getenv("SARVAMAI_KEY")
AWS_BUCKET_VIDEO = 'video-bucket-s-1'
AWS_BUCKET_IMAGE = 'ppt-image-bucket-1'

s3_client = boto3.client(
    's3',
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
    # region_name=''
)
session = boto3.Session(
    aws_access_key_id=ACCESS_KEY,      # Replace with your access key ID
    aws_secret_access_key=SECRET_KEY,  # Replace with your secret access key
    # aws_session_token=SESSION_TOKEN  # If using temporary credentials, else remove this line
)

s3 = session.resource('s3')
bucketVideo = s3.Bucket(AWS_BUCKET_VIDEO)


async def s3_upload_video(content: bytes, key: str):
    logger.info(f'Uploading thumbnail {key} to s3')
    try:
        bucketVideo.put_object(Key=key, Body=content)
    except Exception as e:
        print(f"Error getting object {key} from bucket {AWS_BUCKET_VIDEO}.")
        print(e)


async def s3_download_image_binary(key: str):
    logger.info(f'Downloading Image {key} from s3')
    try:
        # Retrieve the object from the specified S3 bucket
        response = s3_client.get_object(Bucket=AWS_BUCKET_IMAGE, Key=key)
        # Get the base64 encoded content of the object
        base64_content = response['Body'].read().decode('utf-8')
        # Decode the base64 content to binary data
        decoded_content = base64.b64decode(base64_content)
    except Exception as e:
        print(f"Error getting object {key} from bucket {AWS_BUCKET_IMAGE}.")
        print(e)

    return decoded_content

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
    image_s3: str = ""  # New field for storing image URL


class Slides(BaseModel):
    slides: List[Slide]


class VideoInput(BaseModel):
    slides: List[Slide]
    targetLanguage: str
    speaker_gender: str
    speaker_voice: str


# Define the temporary directory path
TEMP_DIR = "/tmp"

# SarvamAI Text Translate


def translateText(text, target_language, speaker_gender, source_language="en-IN"):
    url = "https://api.sarvam.ai/translate"

    payload = {
        "input": text,
        "source_language_code": source_language,  # "en-IN"
        "target_language_code": target_language,  # "hi-IN"
        "speaker_gender": speaker_gender,  # "Male"
        "mode": "formal",
        "model": "mayura:v1",
        "enable_preprocessing": True
    }
    headers = {"Content-Type": "application/json",
               "api-subscription-key": SARVAMAI_KEY}

    response = requests.request("POST", url, json=payload, headers=headers)

    print("Called")
    print(response.json())

    print(response.json()["translated_text"])

    return response.json()["translated_text"]


def textToSpeech(text, language, index, speaker="meera"):
    url = "https://api.sarvam.ai/text-to-speech"

    payload = {
        "inputs": [text],
        "target_language_code": language,  # "hi-IN"
        "speaker": speaker,  # "meera"
        "pitch": 0,
        "pace": 1.0,
        "loudness": 1.5,
        "speech_sample_rate": 8000,
        "enable_preprocessing": True,
        "model": "bulbul:v1"
    }
    headers = {
        "Content-Type": "application/json",
        "api-subscription-key": "ae9ce32a-9d22-4677-b61e-2c255134d000"
    }

    print("Text to Speech Called.")

    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            # Get the base64-encoded audio data
            audio_base64 = response.json()["audios"][0]

            # Add padding to the base64 string if needed
            missing_padding = len(audio_base64) % 4
            if missing_padding:
                audio_base64 += '=' * (4 - missing_padding)

            # Decode the base64 string into binary audio data
            audio_data = base64.b64decode(audio_base64)

            # Save the decoded audio to a .wav file
            with open(os.path.join(TEMP_DIR, f"script_{index}.wav"), "wb") as wav_file:
                wav_file.write(audio_data)

            print("Text to Speech Success")

            return os.path.join(TEMP_DIR, f"script_{index}.wav")
        else:
            print(response.status_code)
            print(response.content)
    except Exception as e:
        print("Error: ", e)
        print("Failed with status code:", response.status_code)

# Function to create images asynchronously


async def create_image_and_script_async(slide, index, images, script_durations, target_language, speaker_gender, speaker_voice):
    # Create Image and add to list
    image_file_path = await create_image(slide, index)
    images.insert(index, image_file_path)

    # SarvamAI (Text Translate ----> Text to Speech)
    # Create Script Audio and add to list
    translatedText = slide.script
    if (target_language != 'en-IN'):
        translatedText = translateText(
            slide.script, target_language, speaker_gender)  # "hi-IN", "Male"

    # Limiting the Translated Text to max 500 characters for SARVAMAI TTS API
    translatedTextTrunc = (translatedText[:500]) if len(
        translatedText) > 500 else translatedText

    audio_path = textToSpeech(
        translatedTextTrunc, target_language, index, speaker_voice)  # "hi-IN", "meera"
    audio_clip = AudioFileClip(audio_path)
    duration = audio_clip.duration
    script_durations.insert(index, duration)
    audio_clip.close()
    print(index)

# Function to create images asynchronously


async def create_image(slide, index):
    print(slide)
    # Draw the image
    img = Image.new("RGB", (1280, 720), color="white")
    draw = ImageDraw.Draw(img)
    # Set Font Parameters
    font_file_path = "Gidole-Regular.ttf"
    font_title_size = 50
    font_content_size = 30
    font_title = ImageFont.truetype(font_file_path, font_title_size)
    font_content = ImageFont.truetype(font_file_path, font_content_size)
    # Draw Title of Slide
    draw.text((100, 50), slide.title, fill="black", font=font_title)
    content_y = 150
    # Draw Content of Slide
    for line in slide.content:
        draw.text((100, content_y), "• " + line,
                  fill="black", font=font_content)
        content_y += 50

    image_s3 = slide.image_s3
    if isinstance(image_s3, str) and image_s3:
        try:
            image_response = await s3_download_image_binary(key=image_s3)
            if image_response is None:
                logger.error(f"No content found for S3 key: {image_s3}")
            if image_response:
                image = Image.open(BytesIO(image_response))
                image = image.resize((400, 300))
                img.paste(image, (800, 350))
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch image: {e}")
    else:
        logger.warning(f"image_s3 is None or invalid for slide {slide.title}")

    image_file_path = os.path.join(TEMP_DIR, f"temp_image_{index}.jpg")
    img.save(image_file_path)
    return image_file_path

# Asynchronous video generation function


async def generate_video_from_json(input: VideoInput):
    data = input.slides
    images = []
    script_durations = []
    i = 0
    # Asynchronous Image and Script Creation
    async_tasks = []
    for slide in data:
        async_tasks.append(create_image_and_script_async(
            slide, i, images, script_durations, input.targetLanguage, input.speaker_gender, input.speaker_voice))
        i += 1
    await asyncio.gather(*async_tasks)
    print("Function Completed.")
    # Generate Videos from image and audio files
    video_clips = []
    for i in range(len(images)):
        img = images[i]
        image_clip = ImageClip(img).set_duration(script_durations[i])
        audio_clip = AudioFileClip(os.path.join(TEMP_DIR, f"script_{i}.wav"))
        video_clip = image_clip.set_audio(audio_clip)
        video_clips.append(video_clip)
    # Final Result Clip
    final_clip = concatenate_videoclips(video_clips, method="compose")
    print("Video Generated.")
    # Save Video and close the file
    with tempfile.NamedTemporaryFile(suffix=".mp4", dir=TEMP_DIR, delete=False) as temp_file:
        temp_file_path = temp_file.name
        temp_audiofile_path = os.path.join(
            TEMP_DIR, f"{uuid4()}_TEMP_AUDIO.mp3")
        final_clip.write_videofile(
            temp_file_path, fps=1, temp_audiofile=temp_audiofile_path)
        temp_file.close()
        async with aiofiles.open(temp_file_path, mode='rb') as f:
            video_data = await f.read()
        print("Video File Data Read.")
        os.remove(temp_file_path)
    for i in range(len(images)):
        os.remove(images[i])
        os.remove(os.path.join(TEMP_DIR, f"script_{i}.wav"))
    print("All Files Removed.")

    uniqueID = uuid4()
    file_name = f"{uniqueID}.mp4"
    # image_file_path = os.path.join(TEMP_DIR, file_name)
    await s3_upload_video(video_data, file_name)
    return file_name


@app.post("/generate_video")
async def generate_video(input: VideoInput):
    try:
        video_s3_file = await generate_video_from_json(input)
        return {
            "video": video_s3_file
        }
    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=500, detail=f"Failed to generate video: {str(e)}")


@app.get("/home")
def home_handler():
    return {
        "status_code": 200,
        "body": json.dumps("Hello")
    }
