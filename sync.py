import json
from pathlib import Path
from typing import Dict, List
from neo4j import GraphDatabase
import time


class Neo4jSync:
    """
    Syncs all converted UACS and budget data to Neo4j database.
    Supports year-based batched budget structure.
    """
    
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.data_dir = Path("data")
        
    def close(self):
        self.driver.close()
    
    def batch_create_nodes(self, tx, label: str, nodes: List[Dict], unique_key: str):
        """Create nodes in batch using UNWIND"""
        query = f"""
        UNWIND $nodes AS node
        MERGE (n:{label} {{{unique_key}: node.{unique_key}}})
        SET n += node
        RETURN count(n) as created
        """
        result = tx.run(query, nodes=nodes)
        return result.single()["created"]
    
    def load_json_file(self, filepath: Path) -> List[Dict]:
        """Load JSON file and return data"""
        if not filepath.exists():
            print(f"  ⚠️  File not found: {filepath}")
            return []
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, list) else [data]
    
    def create_relationships_simple(self, session, query: str, description: str) -> int:
        """Execute a simple relationship creation query and return count"""
        try:
            result = session.run(query)
            summary = result.consume()
            count = summary.counters.relationships_created
            print(f"    ✓ {description}: {count}")
            return count
        except Exception as e:
            print(f"    ✗ {description}: ERROR - {e}")
            return 0
    
    def sync_funding_source(self):
        """Load Funding Source dimension"""
        print("\n" + "="*60)
        print("SYNCING FUNDING SOURCE")
        print("="*60)
        
        base_path = self.data_dir / "funding_source"
        
        with self.driver.session() as session:
            data = self.load_json_file(base_path / "fund_clusters.json")
            if data:
                result = session.execute_write(self.batch_create_nodes, "FundCluster", data, "code")
                print(f"  ✓ Fund Clusters: {result}")
            
            data = self.load_json_file(base_path / "financing_sources.json")
            if data:
                result = session.execute_write(self.batch_create_nodes, "FinancingSource", data, "code")
                print(f"  ✓ Financing Sources: {result}")
            
            data = self.load_json_file(base_path / "authorizations.json")
            if data:
                result = session.execute_write(self.batch_create_nodes, "Authorization", data, "code")
                print(f"  ✓ Authorizations: {result}")
            
            data = self.load_json_file(base_path / "fund_categories.json")
            if data:
                result = session.execute_write(self.batch_create_nodes, "FundCategory", data, "uacs_code")
                print(f"  ✓ Fund Categories: {result}")
            
            data = self.load_json_file(base_path / "funding_sources.json")
            if data:
                result = session.execute_write(self.batch_create_nodes, "FundingSource", data, "uacs_code")
                print(f"  ✓ Funding Sources: {result}")
            
            print("\n  Creating funding source relationships...")
            
            self.create_relationships_simple(session, """
                MATCH (fc:FundCluster)
                MATCH (fcat:FundCategory {fund_cluster: fc.description})
                MATCH (fin:FinancingSource {description: fcat.financing_source})
                MERGE (fc)-[:HAS_FINANCING_SOURCE]->(fin)
            """, "FundCluster → FinancingSource")
            
            self.create_relationships_simple(session, """
                MATCH (fin:FinancingSource)
                MATCH (fcat:FundCategory {financing_source: fin.description})
                MATCH (auth:Authorization {description: fcat.authorization})
                MERGE (fin)-[:HAS_AUTHORIZATION]->(auth)
            """, "FinancingSource → Authorization")
            
            self.create_relationships_simple(session, """
                MATCH (auth:Authorization)
                MATCH (fcat:FundCategory {authorization: auth.description})
                MERGE (auth)-[:HAS_FUND_CATEGORY]->(fcat)
            """, "Authorization → FundCategory")
            
            self.create_relationships_simple(session, """
                MATCH (fcat:FundCategory)
                MATCH (fs:FundingSource {uacs_code: fcat.uacs_code})
                MERGE (fcat)-[:HAS_FUNDING_SOURCE]->(fs)
            """, "FundCategory → FundingSource")
    
    def sync_organization(self):
        """Load Organization dimension"""
        print("\n" + "="*60)
        print("SYNCING ORGANIZATION")
        print("="*60)
        
        base_path = self.data_dir / "organization"
        
        with self.driver.session() as session:
            data = self.load_json_file(base_path / "departments.json")
            if data:
                result = session.execute_write(self.batch_create_nodes, "Department", data, "code")
                print(f"  ✓ Departments: {result}")
            
            data = self.load_json_file(base_path / "agencies.json")
            if data:
                result = session.execute_write(self.batch_create_nodes, "Agency", data, "uacs_code")
                print(f"  ✓ Agencies: {result}")
            
            data = self.load_json_file(base_path / "operating_unit_classes.json")
            if data:
                result = session.execute_write(self.batch_create_nodes, "OperatingUnitClass", data, "code")
                print(f"  ✓ Operating Unit Classes: {result}")
            
            data = self.load_json_file(base_path / "operating_units.json")
            if data:
                result = session.execute_write(self.batch_create_nodes, "OperatingUnit", data, "uacs_code")
                print(f"  ✓ Operating Units: {result}")
            
            data = self.load_json_file(base_path / "organizations.json")
            if data:
                result = session.execute_write(self.batch_create_nodes, "Organization", data, "uacs_code")
                print(f"  ✓ Organizations: {result}")
            
            print("\n  Creating organization relationships...")
            
            self.create_relationships_simple(session, """
                MATCH (d:Department)
                MATCH (a:Agency {department_code: d.code})
                MERGE (d)-[:HAS_AGENCY]->(a)
            """, "Department → Agency")
            
            self.create_relationships_simple(session, """
                MATCH (a:Agency)
                MATCH (ou:OperatingUnit)
                WHERE ou.department_code + ou.agency_code = a.uacs_code
                MATCH (ouc:OperatingUnitClass {code: ou.class_code})
                MERGE (a)-[:HAS_OPERATING_UNIT_CLASS]->(ouc)
            """, "Agency → OperatingUnitClass")
            
            self.create_relationships_simple(session, """
                MATCH (ouc:OperatingUnitClass)
                MATCH (ou:OperatingUnit {class_code: ouc.code})
                MERGE (ouc)-[:HAS_OPERATING_UNIT]->(ou)
            """, "OperatingUnitClass → OperatingUnit")
    
    def sync_location(self):
        """Load Location dimension"""
        print("\n" + "="*60)
        print("SYNCING LOCATION")
        print("="*60)
        
        base_path = self.data_dir / "location"
        
        with self.driver.session() as session:
            data = self.load_json_file(base_path / "regions.json")
            if data:
                result = session.execute_write(self.batch_create_nodes, "Region", data, "code")
                print(f"  ✓ Regions: {result}")
            
            data = self.load_json_file(base_path / "provinces.json")
            if data:
                result = session.execute_write(self.batch_create_nodes, "Province", data, "psgc_code")
                print(f"  ✓ Provinces: {result}")
            
            data = self.load_json_file(base_path / "cities_municipalities.json")
            if data:
                result = session.execute_write(self.batch_create_nodes, "CityMunicipality", data, "psgc_code")
                print(f"  ✓ Cities/Municipalities: {result}")
            
            print("  Loading barangays...")
            data = self.load_json_file(base_path / "barangays.json")
            if data:
                batch_size = 10000
                total = len(data)
                for i in range(0, total, batch_size):
                    batch = data[i:i+batch_size]
                    session.execute_write(self.batch_create_nodes, "Barangay", batch, "psgc_code")
                    print(f"    Progress: {min(i+batch_size, total):,}/{total:,}")
                print(f"  ✓ Barangays: {total:,}")
            
            print("\n  Creating location relationships...")
            
            self.create_relationships_simple(session, """
                MATCH (r:Region)
                MATCH (p:Province {region_code: r.code})
                MERGE (r)-[:HAS_PROVINCE]->(p)
            """, "Region → Province")
            
            self.create_relationships_simple(session, """
                MATCH (p:Province)
                MATCH (c:CityMunicipality)
                WHERE c.region_code + c.province_code = p.psgc_code
                MERGE (p)-[:HAS_CITY]->(c)
            """, "Province → City")
            
            print("  Creating barangay relationships (batched)...")
            batch_size = 50000
            offset = 0
            total_created = 0
            while True:
                result = session.run("""
                    MATCH (c:CityMunicipality)
                    MATCH (b:Barangay)
                    WHERE c.psgc_code = b.region_code + b.province_code + b.city_code
                    WITH c, b SKIP $offset LIMIT $batch
                    MERGE (c)-[:HAS_BARANGAY]->(b)
                    RETURN count(*) as created
                """, offset=offset, batch=batch_size)
                created = result.single()["created"]
                total_created += created
                if created == 0:
                    break
                offset += batch_size
                print(f"    Progress: {total_created:,}...")
            print(f"    ✓ City → Barangay: {total_created:,}")
    
    def sync_pap(self):
        """Load PAP/PREXC reference data"""
        print("\n" + "="*60)
        print("SYNCING PAP/PREXC REFERENCE DATA")
        print("="*60)
        
        base_path = self.data_dir / "pap"
        
        with self.driver.session() as session:
            data = self.load_json_file(base_path / "sector_outcomes.json")
            if data:
                result = session.execute_write(self.batch_create_nodes, "SectorOutcome", data, "code")
                print(f"  ✓ Sector Outcomes: {result}")
            
            data = self.load_json_file(base_path / "horizontal_programs.json")
            if data:
                result = session.execute_write(self.batch_create_nodes, "HorizontalProgram", data, "code")
                print(f"  ✓ Horizontal Programs: {result}")
    
    def sync_object_code(self):
        """Load Object Code dimension"""
        print("\n" + "="*60)
        print("SYNCING OBJECT CODE")
        print("="*60)
        
        base_path = self.data_dir / "object_code"
        
        with self.driver.session() as session:
            data = self.load_json_file(base_path / "classifications.json")
            if data:
                result = session.execute_write(self.batch_create_nodes, "Classification", data, "code")
                print(f"  ✓ Classifications: {result}")
            
            data = self.load_json_file(base_path / "sub_classes.json")
            if data:
                result = session.execute_write(self.batch_create_nodes, "SubClass", data, "code")
                print(f"  ✓ Sub-Classes: {result}")
            
            data = self.load_json_file(base_path / "groups.json")
            if data:
                result = session.execute_write(self.batch_create_nodes, "ExpenseGroup", data, "full_code")
                print(f"  ✓ Groups: {result}")
            
            data = self.load_json_file(base_path / "objects.json")
            if data:
                result = session.execute_write(self.batch_create_nodes, "Object", data, "full_code")
                print(f"  ✓ Objects: {result}")
            
            data = self.load_json_file(base_path / "sub_objects.json")
            if data:
                result = session.execute_write(self.batch_create_nodes, "SubObject", data, "uacs_code")
                print(f"  ✓ Sub-Objects: {result}")
            
            print("\n  Creating expense classification relationships...")
            
            self.create_relationships_simple(session, """
                MATCH (c:Classification)
                MATCH (sc:SubClass {classification_code: c.code})
                MERGE (c)-[:HAS_SUB_CLASS]->(sc)
            """, "Classification → SubClass")
            
            self.create_relationships_simple(session, """
                MATCH (sc:SubClass)
                MATCH (eg:ExpenseGroup {sub_class_code: sc.code, classification_code: sc.classification_code})
                MERGE (sc)-[:HAS_GROUP]->(eg)
            """, "SubClass → ExpenseGroup")
            
            count1 = self.create_relationships_simple(session, """
                MATCH (eg:ExpenseGroup)
                MATCH (o:Object {group_code: eg.code, sub_class_code: eg.sub_class_code, classification_code: eg.classification_code})
                MERGE (eg)-[:HAS_OBJECT]->(o)
            """, "ExpenseGroup → Object")
            
            if count1 == 0:
                self.create_relationships_simple(session, """
                    MATCH (eg:ExpenseGroup)
                    MATCH (o:ExpenseObject {group_code: eg.code, sub_class_code: eg.sub_class_code, classification_code: eg.classification_code})
                    MERGE (eg)-[:HAS_OBJECT]->(o)
                """, "ExpenseGroup → ExpenseObject")
            
            count2 = self.create_relationships_simple(session, """
                MATCH (o:Object)
                MATCH (so:SubObject {object_code: o.code, group_code: o.group_code, sub_class_code: o.sub_class_code, classification_code: o.classification_code})
                MERGE (o)-[:HAS_SUB_OBJECT]->(so)
            """, "Object → SubObject")
            
            if count2 == 0:
                self.create_relationships_simple(session, """
                    MATCH (o:ExpenseObject)
                    MATCH (so:SubObject {object_code: o.code, group_code: o.group_code, sub_class_code: o.sub_class_code, classification_code: o.classification_code})
                    MERGE (o)-[:HAS_SUB_OBJECT]->(so)
                """, "ExpenseObject → SubObject")
    
    def sync_budget_records(self, fiscal_year: str, budget_type: str):
        """Load budget records from batched files"""
        print(f"\n  Loading {budget_type} {fiscal_year}...")
        
        year_dir = self.data_dir / "budget" / fiscal_year
        items_dir = year_dir / "items"
        
        if not items_dir.exists():
            print(f"    ⚠️  No items directory found")
            return
        
        # Load all batch files
        batch_files = sorted(items_dir.glob(f"{budget_type.lower()}_{fiscal_year}_batch_*.json"))
        
        if not batch_files:
            print(f"    ⚠️  No batch files found")
            return
        
        print(f"    Found {len(batch_files)} batch file(s)")
        
        # Load all records from batches
        data = []
        for batch_file in batch_files:
            with open(batch_file, 'r', encoding='utf-8') as f:
                batch_data = json.load(f)
                data.extend(batch_data)
            print(f"      Loaded: {batch_file.name} ({len(batch_data):,} records)")
        
        print(f"    Total records: {len(data):,}")
        
        with self.driver.session() as session:
            print(f"    Creating budget nodes...")
            batch_size = 5000
            total = len(data)
            for i in range(0, total, batch_size):
                batch = data[i:i+batch_size]
                session.execute_write(self.batch_create_nodes, "BudgetRecord", batch, "id")
                progress = min(i+batch_size, total)
                pct = (progress / total) * 100
                print(f"      Progress: {progress:,}/{total:,} ({pct:.1f}%)")
            
            print(f"    ✓ Budget records created: {total:,}")
            print(f"\n    Creating budget relationships...")
            
            # To FundingSource
            print(f"      → FundingSource...")
            total_count = 0
            offset = 0
            rel_batch = 10000
            while True:
                result = session.run("""
                    MATCH (br:BudgetRecord {fiscal_year: $year, budget_type: $type})
                    WHERE br.funding_uacs_code IS NOT NULL
                    WITH br SKIP $offset LIMIT $batch
                    MATCH (fs:FundingSource {uacs_code: br.funding_uacs_code})
                    MERGE (br)-[:FUNDED_BY]->(fs)
                    RETURN count(*) as count
                """, year=fiscal_year, type=budget_type, offset=offset, batch=rel_batch)
                count = result.single()["count"]
                total_count += count
                if count == 0:
                    break
                offset += rel_batch
            print(f"        ✓ Created: {total_count:,}")
            
            # To Organization
            print(f"      → Organization...")
            total_count = 0
            offset = 0
            while True:
                result = session.run("""
                    MATCH (br:BudgetRecord {fiscal_year: $year, budget_type: $type})
                    WHERE br.org_uacs_code IS NOT NULL
                    WITH br SKIP $offset LIMIT $batch
                    MATCH (org:Organization {uacs_code: br.org_uacs_code})
                    MERGE (br)-[:ALLOCATED_TO]->(org)
                    RETURN count(*) as count
                """, year=fiscal_year, type=budget_type, offset=offset, batch=rel_batch)
                count = result.single()["count"]
                total_count += count
                if count == 0:
                    break
                offset += rel_batch
            print(f"        ✓ Created: {total_count:,}")
            
            # To Region
            print(f"      → Region...")
            total_count = 0
            offset = 0
            while True:
                result = session.run("""
                    MATCH (br:BudgetRecord {fiscal_year: $year, budget_type: $type})
                    WHERE br.region_code IS NOT NULL AND br.region_code <> '00'
                    WITH br SKIP $offset LIMIT $batch
                    MATCH (r:Region {code: br.region_code})
                    MERGE (br)-[:LOCATED_IN_REGION]->(r)
                    RETURN count(*) as count
                """, year=fiscal_year, type=budget_type, offset=offset, batch=rel_batch)
                count = result.single()["count"]
                total_count += count
                if count == 0:
                    break
                offset += rel_batch
            print(f"        ✓ Created: {total_count:,}")
            
            # To SubObject
            print(f"      → SubObject...")
            total_count = 0
            offset = 0
            while True:
                result = session.run("""
                    MATCH (br:BudgetRecord {fiscal_year: $year, budget_type: $type})
                    WHERE br.object_uacs_code IS NOT NULL
                    WITH br SKIP $offset LIMIT $batch
                    MATCH (so:SubObject {uacs_code: br.object_uacs_code})
                    MERGE (br)-[:CLASSIFIED_AS]->(so)
                    RETURN count(*) as count
                """, year=fiscal_year, type=budget_type, offset=offset, batch=rel_batch)
                count = result.single()["count"]
                total_count += count
                if count == 0:
                    break
                offset += rel_batch
            print(f"        ✓ Created: {total_count:,}")
            
            print(f"    ✓ {budget_type} {fiscal_year} complete")
    
    def sync_all(self):
        """Sync all data to Neo4j"""
        start_time = time.time()
        
        print("\n" + "="*60)
        print("NEO4J DATA SYNC - YEAR-BASED BATCHED STRUCTURE")
        print("="*60)
        print(f"\nData directory: {self.data_dir.absolute()}")
        
        try:
            print("\nCreating constraints...")
            self.create_constraints()
            
            self.sync_funding_source()
            self.sync_organization()
            self.sync_location()
            self.sync_pap()
            self.sync_object_code()
            
            print("\n" + "="*60)
            print("SYNCING BUDGET DATA")
            print("="*60)
            
            budget_base_dir = self.data_dir / "budget"
            if not budget_base_dir.exists():
                print("\n  ⚠️  No budget directory found")
            else:
                # Find all year directories
                year_dirs = [d for d in budget_base_dir.iterdir() if d.is_dir() and d.name.isdigit()]
                
                if not year_dirs:
                    print("\n  ⚠️  No year directories found")
                else:
                    print(f"\n  Found {len(year_dirs)} year(s): {', '.join(sorted([d.name for d in year_dirs]))}")
                    
                    for year_dir in sorted(year_dirs):
                        year = year_dir.name
                        items_dir = year_dir / "items"
                        
                        if items_dir.exists():
                            nep_files = list(items_dir.glob(f"nep_{year}_batch_*.json"))
                            gaa_files = list(items_dir.glob(f"gaa_{year}_batch_*.json"))
                            
                            if nep_files:
                                self.sync_budget_records(year, "NEP")
                            if gaa_files:
                                self.sync_budget_records(year, "GAA")
            
            elapsed = time.time() - start_time
            print("\n" + "="*60)
            print("SYNC COMPLETE!")
            print("="*60)
            print(f"\nTotal time: {elapsed:.2f} seconds ({elapsed/60:.1f} minutes)")
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
    
    def create_constraints(self):
        """Create uniqueness constraints"""
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (fc:FundCluster) REQUIRE fc.code IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (fin:FinancingSource) REQUIRE fin.code IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (auth:Authorization) REQUIRE auth.code IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (fcat:FundCategory) REQUIRE fcat.uacs_code IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (fs:FundingSource) REQUIRE fs.uacs_code IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Department) REQUIRE d.code IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (a:Agency) REQUIRE a.uacs_code IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (ouc:OperatingUnitClass) REQUIRE ouc.code IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (ou:OperatingUnit) REQUIRE ou.uacs_code IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (org:Organization) REQUIRE org.uacs_code IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (r:Region) REQUIRE r.code IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Province) REQUIRE p.psgc_code IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (c:CityMunicipality) REQUIRE c.psgc_code IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (b:Barangay) REQUIRE b.psgc_code IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (cl:Classification) REQUIRE cl.code IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (sc:SubClass) REQUIRE sc.code IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (eg:ExpenseGroup) REQUIRE eg.full_code IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (o:Object) REQUIRE o.full_code IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (so:SubObject) REQUIRE so.uacs_code IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (br:BudgetRecord) REQUIRE br.id IS UNIQUE",
        ]
        
        with self.driver.session() as session:
            for constraint in constraints:
                session.run(constraint)
        
        print("  ✓ Constraints created")


def main():
    import os
    
    uri = os.getenv("NEO4J_URI", "neo4j://localhost")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "Password123!")
    
    if not password:
        print("❌ Error: NEO4J_PASSWORD environment variable required")
        return
    
    print(f"\nConnecting to Neo4j at {uri}...")
    
    sync = Neo4jSync(uri, user, password)
    
    try:
        sync.sync_all()
    finally:
        sync.close()


if __name__ == "__main__":
    main()