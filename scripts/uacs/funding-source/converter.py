import pandas as pd
import json
from typing import Dict, List
from pathlib import Path
from datetime import datetime


class FundingSourceConverter:
    """
    Converts Funding Source Excel files into structured JSON format for Neo4j.
    Handles FundCluster, FinancingSource, Authorization, and FundCategory entities.
    """
    
    def __init__(self):
        # Define folder structure
        self.base_dir = Path(__file__).parent
        self.input_dir = self.base_dir / "input"
        # Navigate to project root (3 levels up from scripts/uacs/funding-source/)
        project_root = self.base_dir.parent.parent.parent
        self.output_dir = project_root / "data" / "funding_source"

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def convert_fund_cluster(self, excel_file: str) -> List[Dict]:
        """
        Convert fundcluster.xlsx to JSON
        
        Node Structure:
        {
            "code": "01",
            "description": "Regular Agency Fund",
            "status": "Active"
        }
        """
        file_path = self.input_dir / excel_file
        df = pd.read_excel(file_path, sheet_name="UACS Code")
        
        # Clean column names
        df.columns = df.columns.str.strip()
        
        fund_clusters = []
        for _, row in df.iterrows():
            fund_cluster = {
                "code": str(row["UACS"]).strip().zfill(2),  # Ensure 2 digits
                "description": str(row["Fund Cluster"]).strip(),
                "status": str(row["Status"]).strip()
            }
            fund_clusters.append(fund_cluster)
        
        print(f"✓ Converted {len(fund_clusters)} Fund Clusters")
        return fund_clusters
    
    def convert_financing_source(self, excel_file: str) -> List[Dict]:
        """
        Convert financingsource.xlsx to JSON
        
        Node Structure:
        {
            "code": "1",
            "description": "General Fund",
            "status": "Active"
        }
        """
        file_path = self.input_dir / excel_file
        df = pd.read_excel(file_path, sheet_name="UACS Code")
        
        # Clean column names
        df.columns = df.columns.str.strip()
        
        financing_sources = []
        for _, row in df.iterrows():
            financing_source = {
                "code": str(row["UACS"]).strip(),  # Can be 1 or 2 digits
                "description": str(row["Financing Source"]).strip(),
                "status": str(row["Status"]).strip()
            }
            financing_sources.append(financing_source)
        
        print(f"✓ Converted {len(financing_sources)} Financing Sources")
        return financing_sources
    
    def convert_authorization(self, excel_file: str) -> List[Dict]:
        """
        Convert authorizationcode.xlsx to JSON
        
        Node Structure:
        {
            "code": "01",
            "description": "New General Appropriations",
            "financing_source": "General Fund",
            "status": "Active"
        }
        """
        file_path = self.input_dir / excel_file
        df = pd.read_excel(file_path, sheet_name="UACS Code")
        
        # Clean column names
        df.columns = df.columns.str.strip()
        
        authorizations = []
        for _, row in df.iterrows():
            # Extract last 2 digits from UACS (e.g., "101" -> "01")
            uacs = str(row["UACS"]).strip()
            code = uacs[-2:].zfill(2) if len(uacs) >= 2 else uacs.zfill(2)
            
            authorization = {
                "code": code,  # 2 digits
                "description": str(row["Authorization Code"]).strip(),
                "financing_source": str(row["Financing Source"]).strip(),
                "status": str(row["Status"]).strip()
            }
            authorizations.append(authorization)
        
        print(f"✓ Converted {len(authorizations)} Authorizations")
        return authorizations
    
    def convert_fund_category(self, excel_file: str) -> List[Dict]:
        """
        Convert fundcategory.xlsx to JSON
        
        Node Structure:
        {
            "uacs_code": "01101101",
            "code": "101",
            "description": "Specific Budgets of National Government Agencies",
            "sub_category": "Specific Budgets of National Government Agencies",
            "fund_cluster": "Regular Agency Fund",
            "financing_source": "General Fund",
            "authorization": "New General Appropriations",
            "status": "Active"
        }
        """
        file_path = self.input_dir / excel_file
        df = pd.read_excel(file_path, sheet_name="UACS Code")
        
        # Clean column names
        df.columns = df.columns.str.strip()
        
        fund_categories = []
        for _, row in df.iterrows():
            uacs_code = str(row["UACS"]).strip().zfill(8)
            
            fund_category = {
                "uacs_code": uacs_code,  # Full 8-digit code
                "code": uacs_code[-3:],  # Last 3 digits
                "description": str(row["Fund Category"]).strip(),
                "sub_category": str(row["Fund Sub-Category"]).strip(),
                "fund_cluster": str(row["Fund Cluster"]).strip(),
                "financing_source": str(row["Financing Source"]).strip(),
                "authorization": str(row["Authorization"]).strip(),
                "status": str(row["Status"]).strip()
            }
            fund_categories.append(fund_category)
        
        print(f"✓ Converted {len(fund_categories)} Fund Categories")
        return fund_categories
    
    def create_funding_source_composite(self, fund_categories: List[Dict]) -> List[Dict]:
        """
        Create FundingSource composite nodes (8-digit UACS code)
        These are the main nodes that NEP/GAA will link to
        
        UACS Code Structure (8 digits): [FC][FS][AUTH][CAT]
        Example: "01101101"
        - Positions 0-1 (2 digits): Fund Cluster = "01"
        - Position 2 (1 digit): Financing Source = "1" 
        - Positions 3-4 (2 digits): Authorization = "01"
        - Positions 5-7 (3 digits): Category = "101"
        
        Node Structure:
        {
            "uacs_code": "01101101",
            "description": "Regular Agency Fund - General Fund - New General Appropriations - Specific Budgets",
            "fund_cluster_code": "01",
            "financing_source_code": "1",
            "authorization_code": "01",
            "category_code": "101",
            "status": "Active"
        }
        """
        funding_sources = []
        
        for category in fund_categories:
            uacs = category["uacs_code"]
            
            # Parse UACS: [01][1][01][101]
            fund_cluster_code = uacs[0:2]        # Positions 0-1: "01"
            financing_source_code = uacs[2:3]     # Position 2: "1"
            authorization_code = uacs[3:5]        # Positions 3-4: "01"
            category_code = uacs[5:8]             # Positions 5-7: "101"
            
            funding_source = {
                "uacs_code": uacs,
                "description": f"{category['fund_cluster']} - {category['financing_source']} - {category['authorization']} - {category['description']}",
                "fund_cluster_code": fund_cluster_code,
                "financing_source_code": financing_source_code,
                "authorization_code": authorization_code,
                "category_code": category_code,
                "status": category["status"]
            }
            funding_sources.append(funding_source)
        
        print(f"✓ Created {len(funding_sources)} Funding Source Composites")
        return funding_sources
    
    def save_json(self, data: List[Dict], filename: str):
        """Save data to JSON file"""
        output_path = self.output_dir / filename
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"  → Saved to: {output_path}")
    
    def convert_all(self):
        """
        Convert all funding source files and save to JSON
        """
        print("\n" + "="*60)
        print("FUNDING SOURCE CONVERSION")
        print("="*60 + "\n")
        
        print(f"Input directory: {self.input_dir}")
        print(f"Output directory: {self.output_dir}\n")
        
        # Convert individual entities
        print("Converting individual entities...")
        fund_clusters = self.convert_fund_cluster("fundcluster.xlsx")
        self.save_json(fund_clusters, "fund_clusters.json")
        
        financing_sources = self.convert_financing_source("financingsource.xlsx")
        self.save_json(financing_sources, "financing_sources.json")
        
        authorizations = self.convert_authorization("authorizationcode.xlsx")
        self.save_json(authorizations, "authorizations.json")
        
        fund_categories = self.convert_fund_category("fundcategory.xlsx")
        self.save_json(fund_categories, "fund_categories.json")
        
        print("\nCreating composite entities...")
        funding_sources = self.create_funding_source_composite(fund_categories)
        self.save_json(funding_sources, "funding_sources.json")
        
        # Create summary
        summary = {
            "entity": "funding_source",
            "total_fund_clusters": len(fund_clusters),
            "total_financing_sources": len(financing_sources),
            "total_authorizations": len(authorizations),
            "total_fund_categories": len(fund_categories),
            "total_funding_sources": len(funding_sources),
            "conversion_date": datetime.now().isoformat(),
            "input_files": [
                "fundcluster.xlsx",
                "financingsource.xlsx",
                "authorizationcode.xlsx",
                "fundcategory.xlsx"
            ],
            "output_files": [
                "fund_clusters.json",
                "financing_sources.json",
                "authorizations.json",
                "fund_categories.json",
                "funding_sources.json"
            ]
        }
        self.save_json([summary], "_metadata.json")
        
        print("\n" + "="*60)
        print("CONVERSION COMPLETE!")
        print("="*60)
        print(f"\nFiles created in '{self.output_dir}' directory:")
        print("  • fund_clusters.json")
        print("  • financing_sources.json")
        print("  • authorizations.json")
        print("  • fund_categories.json")
        print("  • funding_sources.json (composite)")
        print("  • _metadata.json")
        
        return {
            "fund_clusters": fund_clusters,
            "financing_sources": financing_sources,
            "authorizations": authorizations,
            "fund_categories": fund_categories,
            "funding_sources": funding_sources
        }


def main():
    """
    Main execution function
    
    Folder Structure:
        scripts/uacs/funding-source/
            input/
                fundcluster.xlsx
                financingsource.xlsx
                authorizationcode.xlsx
                fundcategory.xlsx
            converter.py (this file)
            README.md

        data/
            fund_clusters.json
            financing_sources.json
            authorizations.json
            fund_categories.json
            funding_sources.json
            _metadata.json
    """
    try:
        converter = FundingSourceConverter()
        results = converter.convert_all()
        
        # Display sample data
        print("\n" + "="*60)
        print("SAMPLE DATA")
        print("="*60)
        
        print("\nSample Fund Cluster:")
        print(json.dumps(results["fund_clusters"][0], indent=2))
        
        print("\nSample Financing Source:")
        print(json.dumps(results["financing_sources"][0], indent=2))
        
        print("\nSample Authorization:")
        print(json.dumps(results["authorizations"][0], indent=2))
        
        print("\nSample Fund Category:")
        print(json.dumps(results["fund_categories"][0], indent=2))
        
        print("\nSample Funding Source (Composite):")
        print(json.dumps(results["funding_sources"][0], indent=2))
        
    except FileNotFoundError as e:
        print(f"\n❌ Error: Could not find input file - {e}")
        print("\nPlease ensure the following files exist in the 'input' directory:")
        print("  • fundcluster.xlsx")
        print("  • financingsource.xlsx")
        print("  • authorizationcode.xlsx")
        print("  • fundcategory.xlsx")
    except Exception as e:
        print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    main()