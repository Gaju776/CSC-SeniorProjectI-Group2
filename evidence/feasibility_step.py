"""Feasibility spike for CSC 59866 DESIGN.md Section 9.

Question: does one reduced (cycle-averaged) converter-plus-storage model
produce a stable, bounded PCC-voltage response under a 20 MW load step,
without numerical stiffness, and does an undersized-storage variant produce
a failure the tool must report rather than mask (reference case U)?

Model (averaged, DC-equivalent; all parameters ASSUMED placeholders):
  Grid Thevenin :  L_g di_g/dt   = E_g - R_g i_g - v_pcc
  Input cap     :  C_in dv/dt    = i_g - i_c
  Converter lag :  tau_c di_c/dt + i_c = P_ac_ref / (eta * v_pcc)
  DC bus        :  C_dc dv_dc/dt = eta * v_pcc * i_c - P_load + P_batt
  Battery ctrl  :  P_batt = clip(Kp (V_ref - v_dc) + Ki x_i, +/- P_batt_max)
                  dx_i/dt = V_ref - v_dc
  P_ac_ref = P_load - P_batt   (DC-bus demand seen by the rectifier)

NOTE (finding of this spike): the battery is the only DC-bus regulating
element in this reduced model, so it supplies net energy indefinitely.
E_batt_J below is the cumulative energy it would have delivered; the
design consequence (battery SOC / recharge loop) is recorded in
DESIGN.md Section 9.

Run:  python evidence/feasibility_step.py
"""

import numpy as np
from scipy.integrate import solve_ivp

# --- assumed parameters (placeholder, not measured) ---
E_G = 7974.0        # V, phase-neutral equivalent of 13.8 kV LL
R_G = 0.2           # ohm
L_G = 10e-3         # H
C_IN = 2e-2         # F
C_DC = 1.0          # F
TAU_C = 0.05        # s, converter closed-loop lag
ETA = 0.97          # rectifier efficiency
V_DC_REF = 800.0    # V
K_P = 5e5           # W/V droop gain
K_I = 1e6           # W/(V s)
P_BASE = 40e6       # W
P_STEP = 20e6       # W
T_STEP = 2.0        # s
T_END = 10.0        # s


def simulate(p_batt_max=30e6, label="run", t_end=T_END):
    """Simulate one case; return a metrics dict."""
    def rhs(t, y):
        i_g, v, i_c, v_dc, x_i = y
        p_load = P_BASE + (P_STEP if t >= T_STEP else 0.0)
        p_batt = float(np.clip(K_P * (V_DC_REF - v_dc) + K_I * x_i,
                               -p_batt_max, p_batt_max))
        p_ac = max(p_load - p_batt, 1e3) / ETA
        i_ref = p_ac / max(v, 1.0)
        return [
            (E_G - R_G * i_g - v) / L_G,              # di_g
            (i_g - i_c) / C_IN,                        # dv_pcc
            (i_ref - i_c) / TAU_C,                     # di_c
            (ETA * v * i_c - p_load + p_batt) / C_DC,  # dv_dc
            V_DC_REF - v_dc,                           # d(x_i)
        ]

    y0 = [P_BASE / ETA / E_G, E_G, P_BASE / ETA / E_G, V_DC_REF, 0.0]
    sol = solve_ivp(rhs, [0, t_end], y0, method="LSODA",
                    dense_output=True, rtol=1e-6, atol=1e-3,
                    max_step=1e-3)
    if not sol.success:
        return {"label": label, "status": f"SOLVER FAILED: {sol.message}"}

    t = np.linspace(0, t_end, int(t_end * 2000) + 1)
    i_g, v, i_c, v_dc, x_i = sol.sol(t)
    if not np.isfinite(v).all() or not np.isfinite(v_dc).all():
        return {"label": label, "status": "NON-FINITE STATE (diverged)"}

    # battery power trace (recompute for reporting only)
    p_batt = np.clip(K_P * (V_DC_REF - v_dc) + K_I * x_i,
                     -p_batt_max, p_batt_max)
    e_batt_delivered = float(np.trapezoid(p_batt, t))  # J, + = discharged

    pre = float(v[t < 1.5].mean())
    post = float(v[t > t_end - 1.0].mean())
    m = (t >= T_STEP) & (t < t_end - 1.0)

    # physical-validity check: a settled-looking trace with states outside
    # plausible bounds is reported as UNSTABLE, not as a result (case U).
    plausible = (0.5 * E_G < post < 1.5 * E_G
                 and 0.0 < v_dc[m].min() and v_dc[m].max() < 2 * V_DC_REF)
    if not plausible:
        return {
            "label": label,
            "status": "UNSTABLE/NONPHYSICAL (v_dc or v_pcc out of bounds)",
            "v_pcc_post_V": round(post, 1),
            "v_dc_min_V": round(float(v_dc[m].min()), 1),
            "nfev": sol.nfev,
        }

    dev = v[m] - post
    band = 0.02 * abs(post)
    exc = np.where(np.abs(dev) > band)[0]
    t_settle = float(t[m][exc[-1]] - T_STEP) if len(exc) else 0.0
    peak_dev = float(np.max(np.abs(v[m] - pre)))
    vdc_min = float(v_dc[m].min())

    # C1-style energy check on the facility side:
    #   E_in = int(v_pcc * i_g) dt          (into the input capacitor)
    #   out   = E_load - E_batt + E_loss
    #   E_batt = int(P_batt) dt             (energy the battery supplies)
    #   E_loss = int(R_G i_g^2) dt + int((1-ETA) v i_c) dt
    #            + stored-energy change in the two capacitors
    p_in = v * i_g
    e_in = float(np.trapezoid(p_in, t))
    p_load_arr = P_BASE + np.where(t >= T_STEP, P_STEP, 0.0)
    e_load = float(np.trapezoid(p_load_arr, t))
    e_loss = float(
        np.trapezoid(R_G * i_g**2, t)
        + np.trapezoid((1 - ETA) * v * i_c, t)
        + 0.5 * C_IN * (v[-1]**2 - v[0]**2)
        + 0.5 * C_DC * (v_dc[-1]**2 - v_dc[0]**2))
    e_expected = e_load - e_batt_delivered + e_loss
    imbalance = (abs(e_in - e_expected) / abs(e_in)
                 if abs(e_in) > 0 else float("nan"))

    return {
        "label": label, "status": "ok",
        "v_pcc_pre_V": round(pre, 1),
        "v_pcc_post_V": round(post, 1),
        "peak_dev_vs_pre_V": round(peak_dev, 2),
        "settling_time_s": round(t_settle, 4),
        "v_dc_min_V": round(vdc_min, 1),
        "e_batt_delivered_J": round(e_batt_delivered, 0),
        "energy_imbalance": round(float(imbalance), 5),
        "nfev": sol.nfev,
    }


def zip_steady_state_v(p_load_w):
    """Static ZIP baseline: constant-power load P at the input capacitor.

    Steady state of  E_g = R_g i + v  with  i = P / v  gives
    v^2 - E_g v + R_g P = 0 ; take the high-voltage root.
    """
    disc = E_G**2 - 4 * R_G * p_load_w
    if disc < 0:
        return None  # beyond maximum power transfer -> collapse
    return (E_G + np.sqrt(disc)) / 2


if __name__ == "__main__":
    s = simulate(label="S nominal (30 MW battery)")
    # Case U: battery power rating below the 20 MW step -> DC bus must
    # collapse; the tool should report non-settling/instability, not a
    # settled result.
    u = simulate(p_batt_max=15e6, label="U undersized battery (15 MW)")
    for r in (s, u):
        print(r)
    v_zip = zip_steady_state_v(P_BASE + P_STEP)
    print({"label": "ZIP baseline (static, 60 MW)",
           "v_pcc_steady_V": None if v_zip is None else round(float(v_zip), 1)})
    if s.get("status") == "ok" and v_zip is not None:
        print({"label": "dynamic-vs-ZIP steady-state delta",
               "delta_V": round(s["v_pcc_post_V"] - float(v_zip), 1)})
