# Power System Optimization with Pyomo

This project provides a set of Python scripts for power system optimization, including economic dispatch and resilience analysis, using Pyomo for modeling and the NEOS server for solving.

## Project Overview

The project aims to demonstrate advanced power system optimization techniques on standard IEEE test systems. It includes three main models:
1.  **Basic DC OPF:** A simple economic dispatch model for a single time period.
2.  **OPF with DERs:** A multi-period (24-hour) model that includes time-varying loads, solar PV generation, and a battery energy storage system. This model demonstrates economic arbitrage of the battery based on time-of-use pricing.
3.  **Resilience OPF:** A two-stage stochastic optimization model that schedules the system to be resilient against a set of N-1 line contingencies, minimizing both operational cost and expected load shedding.

The project is designed to be extensible and can be run on both the IEEE 33-bus and IEEE 123-bus systems.

## File Structure

The project is organized into the following modules:

-   `main.py`: The main entry point for running all simulations. It uses command-line arguments to select the system and model type.
-   `data_parser.py`: A robust module for parsing MATPOWER case files (`.m` format) into a Python-friendly dictionary.
-   `system_data_extended.py`: Contains the raw case data for the 33-bus and 123-bus systems, as well as all extended data such as time-series profiles (load, solar, price) and resilience scenarios.
-   `dc_opf.py`: A library file containing the Pyomo model for the basic DC OPF.
-   `dc_opf_with_der.py`: A library file containing the Pyomo model for the multi-period DC OPF with DERs and storage.
-   `resilience_opf.py`: A library file containing the Pyomo model for the two-stage stochastic resilience OPF.

## How to Run

All models can be run from the command line using `main.py`. You must also provide a valid email address for the NEOS server via the `NEOS_EMAIL` environment variable.

**Syntax:**
```bash
NEOS_EMAIL=<your_email@example.com> python main.py <system> <model_type>
```

**Arguments:**

-   `<system>`: The power system to use.
    -   `33bus`: The IEEE 33-bus system.
    -   `123bus`: The IEEE 123-bus system.
-   `<model_type>`: The type of optimization model to run.
    -   `basic`: Simple DC OPF.
    -   `der`: DC OPF with DERs and storage over 24 hours.
    -   `resilience`: Two-stage stochastic resilience OPF.

**Examples:**

To run the economic dispatch model with DERs on the 33-bus system:
```bash
NEOS_EMAIL=jules@example.com python main.py 33bus der
```

To run the resilience model on the 33-bus system:
```bash
NEOS_EMAIL=jules@example.com python main.py 33bus resilience
```

To run the economic dispatch model with DERs on the 123-bus system:
```bash
NEOS_EMAIL=jules@example.com python main.py 123bus der
```
