"""
Generator for realistic electronic component burn-in screening dataset.
Based on standard AEC-Q100 / MIL-STD-883 HTOL stress testing profiles.
Generates genuine physical measurement distributions without random garbage.
"""
import numpy as np
import pandas as pd

def generate_sample_burnin_dataset(output_path: str = "data/samples/htol_burnin_measurements.csv"):
    np.random.seed(42)
    timepoints = [0.0, 24.0, 48.0, 72.0, 96.0, 120.0, 144.0, 168.0] # 168h standard burn-in
    
    rows = []
    
    # 60 components across 2 lots
    lots = ["LOT_2026_HTOL_A", "LOT_2026_HTOL_B"]
    
    for i in range(1, 61):
        dut_id = f"DUT_{i:03d}"
        lot = lots[0] if i <= 30 else lots[1]
        test_cond = "HTOL_125C_3V3"
        
        # Base healthy component characteristics
        base_temp = 125.0 + np.random.normal(0, 0.4)
        base_v = 3.30 + np.random.normal(0, 0.005)
        base_curr = 12.5 + np.random.normal(0, 0.25)
        base_res = 115.0 + np.random.normal(0, 2.5) # mOhm
        base_leak = 0.12 + np.random.exponential(0.04) # uA
        
        # Anomaly archetypes:
        is_high_drift = (i == 7)     # Sneaky drift: passes static limit 140 mOhm, but +23% slope
        is_leak_escal = (i == 19)    # Leakage escalation: passes static limit 1.0 uA, but 4x jump
        is_instability = (i == 28)   # Severe measurement jitter / instability
        is_step_jump = (i == 43)     # Sudden step jump at 72h
        is_vref_drop = (i == 52)     # Subtle voltage degradation
        is_static_fail = (i == 58)   # Hard static limit violator (RDS > 140 mOhm at end)
        
        for t_idx, t in enumerate(timepoints):
            temp = base_temp + np.random.normal(0, 0.2)
            
            # Normal thermal drift: very small linear drift or settling
            normal_drift_res = 0.015 * t # ~2.5 mOhm drift over 168h (~2%)
            normal_drift_curr = 0.0008 * t
            normal_drift_v = -0.00005 * t
            normal_drift_leak = 0.0002 * t
            
            noise_res = np.random.normal(0, 0.2)
            noise_curr = np.random.normal(0, 0.02)
            noise_v = np.random.normal(0, 0.001)
            noise_leak = np.random.normal(0, 0.005)
            
            v = base_v + normal_drift_v + noise_v
            curr = base_curr + normal_drift_curr + noise_curr
            res = base_res + normal_drift_res + noise_res
            leak = base_leak + normal_drift_leak + noise_leak
            
            # Inject realistic degradation patterns
            if is_high_drift:
                # Steep linear degradation: +0.12 mOhm/hr -> +20 mOhm over 168h
                # Starts at 114, ends at 134.2 mOhm (limit is 140 mOhm)
                res = base_res + 0.125 * t + np.random.normal(0, 0.25)
                curr = base_curr + 0.004 * t
                
            elif is_leak_escal:
                # Exponential leakage current degradation
                leak = base_leak + 0.00003 * (t ** 1.9) + np.random.normal(0, 0.01)
                
            elif is_instability:
                # High erratic variance due to thermal interface void
                res = base_res + np.random.normal(0, 4.2)
                curr = base_curr + np.random.normal(0, 0.6)
                leak = base_leak + abs(np.random.normal(0, 0.08))
                
            elif is_step_jump:
                # Step jump after t >= 72h
                jump = 14.5 if t >= 72.0 else 0.0
                res = base_res + normal_drift_res + jump + np.random.normal(0, 0.2)
                if t >= 72.0:
                    curr += 0.45
                    
            elif is_vref_drop:
                # Gradual bandgap reference voltage collapse
                v = base_v - 0.0008 * t + np.random.normal(0, 0.002)
                
            elif is_static_fail:
                # Exceeds limit at t >= 120h
                res = base_res + 0.19 * t + np.random.normal(0, 0.3)
            
            # Physical power dissipation P = V * I + I^2 * R
            power = round((v * curr) + ((curr / 1000.0) ** 2) * (res / 1000.0) * 1000.0, 3)
            
            rows.append({
                "component_id": dut_id,
                "batch_id": lot,
                "test_id": test_cond,
                "timestamp": t,
                "temperature_c": round(float(temp), 2),
                "voltage_v": round(float(v), 4),
                "current_ma": round(float(curr), 3),
                "resistance_mohm": round(float(res), 2),
                "leakage_current_ua": round(max(0.01, float(leak)), 4),
                "power_consumption_mw": power
            })
            
    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False)
    print(f"Generated {len(df)} records across {df['component_id'].nunique()} components at '{output_path}'.")

if __name__ == "__main__":
    generate_sample_burnin_dataset()
