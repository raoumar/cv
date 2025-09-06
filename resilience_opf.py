import pyomo.environ as pyo

def build_resilience_opf_model(case_data, der_data, load_profile, solar_profile, price_profile,
                               contingencies, shed_cost):
    """
    Builds a two-stage stochastic DC OPF model for resilience.
    """
    model = pyo.ConcreteModel()

    # --- SETS ---
    model.T = pyo.RangeSet(1, 24)
    model.Scenarios = pyo.Set(initialize=contingencies.keys())
    model.buses = pyo.Set(initialize=[int(b[0]) for b in case_data['bus']])
    model.generators = pyo.Set(initialize=[int(g[0]) for g in case_data['gen']])
    model.branches = pyo.Set(initialize=range(len(case_data['branch'])))
    model.solar_pvs = pyo.Set(initialize=range(len(der_data['solar_pvs'])))
    model.batteries = pyo.Set(initialize=range(len(der_data['batteries'])))

    # --- PARAMETERS ---
    base_mva = case_data['baseMVA']
    num_scenarios = len(model.Scenarios)
    scenario_prob = 1.0 / num_scenarios

    model.bus_pd = pyo.Param(model.buses, model.T, initialize={(int(b[0]), t): b[2] * load_profile[t-1] / base_mva for b in case_data['bus'] for t in model.T})
    model.price = pyo.Param(model.T, initialize={t: p for t, p in enumerate(price_profile, 1)})
    model.contingency_branch = pyo.Param(model.Scenarios, initialize=contingencies, within=pyo.Any)
    model.load_shed_cost = pyo.Param(initialize=shed_cost)

    # (Other parameters for gen, branch, pv, battery are the same as before)
    gen_p_min = {int(g[0]): g[9] / base_mva for g in case_data['gen']}
    gen_p_max = {int(g[0]): g[8] / base_mva for g in case_data['gen']}
    model.gen_bus = pyo.Param(model.generators, initialize={int(g[0]): int(g[0]) for g in case_data['gen']})
    model.branch_x = pyo.Param(model.branches, initialize={i: b[3] for i, b in enumerate(case_data['branch'])})
    model.branch_from = pyo.Param(model.branches, initialize={i: int(b[0]) for i, b in enumerate(case_data['branch'])})
    model.branch_to = pyo.Param(model.branches, initialize={i: int(b[1]) for i, b in enumerate(case_data['branch'])})
    model.branch_limit = pyo.Param(model.branches, initialize={i: 9999 / base_mva for i, b in enumerate(case_data['branch'])})
    model.pv_bus = pyo.Param(model.solar_pvs, initialize={i: pv['bus'] for i, pv in enumerate(der_data['solar_pvs'])})
    model.pv_capacity = pyo.Param(model.solar_pvs, initialize={i: pv['capacity_mw'] / base_mva for i, pv in enumerate(der_data['solar_pvs'])})
    model.pv_profile = pyo.Param(model.T, initialize={t: p for t, p in enumerate(solar_profile, 1)})
    model.battery_bus = pyo.Param(model.batteries, initialize={i: b['bus'] for i, b in enumerate(der_data['batteries'])})
    model.b_p_max = pyo.Param(model.batteries, initialize={i: b['power_mw'] / base_mva for i, b in enumerate(der_data['batteries'])})
    model.b_e_max = pyo.Param(model.batteries, initialize={i: b['energy_mwh'] / base_mva for i, b in enumerate(der_data['batteries'])})
    model.b_eff_ch = pyo.Param(model.batteries, initialize={i: b['eff_charge'] for i, b in enumerate(der_data['batteries'])})
    model.b_eff_dis = pyo.Param(model.batteries, initialize={i: b['eff_discharge'] for i, b in enumerate(der_data['batteries'])})

    # --- STAGE 1 VARIABLES (Here-and-now) ---
    model.p_gen = pyo.Var(model.generators, model.T, within=pyo.NonNegativeReals)
    model.p_solar = pyo.Var(model.solar_pvs, model.T, within=pyo.NonNegativeReals)

    # --- STAGE 2 VARIABLES (Wait-and-see) ---
    model.p_charge = pyo.Var(model.batteries, model.T, model.Scenarios, within=pyo.NonNegativeReals)
    model.p_discharge = pyo.Var(model.batteries, model.T, model.Scenarios, within=pyo.NonNegativeReals)
    model.soc = pyo.Var(model.batteries, pyo.RangeSet(0, 24), model.Scenarios, within=pyo.NonNegativeReals)
    model.load_shed = pyo.Var(model.buses, model.T, model.Scenarios, within=pyo.NonNegativeReals)
    model.theta = pyo.Var(model.buses, model.T, model.Scenarios)

    # --- OBJECTIVE FUNCTION ---
    def total_cost_rule(model):
        op_cost = sum(model.price[t] * model.p_gen[g, t] * base_mva for g in model.generators for t in model.T)
        shed_cost = sum(scenario_prob * model.load_shed_cost * model.load_shed[b, t, s] * base_mva
                        for b in model.buses for t in model.T for s in model.Scenarios)
        return op_cost + shed_cost
    model.objective = pyo.Objective(rule=total_cost_rule, sense=pyo.minimize)

    # --- STAGE 1 CONSTRAINTS ---
    model.p_gen_limits = pyo.Constraint(model.generators, model.T, rule=lambda m, g, t: pyo.inequality(gen_p_min[g], m.p_gen[g, t], gen_p_max[g]))
    model.p_solar_limits = pyo.Constraint(model.solar_pvs, model.T, rule=lambda m, pv, t: m.p_solar[pv, t] <= m.pv_capacity[pv] * m.pv_profile[t])

    # --- STAGE 2 CONSTRAINTS (for each scenario) ---
    # Battery constraints are now scenario-dependent
    model.soc_update = pyo.Constraint(model.batteries, model.T, model.Scenarios, rule=lambda m, b, t, s: m.soc[b, t, s] == m.soc[b, t-1, s] + m.b_eff_ch[b] * m.p_charge[b, t, s] - (1/m.b_eff_dis[b]) * m.p_discharge[b, t, s] if t > 0 else pyo.Constraint.Skip)
    model.soc_limits = pyo.Constraint(model.batteries, model.T, model.Scenarios, rule=lambda m, b, t, s: m.soc[b, t, s] <= m.b_e_max[b])
    model.charge_limits = pyo.Constraint(model.batteries, model.T, model.Scenarios, rule=lambda m, b, t, s: m.p_charge[b, t, s] <= m.b_p_max[b])
    model.discharge_limits = pyo.Constraint(model.batteries, model.T, model.Scenarios, rule=lambda m, b, t, s: m.p_discharge[b, t, s] <= m.b_p_max[b])
    model.soc_cycle = pyo.Constraint(model.batteries, model.Scenarios, rule=lambda m, b, s: m.soc[b, 0, s] == m.soc[b, 24, s])
    model.initial_soc = pyo.Constraint(model.batteries, model.Scenarios, rule=lambda m, b, s: m.soc[b, 0, s] == m.b_e_max[b] * 0.5)

    def power_balance_rule(model, b, t, s):
        gen_inj = sum(model.p_gen[g, t] for g in model.generators if model.gen_bus[g] == b)
        solar_inj = sum(model.p_solar[pv, t] for pv in model.solar_pvs if model.pv_bus[pv] == b)
        discharge_inj = sum(model.p_discharge[bess, t, s] for bess in model.batteries if model.battery_bus[bess] == b)
        load_wd = model.bus_pd[b, t]
        charge_wd = sum(model.p_charge[bess, t, s] for bess in model.batteries if model.battery_bus[bess] == b)
        shed_wd = model.load_shed[b, t, s]
        flow_out = sum((1/model.branch_x[br]) * (model.theta[model.branch_from[br], t, s] - model.theta[model.branch_to[br], t, s]) for br in model.branches if model.branch_from[br] == b and br != model.contingency_branch[s])
        flow_in = sum((1/model.branch_x[br]) * (model.theta[model.branch_to[br], t, s] - model.theta[model.branch_from[br], t, s]) for br in model.branches if model.branch_to[br] == b and br != model.contingency_branch[s])
        return gen_inj + solar_inj + discharge_inj - load_wd - charge_wd + shed_wd == flow_out + flow_in
    model.power_balance = pyo.Constraint(model.buses, model.T, model.Scenarios, rule=power_balance_rule)

    def branch_flow_rule(model, br, t, s):
        if br == model.contingency_branch[s]:
            return pyo.Constraint.Skip # Line is out
        from_bus = model.branch_from[br]
        to_bus = model.branch_to[br]
        limit = model.branch_limit[br]
        flow = (1/model.branch_x[br]) * (model.theta[from_bus, t, s] - model.theta[to_bus, t, s])
        return pyo.inequality(-limit, flow, limit)
    model.branch_flow_limits = pyo.Constraint(model.branches, model.T, model.Scenarios, rule=branch_flow_rule)

    ref_bus_id = [int(b[0]) for b in case_data['bus'] if b[1] == 3][0]
    def ref_bus_angle_rule(model, t, s):
        return model.theta[ref_bus_id, t, s] == 0
    model.ref_bus_angle = pyo.Constraint(model.T, model.Scenarios, rule=ref_bus_angle_rule)

    def load_shed_positive_rule(model, b, t, s):
        return model.load_shed[b, t, s] <= model.bus_pd[b,t]
    model.load_shed_positive = pyo.Constraint(model.buses, model.T, model.Scenarios, rule=load_shed_positive_rule)

    def no_shed_in_base_case_rule(model, b, t):
        return model.load_shed[b, t, 0] == 0
    model.no_shed_in_base_case = pyo.Constraint(model.buses, model.T, rule=no_shed_in_base_case_rule)

    return model
