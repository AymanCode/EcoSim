"""
Quick script to check training data generation progress.

Run this anytime to see how far along the generation is.
"""

import os
import glob
from datetime import datetime

print("="*70)
print("TRAINING DATA GENERATION - PROGRESS CHECK")
print("="*70)
print(f"Checked at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

# Check for checkpoint files
checkpoints = sorted(glob.glob("training_data_checkpoint_*.csv"))
if checkpoints:
    latest_checkpoint = checkpoints[-1]
    checkpoint_num = int(latest_checkpoint.split('_')[-1].replace('.csv', ''))
    progress_pct = (checkpoint_num / 500) * 100

    print(f"✓ Progress: {checkpoint_num}/500 samples ({progress_pct:.1f}%)")
    print(f"  Latest checkpoint: {latest_checkpoint}")

    # Estimate time remaining
    import pandas as pd
    file_time = os.path.getmtime(latest_checkpoint)
    elapsed_minutes = (datetime.now().timestamp() - file_time) / 60

    if checkpoint_num >= 50:
        # Calculate rate from first checkpoint
        first_checkpoint_time = os.path.getmtime("training_data_checkpoint_50.csv")
        if checkpoint_num > 50:
            time_for_increment = (file_time - first_checkpoint_time) / 60
            samples_done = checkpoint_num - 50
            rate = time_for_increment / samples_done if samples_done > 0 else 15/60
            remaining_samples = 500 - checkpoint_num
            eta_minutes = remaining_samples * rate

            print(f"  Rate: ~{rate*60:.1f}s per sample")
            print(f"  ETA: ~{eta_minutes:.0f} minutes remaining")

    print()

    # Show sample from checkpoint
    df = pd.read_csv(latest_checkpoint)
    print(f"Sample data (last checkpoint with {len(df)} samples):")
    print("-"*70)
    print(df[['wageTax', 'minimumWage', 'gdp', 'unemployment_rate', 'mean_wage']].tail(3).to_string(index=False))

else:
    print("⏳ No checkpoints found yet (first checkpoint at 50 samples)")
    print("   Generation is still in early stages...")

print()

# Check for final file
final_files = [f for f in glob.glob("training_data_*.csv") if "checkpoint" not in f]
final_files = [f for f in final_files if os.path.getmtime(f) > datetime.now().timestamp() - 7200]  # Within last 2 hours

if final_files:
    latest_final = sorted(final_files)[-1]
    import pandas as pd
    df = pd.read_csv(latest_final)

    print("="*70)
    print("✓✓✓ GENERATION COMPLETE! ✓✓✓")
    print("="*70)
    print(f"Final dataset: {latest_final}")
    print(f"Total samples: {len(df)}")
    print()
    print("Dataset summary:")
    print("-"*70)
    print(df[['gdp', 'unemployment_rate', 'mean_wage', 'gini_coefficient']].describe())
    print()
    print("Ready to train ML model!")
    print("Run: python backend/train_ml_model.py")
else:
    print("Final dataset not yet generated. Generation still in progress...")

print()
print("="*70)
