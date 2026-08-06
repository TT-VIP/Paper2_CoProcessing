from pathlib import Path
import json
from typing import Any, Dict, List
from dataclasses import asdict

from Instances.instance_generator_final_square import InstanceData, generate_instance


#region JSON serialization
def _make_json_serializable(obj: Any) -> Any:
    if isinstance(obj, range):
        return list(obj)
    elif isinstance(obj, dict):
        return {key: _make_json_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_make_json_serializable(value) for value in obj]
    return obj
#endregion
def summarize_distance_matrix(name: str, matrix: List[List[int]]) -> None:
    """
    Print basic diagnostics for a distance matrix.
    """
    values = [value for row in matrix for value in row]
    values_sorted = sorted(values)

    n = len(values_sorted)

    def quantile(q: float) -> int:
        index = int(round(q * (n - 1)))
        return values_sorted[index]

    print(f"\n{name}")
    print(f"  min:    {min(values)} km")
    print(f"  q25:    {quantile(0.25)} km")
    print(f"  mean:   {sum(values) / n:.2f} km")
    print(f"  median: {quantile(0.50)} km")
    print(f"  q75:    {quantile(0.75)} km")
    print(f"  max:    {max(values)} km")

#region JSON writer
def write_instance_to_json(
        output_path: Path,
        instance_id: str,
        size_class: str,
        structural_regime: str,
        seed: int,
        instance_parameters: Dict[str, Any],
        generator_version: str = "V2.0"
) -> Path:
    '''
    Generate an instance and write it to a JSON file with separated metadata and data:
    {
    "metadata": {
        "instance_id": "instance_001",
        "size_class": "small",
        "structural_regime": "balanced",
        "seed": 7,
        "distribution_settings": {...}
    },
    "data": {
        ... instance data fields ...
    }
    }
    '''
    instance_data = generate_instance(
        seed=seed,
        **instance_parameters
    )
    # instance_data = generate_instance(
    #     S_total=instance_parameters["S_total"],
    #     I_total=instance_parameters["I_total"],
    #     L_total=instance_parameters["L_total"],
    #     C_total=instance_parameters["C_total"],

    #     city_size=instance_parameters["city_size"],
    #     grid_cell_size=instance_parameters["grid_cell_size"],
    #     waste_gen_density=instance_parameters["waste_gen_density"],

    #     incinerator_radius_min=instance_parameters["incinerator_radius_min"],
    #     incinerator_radius_max=instance_parameters["incinerator_radius_max"],
    #     incinerator_radius_center=instance_parameters["incinerator_radius_center"],
    #     incinerator_colocation_probability=instance_parameters["incinerator_colocation_probability"],
    #     landfill_radius_min=instance_parameters["landfill_radius_min"],
    #     landfill_radius_max=instance_parameters["landfill_radius_max"],
    #     landfill_radius_center=instance_parameters["landfill_radius_center"],
    #     cement_radius_min=instance_parameters["cement_radius_min"],
    #     cement_radius_max=instance_parameters["cement_radius_max"],
    #     cement_radius_center=instance_parameters["cement_radius_center"],

    #     clipping_distances=instance_parameters["clipping_distances"],
    #     seed=seed,
    # )

    # Transport distance analysis
    summarize_distance_matrix("TD_gs (generation to transfer)", instance_data.TD_gs)
    summarize_distance_matrix("TD_si (transfer to incineration)", instance_data.TD_si)
    summarize_distance_matrix("TD_sl (transfer to landfill)", instance_data.TD_sl)
    summarize_distance_matrix("TD_sc (transfer to cement)", instance_data.TD_sc)

    metadata = {
        "instance_id": instance_id,
        "size_class": size_class,
        "structural_regime": structural_regime,
        "seed": seed,

        "dimensions": {
            "G_total": instance_data.G_max,
            "S_total": instance_parameters["S_total"],
            "I_total": instance_parameters["I_total"],
            "L_total": instance_parameters["L_total"],
            "C_total": instance_parameters["C_total"],
        },
        
        "network_settings": {
            "city_size": instance_parameters["city_size"],
            "grid_cell_size": instance_parameters["grid_cell_size"],
            "waste_gen_density": instance_parameters["waste_gen_density"],

            "incinerator_radius_min": instance_parameters["incinerator_radius_min"],
            "incinerator_radius_max": instance_parameters["incinerator_radius_max"],
            "incinerator_radius_center": instance_parameters["incinerator_radius_center"],
            "incinerator_colocation_probability": instance_parameters["incinerator_colocation_probability"],
            "landfill_radius_min": instance_parameters["landfill_radius_min"],
            "landfill_radius_max": instance_parameters["landfill_radius_max"],
            "landfill_radius_center": instance_parameters["landfill_radius_center"],
            "cement_radius_min": instance_parameters["cement_radius_min"],
            "cement_radius_max": instance_parameters["cement_radius_max"],
            "cement_radius_center": instance_parameters["cement_radius_center"],
            "clipping_distances": instance_parameters["clipping_distances"],
        },

        "waste_split (uniform, float)": [0.4, 0.7],  # range for high moisture split
        "alpha_c (triangular, int)": [7000, 18000, 15000],
        "budget_availability_municipality": 0.80,   # 80% of the maximum total potential waste flow to kilns can be subsidized supposing maximum subsidy levels
        "budget_availability_cement": 0.65,         # Only 65% of the maximum total potential investment cost for co-processing is available
        "generator_version": generator_version
    }

    payload = {
        "metadata": metadata,
        "data": _make_json_serializable(asdict(instance_data))
    }

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open('w', encoding='utf-8') as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)
    
    return output_path
#endregion

#region JSON reader
# JSON turns dict keys into strings, so it is necessary to convert them back to ints for indexed Big-M values
def _keys_to_int(d: dict) -> dict:
    return {int(k): v for k, v in d.items()}

def _keys_to_int_recursive(obj):
    if isinstance(obj, dict):
        return {int(k): _keys_to_int_recursive(v) for k, v in obj.items()}
    return obj

# JSON to InstanceData object
def read_instanceData_from_json(json_path: Path) -> InstanceData:
    with json_path.open('r', encoding='utf-8') as file:
        payload = json.load(file)

    data = payload["data"]

    # Convert lists back to ranges for index sets
    data['G'] = range(data['G_max'])
    data['S'] = range(data['S_max'])
    data['W'] = range(data['W_max'])
    data['I'] = range(data['I_max'])
    data['L'] = range(data['L_max'])
    data['C'] = range(data['C_max'])
    data['K'] = range(data['K_max'])
    data['F'] = range(data['F_max'])
    data['H'] = range(data['H_max'])

    # Convert JSON string keys back to ints for coordinates (Dict[int, Tuple[float, float]])
    data['G_coords'] = {int(k): tuple(v) for k, v in data['G_coords'].items()}
    data['S_coords'] = {int(k): tuple(v) for k, v in data['S_coords'].items()}
    data['I_coords'] = {int(k): tuple(v) for k, v in data['I_coords'].items()}
    data['L_coords'] = {int(k): tuple(v) for k, v in data['L_coords'].items()}
    data['C_coords'] = {int(k): tuple(v) for k, v in data['C_coords'].items()}

    # Convert JSON string keys back to ints for indexed Big-M values
    data['M_primal']['F4'] = _keys_to_int(data['M_primal']['F4'])
    data['M_primal']['r_sw'] = _keys_to_int_recursive(data['M_primal']['r_sw'])
    data['M_primal']['q_cf'] = _keys_to_int_recursive(data['M_primal']['q_cf'])
    data['M_primal']['q_scw'] = _keys_to_int_recursive(data['M_primal']['q_scw'])

    return InstanceData(**data)
    # instance = InstanceData(
    #     G_max=data['G_max'], S_max=data['S_max'], W_max=data['W_max'], 
    #     I_max=data['I_max'], L_max=data['L_max'], C_max=data['C_max'],
    #     K_max=data['K_max'], F_max=data['F_max'], H_max=data['H_max'],

    #     G=data['G'], S=data['S'], W=data['W'], I=data['I'], L=data['L'], 
    #     C=data['C'], K=data['K'], F=data['F'], H=data['H'],

    #     G_coords=data['G_coords'], S_coords=data['S_coords'], I_coords=data['I_coords'],
    #     L_coords=data['L_coords'], C_coords=data['C_coords'],
        
    #     cement_names=data['cement_names'],
        
    #     TD_gs=data['TD_gs'], TD_sl=data['TD_sl'], 
    #     TD_sc=data['TD_sc'], TD_si=data['TD_si'], 
    #     TD_si_avg=data['TD_si_avg'],
        
    #     epsilon_truck=data['epsilon_truck'],
    #     epsilon_land=data['epsilon_land'], epsilon_inc=data['epsilon_inc'], 
    #     epsilon_kiln_w=data['epsilon_kiln_w'], epsilon_kiln_f=data['epsilon_kiln_f'],

    #     c_truck=data['c_truck'], c_land=data['c_land'], c_inc=data['c_inc'],

    #     Q_gw=data['Q_gw'], Q_gen_total=data['Q_gen_total'],
    #     Q_s=data['Q_s'], Q_l=data['Q_l'], Q_i=data['Q_i'],
    #     Q_k=data['Q_k'], Q_k_max=data['Q_k_max'],

    #     weight_env=data['weight_env'], weight_mon=data['weight_mon'],

    #     kappa_land=data['kappa_land'], kappa_coproc=data['kappa_coproc'],

    #     budget_municipality=data['budget_municipality'],
    #     budget_cem=data['budget_cem'],

    #     phi_max=data['phi_max'],
    #     phi_wh=data['phi_wh'],

    #     price_f=data['price_f'], 
    #     beta_f=data['beta_f'], beta_w=data['beta_w'],

    #     alpha_c=data['alpha_c'], 

    #     c_invest_k=data['c_invest_k'], 
    #     c_preproc_w=data['c_preproc_w'],
    #     c_penalty=data['c_penalty'], 

    #     tau = data["tau"],
    #     fixcost_invest_k = data["fixcost_invest_k"],

    #     M_primal=data['M_primal'], M_dual=data['M_dual'],
    #     U_w=data['U_w']
    # )

    # return instance
#endregion

def read_instance_metadata_from_json(json_path: Path) -> Dict[str, Any]:
    with json_path.open('r', encoding='utf-8') as file:
        payload = json.load(file)
    return payload["metadata"]

#region Run instance generator
# call the script to generate an instance and save to JSON within the python environment (can be adapted to command-line arguments if needed)
if __name__ == "__main__":
    instance_name = "instance_s_base_002.json"
    
    instance_parameters = {
        "S_total": 4,
        "I_total": 3,
        "L_total": 2,
        "C_total": 3,

        "city_size": 20.0,
        "grid_cell_size": 10.0,
        "waste_gen_density": 2500,

        "incinerator_radius_min": 10.0,
        "incinerator_radius_max": 60.0,
        "incinerator_radius_center": 35.0,
        "incinerator_colocation_probability": 0.025,

        "landfill_radius_min": 40.0,
        "landfill_radius_max": 120.0,
        "landfill_radius_center": 75.0,
        
        "cement_radius_min": 80.0,
        "cement_radius_max": 250.0,
        "cement_radius_center": 150.0,

        "clipping_distances": False,
    }

    output_path = write_instance_to_json(
        output_path=Path(__file__).parent / "generated_instances" / instance_name,
        instance_id=instance_name[:-5],  # Remove ".json" extension
        size_class="medium",
        structural_regime="baseline",
        seed=42,
        instance_parameters=instance_parameters,
    )
    print(f"Instance generated and saved to {output_path}")

    # instance = read_instanceData_from_json(output_path)
    # print(instance)