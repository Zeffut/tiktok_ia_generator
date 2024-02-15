import os, json
from pytube import YouTube
import moviepy.editor as mp
import whisper
from urllib.parse import parse_qs, urlparse
from moviepy.video.io.VideoFileClip import VideoFileClip
import g4f
from g4f.Provider import (Bing)

def decouper_prompt(prompt, context, longueur_morceau):
    morceaux = [prompt[i:i+longueur_morceau] for i in range(0, len(prompt), longueur_morceau)]
    messages = [{"role": "system","content": context}]
    for i, morceau in enumerate(morceaux):
        message = {"role": "user","content": morceau}
        messages.append(message)
    return messages

def extract_video_id(video_url):
    try:
        query = parse_qs(urlparse(video_url).query)
        video_id = query.get("v") or query.get("vi") or query.get("video_id") or query.get("vkey")
        return video_id[0] if video_id else None
    except Exception as e:
        print(f"Une erreur est survenue lors de l'extraction de l'ID de la vidéo : {str(e)}")
        return None

def download_video(url, output_folder):
    try:
        yt = YouTube(url, use_oauth=True, allow_oauth_cache=True)
        video_stream = next((stream for stream in yt.streams if stream.resolution == '1080p' and stream.mime_type.startswith('video/mp4')), None)
        if not video_stream:
            video_stream = yt.streams.filter(file_extension="mp4", progressive=True).order_by('resolution').desc().first()

        if not video_stream:
            raise Exception("Aucun flux vidéo disponible n'a été trouvé.")
        video_stream.download(output_folder, filename='full_video_video.mp4')
        audio_stream = yt.streams.filter(only_audio=True).first()
        audio_stream.download(output_folder, filename='full_video_audio.mp3')

        audio = mp.AudioFileClip(f"{output_folder}/full_video_audio.mp3")
        video = mp.VideoFileClip(f"{output_folder}/full_video_video.mp4")
        merge_video_audio(output_folder, audio, video)

    except Exception as e:
        print(f"Une erreur est survenue : {str(e)}")

def merge_video_audio(output_folder, audio, video):
    final = video.set_audio(audio)
    final.write_videofile(f"{output_folder}/full_video.mp4", codec='libx264', audio_codec='libvorbis')

    os.remove(f"{output_folder}/full_video_video.mp4")

def clear_transcript(transcript):
    for segment in transcript["segments"]:
        segment["text"] = segment["text"].split(' ', 1)[1] if ' ' in segment["text"] else segment["text"]
        del segment["tokens"]
        del segment["temperature"]
        del segment["avg_logprob"]
        del segment["compression_ratio"]
        del segment["no_speech_prob"]

    return transcript

def crop_video(input_path, output_path, start_time, end_time):
    video_clip = VideoFileClip(input_path)
    cropped_clip = video_clip.subclip(start_time, end_time)
    cropped_clip.write_videofile(output_path, codec="libx264", audio_codec="aac")
    video_clip.close()
    cropped_clip.close()

def extract_audio(video_file, audio_file) :
    video_clip = VideoFileClip(video_file)
    audio_clip = video_clip.audio
    audio_clip.write_audiofile(audio_file, codec='mp3')

def main():
    video_url = "https://www.youtube.com/watch?v=mkZsaDA2JnA"
    output_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Video")
    audio_path = os.path.join(output_folder, "full_video_audio.mp3")
    model = whisper.load_model("tiny")
    download_video(video_url, output_folder)
    video_path = os.path.join(output_folder, "full_video.mp4")
    extract_audio(video_path, audio_path)
    #os.remove(video_path)

    transcript = model.transcribe(audio_path)
    transcript_path = os.path.join(output_folder, "transcript.txt")
    transcript_clear = clear_transcript(transcript)
    with open(transcript_path, 'w') as json_file:
        json_file.write(json.dumps(transcript_clear, indent=2))
    context = "You are a ViralGPT helpful assistant. You are master at reading youtube transcripts and identifying the most Interesting and Viral Content"
    response_obj='''[
  {
    "start_time": 97.19, 
    "end_time": 127.43,
    "description": "Put here a simple description of the context in max 10 words"
    "duration":60 #Length in seconds
  },
]'''
    prompt = f"This is a transcript of a video. Please identify the most interesing sections from the whole, make sure that the duration is more than 1 minutes (it MUST to be more than 60 seconds), Make Sure you provide extremely accurate timestamps and respond only and absolute in this JSON format {response_obj}  \n Here is the Transcription:\n{transcript_clear}"
    messages = decouper_prompt(prompt, context, 30000)

    with open("temp_file.txt", 'w') as file:
        file.write(str(messages))
 
    g4f.debug.logging = False
    g4f.debug.version_check = False

    response = g4f.ChatCompletion.create(
        model=g4f.models.gpt_4_32k_0613,
        provider=g4f.Provider.Bing,
        messages=messages
    )
    response_dict = json.loads(response)
    print(response_dict)

    start_time = response_dict.get("start_time")
    end_time = response_dict.get("end_time")
    description = response_dict.get("description")

    crop_video(video_path, os.path.join(output_folder, f"{description}.mp4"), start_time, end_time)

main()
