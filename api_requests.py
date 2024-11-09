import requests
import json

def send_request_to_api(data):
    url = "http://humble-mantis-evident.ngrok-free.app/chat"
    headers = {'Content-Type': 'application/json'}
    try:
        response = requests.post(url, data=json.dumps(data), headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Error sending request to API: {e}")
        return None
