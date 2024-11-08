import os, json
import yt_dlp
import moviepy.editor as mp
import whisper
from urllib.parse import parse_qs, urlparse
from moviepy.video.io.VideoFileClip import VideoFileClip
from api_requests import send_request_to_api

def decouper_prompt(prompt, context, longueur_morceau):
    morceaux = [prompt[i:i+longueur_morceau] for i in range(0, len(prompt), longueur_morceau)]
    messages = [{
            "role": "system",
            "content": context
        }]
    for i, morceau in enumerate(morceaux):
        message = {
            "role": "user",
            "content": morceau
        }
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
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': os.path.join(output_folder, 'full_video.%(ext)s'),
            'merge_output_format': 'mp4',
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        print("Téléchargement de la vidéo terminé")
    except Exception as e:
        print(f"Une erreur est survenue : {str(e)}")

def clear_transcript(transcript):
    for segment in transcript["segments"]:
        segment["text"] = segment["text"].split(' ', 1)[1] if ' ' in segment["text"] else segment["text"]
        del segment["tokens"]
        del segment["temperature"]
        del segment["avg_logprob"]
        del segment["compression_ratio"]
        del segment["no_speech_prob"]

    # Ajouter des retours à la ligne pour la lisibilité
    transcript_text = "\n".join([json.dumps(segment, indent=2) for segment in transcript["segments"]])
    return transcript_text

def crop_video(input_path, output_path, start_time, end_time):
    video_clip = VideoFileClip(input_path)
    duration = video_clip.duration
    start_time = max(0, min(start_time, duration))
    end_time = max(start_time, min(end_time, duration))
    cropped_clip = video_clip.subclip(start_time, end_time)
    cropped_clip.write_videofile(output_path, codec="libx264", audio_codec="aac")
    video_clip.close()
    cropped_clip.close()

def extract_audio(video_file, audio_file) :
    video_clip = VideoFileClip(video_file)
    audio_clip = video_clip.audio
    audio_clip.write_audiofile(audio_file, codec='mp3')

def crop_viral_clips(video_path, output_folder, viral_clips):
    for i, clip in enumerate(viral_clips):
        start_time = clip["start_time"]
        end_time = clip["end_time"]
        output_path = os.path.join(output_folder, f"viral_clip_{i+1}.mp4")
        crop_video(video_path, output_path, start_time, end_time)

def main():
    video_url = input("Entrez l'URL de la vidéo YouTube : ")
    output_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Video")
    audio_path = os.path.join(output_folder, "full_video_audio.mp3")
    model = whisper.load_model("tiny")
    download_video(video_url, output_folder)
    video_path = os.path.join(output_folder, "full_video.mp4")
    
    # Vérifiez si le fichier vidéo a été téléchargé avec succès
    if not os.path.exists(video_path):
        print(f"Erreur : le fichier vidéo {video_path} n'a pas été trouvé.")
        return
    
    crop_audio_path = os.path.join(output_folder, "cropped_audio.mp3")
    extract_audio(video_path, crop_audio_path)

    transcript = model.transcribe(crop_audio_path)
    transcript_clear = clear_transcript(transcript)

    context = "You are a ViralGPT helpful assistant. You are master at reading youtube transcripts and identifying the most Interesting and Viral Content"
    response_obj='''{
    "start_time": 97.19, 
    "end_time": 127.43,
    "description": "Put here a simple description of the context in max 10 words",
    "duration":60 #Length in seconds
  }'''
    prompt = f"This is a transcript of a video. Please identify the most interesing sections from the whole, make sure that the duration is more than 1 minutes (it MUST to be more than 60 seconds), Make Sure you provide extremely accurate timestamps and respond only in this JSON format {response_obj}  \n Here is the Transcription:\n{transcript_clear}"
    messages = decouper_prompt(prompt, context, 32000)

    # Convertir les messages en texte brut
    messages_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])
    response = send_request_to_api({"message": messages_text})
    print(response)
    if response:
        # Vérifiez le contenu de la réponse avant de l'analyser en JSON
        try:
            response_text = response.get('response', '')
            viral_clips = json.loads(response_text)
        except json.JSONDecodeError as e:
            print(f"Erreur lors de l'analyse de la réponse JSON : {e}")
            print(f"Contenu de la réponse : {response_text}")
            return
        
        # Recadrez la vidéo en fonction des extraits viraux
        crop_viral_clips(video_path, output_folder, viral_clips)

    # Supprimez le fichier vidéo original après avoir terminé toutes les opérations
    os.remove(video_path)

main()
