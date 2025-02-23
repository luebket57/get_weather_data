import os
import pandas as pd
import csv
import datetime
import random
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.http import MediaFileUpload
import wetteronline

# KONFIGURATION
#SERVICE_ACCOUNT_FILE = "credentials.json"  # GITHUB Deine JSON-Datei mit Service-Account-Zugang
SERVICE_ACCOUNT_FILE = r"C:\Users\luebk\Documents\Python_Projects\google_cloud_credentials_weatherbot.json"  # Lokal Deine JSON-Datei mit Service-Account-Zugang
GDRIVE_FOLDER_ID = "17OtfrNTzSV_CJficpftk7DCBGsw7m6XG"       # Google Drive Ordner-ID
CSV_DATEI = "wetterdaten_wetteronline.csv"
LOCATIONS = ["Zuerich", "Ibbenbueren", "Muenster", "Rigi-Kulm"] #Orte mit Lerzeichen immer mit - verbinden

# 1️⃣ Wetterdaten für mehrere Orte abrufen
def get_weather(staedte):
    dfs = []

    for location in staedte:
        try:
            # Wetterdaten abrufen
            w = wetteronline.weather(f"wetter/{location.lower()}")

            # Daten in DataFrame umwandeln
            df = pd.DataFrame.from_dict(w.forecast_4d, orient='index').reset_index()
            df.rename(columns={'index': 'Datum'}, inplace=True)
            df['Prediction_Timestamp'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            df['Location'] = location

            # In die Liste speichern
            dfs.append(df)
        except Exception as e:
            print(f"⚠️ Fehler für {location}: {e}")

    # Alle DataFrames zusammenfügen
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

# 2️⃣ CSV-Datei aktualisieren oder erstellen
def update_csv(LOCATIONS):
    df_weather = get_weather(LOCATIONS)
    header = ["Datum", "Location", "maxTemperature", "minTemperature", "sunHours", "precipitationProbability", "Prediction_Timestamp"]

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

if __name__ == "__main__":
    update_csv(LOCATIONS)       # CSV lokal aktualisieren
    upload_to_gdrive() # Datei in Google Drive hochladen oder ersetzen
