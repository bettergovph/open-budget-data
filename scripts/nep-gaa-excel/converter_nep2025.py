import pandas as pd
import json
import sys
import os
from pathlib import Path
from tqdm import tqdm

def excel_to_json(excel_file_path, output_dir=None):
    """
    Convert NEP-2025 Excel file to JSON format
    This script specifically handles the NEP-2025.xlsx file which has data in the second sheet

    Args:
        excel_file_path (str): Path to the Excel file
        output_dir (str, optional): Directory to save the JSON file. If None, saves in the same directory as Excel file
    """
    try:
        print("\nProcessing Excel file...")

        # Check available sheets
        xl = pd.ExcelFile(excel_file_path)
        print(f"Available sheets: {xl.sheet_names}")

        # Try to find the data sheet (not Sheet1)
        data_sheet = None
        for sheet in xl.sheet_names:
            if sheet.strip().lower() != 'sheet1':
                data_sheet = sheet
                break

        if not data_sheet:
            print("Warning: Could not find data sheet, using first sheet")
            data_sheet = xl.sheet_names[0]

        print(f"Reading data from sheet: '{data_sheet}'")

        with tqdm(total=3, desc="Progress", bar_format="{l_bar}{bar}") as pbar:
            # Read Excel file from the correct sheet
            pbar.set_description("Reading Excel file")
            df = pd.read_excel(excel_file_path, sheet_name=data_sheet, dtype=str)
            df = df.fillna('')
            pbar.update(1)

            print(f"Data shape: {df.shape[0]} rows x {df.shape[1]} columns")
            print(f"Columns: {', '.join(df.columns.tolist())}")

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
        print(f"Total records: {len(json_data)}")
        return True

    except Exception as e:
        print(f"Error converting file: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    if len(sys.argv) < 2:
        print("Usage: python converter_nep2025.py <excel_file_path> [output_directory]")
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
