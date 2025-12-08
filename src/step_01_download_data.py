
import pandas as pd
import ssl
import urllib.request

# Define the Google Sheet URL
SHEET_ID = "1s1hdDGjMQTjT1P5zO3xMX__hM1V-5Y9rEGt8uUg5_B0"
url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx"

# Define the tabs to download
SHEET_NAMES = ["Task Availability", "Calendar Availability", "January 2026"]

def download_data():
    try:
        print(f"Downloading data from {url}...")
        
        # Bypass SSL verification
        ssl._create_default_https_context = ssl._create_unverified_context
        
        # Read the Excel file directly from the URL
        # sheet_name=None reads all sheets, list reads specific ones
        data = pd.read_excel(url, sheet_name=SHEET_NAMES, engine='openpyxl')
        
        for name, df in data.items():
            print(f"\n--- {name} ---")
            print(df.head())
            print(f"Shape: {df.shape}")
            
            # Save to CSV for verification
            from pathlib import Path
            output_dir = Path(__file__).parent.parent / "data" / "raw"
            output_dir.mkdir(parents=True, exist_ok=True)

            filename = output_dir / f"{name.replace(' ', '_').lower()}.csv"
            df.to_csv(filename, index=False)
            print(f"Saved to {filename}")
            
    except Exception as e:
        print(f"Error downloading data: {e}")

if __name__ == "__main__":
    download_data()
