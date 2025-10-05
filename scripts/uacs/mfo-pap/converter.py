import pandas as pd
import json
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime


class PAPConverter:
    """
    Converts PAP (Program/Activity/Project) and PREXC Excel files into structured JSON for Neo4j.
    
    PREXC Structure (15-digit): SECTOR(1) + COST(1) + OO(2) + PROG(2) + SUBPROG(2) + 
                                 IDENT(1) + ACTIVITY(5) + RESERVED(3)
    
    Levels:
    1 = Cost Structure (GAS/STO/Operations)
    2 = Organizational Outcome
    3 = Program
    4 = Sub-program
    5 = Activity Type (1=Activity, 2=LFP, 3=FAP)
    6 = Activity/Project
    7 = Lowest Activity Level
    """
    
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.input_dir = self.base_dir / "input"
        project_root = self.base_dir.parent.parent.parent
        self.output_dir = project_root / "data" / "pap"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Sector/Sub-Sector Outcomes from UACS PDF
        self.sector_outcomes = self.load_sector_outcomes()
        self.horizontal_programs = {
            "00": "None",
            "01": "Disaster Related",
            "02": "Climate Change Mitigation",
            "03": "Climate Change Adaptation"
        }
    
    def load_sector_outcomes(self) -> Dict[str, Dict]:
        """Load sector and sub-sector outcome codes"""
        return {
            # General Public Services
            "100": {"type": "Sector", "description": "General public services"},
            "101": {"type": "Sub-Sector", "description": "Executive and legislative organs, financial and fiscal affairs, external affairs"},
            "102": {"type": "Sub-Sector", "description": "Foreign economic aid"},
            "103": {"type": "Sub-Sector", "description": "General services"},
            "104": {"type": "Sub-Sector", "description": "Basic research"},
            "105": {"type": "Sub-Sector", "description": "R&D General public services"},
            "106": {"type": "Sub-Sector", "description": "General public services n.e.c."},
            "107": {"type": "Sub-Sector", "description": "Public debt transactions"},
            "108": {"type": "Sub-Sector", "description": "Transfers of a general character between different levels of government"},
            "109": {"type": "Sub-Sector", "description": "Governance / Government Institutions and Regulatory Regime"},
            
            # Defense
            "120": {"type": "Sector", "description": "Defense"},
            "121": {"type": "Sub-Sector", "description": "Military Defense"},
            "122": {"type": "Sub-Sector", "description": "Civil Defense"},
            "123": {"type": "Sub-Sector", "description": "Foreign military aid"},
            "124": {"type": "Sub-Sector", "description": "R&D Defense"},
            "125": {"type": "Sub-Sector", "description": "Territorial integrity"},
            "126": {"type": "Sub-Sector", "description": "Defense against cybercrimes"},
            "127": {"type": "Sub-Sector", "description": "Defense n.e.c."},
            
            # Public Order and Safety
            "140": {"type": "Sector", "description": "Public order and safety"},
            "141": {"type": "Sub-Sector", "description": "Police services"},
            "142": {"type": "Sub-Sector", "description": "Fire-protection services"},
            "143": {"type": "Sub-Sector", "description": "Law courts"},
            "144": {"type": "Sub-Sector", "description": "Prisons"},
            "145": {"type": "Sub-Sector", "description": "R&D Public order and safety"},
            "146": {"type": "Sub-Sector", "description": "Public order and safety n.e.c."},
            
            # Economic Affairs
            "160": {"type": "Sector", "description": "Economic affairs"},
            "161": {"type": "Sub-Sector", "description": "General economic, commercial and labor affairs"},
            "162": {"type": "Sub-Sector", "description": "Agriculture, forestry, fishing and hunting"},
            "163": {"type": "Sub-Sector", "description": "Fuel and energy"},
            "164": {"type": "Sub-Sector", "description": "Mining, manufacturing and construction"},
            "165": {"type": "Sub-Sector", "description": "Transport"},
            "166": {"type": "Sub-Sector", "description": "Communication"},
            "167": {"type": "Sub-Sector", "description": "Other industries"},
            "168": {"type": "Sub-Sector", "description": "R&D Economic affairs"},
            "169": {"type": "Sub-Sector", "description": "Economic affairs n.e.c."},
            
            # Environmental Protection
            "180": {"type": "Sector", "description": "Environmental protection"},
            "181": {"type": "Sub-Sector", "description": "Waste management"},
            "182": {"type": "Sub-Sector", "description": "Waste water management"},
            "183": {"type": "Sub-Sector", "description": "Pollution abatement"},
            "184": {"type": "Sub-Sector", "description": "Protection of biodiversity and landscape"},
            "185": {"type": "Sub-Sector", "description": "R&D Environmental protection"},
            "186": {"type": "Sub-Sector", "description": "Environmental protection n.e.c."},
            
            # Housing and Community Amenities
            "200": {"type": "Sector", "description": "Housing and community amenities"},
            "201": {"type": "Sub-Sector", "description": "Housing development"},
            "202": {"type": "Sub-Sector", "description": "Community development"},
            "203": {"type": "Sub-Sector", "description": "Water supply"},
            "204": {"type": "Sub-Sector", "description": "Street lighting"},
            "205": {"type": "Sub-Sector", "description": "R&D Housing and community amenities"},
            "206": {"type": "Sub-Sector", "description": "Housing and community amenities n.e.c."},
            
            # Health
            "220": {"type": "Sector", "description": "Health"},
            "221": {"type": "Sub-Sector", "description": "Medical products, appliances and equipment"},
            "222": {"type": "Sub-Sector", "description": "Outpatient services"},
            "223": {"type": "Sub-Sector", "description": "Hospital services"},
            "224": {"type": "Sub-Sector", "description": "Public health services"},
            "225": {"type": "Sub-Sector", "description": "R&D Health"},
            "226": {"type": "Sub-Sector", "description": "Health insurance"},
            "227": {"type": "Sub-Sector", "description": "Health n.e.c."},
            
            # Recreation and Culture
            "240": {"type": "Sector", "description": "Recreation and culture"},
            "241": {"type": "Sub-Sector", "description": "Recreational and sporting services"},
            "242": {"type": "Sub-Sector", "description": "Cultural services"},
            "243": {"type": "Sub-Sector", "description": "Broadcasting and publishing services"},
            "244": {"type": "Sub-Sector", "description": "Other community services"},
            "245": {"type": "Sub-Sector", "description": "R&D Recreation and, culture"},
            "246": {"type": "Sub-Sector", "description": "Recreation and, culture n.e.c."},
            
            # Education
            "260": {"type": "Sector", "description": "Education"},
            "261": {"type": "Sub-Sector", "description": "Pre-primary and primary education"},
            "262": {"type": "Sub-Sector", "description": "Secondary education"},
            "263": {"type": "Sub-Sector", "description": "Post-secondary non-tertiary education"},
            "264": {"type": "Sub-Sector", "description": "Tertiary education"},
            "265": {"type": "Sub-Sector", "description": "Education not definable by level"},
            "266": {"type": "Sub-Sector", "description": "Subsidiary services to education"},
            "267": {"type": "Sub-Sector", "description": "R&D Education"},
            "268": {"type": "Sub-Sector", "description": "School Buildings"},
            "269": {"type": "Sub-Sector", "description": "Education n.e.c."},
            "270": {"type": "Sub-Sector", "description": "Pre-Primary, Primary, and Secondary Education"},
            
            # Social Protection
            "280": {"type": "Sector", "description": "Social protection"},
            "281": {"type": "Sub-Sector", "description": "Sickness and disability"},
            "282": {"type": "Sub-Sector", "description": "Old age"},
            "283": {"type": "Sub-Sector", "description": "Survivors"},
            "284": {"type": "Sub-Sector", "description": "Family and children"},
            "285": {"type": "Sub-Sector", "description": "Unemployment"},
            "286": {"type": "Sub-Sector", "description": "Housing"},
            "287": {"type": "Sub-Sector", "description": "Pantawid Pamilya Program or the Conditional Cash Transfer (CCT)"},
            "288": {"type": "Sub-Sector", "description": "Social exclusion n.e.c"},
            "289": {"type": "Sub-Sector", "description": "R&D Social protection"},
            "290": {"type": "Sub-Sector", "description": "Local membership to insurance"},
            "291": {"type": "Sub-Sector", "description": "Conflict-affected areas"},
            "292": {"type": "Sub-Sector", "description": "Social protection n.e.c."},
        }
    
    def parse_prexc_code(self, prexc_code: str) -> Dict:
        """
        Parse 15-digit PREXC code into components
        
        Structure: SECTOR(1) COST(1) OO(2) PROG(2) SUBPROG(2) IDENT(1) ACTIVITY(5) RES(3)
        Example: 310400100002000
        """
        code = str(prexc_code).zfill(15)
        
        return {
            "full_code": code,
            "sector_horizontal": code[0:1],  # Sector/Horizontal outcome
            "cost_structure": code[1:2],     # 1=GAS, 2=STO, 3=Operations
            "org_outcome": code[2:4],        # Organizational Outcome
            "program": code[4:6],            # Program
            "sub_program": code[6:8],        # Sub-program
            "identifier": code[8:9],         # 1=Activity, 2=LFP, 3=FAP
            "activity_project": code[9:14],  # Activity/Project code
            "reserved": code[14:15]          # Reserved
        }
    
    def get_cost_structure_name(self, code: str) -> str:
        """Get cost structure name"""
        mapping = {
            "1": "General Administration and Support (GAS)",
            "2": "Support to Operations (STO)",
            "3": "Operations",
            "4": "Special Purpose Funds (SPF)"
        }
        return mapping.get(code, f"Unknown ({code})")
    
    def get_identifier_type(self, code: str) -> str:
        """Get identifier type"""
        mapping = {
            "1": "Activity",
            "2": "Locally-Funded Project (LFP)",
            "3": "Foreign-Assisted Project (FAP)"
        }
        return mapping.get(code, f"Unknown ({code})")
    
    def convert_prexc_records(self, nep_records: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Convert NEP/GAA records into structured PAP entities
        
        Returns dictionary with separate lists for each level
        """
        sectors = {}
        org_outcomes = {}
        programs = {}
        sub_programs = {}
        activities = {}
        
        for record in nep_records:
            prexc_id = str(record.get('PREXC_FPAP_ID', '')).zfill(15)
            if not prexc_id or prexc_id == '000000000000000':
                continue
            
            parsed = self.parse_prexc_code(prexc_id)
            level = record.get('PREXC_LEVEL', 0)
            description = record.get('DSC', '')
            
            # Sector/Horizontal (digit 1)
            sector_code = parsed['sector_horizontal']
            if sector_code not in sectors:
                sectors[sector_code] = {
                    "code": sector_code,
                    "description": self.sector_outcomes.get(sector_code + "00", {}).get("description", f"Sector {sector_code}"),
                    "type": "sector"
                }
            
            # Organizational Outcome (digits 3-4)
            oo_code = parsed['org_outcome']
            if oo_code != "00" and oo_code not in org_outcomes:
                org_outcomes[oo_code] = {
                    "code": oo_code,
                    "description": f"Organizational Outcome {oo_code}",
                    "sector_code": sector_code,
                    "cost_structure": self.get_cost_structure_name(parsed['cost_structure'])
                }
            
            # Program (digits 5-6)
            prog_code = parsed['program']
            prog_key = f"{oo_code}-{prog_code}"
            if prog_code != "00" and prog_key not in programs:
                programs[prog_key] = {
                    "code": prog_code,
                    "full_code": prexc_id[0:6],
                    "description": description if level == 3 else f"Program {prog_code}",
                    "org_outcome_code": oo_code,
                    "sector_code": sector_code
                }
            
            # Sub-program (digits 7-8)
            subprog_code = parsed['sub_program']
            subprog_key = f"{prog_key}-{subprog_code}"
            if subprog_code != "00" and subprog_key not in sub_programs:
                sub_programs[subprog_key] = {
                    "code": subprog_code,
                    "full_code": prexc_id[0:8],
                    "description": description if level == 4 else f"Sub-program {subprog_code}",
                    "program_code": prog_code,
                    "org_outcome_code": oo_code
                }
            
            # Activity/Project (digits 9-14)
            act_code = parsed['activity_project']
            act_key = f"{subprog_key}-{act_code}"
            if act_code != "00000" and act_key not in activities:
                activities[act_key] = {
                    "code": act_code,
                    "full_code": prexc_id[0:14],
                    "description": description,
                    "prexc_id": prexc_id,
                    "level": level,
                    "identifier_type": self.get_identifier_type(parsed['identifier']),
                    "sub_program_code": subprog_code,
                    "program_code": prog_code,
                    "org_outcome_code": oo_code,
                    "sector_code": sector_code
                }
        
        return {
            "sectors": list(sectors.values()),
            "organizational_outcomes": list(org_outcomes.values()),
            "programs": list(programs.values()),
            "sub_programs": list(sub_programs.values()),
            "activities": list(activities.values())
        }
    
    def save_json(self, data: List[Dict], filename: str):
        """Save data to JSON file"""
        output_path = self.output_dir / filename
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"  → Saved to: {output_path}")
    
    def convert_all(self, nep_sample_file: Optional[str] = None):
        """
        Convert PAP/PREXC data
        
        Args:
            nep_sample_file: Path to NEP/GAA JSON sample file with PREXC codes
        """
        print("\n" + "="*60)
        print("PAP/PREXC CONVERSION")
        print("="*60 + "\n")
        
        # Save sector outcomes
        print("Saving sector outcomes...")
        sector_list = [
            {"code": k, **v} for k, v in self.sector_outcomes.items()
        ]
        self.save_json(sector_list, "sector_outcomes.json")
        
        # Save horizontal programs
        print("Saving horizontal programs...")
        horizontal_list = [
            {"code": k, "description": v} 
            for k, v in self.horizontal_programs.items()
        ]
        self.save_json(horizontal_list, "horizontal_programs.json")
        
        # If NEP sample provided, parse and create hierarchy
        if nep_sample_file:
            print(f"\nParsing PREXC codes from: {nep_sample_file}")
            with open(nep_sample_file, 'r') as f:
                nep_records = json.load(f)
            
            results = self.convert_prexc_records(nep_records)
            
            print(f"\nExtracted PAP hierarchy:")
            print(f"  • {len(results['sectors'])} Sectors")
            print(f"  • {len(results['organizational_outcomes'])} Organizational Outcomes")
            print(f"  • {len(results['programs'])} Programs")
            print(f"  • {len(results['sub_programs'])} Sub-programs")
            print(f"  • {len(results['activities'])} Activities/Projects")
            
            for key, items in results.items():
                self.save_json(items, f"{key}.json")
        
        # Create summary
        summary = {
            "entity": "pap_prexc",
            "total_sector_outcomes": len(self.sector_outcomes),
            "total_horizontal_programs": len(self.horizontal_programs),
            "conversion_date": datetime.now().isoformat(),
            "prexc_structure": {
                "digit_1": "Sector/Horizontal Outcome",
                "digit_2": "Cost Structure (1=GAS, 2=STO, 3=Ops, 4=SPF)",
                "digits_3_4": "Organizational Outcome",
                "digits_5_6": "Program",
                "digits_7_8": "Sub-program",
                "digit_9": "Identifier (1=Activity, 2=LFP, 3=FAP)",
                "digits_10_14": "Activity/Project Code",
                "digit_15": "Reserved"
            },
            "output_files": [
                "sector_outcomes.json",
                "horizontal_programs.json"
            ]
        }
        self.save_json([summary], "_metadata.json")
        
        print("\n" + "="*60)
        print("CONVERSION COMPLETE!")
        print("="*60)
        print(f"\nFiles created in '{self.output_dir}' directory:")
        print("  • sector_outcomes.json")
        print("  • horizontal_programs.json")
        print("  • _metadata.json")
        if nep_sample_file:
            print("  • sectors.json")
            print("  • organizational_outcomes.json")
            print("  • programs.json")
            print("  • sub_programs.json")
            print("  • activities.json")


def main():
    """
    Main execution function
    
    Usage:
        # Convert sector outcomes and horizontal programs
        python converter.py
        
        # Parse PREXC from NEP/GAA sample
        python converter.py --nep-sample nep_sample.json
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='Convert PAP/PREXC data')
    parser.add_argument('--nep-sample', type=str,
                       help='Path to NEP/GAA JSON sample file with PREXC codes')
    
    args = parser.parse_args()
    
    try:
        converter = PAPConverter()
        converter.convert_all(nep_sample_file=args.nep_sample)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()