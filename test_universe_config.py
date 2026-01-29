#!/usr/bin/env python3
"""
Test configuration changes for cyclical limit and bank exemption.

Validates that the universe_builder.py has correct settings for:
1. Cyclical limit = 6 (allows 3 Energy + 3 Basic Materials)
2. Bank exemption list includes priority banks (JPM, WFC, BAC, USB)
"""

from universe_builder import SECTOR_DIVERSITY_CONSTRAINTS, TRADITIONAL_BANKS

print("="*70)
print("CONFIGURATION VALIDATION")
print("="*70)

# Test 1: Cyclical limit
print("\n1. Cyclical Limit Check:")
cyclical_limit = SECTOR_DIVERSITY_CONSTRAINTS['max_cyclical_total']
print(f"   Current limit: {cyclical_limit}")

if cyclical_limit == 6:
    print("   [OK] PASS: Cyclical limit set to 6 (allows 3 Energy + 3 Basic Materials)")
elif cyclical_limit == 4:
    print("   [X] FAIL: Cyclical limit still at 4 (should be 6)")
else:
    print(f"   [?] WARN: Unexpected cyclical limit: {cyclical_limit}")

# Test 2: Bank exemption list
print("\n2. Bank Exemption List:")
print(f"   Traditional banks defined: {len(TRADITIONAL_BANKS)}")
print(f"   Banks: {', '.join(TRADITIONAL_BANKS)}")

expected_banks = ['JPM', 'WFC', 'BAC', 'USB']
missing = [b for b in expected_banks if b not in TRADITIONAL_BANKS]

if not missing:
    print("   [OK] PASS: All priority banks (JPM, WFC, BAC, USB) in exemption list")
else:
    print(f"   [X] FAIL: Missing banks from exemption list: {', '.join(missing)}")

# Test 3: Other important constraints
print("\n3. Other Constraint Checks:")
min_per_sector = SECTOR_DIVERSITY_CONSTRAINTS.get('min_per_sector', 0)
max_sector_pct = SECTOR_DIVERSITY_CONSTRAINTS.get('max_sector_pct', 0)
min_sectors = SECTOR_DIVERSITY_CONSTRAINTS.get('min_sectors', 0)

print(f"   Min per sector: {min_per_sector} (expected: 3)")
print(f"   Max sector %: {max_sector_pct:.0%} (expected: 35%)")
print(f"   Min sectors: {min_sectors} (expected: 6)")

all_ok = (
    min_per_sector == 3 and
    max_sector_pct == 0.35 and
    min_sectors == 6
)

if all_ok:
    print("   [OK] PASS: All sector constraints correct")
else:
    print("   [?] WARN: Some constraints may need adjustment")

print("\n" + "="*70)
print("VALIDATION COMPLETE")
print("="*70)
