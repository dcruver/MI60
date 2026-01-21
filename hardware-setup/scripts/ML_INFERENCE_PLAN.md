# ML Inference for GPU Fan Control

## Overview

Replace the current rule-based PWM lookup (11-point interpolation) with a trained ML model that can make finer-grained decisions based on multiple features.

## Current Approach

- **Input**: max_util only
- **Output**: PWM via linear interpolation on 11 fixed points
- **Limitation**: Can't account for current thermal state, trends, or non-linear relationships

## Proposed Approach

### Features (Inputs)

| Feature | Description | Rationale |
|---------|-------------|-----------|
| `max_power` | Max GPU power draw (W) | **Primary heat indicator** - directly causal to temp |
| `max_util` | Max GPU utilization (0-100) | Load indicator (less causal than power) |
| `max_temp` | Max junction temp (°C) | Current thermal state |
| `temp_trend` | Rate of temp change (°C/s) | Predict where temps are heading |
| `power_trend` | Rate of power change (W/s) | Early warning of heat generation |
| `current_pwm` | Current PWM setting | Smooth transitions |

### Output

- **PWM value** (110-255): Continuous output, not bucketed

### Model Options

1. **Gradient Boosting (LightGBM/XGBoost)**
   - Pros: Fast inference (~1ms), handles tabular data well, interpretable
   - Cons: May produce discontinuous outputs

2. **Small Neural Net (2-3 layers)**
   - Pros: Smooth continuous outputs, can learn complex patterns
   - Cons: Slightly slower (~3-5ms), less interpretable

3. **2D Lookup Table with Interpolation**
   - Pros: Fastest inference, predictable
   - Cons: Limited to 2 dimensions, requires manual binning

**Recommendation**: Start with LightGBM for speed and interpretability.

### Training Methodology

The key insight from the current system: we want to learn what PWM values **actually kept temps safe**, not predict temps from features.

**Approach:**
1. Collect data at 10-20Hz with the new sysfs-based polling
2. Label samples by outcome:
   - "safe": max_temp stayed <= 82°C for next N seconds
   - "hot": max_temp exceeded 85°C within N seconds
3. For each feature combination, find the minimum PWM that achieved "safe" outcomes
4. Train model to predict this optimal PWM

**Alternative (regression):**
- Train to predict `temp_delta` (temp change over next N samples)
- Use model to find PWM that minimizes predicted temp rise

### Training Script Changes

```python
# New features to compute from rolling windows
features = {
    'max_util': current max utilization,
    'max_temp': current max junction temp,
    'temp_trend': (temp[-1] - temp[-5]) / (5 * poll_interval),
    'util_trend': (util[-1] - util[-5]) / (5 * poll_interval),
    'current_pwm': current PWM setting,
}

# Label: what happened next?
# Look ahead N samples to see if temps stayed safe
```

### Inference Integration

```python
import lightgbm as lgb

class FanController:
    def __init__(self):
        # Load trained model
        self.model = lgb.Booster(model_file='/opt/gpu-fan-control/fan_model.lgb')

    def get_model_pwm(self, max_util, max_temp, temp_trend, util_trend, current_pwm):
        features = [[max_util, max_temp, temp_trend, util_trend, current_pwm]]
        pwm = self.model.predict(features)[0]
        return int(np.clip(pwm, MIN_PWM, MAX_PWM))
```

### Safety Constraints

The model output should be treated as a suggestion, with hard limits:

1. **Emergency override**: If `max_temp >= 92°C`, force PWM to 255 regardless of model
2. **Minimum PWM**: Never go below 110 (idle cooling)
3. **Rate limiting**: Still apply rate limiting on decreases to prevent oscillation
4. **Fallback**: If model inference fails, fall back to current rule-based curve

## Data Collection Plan

### Phase 1: Collect High-Frequency Data (Current)
- Polling at 10-20Hz with sysfs reads
- Log: timestamp, gpu0_temp, gpu0_util, gpu1_temp, gpu1_util, max_temp, max_util, pwm
- Duration: 1-2 weeks of typical workload

### Phase 2: Feature Engineering
- Compute rolling statistics (trends, averages)
- Label samples with forward-looking outcomes
- Split into train/validation/test sets

### Phase 3: Model Training
- Train LightGBM regressor
- Validate on held-out data
- Compare against current rule-based system

### Phase 4: Deployment
- A/B test: alternate between model and rule-based
- Monitor thermal outcomes
- Iterate on features/model if needed

## Success Metrics

1. **Max temp reduction**: Target < 90°C at sustained 100% load (currently hits 94-95°C)
2. **Temp stability**: Fewer spikes, smoother curves
3. **Response time**: Faster PWM adjustment when load changes
4. **Fan noise**: Avoid unnecessary high-speed fan operation when temps are safe

## Files

- `ml-fan-control.py` - Main control script (update for inference)
- `train_model.py` - New training script for ML model (to be created)
- `fan_model.lgb` - Trained LightGBM model (to be generated)
- `/var/log/gpu-fan-control.csv` - Training data source

## Timeline

1. **Now**: Collect data with new 10-20Hz polling
2. **After 1-2 weeks**: Train initial model
3. **Test**: Deploy with safety fallbacks
4. **Iterate**: Refine based on results
