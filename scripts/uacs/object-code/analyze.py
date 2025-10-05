import json
from collections import defaultdict
from pathlib import Path


class UACSAnalyzer:
    """
    Analyzes UACS code structure to identify how to separate hierarchical levels
    """
    
    def __init__(self, json_file_path: str):
        self.file_path = Path(json_file_path)
        self.data = []
        
    def load_data(self):
        """Load JSON data"""
        with open(self.file_path, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
        print(f"Loaded {len(self.data)} records from {self.file_path.name}")
        
    def analyze_uacs_lengths(self):
        """Analyze UACS code lengths"""
        print("\n" + "="*60)
        print("UACS CODE LENGTH ANALYSIS")
        print("="*60)
        
        length_counts = defaultdict(int)
        length_samples = defaultdict(list)
        
        for item in self.data:
            uacs = str(item.get('UACS', '')).strip()
            length = len(uacs)
            length_counts[length] += 1
            
            # Store first 3 samples of each length
            if len(length_samples[length]) < 3:
                length_samples[length].append({
                    'uacs': uacs,
                    'classification': item.get('Classification', ''),
                    'sub_class': item.get('Sub-Class', ''),
                    'group': item.get('Group', ''),
                    'object': item.get('Object Code', ''),
                    'sub_object': item.get('Sub-Object Code', '')
                })
        
        for length in sorted(length_counts.keys()):
            print(f"\n{length} digits: {length_counts[length]} records")
            print("Samples:")
            for sample in length_samples[length]:
                print(f"  UACS: {sample['uacs']}")
                print(f"    Classification: {sample['classification']}")
                print(f"    Sub-Class: {sample['sub_class']}")
                print(f"    Group: {sample['group']}")
                print(f"    Object: {sample['object']}")
                if sample['sub_object']:
                    print(f"    Sub-Object: {sample['sub_object']}")
                print()
    
    def analyze_classification_patterns(self):
        """Analyze first digit (classification) patterns"""
        print("\n" + "="*60)
        print("CLASSIFICATION CODE ANALYSIS (1st digit)")
        print("="*60)
        
        classification_map = defaultdict(set)
        
        for item in self.data:
            uacs = str(item.get('UACS', '')).strip()
            if uacs:
                first_digit = uacs[0]
                classification = item.get('Classification', '')
                classification_map[first_digit].add(classification)
        
        for digit in sorted(classification_map.keys()):
            print(f"\nCode '{digit}': {', '.join(classification_map[digit])}")
    
    def analyze_subclass_patterns(self):
        """Analyze positions 2-3 (sub-class) patterns"""
        print("\n" + "="*60)
        print("SUB-CLASS CODE ANALYSIS (positions 2-3)")
        print("="*60)
        
        subclass_map = defaultdict(lambda: defaultdict(set))
        
        for item in self.data:
            uacs = str(item.get('UACS', '')).strip()
            if len(uacs) >= 3:
                classification = uacs[0]
                subclass_code = uacs[1:3]
                subclass_name = item.get('Sub-Class', '')
                subclass_map[classification][subclass_code].add(subclass_name)
        
        for classification in sorted(subclass_map.keys()):
            print(f"\nClassification '{classification}':")
            for code in sorted(subclass_map[classification].keys()):
                names = ', '.join(subclass_map[classification][code])
                print(f"  {classification}{code}: {names}")
    
    def analyze_group_patterns(self):
        """Analyze positions 4-5 (group) patterns"""
        print("\n" + "="*60)
        print("GROUP CODE ANALYSIS (positions 4-5)")
        print("="*60)
        
        group_map = defaultdict(lambda: defaultdict(set))
        
        for item in self.data:
            uacs = str(item.get('UACS', '')).strip()
            if len(uacs) >= 5:
                subclass_prefix = uacs[0:3]
                group_code = uacs[3:5]
                group_name = item.get('Group', '')
                group_map[subclass_prefix][group_code].add(group_name)
        
        # Show first 5 sub-classes
        count = 0
        for subclass in sorted(group_map.keys()):
            if count >= 5:
                print("\n... (showing first 5 sub-classes only)")
                break
            print(f"\nSub-Class '{subclass}':")
            for code in sorted(group_map[subclass].keys()):
                names = ', '.join(group_map[subclass][code])
                print(f"  {subclass}{code}: {names}")
            count += 1
    
    def analyze_object_patterns(self):
        """Analyze positions 6-8 (object) patterns"""
        print("\n" + "="*60)
        print("OBJECT CODE ANALYSIS (positions 6-8)")
        print("="*60)
        
        object_map = defaultdict(lambda: defaultdict(set))
        
        for item in self.data:
            uacs = str(item.get('UACS', '')).strip()
            if len(uacs) >= 8:
                group_prefix = uacs[0:5]
                object_code = uacs[5:8]
                object_name = item.get('Object Code', '')
                object_map[group_prefix][object_code].add(object_name)
        
        # Show first 3 groups
        count = 0
        for group in sorted(object_map.keys()):
            if count >= 3:
                print("\n... (showing first 3 groups only)")
                break
            print(f"\nGroup '{group}':")
            for code in sorted(object_map[group].keys()):
                names = ', '.join(object_map[group][code])
                print(f"  {group}{code}: {names}")
            count += 1
    
    def analyze_subobject_patterns(self):
        """Analyze positions 9-10 (sub-object) patterns if available"""
        print("\n" + "="*60)
        print("SUB-OBJECT CODE ANALYSIS (positions 9-10)")
        print("="*60)
        
        has_subobject = False
        subobject_map = defaultdict(lambda: defaultdict(set))
        
        for item in self.data:
            uacs = str(item.get('UACS', '')).strip()
            if len(uacs) >= 10:
                has_subobject = True
                object_prefix = uacs[0:8]
                subobject_code = uacs[8:10]
                subobject_name = item.get('Sub-Object Code', '')
                subobject_map[object_prefix][subobject_code].add(subobject_name)
        
        if not has_subobject:
            print("\nNo sub-object codes found (UACS < 10 digits)")
            return
        
        # Show first 3 objects
        count = 0
        for obj in sorted(subobject_map.keys()):
            if count >= 3:
                print("\n... (showing first 3 objects only)")
                break
            print(f"\nObject '{obj}':")
            for code in sorted(subobject_map[obj].keys()):
                names = ', '.join(subobject_map[obj][code])
                print(f"  {obj}{code}: {names}")
            count += 1
    
    def verify_parsing_logic(self):
        """Verify the proposed parsing logic"""
        print("\n" + "="*60)
        print("PARSING LOGIC VERIFICATION")
        print("="*60)
        
        print("\nProposed Structure:")
        print("  Position 0 (1 digit):  Classification")
        print("  Positions 1-2 (2 digits): Sub-Class")
        print("  Positions 3-4 (2 digits): Group")
        print("  Positions 5-7 (3 digits): Object")
        print("  Positions 8-9 (2 digits): Sub-Object (if 10-digit code)")
        
        print("\nTesting on first 5 records:")
        for i, item in enumerate(self.data[:5]):
            uacs = str(item.get('UACS', '')).strip()
            print(f"\n{i+1}. UACS: {uacs}")
            
            if len(uacs) >= 8:
                print(f"   Classification [{uacs[0]}]: {item.get('Classification', '')}")
                print(f"   Sub-Class [{uacs[1:3]}]: {item.get('Sub-Class', '')}")
                print(f"   Group [{uacs[3:5]}]: {item.get('Group', '')}")
                print(f"   Object [{uacs[5:8]}]: {item.get('Object Code', '')}")
                
            if len(uacs) >= 10:
                print(f"   Sub-Object [{uacs[8:10]}]: {item.get('Sub-Object Code', '')}")
    
    def run_full_analysis(self):
        """Run all analyses"""
        self.load_data()
        self.analyze_uacs_lengths()
        self.analyze_classification_patterns()
        self.analyze_subclass_patterns()
        self.analyze_group_patterns()
        self.analyze_object_patterns()
        self.analyze_subobject_patterns()
        self.verify_parsing_logic()
        
        print("\n" + "="*60)
        print("ANALYSIS COMPLETE")
        print("="*60)


def main():
    """
    Run the analyzer
    
    Usage:
        analyzer = UACSAnalyzer('path/to/subobjectcode.json')
        analyzer.run_full_analysis()
    """
    # Path to input file (in input folder)
    script_dir = Path(__file__).parent
    file_path = script_dir / "input" / "subobjectcode.json"
    
    try:
        analyzer = UACSAnalyzer(file_path)
        analyzer.run_full_analysis()
    except FileNotFoundError:
        print(f"❌ File not found: {file_path}")
        print("\nPlease update the file_path in main() to point to your subobjectcode.json file")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()