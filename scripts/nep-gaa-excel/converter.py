import pandas as pd
import json
import sys
import os
from pathlib import Path
from tqdm import tqdm
import time

def excel_to_json(excel_file_path, output_dir=None):
    """
    Convert Excel file to JSON format
    
    Args:
        excel_file_path (str): Path to the Excel file
        output_dir (str, optional): Directory to save the JSON file. If None, saves in the same directory as Excel file
    """
    try:
        print("\nProcessing Excel file...")
        with tqdm(total=3, desc="Progress", bar_format="{l_bar}{bar}") as pbar:
            # Read Excel file as text to preserve exact formatting including leading zeros
            # Skip first row which contains "(In Thousand Pesos)" and use second row as header
            pbar.set_description("Reading Excel file")
            df = pd.read_excel(excel_file_path, dtype=str, header=1)
            df = df.fillna('')
            pbar.update(1)

            # Convert DataFrame to JSON
            pbar.set_description("Converting to JSON")
            json_data = df.to_dict(orient='records')
            pbar.update(1)

            # Create output path
            pbar.set_description("Preparing output")
            pbar.update(1)
        excel_path = Path(excel_file_path)
        if output_dir:
            output_path = Path(output_dir) / f"{excel_path.stem}.json"
        else:
            output_path = excel_path.with_suffix('.json')
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write JSON file
        print("\nWriting JSON file...")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)

        print(f"\nSuccessfully converted '{excel_file_path}' to '{output_path}'")
        return True
        
    except Exception as e:
        print(f"Error converting file: {str(e)}")
        return False

def main():
    if len(sys.argv) < 2:
        print("Usage: python excel_to_json_converter.py <excel_file_path> [output_directory]")
        sys.exit(1)
    
    excel_file = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not os.path.exists(excel_file):
        print(f"Error: Excel file '{excel_file}' not found")
        sys.exit(1)
    
    success = excel_to_json(excel_file, output_dir)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()