# MQ135 Calibration Guide for 650m Mountain Air

## Why Re-calibration is Needed

Your sensor currently reads **1.5 ppm CO₂** when outdoor air should read **410-420 ppm CO₂**.
The R_ZERO value (baseline resistance in clean air) is incorrect.

**You're at 650m altitude in the mountains** = PERFECT for calibration!
Mountain air is clean and stable = ideal baseline.

---

## Calibration Steps

### Step 1: Upload Calibration Firmware
```bash
# The calibrate_mq135.ino firmware will display raw sensor readings
# Upload it to Arduino Due now
```

### Step 2: Place Sensor Outside (Warm-up Phase)
- Place **MQ135 outdoors** in open air (not in direct sun, protected from rain)
- **Let it warm up for 30-60 minutes**
- Watch the serial output - voltage and resistance will stabilize

### Step 3: Monitor Stabilization
Open serial monitor at 115200 baud. You'll see:
```
Sample #10  | V=0.215V | R=189000Ω | Rs/R0=4.47
Sample #20  | V=0.218V | R=188500Ω | Rs/R0=4.46
Sample #30  | V=0.220V | R=187800Ω | Rs/R0=4.44
...
```

**Wait until voltage stabilizes** (stops changing significantly between readings)

### Step 4: Calculate New R_ZERO
When stabilized after 30-60 min, note the **stable resistance value**.

This is your NEW R_ZERO for 650m mountain air!

**Example:** If resistance stabilizes at 95,000Ω, then:
```
NEW R_ZERO = 95000.0
```

### Step 5: Update Config.h
Edit `Config.h` around line 20:
```cpp
// OLD (factory default):
const float MQ135_R_ZERO = 280000.0;

// NEW (your calibration):
const float MQ135_R_ZERO = 95000.0;  // <- Update this value!
```

> **Important:** MQ135 must be powered at **3.3V** during calibration and normal operation. Powering at 5V changes the heater current and sensor resistance, invalidating the R_ZERO calibration.

### Step 6: Recompile and Upload Main Firmware
```bash
# Re-upload ardudueair.ino with new R_ZERO
# Now readings should show ~410-420 ppm CO₂
```

### Step 7: Verify
Expected readings in clean mountain air:
- **CO₂**: 410-450 ppm ✓
- **NH₃**: 10-30 ppm ✓
- **Alcohol**: 5-15 ppm ✓
- **Status**: "Good" or "Fair" ✓
- **Voltage**: 0.2-0.4V ✓

---

## Timeline
- **5 min warm-up**: Voltage still changing
- **15 min warm-up**: Stabilizing
- **30-60 min warm-up**: STABLE (use this reading!)
- **After calibration**: Outdoor CO₂ readings correct

---

## Why Mountain Air = Perfect Baseline
✓ Low pollution
✓ Stable atmospheric conditions
✓ No indoor sources (cooking, breathing, etc.)
✓ Standard CO₂ baseline (~410 ppm)
✓ Perfect for R_ZERO reference

Your location is ideal! Don't use indoor calibration - mountain air is much better.
