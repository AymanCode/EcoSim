# Training Data Generation - Setup Guide

This guide explains how to generate ML training data on your PC.

---

## Prerequisites

### 1. Install Python Dependencies

```bash
# Navigate to the backend directory
cd backend

# Install required packages
pip install numpy pandas scipy
```

**Why these packages:**
- `numpy`: Fast numerical computations
- `pandas`: Data manipulation and CSV export
- `scipy`: Latin Hypercube Sampling (better policy coverage)

---

## Configuration Options

The script `generate_training_data.py` has configurable parameters at the top of the `main()` function:

```python
NUM_SAMPLES = 500              # Number of different policy configurations
NUM_TICKS = 300                # Simulation length (ticks per run)
NUM_HOUSEHOLDS = 1000          # Agents per simulation
NUM_FIRMS_PER_CATEGORY = 5     # Firms per category (Food, Housing, Services)
```

### Performance vs Quality Tradeoffs

| Configuration | Samples | Ticks | Runtime | ML Quality |
|---------------|---------|-------|---------|------------|
| **Quick Test** | 100 | 200 | ~20 min | Basic |
| **Standard** | 500 | 300 | ~2 hours | Good |
| **High Quality** | 1000 | 400 | ~6 hours | Excellent |
| **Production** | 2000 | 500 | ~12 hours | Best |

**Recommendation for first run**: Use **Standard** (500 samples, 300 ticks)

---

## How to Run

### Option 1: Direct Execution

```bash
cd backend
python generate_training_data.py
```

The script will:
1. Generate 500 policy configurations using Latin Hypercube Sampling
2. Run simulations for each policy
3. Save checkpoints every 50 samples
4. Display progress with ETA
5. Save final dataset as `training_data_YYYYMMDD_HHMMSS.csv`

### Option 2: Background Execution (Recommended for long runs)

**Windows (PowerShell):**
```powershell
cd backend
Start-Process python -ArgumentList "generate_training_data.py" -RedirectStandardOutput "training.log" -RedirectStandardError "training_errors.log" -NoNewWindow
```

**Windows (Command Prompt):**
```cmd
cd backend
python generate_training_data.py > training.log 2> training_errors.log
```

**Linux/Mac:**
```bash
cd backend
nohup python generate_training_data.py > training.log 2>&1 &
```

Then monitor progress:
```bash
tail -f training.log
```

---

## Output Files

### During Execution
- `training_data_checkpoint_50.csv` - After 50 samples
- `training_data_checkpoint_100.csv` - After 100 samples
- `training_data_checkpoint_150.csv` - After 150 samples
- ... (every 50 samples)

**Purpose**: If the script crashes, you don't lose all progress

### After Completion
- `training_data_YYYYMMDD_HHMMSS.csv` - Final dataset
  - Example: `training_data_20251227_143052.csv`
  - Contains all 500 samples with 20 columns

---

## Monitoring Progress

The script outputs progress every 10 simulations:

```
[10/500] Sim time: 14.2s | Avg: 14.5s | ETA: 118.3m | GDP: $8.45M | Unemp: 5.2%
[20/500] Sim time: 15.1s | Avg: 14.8s | ETA: 118.4m | GDP: $7.92M | Unemp: 8.1%
...
✓ Checkpoint saved: training_data_checkpoint_50.csv
```

**What this tells you:**
- Current progress (10/500)
- Last simulation time (14.2s)
- Average time per simulation (14.5s)
- Estimated time remaining (118.3 minutes)
- Sample metrics (GDP, Unemployment)

---

## Expected Dataset

### Columns (20 total)

**Policy Inputs (9):**
1. `wageTax` - Wage income tax rate (0% to 30%)
2. `profitTax` - Corporate profit tax rate (10% to 50%)
3. `inflationRate` - Target inflation rate (0% to 10%)
4. `birthRate` - Population growth rate (0% to 5%)
5. `minimumWage` - Minimum wage floor ($15 to $50)
6. `unemploymentBenefitRate` - Unemployment benefit as % of avg wage (0% to 80%)
7. `universalBasicIncome` - UBI amount per household ($0 to $500)
8. `wealthTaxThreshold` - Wealth above this is taxed ($10K to $200K)
9. `wealthTaxRate` - Tax rate on wealth above threshold (0% to 10%)

**Economic Outcomes (11):**
1. `gdp` - Total economic output ($)
2. `unemployment_rate` - Percentage of unemployed (%)
3. `mean_happiness` - Average happiness (0 to 1)
4. `mean_health` - Average health (0 to 1)
5. `mean_wage` - Average wage of employed ($)
6. `median_wage` - Median wage of employed ($)
7. `gini_coefficient` - Wealth inequality (0 to 1, lower = more equal)
8. `government_debt` - Government debt if negative balance ($)
9. `government_balance` - Government cash balance ($)
10. `total_household_wealth` - Sum of all household cash ($)
11. `num_active_firms` - Number of solvent firms

### Sample Row

```csv
wageTax,profitTax,inflationRate,...,gdp,unemployment_rate,mean_happiness,...
0.15,0.25,0.02,...,8450000,5.2,0.65,...
```

---

## Troubleshooting

### Error: ModuleNotFoundError: No module named 'scipy'

**Solution:**
```bash
pip install scipy
```

If you don't have scipy, the script will fall back to random sampling (less optimal but works).

---

### Error: Memory issues / System slows down

**Solution**: Reduce agent count
```python
NUM_HOUSEHOLDS = 500           # Instead of 1000
NUM_FIRMS_PER_CATEGORY = 3     # Instead of 5
```

---

### Script crashes midway

**Solution**: Resume from checkpoint
```python
# In generate_training_data.py, modify main():

# Load existing checkpoint
existing_data = pd.read_csv('training_data_checkpoint_250.csv')
training_data = existing_data.to_dict('records')

# Continue from where it stopped
for i, policy in enumerate(policies[250:], start=250):  # Start at 250
    # ... rest of code
```

---

## Performance Optimization Tips

### 1. Close Other Applications
Running simulations is CPU-intensive. Close browsers, games, etc.

### 2. Check CPU Usage
- Windows: Task Manager → Performance
- Mac: Activity Monitor
- Linux: `htop`

Python should use 25-50% of one CPU core.

### 3. Power Settings
- Set PC to "High Performance" mode
- Disable sleep/hibernation during training

### 4. Monitor Temperature
If your PC runs hot, consider:
- Better ventilation
- Reducing NUM_HOUSEHOLDS to 750
- Taking breaks between batches

---

## After Generation Complete

### 1. Verify the dataset

```bash
# Check file size (should be ~500KB for 500 samples)
ls -lh training_data_*.csv

# Preview first few rows
head -20 training_data_*.csv
```

### 2. Copy to project

The file is already in the `backend/` directory, ready for training!

### 3. Next Steps

Once you have `training_data_YYYYMMDD_HHMMSS.csv`:
1. Commit it to git (or git LFS if >50MB)
2. Run the model training script (Phase 2 - coming next)
3. Deploy the trained models to the API

---

## Quick Start Summary

```bash
# 1. Install dependencies
pip install numpy pandas scipy

# 2. Run generation
cd backend
python generate_training_data.py

# 3. Wait ~2 hours (Standard config)

# 4. Find your dataset
ls training_data_*.csv
```

---

## Questions?

- **How long will it take?** ~2-2.5 hours for 500 samples
- **Can I pause it?** No, but checkpoints save progress every 50 samples
- **What if it crashes?** See "Script crashes midway" in Troubleshooting
- **Can I run overnight?** Yes, use background execution option

---

Good luck! The dataset will be ready for ML training once complete.
