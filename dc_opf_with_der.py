import pyomo.environ as pyo

def build_dc_opf_with_der_model(case_data, der_data, load_profile, solar_profile, price_profile):
    """
    Builds a multi-period DC OPF model with DERs and storage.
    """
    model = pyo.ConcreteModel()

    # --- SETS ---
    model.T = pyo.RangeSet(1, 24)  # 24-hour time horizon
    model.buses = pyo.Set(initialize=[int(b[0]) for b in case_data['bus']])
    model.generators = pyo.Set(initialize=[int(g[0]) for g in case_data['gen']])
    model.branches = pyo.Set(initialize=range(len(case_data['branch'])))
    model.solar_pvs = pyo.Set(initialize=range(len(der_data['solar_pvs'])))
    model.batteries = pyo.Set(initialize=range(len(der_data['batteries'])))

    # --- PARAMETERS ---
    base_mva = case_data['baseMVA']

    # Time-varying load and price
    model.bus_pd = pyo.Param(model.buses, model.T, initialize={(int(b[0]), t): b[2] * load_profile[t-1] / base_mva for b in case_data['bus'] for t in model.T})
    model.price = pyo.Param(model.T, initialize={t: p for t, p in enumerate(price_profile, 1)})

    # Generator data
    gen_p_min = {int(g[0]): g[9] / base_mva for g in case_data['gen']}
    gen_p_max = {int(g[0]): g[8] / base_mva for g in case_data['gen']}
    model.gen_bus = pyo.Param(model.generators, initialize={int(g[0]): int(g[0]) for g in case_data['gen']})

    # Branch data
    model.branch_x = pyo.Param(model.branches, initialize={i: b[3] for i, b in enumerate(case_data['branch'])})
    model.branch_from = pyo.Param(model.branches, initialize={i: int(b[0]) for i, b in enumerate(case_data['branch'])})
    model.branch_to = pyo.Param(model.branches, initialize={i: int(b[1]) for i, b in enumerate(case_data['branch'])})
    model.branch_limit = pyo.Param(model.branches, initialize={i: 9999 / base_mva for i, b in enumerate(case_data['branch'])})

    # Solar PV data
    model.pv_bus = pyo.Param(model.solar_pvs, initialize={i: pv['bus'] for i, pv in enumerate(der_data['solar_pvs'])})
    model.pv_capacity = pyo.Param(model.solar_pvs, initialize={i: pv['capacity_mw'] / base_mva for i, pv in enumerate(der_data['solar_pvs'])})
    model.pv_profile = pyo.Param(model.T, initialize={t: p for t, p in enumerate(solar_profile, 1)})

    # Battery data
    model.battery_bus = pyo.Param(model.batteries, initialize={i: b['bus'] for i, b in enumerate(der_data['batteries'])})
    model.b_p_max = pyo.Param(model.batteries, initialize={i: b['power_mw'] / base_mva for i, b in enumerate(der_data['batteries'])})
    model.b_e_max = pyo.Param(model.batteries, initialize={i: b['energy_mwh'] / base_mva for i, b in enumerate(der_data['batteries'])})
    model.b_eff_ch = pyo.Param(model.batteries, initialize={i: b['eff_charge'] for i, b in enumerate(der_data['batteries'])})
    model.b_eff_dis = pyo.Param(model.batteries, initialize={i: b['eff_discharge'] for i, b in enumerate(der_data['batteries'])})

    # --- VARIABLES ---
    model.p_gen = pyo.Var(model.generators, model.T, within=pyo.NonNegativeReals)
    model.theta = pyo.Var(model.buses, model.T)
    model.p_solar = pyo.Var(model.solar_pvs, model.T, within=pyo.NonNegativeReals)
    model.p_charge = pyo.Var(model.batteries, model.T, within=pyo.NonNegativeReals)
    model.p_discharge = pyo.Var(model.batteries, model.T, within=pyo.NonNegativeReals)
    model.soc = pyo.Var(model.batteries, pyo.RangeSet(0, 24), within=pyo.NonNegativeReals) # State of Charge

    # --- OBJECTIVE FUNCTION ---
    def total_cost_rule(model):
        # Minimize the total cost of energy purchased from the grid
        return sum(model.price[t] * model.p_gen[g, t] * base_mva for g in model.generators for t in model.T)
    model.objective = pyo.Objective(rule=total_cost_rule, sense=pyo.minimize)

    # --- CONSTRAINTS ---
    # Generator limits
    def p_gen_limits_rule(model, g, t):
        return pyo.inequality(gen_p_min[g], model.p_gen[g, t], gen_p_max[g])
    model.p_gen_limits = pyo.Constraint(model.generators, model.T, rule=p_gen_limits_rule)

    # Solar PV limits
    def p_solar_limits_rule(model, pv, t):
        return model.p_solar[pv, t] <= model.pv_capacity[pv] * model.pv_profile[t]
    model.p_solar_limits = pyo.Constraint(model.solar_pvs, model.T, rule=p_solar_limits_rule)

    # Battery constraints
    def soc_update_rule(model, bess, t):
        if t == 0:
            return pyo.Constraint.Skip
        return model.soc[bess, t] == model.soc[bess, t-1] + model.b_eff_ch[bess] * model.p_charge[bess, t] - (1/model.b_eff_dis[bess]) * model.p_discharge[bess, t]
    model.soc_update = pyo.Constraint(model.batteries, model.T, rule=soc_update_rule)

    def soc_limits_rule(model, bess, t):
        return model.soc[bess, t] <= model.b_e_max[bess]
    model.soc_limits = pyo.Constraint(model.batteries, model.T, rule=soc_limits_rule)

    def charge_limits_rule(model, bess, t):
        return model.p_charge[bess, t] <= model.b_p_max[bess]
    model.charge_limits = pyo.Constraint(model.batteries, model.T, rule=charge_limits_rule)

    def discharge_limits_rule(model, bess, t):
        return model.p_discharge[bess, t] <= model.b_p_max[bess]
    model.discharge_limits = pyo.Constraint(model.batteries, model.T, rule=discharge_limits_rule)

    # Initial and final SOC
    def soc_cycle_rule(model, bess):
        return model.soc[bess, 0] == model.soc[bess, 24]
    model.soc_cycle = pyo.Constraint(model.batteries, rule=soc_cycle_rule)

    def initial_soc_rule(model, bess):
        return model.soc[bess, 0] == model.b_e_max[bess] * 0.5
    model.initial_soc = pyo.Constraint(model.batteries, rule=initial_soc_rule)

    # Power balance at each bus for each time step
    def power_balance_rule(model, b, t):
        # Injections
        gen_inj = sum(model.p_gen[g, t] for g in model.generators if model.gen_bus[g] == b)
        solar_inj = sum(model.p_solar[pv, t] for pv in model.solar_pvs if model.pv_bus[pv] == b)
        discharge_inj = sum(model.p_discharge[bess, t] for bess in model.batteries if model.battery_bus[bess] == b)

        # Withdrawals
        load_wd = model.bus_pd[b, t]
        charge_wd = sum(model.p_charge[bess, t] for bess in model.batteries if model.battery_bus[bess] == b)

        # Flows
        flow_out = sum((1/model.branch_x[br]) * (model.theta[model.branch_from[br], t] - model.theta[model.branch_to[br], t]) for br in model.branches if model.branch_from[br] == b)
        flow_in = sum((1/model.branch_x[br]) * (model.theta[model.branch_to[br], t] - model.theta[model.branch_from[br], t]) for br in model.branches if model.branch_to[br] == b)

        return gen_inj + solar_inj + discharge_inj - load_wd - charge_wd == flow_out + flow_in
    model.power_balance = pyo.Constraint(model.buses, model.T, rule=power_balance_rule)

    # Branch flow limits
    def branch_flow_rule(model, br, t):
        from_bus = model.branch_from[br]
        to_bus = model.branch_to[br]
        limit = model.branch_limit[br]
        flow = (1/model.branch_x[br]) * (model.theta[from_bus, t] - model.theta[to_bus, t])
        return pyo.inequality(-limit, flow, limit)
    model.branch_flow_limits = pyo.Constraint(model.branches, model.T, rule=branch_flow_rule)

    # Reference bus angle
    ref_bus_id = [int(b[0]) for b in case_data['bus'] if b[1] == 3][0]
    def ref_bus_angle_rule(model, t):
        return model.theta[ref_bus_id, t] == 0
    model.ref_bus_angle = pyo.Constraint(model.T, rule=ref_bus_angle_rule)

    return model
