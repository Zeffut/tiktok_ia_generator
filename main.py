import os, json
import yt_dlp
import moviepy.editor as mp
import whisper
from urllib.parse import parse_qs, urlparse
from moviepy.video.io.VideoFileClip import VideoFileClip
from api_requests import send_request_to_api
import re
import time

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

def is_json(myjson):
    try:
        json_object = json.loads(myjson)
    except ValueError as e:
        return False
    return True

def clean_response_text(response_text):
    try:
        # Rechercher et extraire toutes les structures JSON valides dans le texte
        json_matches = re.findall(r'(\{.*?\})', response_text, re.DOTALL)
        json_data = []
        for match in json_matches:
            try:
                json_data.append(json.loads(match))
            except json.JSONDecodeError:
                print(f"Erreur : JSON invalide trouvé : {match}")
        return json_data if json_data else None
    except Exception as e:
        print(f"Erreur lors du nettoyage de la réponse : {str(e)}")
    return None

def extract_clips_from_response(video_path, output_folder, json_data):
    for i, clip in enumerate(json_data):
        start_time = clip["start_time"]
        end_time = clip["end_time"]
        duration = end_time - start_time
        if duration < 30:
            print(f"Erreur : l'extrait {i+1} fait moins de 30 secondes ({duration} secondes).")
            continue
        output_path = os.path.join(output_folder, f"clip_{i+1}.mp4")
        crop_video(video_path, output_path, start_time, end_time)

def send_multiple_requests(transcript_clear, response_obj):
    max_length = 30 * 250 * 5  # 30 minutes in seconds
    segments = transcript_clear.split('\n')
    combined_results = []

    for i in range(0, len(segments), max_length):
        segment = '\n'.join(segments[i:i + max_length])
        prompt = (
            f"Voici la transcription de la vidéo : \n\n{segment}\n\n"
            f"Identifie les moments les plus intéressants de la vidéo. Chaque extrait sélectionné "
            f"doit impérativement avoir une durée de **60 secondes minimum** et ne doit pas être coupé avant cette durée. "
            f"Les extraits peuvent être plus longs, mais **aucun extrait ne doit être inférieur à 60 secondes**.\n"
            f"Réponds uniquement en JSON dans le format suivant, sans autres commentaires : {response_obj}"
        )

        print("Requète à l'API...")
        response = send_request_to_api({"message": prompt})

        if response:
            response_text = response.get('response', '')
            if not response_text:
                print("Erreur : la réponse de l'API est vide.")
                continue
            json_data = clean_response_text(response_text)
            if json_data:
                combined_results.extend(json_data)
            else:
                print("Erreur : impossible d'extraire un JSON valide de la réponse.")
                print(f"Contenu de la réponse : {response_text}")

    return combined_results

def main():
    video_url = input("Entrez l'URL de la vidéo YouTube : ")
    output_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Video")
    model = whisper.load_model("tiny")
    download_video(video_url, output_folder)
    video_path = os.path.join(output_folder, "full_video.mp4")
    
    if not os.path.exists(video_path):
        print(f"Erreur : le fichier vidéo {video_path} n'a pas été trouvé.")
        return
    
    crop_audio_path = os.path.join(output_folder, "cropped_audio.mp3")
    extract_audio(video_path, crop_audio_path)
    time.sleep(5)

    transcript = model.transcribe(crop_audio_path)
    os.remove(crop_audio_path)
    transcript_clear = clear_transcript(transcript)

    response_obj = '''{
        "start_time": 97.19, 
        "end_time": 167.43,
        "description": "Put here a simple description of the context in max 10 words",
        "duration":60
    },
    {
        "start_time": 530.45, 
        "end_time": 598.27,
        "description": "Put here a simple description of the context in max 10 words",
        "duration":68
    }'''

    combined_results = send_multiple_requests(transcript_clear, response_obj)

    if combined_results:
        print(json.dumps(combined_results, indent=2))
        extract_clips_from_response(video_path, output_folder, combined_results)
    else:
        print("Erreur : aucun extrait valide trouvé.")

    os.remove(video_path)

main()
