import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import re


class YearBasedBudgetConverter:
    """
    Converts budget files into year-based structure with:
    - budget-mapping.json (metadata and unique UACS codes)
    - items/ folder with individual budget records
    """
    
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.input_dir = self.base_dir / "input"
        project_root = self.base_dir.parent.parent
        self.output_dir = project_root / "data" / "budget"
        
        # Load fund categories for 6-digit conversion
        self.fund_category_lookup = self.load_fund_categories()
    
    def load_fund_categories(self) -> Dict[str, str]:
        """Load fund categories for 6-digit funding code conversion"""
        fund_cat_path = self.base_dir.parent.parent / "data" / "funding_source" / "fund_categories.json"
        
        if not fund_cat_path.exists():
            print(f"⚠️  Fund categories not found, 6-digit conversion disabled")
            return {}
        
        lookup = {}
        with open(fund_cat_path, 'r', encoding='utf-8') as f:
            categories = json.load(f)
            for cat in categories:
                uacs = cat.get('uacs_code', '')
                if len(uacs) == 8:
                    lookup[uacs[2:8]] = uacs
        
        return lookup
    
    def detect_budget_type_and_year(self, record: Dict, filename: str) -> tuple[str, str]:
        """Detect budget type and year"""
        filename_upper = filename.upper()
        year_match = re.search(r'(\d{4})', filename)
        year_from_filename = year_match.group(1) if year_match else None
        
        if 'GAA' in filename_upper:
            return ("GAA", year_from_filename or "UNKNOWN")
        elif 'NEP' in filename_upper:
            return ("NEP", year_from_filename or "UNKNOWN")
        
        if "YEAR" in record and record["YEAR"]:
            year_match = re.search(r'(\d{4})', str(record["YEAR"]))
            if year_match:
                return ("GAA", year_match.group(1))
        
        if "LVL" in record and record["LVL"]:
            year_match = re.search(r'FY(\d{4})', str(record["LVL"]))
            if year_match:
                return ("NEP", year_match.group(1))
        
        return ("NEP", year_from_filename or "UNKNOWN")
    
    def is_valid_value(self, value) -> bool:
        """Check if value is valid"""
        if value is None:
            return False
        if isinstance(value, str):
            return value.strip() != ""
        return True
    
    def parse_organization_code(self, dept, agency, operunit) -> Optional[str]:
        """Build 12-digit organization UACS code"""
        if not self.is_valid_value(dept) or not self.is_valid_value(agency) or not self.is_valid_value(operunit):
            return None
        
        dept_str = str(dept).strip().zfill(2)
        agency_str = str(agency).strip().zfill(3)
        operunit_str = str(operunit).strip().zfill(7)
        
        code = f"{dept_str}{agency_str}{operunit_str}"
        return None if code == "000000000000" else code
    
    def parse_region_code(self, region) -> Optional[str]:
        """Parse 2-digit region code"""
        if not self.is_valid_value(region):
            return None
        region_str = str(region).strip().zfill(2)
        return None if region_str == "00" else region_str
    
    def parse_funding_code(self, fundcd) -> Optional[Dict]:
        """Parse funding code, converting 6-digit if needed"""
        if not self.is_valid_value(fundcd):
            return None
        
        fundcd_str = str(fundcd).strip()
        
        if len(fundcd_str) == 8:
            if fundcd_str == "00000000":
                return None
            return {
                "uacs_code": fundcd_str,
                "conversion_type": "native"
            }
        elif len(fundcd_str) == 6 and fundcd_str in self.fund_category_lookup:
            return {
                "uacs_code": self.fund_category_lookup[fundcd_str],
                "conversion_type": "6-digit-lookup",
                "original_code": fundcd_str
            }
        
        return None
    
    def parse_object_code(self, record: Dict) -> Optional[Dict]:
        """Parse object code"""
        obj_cd = record.get("UACS_SOBJ_CD") or record.get("UACS_OBJ_CD")
        if not self.is_valid_value(obj_cd):
            return None
        
        obj_str = str(obj_cd).strip().zfill(10)
        return None if obj_str == "0000000000" else {"uacs_code": obj_str}
    
    def clean_amount(self, amount) -> float:
        """Clean and convert amount to float"""
        if amount is None or amount == "":
            return 0.0
        try:
            return float(str(amount).replace(",", ""))
        except:
            return 0.0
    
    def safe_get(self, record: Dict, key: str, default: str = "") -> str:
        """Safely get value from record"""
        value = record.get(key, default)
        return default if value is None else str(value).strip()
    
    def convert_record(self, record: Dict, budget_type: str, year: str, record_number: int) -> Dict:
        """Convert a single budget record"""
        org_code = self.parse_organization_code(
            record.get("DEPARTMENT"),
            record.get("AGENCY"),
            record.get("OPERUNIT")
        )
        
        region_code = self.parse_region_code(record.get("UACS_REG_ID"))
        funding_info = self.parse_funding_code(record.get("FUNDCD"))
        object_info = self.parse_object_code(record)
        
        prexc_id = self.safe_get(record, "PREXC_FPAP_ID", "000000000000000").zfill(15)
        record_id = f"{budget_type}-{year}-{str(record_number).zfill(10)}"
        
        result = {
            "id": record_id,
            "budget_type": budget_type,
            "fiscal_year": year,
            "amount": self.clean_amount(record.get("AMT")),
            "description": self.safe_get(record, "DSC"),
            "prexc_fpap_id": prexc_id,
        }
        
        if org_code:
            result["org_uacs_code"] = org_code
        if region_code:
            result["region_code"] = region_code
        if funding_info:
            result["funding_uacs_code"] = funding_info["uacs_code"]
            result["funding_conversion_type"] = funding_info.get("conversion_type")
        if object_info:
            result["object_uacs_code"] = object_info["uacs_code"]
        
        return result
    
    def create_budget_mapping(self, records: List[Dict], budget_type: str, year: str) -> Dict:
        """Create budget-mapping.json with metadata and unique codes"""
        unique_orgs = set()
        unique_fundings = set()
        unique_objects = set()
        unique_regions = set()
        unique_prexc = set()
        
        total_amount = 0
        
        for record in records:
            if record.get("org_uacs_code"):
                unique_orgs.add(record["org_uacs_code"])
            if record.get("funding_uacs_code"):
                unique_fundings.add(record["funding_uacs_code"])
            if record.get("object_uacs_code"):
                unique_objects.add(record["object_uacs_code"])
            if record.get("region_code"):
                unique_regions.add(record["region_code"])
            if record.get("prexc_fpap_id"):
                unique_prexc.add(record["prexc_fpap_id"])
            total_amount += record.get("amount", 0)
        
        return {
            "metadata": {
                "budget_type": budget_type,
                "fiscal_year": year,
                "total_records": len(records),
                "total_amount": total_amount,
                "conversion_date": datetime.now().isoformat()
            },
            "unique_codes": {
                "organizations": sorted(list(unique_orgs)),
                "funding_sources": sorted(list(unique_fundings)),
                "object_codes": sorted(list(unique_objects)),
                "regions": sorted(list(unique_regions)),
                "prexc_codes": sorted(list(unique_prexc))
            },
            "statistics": {
                "unique_organizations": len(unique_orgs),
                "unique_funding_sources": len(unique_fundings),
                "unique_object_codes": len(unique_objects),
                "unique_regions": len(unique_regions),
                "unique_prexc_codes": len(unique_prexc)
            }
        }
    
    def convert_file(self, input_file: str, batch_size: int = 100000):
        """Convert a single budget file into batched items"""
        input_path = self.input_dir / input_file
        
        print(f"\nProcessing: {input_file}")
        
        with open(input_path, 'r', encoding='utf-8') as f:
            records = json.load(f)
        
        if not records:
            print(f"  ⚠️  No records found")
            return
        
        budget_type, year = self.detect_budget_type_and_year(records[0], input_file)
        
        print(f"  Type: {budget_type}")
        print(f"  Year: {year}")
        print(f"  Records: {len(records):,}")
        print(f"  Batch size: {batch_size:,} records per file")
        
        # Create year directory structure
        year_dir = self.output_dir / year
        items_dir = year_dir / "items"
        items_dir.mkdir(parents=True, exist_ok=True)
        
        # Convert records in batches
        converted = []
        batch_files = []
        batch_number = 1
        current_batch = []
        
        for idx, record in enumerate(records, start=1):
            converted_record = self.convert_record(record, budget_type, year, idx)
            converted.append(converted_record)
            current_batch.append(converted_record)
            
            # Save batch when it reaches batch_size or at the end
            if len(current_batch) >= batch_size or idx == len(records):
                batch_filename = f"{budget_type.lower()}_{year}_batch_{str(batch_number).zfill(4)}.json"
                batch_path = items_dir / batch_filename
                
                with open(batch_path, 'w', encoding='utf-8') as f:
                    json.dump(current_batch, f, indent=2, ensure_ascii=False)
                
                batch_files.append(batch_filename)
                print(f"    Batch {batch_number}: {len(current_batch):,} records → {batch_filename}")
                
                current_batch = []
                batch_number += 1
            
            if idx % 50000 == 0:
                print(f"    Progress: {idx:,}/{len(records):,}")
        
        # Create budget-mapping.json
        mapping = self.create_budget_mapping(converted, budget_type, year)
        mapping["batch_info"] = {
            "batch_size": batch_size,
            "total_batches": len(batch_files),
            "batch_files": batch_files
        }
        
        mapping_path = year_dir / "budget-mapping.json"
        with open(mapping_path, 'w', encoding='utf-8') as f:
            json.dump(mapping, f, indent=2, ensure_ascii=False)
        
        print(f"  ✓ Created:")
        print(f"    - {year}/budget-mapping.json")
        print(f"    - {year}/items/ ({len(batch_files)} batch files)")
        
        return mapping
    
    def convert_all(self):
        """Convert all budget files"""
        print("\n" + "="*60)
        print("YEAR-BASED BUDGET CONVERSION")
        print("="*60)
        print(f"\nInput directory: {self.input_dir}")
        print(f"Output directory: {self.output_dir}")
        
        json_files = sorted(self.input_dir.glob("*.json"))
        
        if not json_files:
            print("\n⚠️  No JSON files found")
            return
        
        print(f"\nFound {len(json_files)} file(s) to process")
        
        results = []
        for json_file in json_files:
            result = self.convert_file(json_file.name)
            if result:
                results.append(result)
        
        print("\n" + "="*60)
        print("CONVERSION COMPLETE!")
        print("="*60)
        print(f"\nConverted {len(results)} budget file(s)")
        for result in results:
            meta = result["metadata"]
            print(f"  - {meta['fiscal_year']} {meta['budget_type']}: {meta['total_records']:,} items")


def main():
    try:
        converter = YearBasedBudgetConverter()
        converter.convert_all()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()