import os
from neo4j import GraphDatabase
from datetime import datetime


class Neo4jValidator:
    """
    Validates Neo4j relationships after sync
    Runs comprehensive checks and outputs results
    """
    
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.results = []
        
    def close(self):
        self.driver.close()
    
    def run_query(self, query: str, description: str):
        """Execute a query and return results"""
        with self.driver.session() as session:
            try:
                result = session.run(query)
                data = [dict(record) for record in result]
                return {"status": "success", "description": description, "data": data}
            except Exception as e:
                return {"status": "error", "description": description, "error": str(e)}
    
    def print_section(self, title: str):
        """Print a section header"""
        print("\n" + "="*70)
        print(f"  {title}")
        print("="*70)
    
    def print_result(self, description: str, data: list, show_limit: int = 5):
        """Print query results"""
        print(f"\n{description}")
        if not data:
            print("  ⚠️  No results")
            return
        
        if len(data) == 1 and len(data[0]) == 1:
            # Single value result (like a count)
            key = list(data[0].keys())[0]
            value = data[0][key]
            print(f"  ✓ {value:,}")
        else:
            # Multiple rows
            print(f"  ✓ Found {len(data):,} result(s)")
            for i, row in enumerate(data[:show_limit]):
                if i == 0:
                    print(f"     Sample data:")
                print(f"     {i+1}. {row}")
            if len(data) > show_limit:
                print(f"     ... and {len(data) - show_limit} more")
    
    def validate_all(self):
        """Run all validation checks"""
        
        print("\n" + "="*70)
        print("  NEO4J RELATIONSHIP VALIDATION")
        print("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        print("="*70)
        
        # 1. Quick Overview
        self.print_section("1. RELATIONSHIP OVERVIEW")
        result = self.run_query("""
            MATCH ()-[r]->()
            RETURN type(r) as relationship_type, count(r) as count
            ORDER BY count DESC
        """, "All relationship types")
        self.print_result(result["description"], result["data"], show_limit=20)
        
        # 2. Funding Source Hierarchy
        self.print_section("2. FUNDING SOURCE HIERARCHY")
        
        result = self.run_query("""
            MATCH path = (fc:FundCluster)-[:HAS_FINANCING_SOURCE]->(fin:FinancingSource)
                         -[:HAS_AUTHORIZATION]->(auth:Authorization)
                         -[:HAS_FUND_CATEGORY]->(fcat:FundCategory)
                         -[:HAS_FUNDING_SOURCE]->(fs:FundingSource)
            RETURN fc.description as fund_cluster,
                   fin.description as financing_source,
                   auth.description as authorization,
                   fcat.description as fund_category,
                   fs.uacs_code as funding_code
            LIMIT 5
        """, "Complete funding chain")
        self.print_result(result["description"], result["data"])
        
        result = self.run_query("""
            MATCH ()-[r:HAS_FINANCING_SOURCE]->() RETURN count(r) as count
        """, "FundCluster → FinancingSource")
        self.print_result(result["description"], result["data"])
        
        result = self.run_query("""
            MATCH ()-[r:HAS_AUTHORIZATION]->() RETURN count(r) as count
        """, "FinancingSource → Authorization")
        self.print_result(result["description"], result["data"])
        
        result = self.run_query("""
            MATCH ()-[r:HAS_FUND_CATEGORY]->() RETURN count(r) as count
        """, "Authorization → FundCategory")
        self.print_result(result["description"], result["data"])
        
        result = self.run_query("""
            MATCH ()-[r:HAS_FUNDING_SOURCE]->() RETURN count(r) as count
        """, "FundCategory → FundingSource")
        self.print_result(result["description"], result["data"])
        
        # 3. Organization Hierarchy
        self.print_section("3. ORGANIZATION HIERARCHY")
        
        result = self.run_query("""
            MATCH path = (d:Department)-[:HAS_AGENCY]->(a:Agency)
                         -[:HAS_OPERATING_UNIT_CLASS]->(ouc:OperatingUnitClass)
                         -[:HAS_OPERATING_UNIT]->(ou:OperatingUnit)
            RETURN d.description as department,
                   a.description as agency,
                   ouc.description as unit_class,
                   ou.description as operating_unit
            LIMIT 5
        """, "Complete organization chain")
        self.print_result(result["description"], result["data"])
        
        result = self.run_query("""
            MATCH ()-[r:HAS_AGENCY]->() RETURN count(r) as count
        """, "Department → Agency")
        self.print_result(result["description"], result["data"])
        
        result = self.run_query("""
            MATCH ()-[r:HAS_OPERATING_UNIT_CLASS]->() RETURN count(r) as count
        """, "Agency → OperatingUnitClass")
        self.print_result(result["description"], result["data"])
        
        result = self.run_query("""
            MATCH ()-[r:HAS_OPERATING_UNIT]->() RETURN count(r) as count
        """, "OperatingUnitClass → OperatingUnit")
        self.print_result(result["description"], result["data"])
        
        # 4. Expense Classification
        self.print_section("4. EXPENSE CLASSIFICATION HIERARCHY")
        
        result = self.run_query("""
            MATCH path = (c:Classification)-[:HAS_SUB_CLASS]->(sc:SubClass)
                         -[:HAS_GROUP]->(eg:ExpenseGroup)
                         -[:HAS_OBJECT]->(o)
                         -[:HAS_SUB_OBJECT]->(so:SubObject)
            WHERE c.code = '5' AND (o:Object OR o:ExpenseObject)
            RETURN c.description as classification,
                   sc.description as sub_class,
                   eg.description as expense_group,
                   o.description as object,
                   so.description as sub_object
            LIMIT 5
        """, "Complete expense chain")
        self.print_result(result["description"], result["data"])
        
        result = self.run_query("""
            MATCH ()-[r:HAS_SUB_CLASS]->() RETURN count(r) as count
        """, "Classification → SubClass")
        self.print_result(result["description"], result["data"])
        
        result = self.run_query("""
            MATCH ()-[r:HAS_GROUP]->() RETURN count(r) as count
        """, "SubClass → ExpenseGroup")
        self.print_result(result["description"], result["data"])
        
        result = self.run_query("""
            MATCH ()-[r:HAS_OBJECT]->() RETURN count(r) as count
        """, "ExpenseGroup → Object/ExpenseObject")
        self.print_result(result["description"], result["data"])
        
        result = self.run_query("""
            MATCH ()-[r:HAS_SUB_OBJECT]->() RETURN count(r) as count
        """, "Object/ExpenseObject → SubObject")
        self.print_result(result["description"], result["data"])
        
        # 5. Location Hierarchy
        self.print_section("5. LOCATION HIERARCHY")
        
        result = self.run_query("""
            MATCH ()-[r:HAS_PROVINCE]->() RETURN count(r) as count
        """, "Region → Province")
        self.print_result(result["description"], result["data"])
        
        result = self.run_query("""
            MATCH ()-[r:HAS_CITY]->() RETURN count(r) as count
        """, "Province → City")
        self.print_result(result["description"], result["data"])
        
        result = self.run_query("""
            MATCH ()-[r:HAS_BARANGAY]->() RETURN count(r) as count
        """, "City → Barangay")
        self.print_result(result["description"], result["data"])
        
        # 6. Budget Relationships
        self.print_section("6. BUDGET RECORD RELATIONSHIPS")
        
        result = self.run_query("""
            MATCH (br:BudgetRecord) RETURN count(*) as total_budgets
        """, "Total budget records")
        self.print_result(result["description"], result["data"])
        
        result = self.run_query("""
            MATCH ()-[r:ALLOCATED_TO]->() RETURN count(r) as count
        """, "Budget → Organization")
        self.print_result(result["description"], result["data"])
        
        result = self.run_query("""
            MATCH ()-[r:FUNDED_BY]->() RETURN count(r) as count
        """, "Budget → FundingSource")
        self.print_result(result["description"], result["data"])
        
        result = self.run_query("""
            MATCH ()-[r:LOCATED_IN_REGION]->() RETURN count(r) as count
        """, "Budget → Region")
        self.print_result(result["description"], result["data"])
        
        result = self.run_query("""
            MATCH ()-[r:CLASSIFIED_AS]->() RETURN count(r) as count
        """, "Budget → SubObject")
        self.print_result(result["description"], result["data"])
        
        # 7. Coverage Analysis
        self.print_section("7. BUDGET RELATIONSHIP COVERAGE")
        
        result = self.run_query("""
            MATCH (br:BudgetRecord)
            WITH count(br) as total
            MATCH (br2:BudgetRecord)-[:ALLOCATED_TO]->()
            WITH total, count(br2) as with_org
            MATCH (br3:BudgetRecord)-[:FUNDED_BY]->()
            WITH total, with_org, count(br3) as with_fund
            MATCH (br4:BudgetRecord)-[:CLASSIFIED_AS]->()
            RETURN total,
                   with_org, (with_org * 100.0 / total) as org_pct,
                   with_fund, (with_fund * 100.0 / total) as fund_pct,
                   count(br4) as with_class, (count(br4) * 100.0 / total) as class_pct
        """, "Coverage percentages")
        if result["data"]:
            data = result["data"][0]
            print(f"\n{result['description']}")
            print(f"  Total budgets: {data['total']:,}")
            print(f"  With Organization: {data['with_org']:,} ({data['org_pct']:.1f}%)")
            print(f"  With Funding: {data['with_fund']:,} ({data['fund_pct']:.1f}%)")
            print(f"  With Classification: {data['with_class']:,} ({data['class_pct']:.1f}%)")
        
        # 8. Issues Found
        self.print_section("8. ISSUES & ORPHANED NODES")
        
        result = self.run_query("""
            MATCH (fc:FundCluster)
            WHERE NOT (fc)-[:HAS_FINANCING_SOURCE]->()
            RETURN count(*) as count
        """, "Orphaned FundClusters")
        self.print_result(result["description"], result["data"])
        
        result = self.run_query("""
            MATCH (a:Agency)
            WHERE NOT (a)-[:HAS_OPERATING_UNIT_CLASS]->()
            RETURN count(*) as count
        """, "Agencies without OperatingUnitClass")
        self.print_result(result["description"], result["data"])
        
        result = self.run_query("""
            MATCH (so:SubObject)
            WHERE NOT ()-[:HAS_SUB_OBJECT]->(so)
            RETURN count(*) as count
        """, "Orphaned SubObjects")
        self.print_result(result["description"], result["data"])
        
        result = self.run_query("""
            MATCH (br:BudgetRecord)
            WHERE NOT (br)-[:ALLOCATED_TO]->()
            RETURN count(*) as count
        """, "Budgets without Organization")
        self.print_result(result["description"], result["data"])
        
        result = self.run_query("""
            MATCH (br:BudgetRecord)
            WHERE NOT (br)-[:FUNDED_BY]->()
            RETURN count(*) as count
        """, "Budgets without Funding")
        self.print_result(result["description"], result["data"])
        
        # Summary
        self.print_section("VALIDATION COMPLETE")
        print("\nCheck the results above for any issues.")
        print("Counts should be > 0 for all relationships.")
        print("Orphaned nodes should be 0 or minimal.")


def main():
    uri = os.getenv("NEO4J_URI", "neo4j://localhost")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "Password123!")
    
    if not password:
        print("❌ Error: NEO4J_PASSWORD environment variable required")
        return
    
    print(f"Connecting to Neo4j at {uri}...")
    
    validator = Neo4jValidator(uri, user, password)
    
    try:
        validator.validate_all()
    finally:
        validator.close()


if __name__ == "__main__":
    main()