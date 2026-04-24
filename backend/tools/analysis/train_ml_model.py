from pathlib import Path
import sys

TOOLS_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = TOOLS_ROOT.parent
for _candidate in (BACKEND_ROOT, TOOLS_ROOT, TOOLS_ROOT / 'analysis', TOOLS_ROOT / 'checks', TOOLS_ROOT / 'llm', TOOLS_ROOT / 'runners'):
    _candidate_str = str(_candidate)
    if _candidate_str not in sys.path:
        sys.path.insert(0, _candidate_str)
"""
Train ML models to predict economic outcomes from policy configurations.

This script trains XGBoost models on the generated training data and saves
them for production use in the prediction layer.

Model Architecture:
- Input: 9 policy parameters
- Output: 11 economic outcome metrics
- Algorithm: XGBoost (gradient boosted trees)
- Validation: 5-fold cross-validation
- Metrics: RÂ², RMSE, MAE

Features:
- Hyperparameter tuning
- Feature importance analysis
- Model versioning
- Cross-validation
"""

import sys
import os
import numpy as np
import pandas as pd
from datetime import datetime
import json
import pickle

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def install_xgboost():
    """Install XGBoost if not available."""
    try:
        import xgboost
        return True
    except ImportError:
        print("XGBoost not installed. Installing...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "xgboost", "scikit-learn"])
        print("âœ“ XGBoost installed successfully")
        return True

def load_training_data(data_file):
    """Load and split training data into features and targets."""
    df = pd.read_csv(data_file)

    # Policy features (inputs)
    policy_features = [
        'wageTax', 'profitTax', 'inflationRate', 'birthRate',
        'minimumWage', 'unemploymentBenefitRate', 'universalBasicIncome',
        'wealthTaxThreshold', 'wealthTaxRate'
    ]

    # Economic outcomes (targets)
    outcome_targets = [
        'gdp', 'unemployment_rate', 'mean_happiness', 'mean_health',
        'mean_wage', 'median_wage', 'gini_coefficient',
        'government_debt', 'government_balance', 'total_household_wealth',
        'num_active_firms'
    ]

    X = df[policy_features].values
    y = df[outcome_targets].values

    return X, y, policy_features, outcome_targets, df

def train_models(X, y, policy_features, outcome_targets):
    """
    Train separate XGBoost models for each outcome.

    Using multi-output approach: one model per target for better interpretability
    and individual hyperparameter tuning.
    """
    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
    import xgboost as xgb

    print("="*70)
    print("TRAINING ML MODELS")
    print("="*70)
    print()

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    print(f"Dataset split:")
    print(f"  Training samples: {len(X_train)}")
    print(f"  Test samples: {len(X_test)}")
    print(f"  Features: {len(policy_features)}")
    print(f"  Targets: {len(outcome_targets)}")
    print()

    # Train one model per outcome
    models = {}
    evaluation_results = {}

    print("Training models...")
    print("-"*70)

    for i, target_name in enumerate(outcome_targets):
        print(f"\n[{i+1}/{len(outcome_targets)}] Training model for: {target_name}")

        # Extract single target
        y_train_single = y_train[:, i]
        y_test_single = y_test[:, i]

        # XGBoost model with tuned hyperparameters
        model = xgb.XGBRegressor(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            objective='reg:squarederror'
        )

        # Train
        model.fit(X_train, y_train_single, verbose=False)

        # Predict
        y_pred_train = model.predict(X_train)
        y_pred_test = model.predict(X_test)

        # Evaluate
        train_r2 = r2_score(y_train_single, y_pred_train)
        test_r2 = r2_score(y_test_single, y_pred_test)
        test_rmse = np.sqrt(mean_squared_error(y_test_single, y_pred_test))
        test_mae = mean_absolute_error(y_test_single, y_pred_test)

        # Cross-validation score
        cv_scores = cross_val_score(
            model, X_train, y_train_single,
            cv=5, scoring='r2'
        )
        cv_mean = cv_scores.mean()
        cv_std = cv_scores.std()

        # Store model and metrics
        models[target_name] = model
        evaluation_results[target_name] = {
            'train_r2': float(train_r2),
            'test_r2': float(test_r2),
            'test_rmse': float(test_rmse),
            'test_mae': float(test_mae),
            'cv_r2_mean': float(cv_mean),
            'cv_r2_std': float(cv_std)
        }

        # Print results
        print(f"  Train RÂ²: {train_r2:.4f}")
        print(f"  Test RÂ²:  {test_r2:.4f}")
        print(f"  CV RÂ²:    {cv_mean:.4f} Â± {cv_std:.4f}")
        print(f"  RMSE:     {test_rmse:.4f}")

        # Check for overfitting
        if train_r2 - test_r2 > 0.15:
            print(f"  âš  Warning: Possible overfitting detected")

    return models, evaluation_results, X_test, y_test

def analyze_feature_importance(models, policy_features, outcome_targets):
    """Analyze which policies most impact each outcome."""
    print()
    print("="*70)
    print("FEATURE IMPORTANCE ANALYSIS")
    print("="*70)
    print()

    importance_data = {}

    for target_name in outcome_targets[:5]:  # Show top 5 for brevity
        model = models[target_name]
        importance = model.feature_importances_

        # Sort features by importance
        indices = np.argsort(importance)[::-1]

        print(f"\n{target_name}:")
        print("-"*70)
        importance_data[target_name] = {}

        for i in range(min(5, len(policy_features))):
            idx = indices[i]
            feature = policy_features[idx]
            imp = importance[idx]
            importance_data[target_name][feature] = float(imp)
            print(f"  {i+1}. {feature:25s}: {imp:.4f}")

    return importance_data

def save_models(models, evaluation_results, importance_data, policy_features, outcome_targets, data_file):
    """Save trained models and metadata."""
    print()
    print("="*70)
    print("SAVING MODELS")
    print("="*70)
    print()

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    model_dir = f"ml_models_{timestamp}"
    os.makedirs(model_dir, exist_ok=True)

    # Save individual models
    for target_name, model in models.items():
        model_file = os.path.join(model_dir, f"model_{target_name}.pkl")
        with open(model_file, 'wb') as f:
            pickle.dump(model, f)

    # Save metadata
    metadata = {
        'timestamp': timestamp,
        'training_data_file': data_file,
        'policy_features': policy_features,
        'outcome_targets': outcome_targets,
        'evaluation_results': evaluation_results,
        'feature_importance': importance_data,
        'model_type': 'XGBoost',
        'num_models': len(models)
    }

    metadata_file = os.path.join(model_dir, 'metadata.json')
    with open(metadata_file, 'w') as f:
        json.dump(metadata, indent=2, fp=f)

    print(f"âœ“ Models saved to: {model_dir}/")
    print(f"  - {len(models)} XGBoost models")
    print(f"  - metadata.json")
    print()

    # Print summary
    print("Model Performance Summary:")
    print("-"*70)
    avg_test_r2 = np.mean([r['test_r2'] for r in evaluation_results.values()])
    avg_cv_r2 = np.mean([r['cv_r2_mean'] for r in evaluation_results.values()])

    print(f"Average Test RÂ²:  {avg_test_r2:.4f}")
    print(f"Average CV RÂ²:    {avg_cv_r2:.4f}")
    print()

    # Flag poor performers
    poor_performers = [
        name for name, metrics in evaluation_results.items()
        if metrics['test_r2'] < 0.5
    ]

    if poor_performers:
        print("âš  Models with RÂ² < 0.5 (may need more data or tuning):")
        for name in poor_performers:
            r2 = evaluation_results[name]['test_r2']
            print(f"  - {name}: RÂ² = {r2:.4f}")
        print()

    return model_dir

def main():
    """Main training pipeline."""
    print("="*70)
    print("ML PREDICTION LAYER - MODEL TRAINING")
    print("="*70)
    print()

    # Install dependencies
    install_xgboost()

    # Find most recent training data (include checkpoints)
    import glob
    data_files = glob.glob("training_data_*.csv")
    if not data_files:
        print("âœ— No training data found!")
        print("  Please run: python generate_training_data.py")
        sys.exit(1)

    # Use most recent (sorted by modification time)
    data_file = max(data_files, key=os.path.getmtime)
    print(f"Using training data: {data_file}")
    print()

    # Load data
    print("Loading training data...")
    X, y, policy_features, outcome_targets, df = load_training_data(data_file)
    print(f"âœ“ Loaded {len(df)} samples")
    print()

    # Train models
    models, evaluation_results, X_test, y_test = train_models(
        X, y, policy_features, outcome_targets
    )

    # Feature importance
    importance_data = analyze_feature_importance(
        models, policy_features, outcome_targets
    )

    # Save models
    model_dir = save_models(
        models, evaluation_results, importance_data,
        policy_features, outcome_targets, data_file
    )

    print("="*70)
    print("âœ“ TRAINING COMPLETE")
    print("="*70)
    print()
    print("Next steps:")
    print("  1. Review model performance in metadata.json")
    print("  2. Create ml_predictor.py for inference")
    print("  3. Integrate with server.py for real-time predictions")
    print()
    print(f"Models saved in: {model_dir}/")

if __name__ == "__main__":
    main()

