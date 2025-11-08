#!/usr/bin/env python
"""
Script to regenerate pickle files for NumPy compatibility.
This fixes the 'numpy._core' module not found error when using NumPy < 2.0
"""

import sys
from pathlib import Path
import pickle
import joblib

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def fix_pickle_file(pickle_path):
    """Load and re-save a pickle file with current NumPy version."""
    print(f"Processing: {pickle_path}")
    try:
        # Try loading with joblib first
        try:
            obj = joblib.load(pickle_path)
            print(f"  ✓ Loaded with joblib")
        except Exception as e1:
            print(f"  ⚠ Joblib failed: {e1}")
            # Try standard pickle
            try:
                with open(pickle_path, 'rb') as f:
                    obj = pickle.load(f)
                print(f"  ✓ Loaded with pickle")
            except Exception as e2:
                print(f"  ✗ Both methods failed")
                print(f"    joblib error: {e1}")
                print(f"    pickle error: {e2}")
                return False
        
        # Create backup
        backup_path = pickle_path.with_suffix('.pkl.backup')
        if not backup_path.exists():
            import shutil
            shutil.copy2(pickle_path, backup_path)
            print(f"  ✓ Created backup: {backup_path.name}")
        
        # Re-save with current NumPy
        joblib.dump(obj, pickle_path)
        print(f"  ✓ Re-saved successfully\n")
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}\n")
        return False

def main():
    """Fix all pickle files in scene_predictors directories."""
    print("=" * 60)
    print("Fixing pickle files for NumPy compatibility")
    print("=" * 60)
    
    import numpy
    print(f"\nCurrent NumPy version: {numpy.__version__}\n")
    
    # Get project root
    project_root = Path(__file__).parent.parent
    predictors_dir = project_root / 'oculizer' / 'scene_predictors'
    
    if not predictors_dir.exists():
        print(f"Error: {predictors_dir} not found!")
        return 1
    
    # Find all pickle files
    pickle_files = list(predictors_dir.rglob('*.pkl'))
    
    if not pickle_files:
        print(f"No pickle files found in {predictors_dir}")
        return 1
    
    print(f"Found {len(pickle_files)} pickle file(s):\n")
    
    success_count = 0
    fail_count = 0
    
    for pkl_file in sorted(pickle_files):
        relative_path = pkl_file.relative_to(project_root)
        if fix_pickle_file(pkl_file):
            success_count += 1
        else:
            fail_count += 1
    
    print("=" * 60)
    print(f"Results: {success_count} succeeded, {fail_count} failed")
    print("=" * 60)
    
    if fail_count > 0:
        print("\n⚠ Some files couldn't be fixed automatically.")
        print("You may need to retrain these models with your current NumPy version.")
        return 1
    else:
        print("\n✅ All pickle files updated successfully!")
        print("You can now run your application.")
        return 0

if __name__ == '__main__':
    sys.exit(main())

