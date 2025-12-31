import math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st

# -----------------------------
# Simulation core (event-driven)
# -----------------------------
def simulate_inventory_des(
    horizon_days: float,
    s: int,
    S: int,
    demand_rate_per_day: float,
    lead_time_dist: str,
    lead_time_a: float,
    lead_time_b: float,
    holding_cost_per_unit_day: float,
    stockout_penalty_per_unit: float,
    fixed_order_cost: float,
    allow_backorders: bool,
    seed: int,
):
    """
    Continuous review (s, S) policy, single SKU, single supplier.
    One outstanding order at a time (simple + fast).
    Demand arrivals: Poisson process (exponential inter-arrival), unit-sized.
    Lead time: Uniform(a,b) or Normal(mean=a, std=b) clipped at >=0.
    Costs:
      - Holding: inventory_on_hand * holding_cost_per_unit_day * dt
      - Stockout penalty: per unit demand not immediately filled (or lost sales)
      - Fixed ordering cost: each time we place an order
    Service Level:
      - Fill rate = immediate fills / total demand units
    """
    rng = np.random.default_rng(seed)

    def sample_lead_time():
        if lead_time_dist == "Uniform":
            return float(rng.uniform(lead_time_a, lead_time_b))
        # Normal: a=mean, b=std
        lt = float(rng.normal(lead_time_a, lead_time_b))
        return max(0.0, lt)

    t = 0.0
    inv_on_hand = int(S)  # start full
    backorders = 0
    on_order_qty = 0
    order_arrival_time = math.inf

    # next demand arrival time
    if demand_rate_per_day <= 0:
        next_demand_time = math.inf
    else:
        next_demand_time = float(rng.exponential(1.0 / demand_rate_per_day))

    # metrics
    total_demand = 0
    immediate_fills = 0
    orders_placed = 0
    holding_cost = 0.0
    stockout_cost = 0.0
    ordering_cost = 0.0

    # helper
    def inventory_position():
        return inv_on_hand + on_order_qty - backorders

    def maybe_reorder(now_time: float):
        nonlocal on_order_qty, order_arrival_time, orders_placed, ordering_cost
        if inventory_position() <= s and on_order_qty == 0:
            qty = max(0, int(S - inventory_position()))
            if qty > 0:
                on_order_qty = qty
                orders_placed += 1
                ordering_cost += fixed_order_cost
                order_arrival_time = now_time + sample_lead_time()

    # initial reorder check (usually no, since inv=S)
    maybe_reorder(t)

    # main event loop
    while t < horizon_days:
        next_event_time = min(next_demand_time, order_arrival_time, horizon_days)
        dt = next_event_time - t

        # accrue holding cost over dt (only on-hand inventory counts)
        if dt > 0 and inv_on_hand > 0:
            holding_cost += inv_on_hand * holding_cost_per_unit_day * dt

        t = next_event_time

        if t >= horizon_days:
            break

        # event: demand arrival
        if next_demand_time <= order_arrival_time:
            total_demand += 1
            if inv_on_hand > 0:
                inv_on_hand -= 1
                immediate_fills += 1
            else:
                # stockout
                stockout_cost += stockout_penalty_per_unit
                if allow_backorders:
                    backorders += 1
                # else: lost sale (do nothing)

            # schedule next demand
            next_demand_time = t + float(rng.exponential(1.0 / demand_rate_per_day)) if demand_rate_per_day > 0 else math.inf

            # reorder check after demand
            maybe_reorder(t)

        # event: replenishment arrival
        else:
            inv_on_hand += on_order_qty
            on_order_qty = 0
            order_arrival_time = math.inf

            # fill backorders first (if allowed)
            if allow_backorders and backorders > 0 and inv_on_hand > 0:
                fill = min(backorders, inv_on_hand)
                backorders -= fill
                inv_on_hand -= fill

            # reorder check after receipt (sometimes triggers if still low)
            maybe_reorder(t)

    service_level = (immediate_fills / total_demand) if total_demand > 0 else 1.0
    total_cost = holding_cost + stockout_cost + ordering_cost

    return {
        "service_level": service_level,
        "total_cost": total_cost,
        "holding_cost": holding_cost,
        "stockout_cost": stockout_cost,
        "ordering_cost": ordering_cost,
        "orders_placed": orders_placed,
        "total_demand": total_demand,
        "immediate_fills": immediate_fills,
        "ending_on_hand": inv_on_hand,
        "ending_backorders": backorders,
    }


def ci95(x: np.ndarray):
    """95% CI using normal approximation (fine for n>=30)."""
    x = np.asarray(x, dtype=float)
    n = x.size
    if n <= 1:
        return (float(x.mean()), float(x.mean()), float(x.mean()))
    m = float(x.mean())
    s = float(x.std(ddof=1))
    half = 1.96 * s / math.sqrt(n)
    return (m, m - half, m + half)


@st.cache_data(show_spinner=False)
def run_monte_carlo(config: dict, n_rep: int, seed0: int):
    services = []
    costs = []
    details = []

    for i in range(n_rep):
        out = simulate_inventory_des(seed=seed0 + i, **config)
        services.append(out["service_level"])
        costs.append(out["total_cost"])
        details.append(out)

    services = np.array(services)
    costs = np.array(costs)

    sm, sl, su = ci95(services)
    cm, cl, cu = ci95(costs)

    summary = {
        "service_mean": sm,
        "service_ci_low": sl,
        "service_ci_high": su,
        "cost_mean": cm,
        "cost_ci_low": cl,
        "cost_ci_high": cu,
    }

    return summary, pd.DataFrame(details)


@st.cache_data(show_spinner=False)
def grid_search_optimize(base_config: dict, s_values, S_values, n_rep: int, seed0: int, min_service: float):
    rows = []
    for s in s_values:
        for S in S_values:
            if S <= s:
                continue
            cfg = dict(base_config)
            cfg["s"] = int(s)
            cfg["S"] = int(S)
            summary, _ = run_monte_carlo(cfg, n_rep=n_rep, seed0=seed0 + 10_000 + int(s)*17 + int(S)*31)
            rows.append({
                "s": int(s),
                "S": int(S),
                **summary
            })

    df = pd.DataFrame(rows)
    if df.empty:
        return df, None

    feasible = df[df["service_mean"] >= min_service].copy()
    best = None
    if not feasible.empty:
        best = feasible.sort_values(["cost_mean", "service_mean"], ascending=[True, False]).iloc[0].to_dict()

    return df, best


# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(page_title="Inventory Digital Twin (s,S)", layout="wide")
st.title("Inventory Digital Twin — Simulation + Optimization (s, S)")

with st.sidebar:
    st.header("Model Settings")

    horizon_days = st.number_input("Simulation horizon (days)", min_value=30, max_value=3650, value=365, step=30)

    st.subheader("Demand")
    demand_rate = st.number_input("Demand rate (units/day)", min_value=0.1, max_value=500.0, value=20.0, step=1.0)

    st.subheader("Lead time")
    lead_dist = st.selectbox("Lead time distribution", ["Uniform", "Normal"], index=0)
    if lead_dist == "Uniform":
        lt_a = st.number_input("Lead time a (min days)", min_value=0.0, max_value=365.0, value=1.0, step=0.5)
        lt_b = st.number_input("Lead time b (max days)", min_value=0.0, max_value=365.0, value=5.0, step=0.5)
        if lt_b < lt_a:
            st.warning("For Uniform lead time, b should be ≥ a.")
    else:
        lt_a = st.number_input("Lead time mean (days)", min_value=0.0, max_value=365.0, value=3.0, step=0.5)
        lt_b = st.number_input("Lead time std (days)", min_value=0.0, max_value=365.0, value=1.0, step=0.5)

    st.subheader("Costs")
    holding_c = st.number_input("Holding cost (per unit-day)", min_value=0.0, max_value=1000.0, value=1.0, step=0.1)
    stockout_pen = st.number_input("Stockout penalty (per unit)", min_value=0.0, max_value=10000.0, value=20.0, step=1.0)
    order_fixed = st.number_input("Fixed ordering cost (per order)", min_value=0.0, max_value=100000.0, value=50.0, step=5.0)

    st.subheader("Policy + Evaluation")
    allow_backorders = st.checkbox("Allow backorders (else lost sales)", value=True)
    n_rep = st.slider("Monte Carlo replications", min_value=10, max_value=300, value=80, step=10)
    seed0 = st.number_input("Random seed base", min_value=0, max_value=10_000_000, value=42, step=1)

tab1, tab2, tab3 = st.tabs(["Run Simulation", "Scenario Analysis", "Optimize Policy"])

base_cfg_common = dict(
    horizon_days=float(horizon_days),
    demand_rate_per_day=float(demand_rate),
    lead_time_dist=str(lead_dist),
    lead_time_a=float(lt_a),
    lead_time_b=float(lt_b),
    holding_cost_per_unit_day=float(holding_c),
    stockout_penalty_per_unit=float(stockout_pen),
    fixed_order_cost=float(order_fixed),
    allow_backorders=bool(allow_backorders),
)

# -----------------------------
# TAB 1: Run Simulation
# -----------------------------
with tab1:
    colA, colB = st.columns([1, 2], gap="large")
    with colA:
        st.subheader("Choose a policy (s, S)")
        s_val = st.number_input("Reorder point s", min_value=0, max_value=10000, value=40, step=5)
        S_val = st.number_input("Order-up-to level S", min_value=1, max_value=10000, value=120, step=10)
        if S_val <= s_val:
            st.error("S must be > s.")

        run_btn = st.button("▶️ Run Monte Carlo", type="primary")

    with colB:
        st.subheader("Results")
        if run_btn and S_val > s_val:
            cfg = dict(base_cfg_common)
            cfg.update({"s": int(s_val), "S": int(S_val)})

            summary, df_runs = run_monte_carlo(cfg, n_rep=int(n_rep), seed0=int(seed0))

            m1, m2, m3 = st.columns(3)
            m1.metric("Service level (mean)", f"{summary['service_mean']*100:.2f}%",
                      f"95% CI: [{summary['service_ci_low']*100:.2f}%, {summary['service_ci_high']*100:.2f}%]")
            m2.metric("Total cost (mean)", f"{summary['cost_mean']:.1f}",
                      f"95% CI: [{summary['cost_ci_low']:.1f}, {summary['cost_ci_high']:.1f}]")
            m3.metric("Orders placed (avg)", f"{df_runs['orders_placed'].mean():.2f}")

            st.dataframe(df_runs.describe().T, use_container_width=True)

            csv = df_runs.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Download run-level results (CSV)", data=csv, file_name="mc_runs.csv", mime="text/csv")

# -----------------------------
# TAB 2: Scenario Analysis
# -----------------------------
with tab2:
    st.subheader("Compare scenarios (same policy, different conditions)")
    c1, c2 = st.columns([1, 2], gap="large")
    with c1:
        s_sc = st.number_input("Scenario policy s", min_value=0, max_value=10000, value=40, step=5, key="sc_s")
        S_sc = st.number_input("Scenario policy S", min_value=1, max_value=10000, value=120, step=10, key="sc_S")
        spike_pct = st.slider("Demand spike (%)", min_value=0, max_value=200, value=30, step=5)
        lt_mult = st.slider("Lead time multiplier (disruption)", min_value=1.0, max_value=5.0, value=1.5, step=0.1)
        run_scen = st.button("📊 Run scenario analysis")

    with c2:
        if run_scen and S_sc > s_sc:
            scenarios = []

            # Baseline
            cfg0 = dict(base_cfg_common); cfg0.update({"s": int(s_sc), "S": int(S_sc)})
            sum0, _ = run_monte_carlo(cfg0, n_rep=int(n_rep), seed0=int(seed0))
            scenarios.append(("Baseline", sum0))

            # Demand spike
            cfg1 = dict(cfg0)
            cfg1["demand_rate_per_day"] = cfg0["demand_rate_per_day"] * (1 + spike_pct / 100.0)
            sum1, _ = run_monte_carlo(cfg1, n_rep=int(n_rep), seed0=int(seed0) + 1000)
            scenarios.append((f"Demand +{spike_pct}%", sum1))

            # Lead time disruption
            cfg2 = dict(cfg0)
            if lead_dist == "Uniform":
                cfg2["lead_time_a"] = cfg0["lead_time_a"] * lt_mult
                cfg2["lead_time_b"] = cfg0["lead_time_b"] * lt_mult
            else:
                cfg2["lead_time_a"] = cfg0["lead_time_a"] * lt_mult
                cfg2["lead_time_b"] = cfg0["lead_time_b"] * lt_mult
            sum2, _ = run_monte_carlo(cfg2, n_rep=int(n_rep), seed0=int(seed0) + 2000)
            scenarios.append((f"Lead time ×{lt_mult:.1f}", sum2))

            # Create dataframe
            rows = []
            for name, ssum in scenarios:
                rows.append({
                    "scenario": name,
                    "service_mean": ssum["service_mean"],
                    "service_ci_low": ssum["service_ci_low"],
                    "service_ci_high": ssum["service_ci_high"],
                    "cost_mean": ssum["cost_mean"],
                    "cost_ci_low": ssum["cost_ci_low"],
                    "cost_ci_high": ssum["cost_ci_high"],
                })
            df_sc = pd.DataFrame(rows)
            st.dataframe(df_sc, use_container_width=True)

            # Plot service + cost
            fig = plt.figure()
            ax = plt.gca()
            ax.errorbar(
                df_sc["service_mean"],
                df_sc["cost_mean"],
                xerr=[df_sc["service_mean"] - df_sc["service_ci_low"], df_sc["service_ci_high"] - df_sc["service_mean"]],
                yerr=[df_sc["cost_mean"] - df_sc["cost_ci_low"], df_sc["cost_ci_high"] - df_sc["cost_mean"]],
                fmt="o",
            )
            for i, r in df_sc.iterrows():
                ax.annotate(r["scenario"], (r["service_mean"], r["cost_mean"]), xytext=(6, 6), textcoords="offset points")
            ax.set_xlabel("Service level (fill rate)")
            ax.set_ylabel("Total cost")
            ax.set_title("Scenario comparison (mean ± 95% CI)")
            st.pyplot(fig, clear_figure=True)

# -----------------------------
# TAB 3: Optimization
# -----------------------------
with tab3:
    st.subheader("Optimize (s, S) under a service constraint")
    left, right = st.columns([1, 2], gap="large")

    with left:
        min_service = st.slider("Minimum service level", min_value=0.80, max_value=0.999, value=0.98, step=0.005)

        st.caption("Grid ranges (keep small for speed; still impressive).")
        s_min = st.number_input("s min", min_value=0, max_value=10000, value=10, step=5)
        s_max = st.number_input("s max", min_value=0, max_value=10000, value=60, step=5)
        s_step = st.number_input("s step", min_value=1, max_value=500, value=5, step=1)

        S_min = st.number_input("S min", min_value=1, max_value=10000, value=60, step=10)
        S_max = st.number_input("S max", min_value=1, max_value=10000, value=140, step=10)
        S_step = st.number_input("S step", min_value=1, max_value=500, value=10, step=1)

        opt_rep = st.slider("Replications per policy (optimization)", min_value=10, max_value=150, value=40, step=10)

        optimize_btn = st.button("🧠 Optimize policy", type="primary")

    with right:
        if optimize_btn:
            s_vals = list(range(int(s_min), int(s_max) + 1, int(s_step))) if s_max >= s_min else []
            S_vals = list(range(int(S_min), int(S_max) + 1, int(S_step))) if S_max >= S_min else []

            df_grid, best = grid_search_optimize(
                base_config=dict(base_cfg_common, s=0, S=1),  # placeholder overwritten
                s_values=s_vals,
                S_values=S_vals,
                n_rep=int(opt_rep),
                seed0=int(seed0),
                min_service=float(min_service),
            )

            if df_grid.empty:
                st.warning("No policies evaluated (check grid ranges).")
            else:
                st.dataframe(df_grid.sort_values("cost_mean").head(25), use_container_width=True)

                if best is None:
                    st.error("No feasible policy met the service constraint. Try increasing S range or lowering constraint.")
                else:
                    st.success(f"Best feasible policy: (s={best['s']}, S={best['S']}) "
                               f"→ service={best['service_mean']*100:.2f}% | cost={best['cost_mean']:.1f}")

                # Plot cost vs service scatter
                fig = plt.figure()
                ax = plt.gca()
                ax.scatter(df_grid["service_mean"], df_grid["cost_mean"])

                # mark feasible region
                ax.axvline(float(min_service), linestyle="--")
                ax.set_xlabel("Service level (mean)")
                ax.set_ylabel("Total cost (mean)")
                ax.set_title("Policy trade-off: Cost vs Service (each dot = one (s,S))")

                if best is not None:
                    ax.scatter([best["service_mean"]], [best["cost_mean"]], s=120, marker="X")
                    ax.annotate("Best feasible", (best["service_mean"], best["cost_mean"]), xytext=(8, 8), textcoords="offset points")

                st.pyplot(fig, clear_figure=True)

                csv = df_grid.to_csv(index=False).encode("utf-8")
                st.download_button("⬇️ Download optimization grid (CSV)", data=csv, file_name="policy_grid.csv", mime="text/csv")


st.caption(
    "Model: single SKU, continuous review (s,S), stochastic demand + lead time. "
    "Service level = immediate fill rate. Costs: holding + stockout penalty + fixed order cost."
)
