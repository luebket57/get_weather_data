import os
import pandas as pd
import csv
from datetime import datetime
import requests
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload, MediaIoBaseDownload
import io

# KONFIGURATION
SERVICE_ACCOUNT_FILE = "credentials.json"  # GITHUB Deine JSON-Datei mit Service-Account-Zugang
#SERVICE_ACCOUNT_FILE = r"C:\Users\luebk\Documents\Python_Projects\google_cloud_credentials_weatherbot.json"  # Lokal Deine JSON-Datei mit Service-Account-Zugang
GDRIVE_FOLDER_ID = "17OtfrNTzSV_CJficpftk7DCBGsw7m6XG"       # Google Drive Ordner-ID
API_KEY_METEOBLUE = os.getenv("METEOBLUE_API_KEY")
print(f"API Key: {API_KEY_METEOBLUE}")
CSV_DATEI = "wetterdaten_meteoblue.csv"
LOCATIONS = {
    'Zuerich': (47.3769, 8.5417),
    'Ibbenbueren': (52.2754, 7.7154),
    'Muenster': (51.9625, 7.6256),
    'Rigi Kulm': (47.0567, 8.4853)
}

# 1️⃣ Wetterdaten für mehrere Orte abrufen
def get_weather(staedte):
    dfs_meteoblue = []

    for location in LOCATIONS.keys():
        try:
            # Wetterdaten abrufen
            LATITUDE, LONGITUDE = LOCATIONS[location]
            endpoint = f'https://my.meteoblue.com/packages/basic-day_clouds-day?apikey={API_KEY_METEOBLUE}&lat={LATITUDE}&lon={LONGITUDE}&format=json'

            response = requests.get(endpoint)
            data = response.json()
            # Extract relevant data
            dates = data['data_day']['time'][:]
            max_temps = data['data_day']['temperature_max'][:]
            min_temps = data['data_day']['temperature_min'][:]
            predictability = data['data_day']['predictability'][:]
            sun_hours = data['data_day']['sunshine_time'][:]
            precip_probs = data['data_day']['precipitation_probability'][:]

                        # Create a DataFrame
            df_meteoblue = pd.DataFrame({
                'Datum': dates,
                'Location': location,
                'maxTemperature': max_temps,
                'minTemperature': min_temps,
                'sunHours': sun_hours,
                'precipitationProbability': precip_probs,
                'Prediction_Timestamp': datetime.now(),
                'predictability': predictability,
                'Latitude': LATITUDE,
                'Longitude': LONGITUDE
                
                
            })
            #Convert sunshine time to hours
            df_meteoblue['sunHours'] = df_meteoblue['sunHours'] / 60
            # In die Liste speichern
            dfs_meteoblue.append(df_meteoblue)
        except Exception as e:
            print(f"⚠️ Fehler für {location}: {e}")

    # Alle DataFrames zusammenfügen
    return pd.concat(dfs_meteoblue, ignore_index=True) if dfs_meteoblue else pd.DataFrame()

# 2️⃣ CSV-Datei aktualisieren oder erstellen
def update_csv(LOCATIONS):
    df_weather = get_weather(LOCATIONS)
    header = ["Datum", "Location", "maxTemperature", "minTemperature", "sunHours", "precipitationProbability", "Prediction_Timestamp", "predictability", "Latitude", "Longitude"]

    # Falls Datei nicht existiert, neu erstellen mit Header
    if not os.path.exists(CSV_DATEI):
        df_weather.to_csv(CSV_DATEI, index=False, mode="w", header=True)
    else:
        df_weather.to_csv(CSV_DATEI, index=False, mode="a", header=False)  # Neue Zeilen anhängen


# 3️⃣ Google Drive Service einrichten
def authenticate_drive():
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=credentials)

# 4️⃣ Prüft, ob die Datei schon existiert
def find_existing_file(service, filename):
    query = f"name='{filename}' and '{GDRIVE_FOLDER_ID}' in parents and trashed=false"
    response = service.files().list(q=query, fields="files(id)").execute()
    files = response.get("files", [])
    return files[0]["id"] if files else None

# 5️⃣ CSV-Datei in Google Drive hochladen oder ersetzen
def upload_to_gdrive():
    service = authenticate_drive()
    file_id = find_existing_file(service, CSV_DATEI)

    file_metadata = {
        "name": CSV_DATEI,
        "parents": [GDRIVE_FOLDER_ID]
    }
    media = MediaFileUpload(CSV_DATEI, mimetype="text/csv", resumable=True)

    if file_id:
        print(f"📂 Datei '{CSV_DATEI}' gefunden! Aktualisiere Datei...")
        service.files().update(fileId=file_id, media_body=media).execute()
    else:
        print(f"📤 Datei '{CSV_DATEI}' nicht gefunden. Lade neu hoch...")
        service.files().create(body=file_metadata, media_body=media, fields="id").execute()


def download_existing_csv(service, file_id):
    """Downloads the existing CSV from Google Drive and loads it into a DataFrame."""
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    
    fh.seek(0)
    return pd.read_csv(fh)

def upload_to_gdrive_direct():
    service = authenticate_drive()
    file_id = find_existing_file(service, CSV_DATEI)

    # Neue Wetterdaten abrufen
    df_new = get_weather(LOCATIONS)

    # Falls Datei existiert: Alte Daten aus Google Drive laden
    if file_id:
        print(f"📂 Datei '{CSV_DATEI}' gefunden! Lade vorhandene Daten herunter...")
        df_existing = download_existing_csv(service, file_id)
        df_combined = pd.concat([df_existing, df_new], ignore_index=True)
    else:
        print(f"📤 Datei '{CSV_DATEI}' nicht gefunden. Erstelle eine neue Datei...")
        df_combined = df_new

    # DataFrame direkt in einen Memory-Stream schreiben (kein lokales Speichern)
    csv_stream = io.BytesIO()
    df_combined.to_csv(csv_stream, index=False)
    csv_stream.seek(0)

    # Datei-Metadaten für Google Drive
    file_metadata = {"name": CSV_DATEI, "parents": [GDRIVE_FOLDER_ID]}
    media = MediaIoBaseUpload(csv_stream, mimetype="text/csv", resumable=True)

    # Datei in Google Drive hochladen (überschreiben oder neu erstellen)
    if file_id:
        service.files().update(fileId=file_id, media_body=media).execute()
        print(f"✅ Datei '{CSV_DATEI}' erfolgreich aktualisiert!")
    else:
        service.files().create(body=file_metadata, media_body=media, fields="id").execute()
        print(f"✅ Datei '{CSV_DATEI}' erfolgreich hochgeladen!")


if __name__ == "__main__":
    #update_csv(LOCATIONS)       # CSV lokal aktualisieren
    #upload_to_gdrive() # Datei in Google Drive hochladen oder ersetzen
    upload_to_gdrive_direct() # Datei in Google Drive hochladen oder ersetzen



