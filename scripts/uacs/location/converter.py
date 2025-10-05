import pandas as pd
import json
import requests
import time
import re
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime
from html.parser import HTMLParser


class HTMLCodeParser(HTMLParser):
    """Parse HTML-formatted UACS codes from API response"""
    def __init__(self):
        super().__init__()
        self.codes = []
    
    def handle_data(self, data):
        self.codes.append(data.strip())
    
    def get_psgc_code(self):
        """Combine all code segments into PSGC code"""
        return ''.join(self.codes)


class LocationConverter:
    """
    Converts Location (PSGC) Excel files into structured JSON format for Neo4j.
    Handles Region, Province, City/Municipality, and Barangay entities.
    Includes API fetcher to enrich barangay data with actual names.
    
    UACS Location Structure (PSGC): REG(2d) + PROV(2d) + CITY(2d) + BRGY(3d) = 9 digits
    """
    
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.input_dir = self.base_dir / "input"
        project_root = self.base_dir.parent.parent.parent
        self.output_dir = project_root / "data" / "location"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # API configuration
        self.api_url = "https://uacs.gov.ph/api/uacs/reports/generate"
        self.api_params = {
            'elementId': '3',
            'segmentId': '16',
            'query': '',
            'label': '',
            'description': '',
            'parent1UacsCode': '',
            'dateFrom': '',
            'dateTo': ''
        }
    
    def parse_html_code(self, html_code: str) -> str:
        """Extract PSGC code from HTML spans"""
        parser = HTMLCodeParser()
        parser.feed(html_code)
        return parser.get_psgc_code()
    
    def fetch_batch(self, pages: List[int]) -> tuple[List[Dict], List[int]]:
        """
        Fetch multiple pages concurrently
        
        Returns: (records, failed_pages)
        """
        import concurrent.futures
        
        records = []
        failed = []
        
        def fetch_single_page(page):
            try:
                params = self.api_params.copy()
                params['page'] = page
                response = requests.get(self.api_url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
                return page, data.get('data', []), None
            except Exception as e:
                return page, None, str(e)
        
        # Use ThreadPoolExecutor for concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(fetch_single_page, page) for page in pages]
            
            for future in concurrent.futures.as_completed(futures):
                page, data, error = future.result()
                if error:
                    print(f"    ❌ Page {page}: {error}")
                    failed.append(page)
                elif data:
                    records.extend(data)
                    print(f"    ✓ Page {page}: {len(data)} records")
                else:
                    print(f"    ⚠️  Page {page}: No data")
                    failed.append(page)
        
        return records, failed
    
    def fetch_barangays_from_api(self, start_page: int = 1, end_page: int = 1025, 
                                  batch_size: int = 100) -> List[Dict]:
        """
        Fetch barangay data from UACS API using batch processing
        
        Args:
            start_page: Starting page number
            end_page: Ending page number
            batch_size: Number of pages to fetch concurrently (default: 100)
        
        Returns list of parsed barangay records with actual names
        """
        print("\n" + "="*60)
        print("FETCHING BARANGAY DATA FROM UACS API (BATCH MODE)")
        print("="*60 + "\n")
        print(f"Pages to fetch: {start_page} to {end_page}")
        print(f"Batch size: {batch_size} concurrent requests")
        print(f"Total batches: {(end_page - start_page + 1) // batch_size + 1}")
        print(f"Estimated time: ~{(end_page - start_page + 1) / batch_size * 10 / 60:.1f} minutes\n")
        
        all_barangays = []
        all_failed_pages = []
        
        # Process in batches
        for batch_start in range(start_page, end_page + 1, batch_size):
            batch_end = min(batch_start + batch_size - 1, end_page)
            pages = list(range(batch_start, batch_end + 1))
            
            print(f"\nBatch {batch_start}-{batch_end} ({len(pages)} pages):")
            
            # Fetch batch
            records, failed = self.fetch_batch(pages)
            all_barangays.extend(records)
            all_failed_pages.extend(failed)
            
            print(f"  Batch summary: {len(records)} records, {len(failed)} failed")
            print(f"  Total so far: {len(all_barangays)} records")
            
            # Save batch checkpoint
            checkpoint_file = self.output_dir / f"barangays_batch_{batch_start}_{batch_end}.json"
            batch_data = {
                "batch_range": f"{batch_start}-{batch_end}",
                "records_count": len(records),
                "failed_pages": failed,
                "timestamp": datetime.now().isoformat(),
                "data": records
            }
            with open(checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(batch_data, f, indent=2, ensure_ascii=False)
            print(f"  💾 Batch saved to: {checkpoint_file.name}")
            
            # Small delay between batches
            if batch_end < end_page:
                time.sleep(2)
        
        print(f"\n{'='*60}")
        print("FETCH COMPLETE!")
        print(f"{'='*60}")
        print(f"Total records fetched: {len(all_barangays)}")
        print(f"Total failed pages: {len(all_failed_pages)}")
        if all_failed_pages:
            print(f"Failed pages: {sorted(all_failed_pages)[:20]}...")
            
            # Save failed pages for retry
            failed_file = self.output_dir / "failed_pages.json"
            with open(failed_file, 'w') as f:
                json.dump({
                    "failed_pages": sorted(all_failed_pages),
                    "total_failed": len(all_failed_pages),
                    "timestamp": datetime.now().isoformat()
                }, f, indent=2)
            print(f"  💾 Failed pages saved to: {failed_file.name}")
        
        return all_barangays
    
    def parse_barangay_from_api(self, record: Dict) -> Dict:
        """
        Parse barangay record from API response
        
        API Response Format:
        {
            "code": "<span>19</span><span>99</span><span>08</span><span>002</span>",
            "subCode": "002",
            "label": "Bualan",
            "parent1UacsLabel": "Region name",
            "parent2UacsLabel": "Province name",
            "parent3UacsLabel": "City/Municipality name",
            "dateActivated": "Dec 20, 2022",
            "dateDeactivated": null,
            "status": "Active"
        }
        """
        # Parse HTML-formatted PSGC code
        psgc_code = self.parse_html_code(record.get('code', ''))
        if not psgc_code or len(psgc_code) < 9:
            psgc_code = '000000000'
        
        psgc_code = psgc_code.zfill(9)
        
        return {
            "code": record.get('subCode', psgc_code[6:9]),
            "description": record.get('label', f"Barangay {record.get('subCode', '000')}"),
            "region_code": psgc_code[0:2],
            "province_code": psgc_code[2:4],
            "city_code": psgc_code[4:6],
            "psgc_code": psgc_code,
            "region_name": record.get('parent1UacsLabel', ''),
            "province_name": record.get('parent2UacsLabel', ''),
            "city_municipality_name": record.get('parent3UacsLabel', ''),
            "date_activated": record.get('dateActivated'),
            "date_deactivated": record.get('dateDeactivated'),
            "status": record.get('status', 'Active')
        }
    
    def convert_region(self, excel_file: str) -> List[Dict]:
        """Convert region.xlsx to JSON"""
        file_path = self.input_dir / excel_file
        df = pd.read_excel(file_path, sheet_name="UACS Code")
        df.columns = df.columns.str.strip()
        
        regions = []
        for _, row in df.iterrows():
            region_name = str(row.get("Region_1", row.get("Region", ""))).strip()
            
            region = {
                "code": str(row["UACS"]).strip().zfill(2),
                "description": region_name,
                "psgc_code": str(row["UACS"]).strip().zfill(2),
                "status": str(row["Status"]).strip()
            }
            regions.append(region)
        
        print(f"✓ Converted {len(regions)} Regions")
        return regions
    
    def convert_province(self, excel_file: str) -> List[Dict]:
        """Convert province.xlsx to JSON"""
        file_path = self.input_dir / excel_file
        df = pd.read_excel(file_path, sheet_name="UACS Code")
        df.columns = df.columns.str.strip()
        
        provinces = []
        for _, row in df.iterrows():
            psgc = str(row["UACS"]).strip().zfill(4)
            
            province = {
                "code": psgc[2:4],
                "description": str(row["Province"]).strip(),
                "region_code": psgc[0:2],
                "region_name": str(row.get("Region", "")).strip(),
                "psgc_code": psgc,
                "status": str(row["Status"]).strip()
            }
            provinces.append(province)
        
        print(f"✓ Converted {len(provinces)} Provinces")
        return provinces
    
    def convert_city_municipality(self, excel_file: str) -> List[Dict]:
        """Convert municipality.xlsx to JSON"""
        file_path = self.input_dir / excel_file
        df = pd.read_excel(file_path, sheet_name="UACS Code")
        df.columns = df.columns.str.strip()
        
        cities = []
        for _, row in df.iterrows():
            psgc = str(row["UACS"]).strip().zfill(6)
            name = str(row["City/Municipality"]).strip()
            
            city = {
                "code": psgc[4:6],
                "description": name,
                "region_code": psgc[0:2],
                "province_code": psgc[2:4],
                "region_name": str(row.get("Region", "")).strip(),
                "province_name": str(row.get("Province", "")).strip(),
                "psgc_code": psgc,
                "is_city": "City" in name or "city" in name.lower(),
                "status": str(row["Status"]).strip()
            }
            cities.append(city)
        
        print(f"✓ Converted {len(cities)} Cities/Municipalities")
        return cities
    
    def retry_failed_pages(self, failed_pages_file: str = None) -> List[Dict]:
        """
        Retry fetching failed pages
        
        Args:
            failed_pages_file: Path to failed_pages.json file
        """
        if failed_pages_file is None:
            failed_pages_file = self.output_dir / "failed_pages.json"
        else:
            failed_pages_file = Path(failed_pages_file)
        
        if not failed_pages_file.exists():
            print(f"No failed pages file found: {failed_pages_file}")
            return []
        
        with open(failed_pages_file, 'r') as f:
            failed_data = json.load(f)
        
        failed_pages = failed_data.get('failed_pages', [])
        if not failed_pages:
            print("No failed pages to retry")
            return []
        
        print(f"\nRetrying {len(failed_pages)} failed pages...")
        records, still_failed = self.fetch_batch(failed_pages)
        
        if still_failed:
            print(f"\n⚠️  {len(still_failed)} pages still failed")
            # Update failed pages file
            with open(failed_pages_file, 'w') as f:
                json.dump({
                    "failed_pages": sorted(still_failed),
                    "total_failed": len(still_failed),
                    "timestamp": datetime.now().isoformat(),
                    "retry_attempt": failed_data.get('retry_attempt', 0) + 1
                }, f, indent=2)
        else:
            print("✓ All failed pages successfully retried!")
            # Remove failed pages file
            failed_pages_file.unlink()
        
        return records
    
    def convert_barangay_with_api(self, use_api: bool = True, 
                                   start_page: int = 1, 
                                   end_page: int = 1025,
                                   batch_size: int = 100) -> List[Dict]:
        """
        Convert barangay data using API or Excel file
        
        Args:
            use_api: If True, fetch from API. If False, use Excel file.
            start_page: API start page
            end_page: API end page
            batch_size: Number of concurrent requests per batch (default: 100)
        """
        if use_api:
            print("\nUsing UACS API for barangay data...")
            api_records = self.fetch_barangays_from_api(start_page, end_page, batch_size)
            
            # Save raw API data
            self.save_json(api_records, "barangays_api_raw.json")
            
            # Parse and convert
            barangays = []
            for record in api_records:
                try:
                    barangay = self.parse_barangay_from_api(record)
                    barangays.append(barangay)
                except Exception as e:
                    print(f"⚠️  Error parsing record: {e}")
                    continue
            
            print(f"✓ Converted {len(barangays)} Barangays from API")
            
        else:
            print("\nUsing Excel file for barangay data...")
            file_path = self.input_dir / "barangay .xlsx"
            df = pd.read_excel(file_path, sheet_name="UACS Code")
            df.columns = df.columns.str.strip()
            
            barangays = []
            for _, row in df.iterrows():
                psgc = str(row["UACS"]).strip().zfill(9)
                
                barangay = {
                    "code": psgc[6:9],
                    "description": f"Barangay {psgc[6:9]}",
                    "region_code": psgc[0:2],
                    "province_code": psgc[2:4],
                    "city_code": psgc[4:6],
                    "psgc_code": psgc,
                    "region_name": "",
                    "province_name": "",
                    "city_municipality_name": "",
                    "date_activated": None,
                    "date_deactivated": None,
                    "status": str(row["Status"]).strip()
                }
                barangays.append(barangay)
            
            print(f"✓ Converted {len(barangays)} Barangays from Excel")
        
        return barangays
    
    def create_location_composite(self, barangays: List[Dict]) -> List[Dict]:
        """Create Location composite nodes (9-digit PSGC)"""
        locations = []
        
        for brgy in barangays:
            location = {
                "psgc_code": brgy["psgc_code"],
                "description": brgy["description"],
                "region_code": brgy["region_code"],
                "province_code": brgy["province_code"],
                "city_code": brgy["city_code"],
                "barangay_code": brgy["code"],
                "region_name": brgy.get("region_name", ""),
                "province_name": brgy.get("province_name", ""),
                "city_municipality_name": brgy.get("city_municipality_name", ""),
                "date_activated": brgy.get("date_activated"),
                "date_deactivated": brgy.get("date_deactivated"),
                "status": brgy["status"]
            }
            locations.append(location)
        
        print(f"✓ Created {len(locations)} Location Composites")
        return locations
    
    def save_json(self, data: List[Dict], filename: str):
        """Save data to JSON file"""
        output_path = self.output_dir / filename
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"  → Saved to: {output_path}")
    
    def convert_all(self, use_api: bool = True, api_start: int = 1, api_end: int = 1025,
                    batch_size: int = 100, retry_failed: bool = False):
        """
        Convert all location files and save to JSON
        
        Args:
            use_api: Fetch barangay data from UACS API (recommended)
            api_start: API start page
            api_end: API end page
            batch_size: Number of concurrent requests per batch
            retry_failed: Retry previously failed pages
        """
        print("\n" + "="*60)
        print("LOCATION (PSGC) CONVERSION")
        print("="*60 + "\n")
        print(f"Input directory: {self.input_dir}")
        print(f"Output directory: {self.output_dir}")
        print(f"Barangay source: {'UACS API' if use_api else 'Excel file'}")
        print(f"Batch size: {batch_size} concurrent requests\n")
        
        # Retry failed pages if requested
        if retry_failed:
            retry_records = self.retry_failed_pages()
            if retry_records:
                # Save retry results
                self.save_json(retry_records, "barangays_retry_results.json")
                print(f"\n✓ Retry completed: {len(retry_records)} records recovered")
        
        # Convert individual entities
        print("Converting individual entities...")
        regions = self.convert_region("region 3.xlsx")
        self.save_json(regions, "regions.json")
        
        provinces = self.convert_province("province .xlsx")
        self.save_json(provinces, "provinces.json")
        
        cities = self.convert_city_municipality("municipality.xlsx")
        self.save_json(cities, "cities_municipalities.json")
        
        barangays = self.convert_barangay_with_api(use_api, api_start, api_end, batch_size)
        self.save_json(barangays, "barangays.json")
        
        print("\nCreating composite entities...")
        locations = self.create_location_composite(barangays)
        self.save_json(locations, "locations.json")
        
        # Create summary
        summary = {
            "entity": "location",
            "barangay_source": "UACS API" if use_api else "Excel file",
            "total_regions": len(regions),
            "total_provinces": len(provinces),
            "total_cities_municipalities": len(cities),
            "total_barangays": len(barangays),
            "total_locations": len(locations),
            "conversion_date": datetime.now().isoformat(),
            "input_files": [
                "region 3.xlsx",
                "province .xlsx",
                "municipality.xlsx",
                "barangay .xlsx (optional)" if use_api else "barangay .xlsx"
            ],
            "output_files": [
                "regions.json",
                "provinces.json",
                "cities_municipalities.json",
                "barangays.json",
                "locations.json"
            ]
        }
        
        if use_api:
            summary["api_pages_fetched"] = f"{api_start}-{api_end}"
            summary["output_files"].append("barangays_api_raw.json")
        
        self.save_json([summary], "_metadata.json")
        
        print("\n" + "="*60)
        print("CONVERSION COMPLETE!")
        print("="*60)
        print(f"\nFiles created in '{self.output_dir}' directory:")
        print("  • regions.json")
        print("  • provinces.json")
        print("  • cities_municipalities.json")
        print("  • barangays.json (with actual names!)" if use_api else "  • barangays.json (placeholder names)")
        print("  • locations.json (composite)")
        print("  • _metadata.json")
        if use_api:
            print("  • barangays_api_raw.json (raw API data)")
        
        return {
            "regions": regions,
            "provinces": provinces,
            "cities": cities,
            "barangays": barangays,
            "locations": locations
        }


def main():
    """
    Main execution function
    
    Usage:
        # Use API with default batch size (100 concurrent requests)
        python converter.py
        
        # Use Excel file only (placeholder names)
        python converter.py --no-api
        
        # API with custom batch size
        python converter.py --batch-size 50
        
        # API with custom page range (for testing)
        python converter.py --api-start 1 --api-end 10
        
        # Retry previously failed pages
        python converter.py --retry-failed
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='Convert PSGC Location data')
    parser.add_argument('--no-api', action='store_true', 
                       help='Use Excel file instead of API for barangays')
    parser.add_argument('--api-start', type=int, default=1, 
                       help='API start page (default: 1)')
    parser.add_argument('--api-end', type=int, default=1025, 
                       help='API end page (default: 1025)')
    parser.add_argument('--batch-size', type=int, default=100,
                       help='Number of concurrent requests per batch (default: 100)')
    parser.add_argument('--retry-failed', action='store_true',
                       help='Retry previously failed pages')
    
    args = parser.parse_args()
    
    try:
        converter = LocationConverter()
        results = converter.convert_all(
            use_api=not args.no_api,
            api_start=args.api_start,
            api_end=args.api_end,
            batch_size=args.batch_size,
            retry_failed=args.retry_failed
        )
        
        # Display sample data
        print("\n" + "="*60)
        print("SAMPLE DATA")
        print("="*60)
        
        print("\nSample Region:")
        print(json.dumps(results["regions"][5], indent=2))
        
        print("\nSample Province:")
        print(json.dumps(results["provinces"][0], indent=2))
        
        print("\nSample City/Municipality:")
        print(json.dumps(results["cities"][0], indent=2))
        
        print("\nSample Barangay:")
        print(json.dumps(results["barangays"][0], indent=2))
        
        print("\nSample Location (Composite):")
        print(json.dumps(results["locations"][0], indent=2))
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled by user")
        print("   Progress checkpoints have been saved")
    except FileNotFoundError as e:
        print(f"\n❌ Error: Could not find input file - {e}")
        print("\nPlease ensure the following files exist in the 'input' directory:")
        print("  • region 3.xlsx")
        print("  • province .xlsx")
        print("  • municipality.xlsx")
        print("  • barangay .xlsx (optional if using API)")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()