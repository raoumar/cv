import argparse
import os
import pyomo.environ as pyo

from data_parser import parse_matpower_case_string
from system_data_extended import (data_33_bus, data_123_bus, load_profile,
                                  solar_profile, price_profile)
from dc_opf import build_dc_opf_model
from dc_opf_with_der import build_dc_opf_with_der_model
from resilience_opf import build_resilience_opf_model

def run_model(system, model_type):
    """
    Parses data, builds and solves the selected model for the selected system.
    """
    print(f"--- Running Model ---")
    print(f"System: {system}")
    print(f"Model Type: {model_type}")
    print("-" * 25)

    # 1. Select and parse data
    if system == '33bus':
        system_data = data_33_bus
    elif system == '123bus':
        system_data = data_123_bus
    else:
        raise ValueError("Invalid system type specified.")

    case_data = parse_matpower_case_string(system_data['case_string'])
    if not case_data:
        print("Failed to parse case data. Exiting.")
        return

    # 2. Build the selected model
    print("Building the optimization model...")
    if model_type == 'basic':
        model = build_dc_opf_model(case_data)
    elif model_type == 'der':
        model = build_dc_opf_with_der_model(case_data, system_data['der_data'], load_profile, solar_profile, price_profile)
    elif model_type == 'resilience':
        model = build_resilience_opf_model(case_data, system_data['der_data'], load_profile, solar_profile,
                                           price_profile, system_data['contingency_scenarios'], system_data['load_shed_cost'])
    else:
        raise ValueError("Invalid model type specified.")

    # 3. Solve the model
    print("Model built. Sending to NEOS for solving...")

    # Check for NEOS email, as it's required for remote solving
    if 'NEOS_EMAIL' not in os.environ:
        print("\nERROR: NEOS requires a valid email address.")
        print("Please set the 'NEOS_EMAIL' environment variable before running.")
        print("Example: NEOS_EMAIL=you@example.com python main.py 33bus der")
        return

    solver_manager = pyo.SolverManagerFactory('neos')
    results = solver_manager.solve(model, solver='cbc')

    # 4. Print results
    print("\n--- Solver Results ---")
    print(f"Status: {results.solver.status}")
    print(f"Termination condition: {results.solver.termination_condition}")

    if results.solver.termination_condition == pyo.TerminationCondition.optimal:
        print(f"Objective Cost: ${pyo.value(model.objective):.2f}")
    else:
        print("No optimal solution found.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Run power system optimization models.")
    parser.add_argument('system', choices=['33bus', '123bus'], help="The power system to use.")
    parser.add_argument('model_type', choices=['basic', 'der', 'resilience'], help="The type of optimization model to run.")

    args = parser.parse_args()

    run_model(args.system, args.model_type)
