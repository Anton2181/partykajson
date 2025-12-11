
import pandas as pd
import ssl
import urllib.request

# Define the Google Sheet URL
SHEET_ID = "1s1hdDGjMQTjT1P5zO3xMX__hM1V-5Y9rEGt8uUg5_B0"
url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx"

# Define the tabs to download
import sys

# Define the tabs to download
# "Task Availability" and "Calendar Availability" are fixed. 
# The third one is dynamic.

def download_data(target_month_str=None):
    if target_month_str is None:
        if len(sys.argv) > 1:
            target_month_str = sys.argv[1] # Expected format "January 2026" or "March 2026"
            # If arguments are split (e.g. python script.py January 2026)
            if len(sys.argv) > 2:
                target_month_str = f"{sys.argv[1]} {sys.argv[2]}"
        else:
            target_month_str = "January 2026"

    print(f"Target Sheet: {target_month_str}")
    
    sheet_names = ["Task Availability", "Calendar Availability", target_month_str]

    try:
        print(f"Downloading data from {url}...")
        
        # Bypass SSL verification
        ssl._create_default_https_context = ssl._create_unverified_context
        
        # Read the Excel file directly from the URL
        data = pd.read_excel(url, sheet_name=sheet_names, engine='openpyxl')
        
        for name, df in data.items():
            print(f"\n--- {name} ---")
            # print(df.head())
            print(f"Shape: {df.shape}")
            
            # Save to CSV for verification
            from pathlib import Path
            output_dir = Path("data") / "raw"
            output_dir.mkdir(parents=True, exist_ok=True)

            filename = output_dir / f"{name.replace(' ', '_').lower()}.csv"
            df.to_csv(filename, index=False, encoding='utf-8')
            print(f"Saved to {filename}")
            
    except Exception as e:
        print(f"Error downloading data: {e}")
        return # Stop if download fails

    # --- Chain Step 2: Convert Data ---
    print("\n--- Running Step 2: Convert Data ---")
    
    import pathlib
    root_dir = str(pathlib.Path(__file__).parent.parent)
    if root_dir not in sys.path:
        sys.path.append(root_dir)

    # Format for step 2: "january_2026"
    formatted_month = target_month_str.lower().replace(" ", "_")

    try:
        from src.step_02_convert_data import convert_data
        convert_data(formatted_month)
        print("Step 2 Completed Successfully")
    except ImportError:
         # Fallback
         try:
             from step_02_convert_data import convert_data
             convert_data(formatted_month)
             print("Step 2 Completed Successfully (Local Import)")
         except Exception as e:
             print(f"Error running Step 2: {e}")
    except Exception as e:
        print(f"Error running Step 2: {e}")

if __name__ == "__main__":
    download_data()
