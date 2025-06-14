import requests
import time

# Mets ton propre lien Firebase ici (remplace bien par ton vrai lien)
FIREBASE_URL = 'https://sinda-34c14-default-rtdb.firebaseio.com/production.json'

def listen_to_firebase():
    last_data = None
    while True:
        try:
            response = requests.get(FIREBASE_URL)
            if response.status_code == 200:
                data = response.json()
                if data != last_data:
                    print("Nouvelle donnée reçue de Firebase:", data)
                    last_data = data
            else:
                print("Erreur Firebase:", response.text)
        except Exception as e:
            print("Exception:", str(e))

        time.sleep(5)  # Vérifier toutes les 5 secondes

if __name__ == "__main__":
    listen_to_firebase()
