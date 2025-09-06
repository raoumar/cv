import pyomo.environ as pyo
from data_parser import parse_matpower_case_string
from system_data_extended import data_33_bus

def build_dc_opf_model(case_data):
    """
    Builds a DC Optimal Power Flow (OPF) model using Pyomo.

    Args:
        case_data: A dictionary containing the parsed MATPOWER case data.

    Returns:
        A Pyomo ConcreteModel instance representing the DC OPF problem.
    """
    model = pyo.ConcreteModel()

    # --- SETS ---
    model.buses = pyo.Set(initialize=[int(b[0]) for b in case_data['bus']])
    model.generators = pyo.Set(initialize=[int(g[0]) for g in case_data['gen']])
    model.branches = pyo.Set(initialize=range(len(case_data['branch'])))

    # --- PARAMETERS ---
    # Bus data
    model.bus_pd = pyo.Param(model.buses, initialize={int(b[0]): b[2] for b in case_data['bus']})
    model.bus_qd = pyo.Param(model.buses, initialize={int(b[0]): b[3] for b in case_data['bus']})

    # Generator data
    base_mva = case_data['baseMVA']
    gen_p_min = {int(g[0]): g[9] / base_mva for g in case_data['gen']}
    gen_p_max = {int(g[0]): g[8] / base_mva for g in case_data['gen']}
    model.gen_bus = pyo.Param(model.generators, initialize={int(g[0]): int(g[0]) for g in case_data['gen']})

    # Branch data
    model.branch_r = pyo.Param(model.branches, initialize={i: b[2] for i, b in enumerate(case_data['branch'])})
    model.branch_x = pyo.Param(model.branches, initialize={i: b[3] for i, b in enumerate(case_data['branch'])})
    model.branch_from = pyo.Param(model.branches, initialize={i: int(b[0]) for i, b in enumerate(case_data['branch'])})
    model.branch_to = pyo.Param(model.branches, initialize={i: int(b[1]) for i, b in enumerate(case_data['branch'])})
    model.branch_limit = pyo.Param(model.branches, initialize={i: 9999 / base_mva for i, b in enumerate(case_data['branch'])})

    # Generator cost data
    gen_cost_c1 = {int(case_data['gen'][i][0]): case_data['gencost'][i][5] for i in range(len(case_data['gen']))}

    # --- VARIABLES ---
    model.p_gen = pyo.Var(model.generators, within=pyo.NonNegativeReals)
    model.theta = pyo.Var(model.buses)

    # --- OBJECTIVE FUNCTION ---
    def total_cost_rule(model):
        return sum(gen_cost_c1[g] * model.p_gen[g] * base_mva for g in model.generators)
    model.objective = pyo.Objective(rule=total_cost_rule, sense=pyo.minimize)

    # --- CONSTRAINTS ---
    # Generator power limits
    def p_gen_limits_rule(model, g):
        return pyo.inequality(gen_p_min[g], model.p_gen[g], gen_p_max[g])
    model.p_gen_limits = pyo.Constraint(model.generators, rule=p_gen_limits_rule)

    # Power balance at each bus
    def power_balance_rule(model, b):
        power_in = sum(model.p_gen[g] for g in model.generators if model.gen_bus[g] == b)
        power_out_load = model.bus_pd[b] / base_mva

        power_flow_out = sum(
            (1/model.branch_x[br]) * (model.theta[model.branch_from[br]] - model.theta[model.branch_to[br]])
            for br in model.branches if model.branch_from[br] == b
        )
        power_flow_in = sum(
            (1/model.branch_x[br]) * (model.theta[model.branch_to[br]] - model.theta[model.branch_from[br]])
            for br in model.branches if model.branch_to[br] == b
        )

        return power_in - power_out_load == power_flow_out + power_flow_in
    model.power_balance = pyo.Constraint(model.buses, rule=power_balance_rule)

    # Branch flow limits
    def branch_flow_rule(model, br):
        from_bus = model.branch_from[br]
        to_bus = model.branch_to[br]
        limit = model.branch_limit[br]
        flow = (1/model.branch_x[br]) * (model.theta[from_bus] - model.theta[to_bus])
        return pyo.inequality(-limit, flow, limit)
    model.branch_flow_limits = pyo.Constraint(model.branches, rule=branch_flow_rule)

    # Reference bus angle
    ref_bus_id = [int(b[0]) for b in case_data['bus'] if b[1] == 3][0]
    model.ref_bus_angle = pyo.Constraint(expr=model.theta[ref_bus_id] == 0)

    return model
