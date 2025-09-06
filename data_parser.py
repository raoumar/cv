import re

def parse_matpower_case_string(case_string):
    """
    Parses a MATPOWER case file given as a string.
    This version is more robust to handle different formats, like the IEEE 123-bus case.
    """
    data = {}

    # Extract baseMVA
    base_mva_match = re.search(r"mpc\.baseMVA\s*=\s*(\d+\.?\d*);", case_string)
    if base_mva_match:
        data['baseMVA'] = float(base_mva_match.group(1))
    else:
        data['baseMVA'] = 100.0 # Default value

    # Extract bus, gen, and branch data
    for name in ['bus', 'gen', 'branch', 'gencost']:
        match = re.search(r"mpc\.{}\s*=\s*\[(.*?)\];".format(name), case_string, re.DOTALL | re.IGNORECASE)
        if not match:
             match = re.search(r"mpc\.{}\s*=\s*\.\.\..*?\[(.*?)\];".format(name), case_string, re.DOTALL | re.IGNORECASE)

        if match:
            matrix_str = match.group(1)
            # Remove comments
            matrix_str = re.sub(r'%.*?(\n|$)', '', matrix_str)
            # Replace newlines with spaces to handle wrapped lines, then split by semicolon for rows
            matrix_str = matrix_str.replace('\n', ' ').replace('...', ' ')
            rows_str = matrix_str.split(';')

            matrix = []
            for row_str in rows_str:
                row_str = row_str.strip()
                if row_str:
                    parts = row_str.split()
                    try:
                        row = [eval(p) for p in parts]
                        matrix.append(row)
                    except:
                        print(f"Warning: Could not parse row in {name} matrix: {row_str}")
                        continue
            data[name] = matrix

    # --- Unit Conversions ---
    if data.get('baseMVA', 100.0) == 100.0:
        print("Assuming loads are in kW and impedances in Ohms. Converting to p.u.")
        if 'bus' in data:
            for i in range(len(data['bus'])):
                if len(data['bus'][i]) > 3:
                    data['bus'][i][2] /= 1000.0
                    data['bus'][i][3] /= 1000.0
        if 'bus' in data and 'branch' in data:
            if len(data['bus'][0]) > 9 and data['bus'][0][9]:
                base_kv = data['bus'][0][9]
                v_base = base_kv * 1e3
                s_base = data['baseMVA'] * 1e6
                z_base = v_base**2 / s_base
                for i in range(len(data['branch'])):
                    if len(data['branch'][i]) > 3:
                        data['branch'][i][2] /= z_base
                        data['branch'][i][3] /= z_base
    else:
        print("Assuming loads are in MW/MVAr and impedances are in p.u. No conversion needed.")

    return data
