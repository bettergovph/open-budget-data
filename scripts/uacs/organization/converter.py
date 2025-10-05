import pandas as pd
import json
from typing import Dict, List
from pathlib import Path
from datetime import datetime


class OrganizationConverter:
    """
    Converts Organization Excel files into structured JSON format for Neo4j.
    Handles Department, Agency, OperatingUnit, and OperatingUnitClass entities.
    
    UACS Organization Structure (12 digits): [DEPT][AGENCY][CLASS][LOWER_OU]
    Example: 270012200001
    - Positions 0-1 (2 digits): Department = "27"
    - Positions 2-4 (3 digits): Agency = "001"
    - Positions 5-6 (2 digits): Operating Unit Class = "22"
    - Positions 7-11 (5 digits): Lower Operating Unit = "00001"
    """
    
    def __init__(self):
        # Define folder structure
        self.base_dir = Path(__file__).parent
        self.input_dir = self.base_dir / "input"
        # Navigate to project root (3 levels up from scripts/uacs/organization/)
        project_root = self.base_dir.parent.parent.parent
        self.output_dir = project_root / "data" / "organization"
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def convert_department(self, excel_file: str) -> List[Dict]:
        """
        Convert department.xlsx to JSON
        
        Node Structure:
        {
            "code": "07",
            "description": "Department of Education (DepEd)",
            "abbreviation": "DepEd",
            "status": "Active"
        }
        """
        file_path = self.input_dir / excel_file
        df = pd.read_excel(file_path, sheet_name="UACS Code")
        
        # Clean column names
        df.columns = df.columns.str.strip()
        
        departments = []
        for _, row in df.iterrows():
            # Extract abbreviation from Name (text in parentheses)
            name = str(row["Name"]).strip()
            abbr = ""
            if "(" in name and ")" in name:
                abbr = name[name.rfind("(")+1:name.rfind(")")]
            
            department = {
                "code": str(row["UACS"]).strip().zfill(2),  # Ensure 2 digits
                "description": name,
                "abbreviation": abbr,
                "status": str(row["Status"]).strip()
            }
            departments.append(department)
        
        print(f"✓ Converted {len(departments)} Departments")
        return departments
    
    def convert_agency(self, excel_file: str) -> List[Dict]:
        """
        Convert agency.xlsx to JSON
        
        Node Structure:
        {
            "code": "001",
            "description": "Office of the Secretary",
            "department_code": "07",
            "uacs_code": "07001",
            "tag": "IU",
            "status": "Active"
        }
        """
        file_path = self.input_dir / excel_file
        df = pd.read_excel(file_path, sheet_name="UACS Code")
        
        # Clean column names
        df.columns = df.columns.str.strip()
        
        agencies = []
        for _, row in df.iterrows():
            uacs = str(row["UACS"]).strip().zfill(5)
            
            # Parse 5-digit UACS: [DEPT(2)][AGENCY(3)]
            dept_code = uacs[0:2]
            agency_code = uacs[2:5]
            
            agency = {
                "code": agency_code,  # 3 digits
                "description": str(row["Name"]).strip(),
                "department_code": dept_code,
                "uacs_code": uacs,  # Full 5 digits (dept + agency)
                "tag": str(row.get("Tag", "")).strip(),
                "status": str(row["Status"]).strip()
            }
            agencies.append(agency)
        
        print(f"✓ Converted {len(agencies)} Agencies")
        return agencies
    
    def convert_operating_unit_class(self, excel_file: str) -> List[Dict]:
        """
        Convert operatingunitclass.xlsx to JSON
        
        Node Structure:
        {
            "code": "01",
            "description": "Central Office",
            "status": "Active"
        }
        """
        file_path = self.input_dir / excel_file
        df = pd.read_excel(file_path, sheet_name="UACS Code")
        
        # Clean column names
        df.columns = df.columns.str.strip()
        
        ou_classes = []
        for _, row in df.iterrows():
            ou_class = {
                "code": str(row["UACS"]).strip().zfill(2),  # Ensure 2 digits
                "description": str(row["Name"]).strip(),
                "status": str(row["Status"]).strip()
            }
            ou_classes.append(ou_class)
        
        print(f"✓ Converted {len(ou_classes)} Operating Unit Classes")
        return ou_classes
    
    def convert_operating_unit(self, excel_file: str) -> List[Dict]:
        """
        Convert leveloperatingunit.xlsx to JSON
        
        UACS Structure (12 digits): [DEPT][AGENCY][CLASS][LOWER_OU]
        Example: 270012200001
        - 27 = Department
        - 001 = Agency
        - 22 = Operating Unit Class
        - 00001 = Lower Operating Unit
        
        Node Structure:
        {
            "code": "2200001",
            "description": "Office of the Regional Governor (Proper)",
            "uacs_code": "270012200001",
            "department_code": "27",
            "agency_code": "001",
            "class_code": "22",
            "lower_ou_code": "00001",
            "region_code": "",
            "tag": "IU",
            "status": "Active"
        }
        """
        file_path = self.input_dir / excel_file
        df = pd.read_excel(file_path, sheet_name="UACS Code")
        
        # Clean column names
        df.columns = df.columns.str.strip()
        
        operating_units = []
        for _, row in df.iterrows():
            uacs = str(row["UACS"]).strip().zfill(12)  # Ensure 12 digits
            
            # Parse 12-digit UACS: [DEPT(2)][AGENCY(3)][CLASS(2)][LOWER_OU(5)]
            dept_code = uacs[0:2]           # Positions 0-1
            agency_code = uacs[2:5]         # Positions 2-4
            class_code = uacs[5:7]          # Positions 5-6
            lower_ou_code = uacs[7:12]      # Positions 7-11
            
            # Operating Unit code = CLASS + LOWER_OU (7 digits total)
            ou_code = class_code + lower_ou_code
            
            # Try to get region from the data if available
            region_code = ""
            if "Region" in row and pd.notna(row["Region"]):
                region_str = str(row["Region"]).strip()
                # Try to extract region code
                import re
                match = re.search(r'\b(\d{2})\b', region_str)
                if match:
                    region_code = match.group(1)
            
            operating_unit = {
                "code": ou_code,  # 7 digits (class + lower_ou)
                "description": str(row["Name"]).strip(),
                "uacs_code": uacs,  # Full 12 digits
                "department_code": dept_code,
                "agency_code": agency_code,
                "class_code": class_code,
                "lower_ou_code": lower_ou_code,
                "region_code": region_code,
                "tag": str(row.get("Tag", "")).strip(),
                "status": str(row["Status"]).strip()
            }
            operating_units.append(operating_unit)
        
        print(f"✓ Converted {len(operating_units)} Operating Units")
        return operating_units
    
    def create_organization_composite(self, operating_units: List[Dict]) -> List[Dict]:
        """
        Create Organization composite nodes (12-digit UACS code)
        These are the main nodes that NEP/GAA will link to
        
        Node Structure:
        {
            "uacs_code": "270012200001",
            "description": "Office of the Regional Governor (Proper)",
            "department_code": "27",
            "agency_code": "001",
            "operating_unit_code": "2200001",
            "class_code": "22",
            "lower_ou_code": "00001",
            "region_code": "",
            "tag": "IU",
            "status": "Active"
        }
        """
        organizations = []
        
        for ou in operating_units:
            organization = {
                "uacs_code": ou["uacs_code"],  # 12 digits
                "description": ou["description"],
                "department_code": ou["department_code"],
                "agency_code": ou["agency_code"],
                "operating_unit_code": ou["code"],  # 7 digits
                "class_code": ou["class_code"],
                "lower_ou_code": ou["lower_ou_code"],
                "region_code": ou["region_code"],
                "tag": ou["tag"],
                "status": ou["status"]
            }
            organizations.append(organization)
        
        print(f"✓ Created {len(organizations)} Organization Composites")
        return organizations
    
    def save_json(self, data: List[Dict], filename: str):
        """Save data to JSON file"""
        output_path = self.output_dir / filename
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"  → Saved to: {output_path}")
    
    def convert_all(self):
        """
        Convert all organization files and save to JSON
        """
        print("\n" + "="*60)
        print("ORGANIZATION CONVERSION")
        print("="*60 + "\n")
        
        print(f"Input directory: {self.input_dir}")
        print(f"Output directory: {self.output_dir}\n")
        
        # Convert individual entities
        print("Converting individual entities...")
        departments = self.convert_department("department.xlsx")
        self.save_json(departments, "departments.json")
        
        agencies = self.convert_agency("agency.xlsx")
        self.save_json(agencies, "agencies.json")
        
        ou_classes = self.convert_operating_unit_class("operatingunitclass.xlsx")
        self.save_json(ou_classes, "operating_unit_classes.json")
        
        operating_units = self.convert_operating_unit("leveloperatingunit.xlsx")
        self.save_json(operating_units, "operating_units.json")
        
        print("\nCreating composite entities...")
        organizations = self.create_organization_composite(operating_units)
        self.save_json(organizations, "organizations.json")
        
        # Create summary
        summary = {
            "entity": "organization",
            "total_departments": len(departments),
            "total_agencies": len(agencies),
            "total_operating_unit_classes": len(ou_classes),
            "total_operating_units": len(operating_units),
            "total_organizations": len(organizations),
            "conversion_date": datetime.now().isoformat(),
            "uacs_structure": {
                "total_digits": 12,
                "format": "[DEPT(2)][AGENCY(3)][CLASS(2)][LOWER_OU(5)]",
                "example": "270012200001",
                "breakdown": {
                    "department": "positions 0-1 (2 digits)",
                    "agency": "positions 2-4 (3 digits)",
                    "class": "positions 5-6 (2 digits)",
                    "lower_ou": "positions 7-11 (5 digits)"
                }
            },
            "input_files": [
                "department.xlsx",
                "agency.xlsx",
                "operatingunitclass.xlsx",
                "leveloperatingunit.xlsx"
            ],
            "output_files": [
                "departments.json",
                "agencies.json",
                "operating_unit_classes.json",
                "operating_units.json",
                "organizations.json"
            ]
        }
        self.save_json([summary], "_metadata.json")
        
        print("\n" + "="*60)
        print("CONVERSION COMPLETE!")
        print("="*60)
        print(f"\nFiles created in '{self.output_dir}' directory:")
        print("  • departments.json")
        print("  • agencies.json")
        print("  • operating_unit_classes.json")
        print("  • operating_units.json")
        print("  • organizations.json (composite)")
        print("  • _metadata.json")
        
        return {
            "departments": departments,
            "agencies": agencies,
            "operating_unit_classes": ou_classes,
            "operating_units": operating_units,
            "organizations": organizations
        }


def main():
    """
    Main execution function
    
    Folder Structure:
        scripts/uacs/organization/
            input/
                department.xlsx
                agency.xlsx
                operatingunitclass.xlsx
                leveloperatingunit.xlsx
            converter.py (this file)
            README.md
        
        data/organization/
            departments.json
            agencies.json
            operating_unit_classes.json
            operating_units.json
            organizations.json
            _metadata.json
    """
    try:
        converter = OrganizationConverter()
        results = converter.convert_all()
        
        # Display sample data
        print("\n" + "="*60)
        print("SAMPLE DATA")
        print("="*60)
        
        if len(results["departments"]) > 6:
            print("\nSample Department:")
            print(json.dumps(results["departments"][6], indent=2))  # Show DepEd if exists
        
        print("\nSample Agency:")
        print(json.dumps(results["agencies"][0], indent=2))
        
        print("\nSample Operating Unit Class:")
        print(json.dumps(results["operating_unit_classes"][0], indent=2))
        
        print("\nSample Operating Unit:")
        print(json.dumps(results["operating_units"][0], indent=2))
        
        print("\nSample Organization (Composite):")
        print(json.dumps(results["organizations"][0], indent=2))
        
    except FileNotFoundError as e:
        print(f"\n❌ Error: Could not find input file - {e}")
        print("\nPlease ensure the following files exist in the 'input' directory:")
        print("  • department.xlsx")
        print("  • agency.xlsx")
        print("  • operatingunitclass.xlsx")
        print("  • leveloperatingunit.xlsx")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()