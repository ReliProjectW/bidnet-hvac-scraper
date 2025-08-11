#!/usr/bin/env python3
"""
Debug script to test contract loading
"""

import os

def debug_load_contracts():
    data_dir = "/Users/christophernguyen/bidnet-hvac-scraper/data"
    smart_files = [f for f in os.listdir(data_dir) if f.startswith('smart_contracts_') and f.endswith('.txt')]
    
    latest_file = sorted(smart_files)[-1]
    print(f"Loading from: {latest_file}")
    
    file_path = os.path.join(data_dir, latest_file)
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    print(f"File length: {len(content)}")
    print(f"First 500 chars: {repr(content[:500])}")
    
    # Replace escaped newlines
    content = content.replace('\\n', '\n')
    print(f"After newline replacement: {len(content)}")
    print(f"First 500 chars after: {repr(content[:500])}")
    
    # Look for contracts
    contract_sections = content.split('Contract ')
    print(f"Found {len(contract_sections)} sections")
    
    if len(contract_sections) > 1:
        first_contract = contract_sections[1]
        print(f"First contract section: {repr(first_contract[:300])}")
        
        lines = first_contract.split('\n')
        print(f"Lines in first contract: {len(lines)}")
        
        contract = {}
        for i, line in enumerate(lines[:10]):  # First 10 lines
            print(f"Line {i}: {repr(line)}")
            original_line = line
            line = line.strip()
            if ':' in line and original_line.startswith('  '):
                key, value = line.split(':', 1)
                key = key.strip().lower().replace(' ', '_')
                value = value.strip()
                contract[key] = value
                print(f"  -> Added: {key} = {value}")
        
        print(f"Final contract dict: {contract}")

if __name__ == "__main__":
    debug_load_contracts()