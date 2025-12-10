
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
            # Use data relative to CWD (set by GUI or user)
            output_dir = Path("data") / "raw"
            output_dir.mkdir(parents=True, exist_ok=True)

            filename = output_dir / f"{name.replace(' ', '_').lower()}.csv"
            df.to_csv(filename, index=False, encoding='utf-8')
            print(f"Saved to {filename}")
            
    except Exception as e:
        print(f"Error downloading data: {e}")

    # --- Chain Step 2: Convert Data ---
    # --- Chain Step 2: Convert Data ---
    print("\n--- Running Step 2: Convert Data ---")
    
    # Fix imports: Add project root to sys.path if not present
    # This handles running from src/ or as invoked by GUI
    import sys
    import pathlib
    # Assuming standard structure: project/src/step_01.py
    # We want 'project' in sys.path so 'import src.step_02' works
    # OR we want 'src' in sys.path so 'import step_02' works?
    # The existing code tries 'from src.step_02...', implying project root is expected.
    
    root_dir = str(pathlib.Path(__file__).parent.parent)
    if root_dir not in sys.path:
        sys.path.append(root_dir)

    try:
        from src.step_02_convert_data import convert_data
        convert_data()
        print("Step 2 Completed Successfully")
    except ImportError:
         # Fallback: Maybe we are IN src and src is not a package
         try:
             from step_02_convert_data import convert_data
             convert_data()
             print("Step 2 Completed Successfully (Local Import)")
         except Exception as e:
             print(f"Error running Step 2: {e}")
    except Exception as e:
        print(f"Error running Step 2: {e}")

if __name__ == "__main__":
    download_data()
