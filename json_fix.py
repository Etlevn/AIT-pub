import os
import json
import ast
from typing import Tuple, Union, Dict, Any, List, Optional
import config

# ==== Global configuration ====
# You can define experiments root base dir and an optional single experiment dir name.
# They will be joined to form an effective single experiment path when both are set.
# Examples:
#   GLOBAL_ROOT_BASE_DIR = "/Users/you/Documents/Projects/AIT/exp/Pt 3_BR"
#   GLOBAL_EXPERIMENT_DIR_NAME = "gpt-4o VS gemini-2.5"
# If GLOBAL_EXPERIMENT_DIR_NAME is empty, scanning will traverse all experiments under GLOBAL_ROOT_BASE_DIR.
GLOBAL_ROOT_BASE_DIR = "/Users/you/Documents/Projects/AIT/exp/Pt 2_EP"
GLOBAL_EXPERIMENT_DIR_NAME = ""

# ==============================

def _is_standard_response_dict(obj: Any) -> bool:
    if not isinstance(obj, dict):
        return False
    # Considered valid if it has any of the expected top-level fields
    expected_any = [
        "submitted_orders",
        "observations_and_thoughts",
        "new_content",
    ]
    return any(k in obj for k in expected_any)


def _parse_raw_response_to_dict(raw_resp: Union[str, Dict[str, Any]]) -> Tuple[bool, Union[Dict[str, Any], str]]:
    """
    Try to normalize raw_response into a standard dict.
    Returns (success, dict_or_error_str)
    """
    # If already dict
    if isinstance(raw_resp, dict):
        if _is_standard_response_dict(raw_resp):
            return True, raw_resp
        # May be {"llm_response": ...}
        if "llm_response" in raw_resp:
            inner = raw_resp["llm_response"]
            if isinstance(inner, dict) and _is_standard_response_dict(inner):
                return True, inner
            if isinstance(inner, str):
                # Try parse inner string to dict
                try:
                    inner_parsed = json.loads(inner)
                    if isinstance(inner_parsed, dict) and _is_standard_response_dict(inner_parsed):
                        return True, inner_parsed
                except Exception:
                    pass
                try:
                    inner_lit = ast.literal_eval(inner)
                    if isinstance(inner_lit, dict) and _is_standard_response_dict(inner_lit):
                        return True, inner_lit
                except Exception:
                    pass
        return False, "raw_response dict not in expected schema"

    # If string, try JSON first
    if isinstance(raw_resp, str):
        # Skip explicit error strings
        if raw_resp.startswith("Error:"):
            return False, "error string in raw_response"
        # Direct JSON
        try:
            parsed = json.loads(raw_resp)
            if isinstance(parsed, dict):
                if _is_standard_response_dict(parsed):
                    return True, parsed
                if "llm_response" in parsed:
                    inner = parsed["llm_response"]
                    if isinstance(inner, dict) and _is_standard_response_dict(inner):
                        return True, inner
                    if isinstance(inner, str):
                        try:
                            inner_parsed = json.loads(inner)
                            if isinstance(inner_parsed, dict) and _is_standard_response_dict(inner_parsed):
                                return True, inner_parsed
                        except Exception:
                            pass
                        try:
                            inner_lit = ast.literal_eval(inner)
                            if isinstance(inner_lit, dict) and _is_standard_response_dict(inner_lit):
                                return True, inner_lit
                        except Exception:
                            pass
        except Exception:
            pass

        # Python literal
        try:
            lit = ast.literal_eval(raw_resp)
            if isinstance(lit, dict):
                if _is_standard_response_dict(lit):
                    return True, lit
                if "llm_response" in lit:
                    inner = lit["llm_response"]
                    if isinstance(inner, dict) and _is_standard_response_dict(inner):
                        return True, inner
                    if isinstance(inner, str):
                        try:
                            inner_parsed = json.loads(inner)
                            if isinstance(inner_parsed, dict) and _is_standard_response_dict(inner_parsed):
                                return True, inner_parsed
                        except Exception:
                            pass
                        try:
                            inner_lit = ast.literal_eval(inner)
                            if isinstance(inner_lit, dict) and _is_standard_response_dict(inner_lit):
                                return True, inner_lit
                        except Exception:
                            pass
        except Exception:
            pass

    return False, "unable to parse raw_response into standard dict"


def _simple_fix_truncated_response(json_input: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Accept str or dict. If dict, return as-is. If str, try to salvage orders and texts.
    """
    if isinstance(json_input, dict):
        return json_input

    json_str = json_input
    # Try direct parse
    try:
        parsed = json.loads(json_str)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    # Try parse by trimming to the last closing brace (recover truncated tails)
    try:
        last_brace = json_str.rfind('}')
        if last_brace != -1:
            trimmed = json_str[: last_brace + 1]
            parsed = json.loads(trimmed)
            if isinstance(parsed, dict):
                return parsed
    except Exception:
        pass

    lines = json_str.split('\n')
    orders: List[Dict[str, Any]] = []
    current_order: Dict[str, Any] = {}
    in_order = False

    for raw_line in lines:
        line = raw_line.strip()
        if line.startswith('{') and '"order_type"' in line:
            try:
                order = json.loads(line.rstrip(','))
                if all(k in order for k in ["order_type", "quantity", "limit_price"]):
                    orders.append(order)
            except Exception:
                pass
        elif line.startswith('{'):
            in_order = True
            current_order = {}
        elif in_order and '"order_type"' in line and '": "' in line:
            current_order["order_type"] = line.split('": "')[1].rstrip('",')
        elif in_order and '"quantity"' in line and '": ' in line:
            try:
                current_order["quantity"] = int(line.split('": ')[1].rstrip(','))
            except Exception:
                pass
        elif in_order and '"limit_price"' in line and '": ' in line:
            try:
                price_str = line.split('": ')[1].rstrip(',')
                price = float(price_str) if '.' in price_str else int(price_str)
                current_order["limit_price"] = price
            except Exception:
                pass
        elif line.startswith('}') and in_order:
            if len(current_order) == 3:
                orders.append(current_order)
            in_order = False
            current_order = {}

    result: Dict[str, Any] = {
        "observations_and_thoughts": "Market analysis and trading decisions",
        "new_content": {
            "PLANS.txt": "",
            "INSIGHTS.txt": "",
            "price_forecasts": []
        },
        "submitted_orders": orders
    }

    try:
        if '"observations_and_thoughts"' in json_str:
            # Robust extraction without requiring trailing comma/next key
            key_token = '"observations_and_thoughts": "'
            start = json_str.find(key_token)
            if start != -1:
                i = start + len(key_token)
                val_chars: List[str] = []
                escaped = False
                while i < len(json_str):
                    ch = json_str[i]
                    if escaped:
                        val_chars.append(ch)
                        escaped = False
                    else:
                        if ch == '\\':
                            escaped = True
                            val_chars.append(ch)
                        elif ch == '"':
                            break
                        else:
                            val_chars.append(ch)
                    i += 1
                if val_chars:
                    result["observations_and_thoughts"] = ''.join(val_chars)

        if '"PLANS.txt"' in json_str:
            import re
            m = re.search(r"\"PLANS\.txt\":\s*\"([\s\S]*?)\"\s*,", json_str)
            if m:
                result["new_content"]["PLANS.txt"] = m.group(1).replace('\\n', '\n')
            else:
                start = json_str.find('"PLANS.txt": "') + 14
                end = json_str.find('",', start)
                if end > start:
                    result["new_content"]["PLANS.txt"] = json_str[start:end].replace('\\n', '\n')

        if '"INSIGHTS.txt"' in json_str:
            import re
            m = re.search(r"\"INSIGHTS\.txt\":\s*\"([\s\S]*?)\"\s*,", json_str)
            if m:
                result["new_content"]["INSIGHTS.txt"] = m.group(1).replace('\\n', '\n')
            else:
                start = json_str.find('"INSIGHTS.txt": "') + 17
                end = json_str.find('",', start)
                if end > start:
                    result["new_content"]["INSIGHTS.txt"] = json_str[start:end].replace('\\n', '\n')

        if '"price_forecasts"' in json_str:
            start = json_str.find('"price_forecasts": [') + 20
            end = json_str.find(']', start)
            if end > start:
                forecasts_str = json_str[start:end]
                try:
                    forecasts = json.loads(f"[{forecasts_str}]")
                    result["new_content"]["price_forecasts"] = forecasts
                except Exception:
                    result["new_content"]["price_forecasts"] = []
    except Exception:
        if "new_content" not in result:
            result["new_content"] = {}
        if "price_forecasts" not in result["new_content"]:
            result["new_content"]["price_forecasts"] = []

    return result


def fix_single_json_file(file_path: str, create_backup: bool = True) -> Tuple[bool, str]:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # No need to fix
        if not (isinstance(data, dict) and "raw_response" in data and len(data) == 1):
            return True, "File format is correct, no fix needed"

        raw_resp = data["raw_response"]

        # Skip explicit error
        if isinstance(raw_resp, str) and raw_resp.startswith("Error:"):
            return True, "Cannot fix error responses"

        # 1) Try normalize to dict directly
        ok, parsed_dict_or_msg = _parse_raw_response_to_dict(raw_resp)
        if ok:
            fixed_json = parsed_dict_or_msg  # type: ignore
        else:
            # 2) Fall back to simple salvage
            fixed_json = _simple_fix_truncated_response(raw_resp)

        if not isinstance(fixed_json, dict):
            return False, "Fix failed: not a dict after salvage"

        if create_backup:
            # Place backups under output/backup/<r?>/
            round_folder = os.path.basename(os.path.dirname(file_path))
            output_root = os.path.dirname(os.path.dirname(file_path))
            backup_dir = os.path.join(output_root, 'backup', round_folder)
            os.makedirs(backup_dir, exist_ok=True)
            backup_path = os.path.join(backup_dir, os.path.basename(file_path).replace('.json', '_backup.json'))
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(fixed_json, f, ensure_ascii=False, indent=4)

        return True, "Fix successful"

    except Exception as e:
        return False, f"Fix failed: {e}"


def post_round_json_fix(exp_run_dir: str, round_num: int, num_llms: int, create_backup: bool = True) -> Dict[str, Any]:
    # Respect global config switch
    if not config.AUTO_JSON_FIX.get("enabled", True):
        return {"status": "disabled", "message": "Auto JSON fix is disabled in config"}
    output_dir = os.path.join(exp_run_dir, "output", f"r{round_num}")
    if not os.path.exists(output_dir):
        return {"status": "error", "message": f"Output directory not found: {output_dir}"}

    results = {
        "total_files": 0,
        "fixed_files": 0,
        "error_files": 0,
        "details": []
    }

    print(f"\n[json_fix] Post-round JSON check for round {round_num}...")

    for i in range(1, num_llms + 1):
        llm_id = f"llm_{i:03d}"
        json_file = os.path.join(output_dir, f"{llm_id}_r{round_num}.json")
        results["total_files"] += 1

        if not os.path.exists(json_file):
            results["error_files"] += 1
            continue

        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            if "raw_response" in data and len(data) == 1:
                success, message = fix_single_json_file(json_file, create_backup=create_backup)
                results["details"].append({"file": json_file, "success": success, "message": message})
                cannot_fix = isinstance(message, str) and "Cannot fix error responses" in message
                no_fix_needed = isinstance(message, str) and "no fix" in message
                if success and not no_fix_needed and not cannot_fix:
                    results["fixed_files"] += 1
                    print(f"[json_fix] ✓ Fixed: {llm_id}_r{round_num}.json - {message}")
                elif cannot_fix or not success:
                    # Save the original file content into output/error/r{round_num}/ as an error record
                    try:
                        error_dir = os.path.join(exp_run_dir, "output", "error", f"r{round_num}")
                        os.makedirs(error_dir, exist_ok=True)
                        error_path = os.path.join(error_dir, os.path.basename(json_file).replace('.json', '_error.json'))
                        with open(error_path, 'w', encoding='utf-8') as ef:
                            json.dump(data, ef, ensure_ascii=False, indent=4)
                    except Exception:
                        pass
                    results["error_files"] += 1
                    print(f"[json_fix] ✗ Fix failed: {llm_id}_r{round_num}.json - {message}")

        except Exception as e:
            results["error_files"] += 1
            print(f"[json_fix] ✗ Error processing: {llm_id}_r{round_num}.json - {e}")

    if results["fixed_files"] > 0:
        print(f"[json_fix] Round {round_num} JSON fix summary: {results['fixed_files']}/{results['total_files']} files fixed")
    else:
        print(f"[json_fix] Round {round_num} JSON check complete: All {results['total_files']} files are normal")

    return results


def scan_and_fix_experiment(exp_run_dir: str, create_backup: bool = True, group_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Manually scan an experiment run directory (e.g., exp/20250922_012133) and fix all raw_response files.
    """
    # Manual mode always runs regardless of enabled switch; only create_backup is respected
    exp_name = os.path.basename(exp_run_dir.rstrip('/'))
    header = f"{group_name} | {exp_name}" if group_name else exp_name
    print(f"[json_fix] ========== {header} ==========")
    output_root = os.path.join(exp_run_dir, "output")
    if not os.path.exists(output_root):
        return {"status": "error", "message": f"Output root not found: {output_root}"}

    total_files = 0
    fixed_files = 0
    error_files = 0
    details: List[Dict[str, Any]] = []

    for round_folder in sorted(os.listdir(output_root)):
        round_path = os.path.join(output_root, round_folder)
        if not os.path.isdir(round_path):
            continue
        if not round_folder.startswith('r'):
            continue

        for filename in sorted(os.listdir(round_path)):
            if not filename.endswith('.json'):
                continue
            if filename.endswith('_backup.json'):
                continue
            file_path = os.path.join(round_path, filename)
            total_files += 1
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, dict) and "raw_response" in data and len(data) == 1:
                    success, message = fix_single_json_file(file_path, create_backup=create_backup)
                    details.append({"file": file_path, "success": success, "message": message})
                    cannot_fix = isinstance(message, str) and "Cannot fix error responses" in message
                    no_fix_needed = isinstance(message, str) and "no fix" in message
                    if success and not no_fix_needed and not cannot_fix:
                        fixed_files += 1
                        print(f"[json_fix] ✓ Fixed: {round_folder}/{filename} - {message}")
                    elif cannot_fix or not success:
                        # Save the original file content into output/error/<round_folder>/ as an error record
                        try:
                            error_dir = os.path.join(output_root, 'error', round_folder)
                            os.makedirs(error_dir, exist_ok=True)
                            error_path = os.path.join(error_dir, os.path.basename(file_path).replace('.json', '_error.json'))
                            with open(error_path, 'w', encoding='utf-8') as ef:
                                json.dump(data, ef, ensure_ascii=False, indent=4)
                        except Exception:
                            pass
                        error_files += 1
                        print(f"[json_fix] ✗ Fix failed: {round_folder}/{filename} - {message}")
            except Exception as e:
                error_files += 1
                details.append({"file": file_path, "success": False, "message": str(e)})
                print(f"[json_fix] ✗ Error reading: {round_folder}/{filename} - {e}")

    summary = {
        "total_files": total_files,
        "fixed_files": fixed_files,
        "error_files": error_files,
        "details": details,
    }
    print(f"[json_fix] {fixed_files}/{total_files} files fixed, {error_files} errors\n")
    return summary


def scan_and_fix_all_experiments(root_exp_dir: str, create_backup: bool = True) -> Dict[str, Any]:
    """
    Scan all experiment run directories under a root experiments directory and fix outputs.
    """
    # Manual mode always runs regardless of enabled switch; only create_backup is respected
    if not os.path.exists(root_exp_dir):
        return {"status": "error", "message": f"Experiments root not found: {root_exp_dir}"}

    total_files = 0
    fixed_files = 0
    error_files = 0
    per_exp: List[Dict[str, Any]] = []

    # Discover experiment directories up to depth 2; skip hidden/backup/underscore dirs
    def _should_skip_dir(name: str) -> bool:
        return name.startswith('_') or name.startswith('.') or name == 'backup'

    # (top_level_name, experiment_path)
    discovered: List[Tuple[str, str]] = []

    # Depth 1
    for entry in sorted(os.listdir(root_exp_dir)):
        if _should_skip_dir(entry):
            continue
        path1 = os.path.join(root_exp_dir, entry)
        if not os.path.isdir(path1):
            continue
        # If this dir has output, treat as experiment
        if os.path.exists(os.path.join(path1, 'output')):
            discovered.append((entry, path1))
            continue
        # Depth 2
        try:
            for sub in sorted(os.listdir(path1)):
                if _should_skip_dir(sub):
                    continue
                path2 = os.path.join(path1, sub)
                if not os.path.isdir(path2):
                    continue
                if os.path.exists(os.path.join(path2, 'output')):
                    discovered.append((entry, path2))
        except PermissionError:
            continue

    if not discovered:
        print(f"[json_fix] No experiment directories found under: {root_exp_dir}")

    # Aggregation by top-level directory under root
    group_totals: Dict[str, Dict[str, int]] = {}

    for top_level, exp_path in discovered:
        exp_folder = os.path.basename(exp_path)
        res = scan_and_fix_experiment(exp_path, create_backup=create_backup, group_name=top_level)
        per_exp.append({"experiment": exp_folder, **res})
        total_files += res.get("total_files", 0)
        fixed_files += res.get("fixed_files", 0)
        error_files += res.get("error_files", 0)

        # Update group totals
        grp = group_totals.setdefault(top_level, {"total_files": 0, "fixed_files": 0, "error_files": 0, "experiments": 0})
        grp["total_files"] += res.get("total_files", 0)
        grp["fixed_files"] += res.get("fixed_files", 0)
        grp["error_files"] += res.get("error_files", 0)
        grp["experiments"] += 1

    # Print group summaries (immediate child of root level)
    if group_totals:
        print("[json_fix] ===== Group summaries =====")
        for group_name in sorted(group_totals.keys()):
            g = group_totals[group_name]
            print(f"[json_fix] Group summary ({group_name}): {g['fixed_files']}/{g['total_files']} files fixed across {g['experiments']} experiments, {g['error_files']} errors")

    print(f"\n[json_fix] Root summary: {fixed_files}/{total_files} files fixed across {len(per_exp)} experiments, {error_files} errors")
    return {
        "experiments": per_exp,
        "total_files": total_files,
        "fixed_files": fixed_files,
        "error_files": error_files,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="JSON fix tool for AIT outputs")
    sub = parser.add_subparsers(dest="cmd")

    # Manual scan
    p_scan = sub.add_parser("scan", help="Scan experiments and fix outputs")
    p_scan.add_argument("path", type=str, nargs='?', help="Path to experiment run dir or experiments root dir")
    p_scan.add_argument("--no-backup", action="store_true", help="Do not create backup files")

    # Post-round (for integration with main)
    p_round = sub.add_parser("round", help="Fix a specific round outputs by llm count")
    p_round.add_argument("exp_run_dir", type=str)
    p_round.add_argument("round_num", type=int)
    p_round.add_argument("num_llms", type=int)
    p_round.add_argument("--no-backup", action="store_true")

    args = parser.parse_args()

    if args.cmd == "scan":
        target_path = args.path
        if not target_path:
            # No CLI path provided: derive from global base/name settings
            if not GLOBAL_ROOT_BASE_DIR:
                print("Please set GLOBAL_ROOT_BASE_DIR (and optionally GLOBAL_EXPERIMENT_DIR_NAME) or pass a path")
            else:
                if GLOBAL_EXPERIMENT_DIR_NAME:
                    single = os.path.join(GLOBAL_ROOT_BASE_DIR, GLOBAL_EXPERIMENT_DIR_NAME)
                    backup_flag = config.AUTO_JSON_FIX.get("create_backup", True) and (not args.no_backup)
                    scan_and_fix_experiment(single, create_backup=backup_flag)
                else:
                    backup_flag = config.AUTO_JSON_FIX.get("create_backup", True) and (not args.no_backup)
                    scan_and_fix_all_experiments(GLOBAL_ROOT_BASE_DIR, create_backup=backup_flag)
        else:
            # Path provided: decide whether it's a single experiment or a root
            if os.path.isdir(target_path):
                if os.path.exists(os.path.join(target_path, 'output')):
                    backup_flag = config.AUTO_JSON_FIX.get("create_backup", True) and (not args.no_backup)
                    scan_and_fix_experiment(target_path, create_backup=backup_flag)
                else:
                    backup_flag = config.AUTO_JSON_FIX.get("create_backup", True) and (not args.no_backup)
                    scan_and_fix_all_experiments(target_path, create_backup=backup_flag)
            else:
                print(f"Invalid path: {target_path}")
    elif args.cmd == "round":
        # Manual round fix always runs; only create_backup is respected
        backup_flag = config.AUTO_JSON_FIX.get("create_backup", True) and (not args.no_backup)
        post_round_json_fix(args.exp_run_dir, args.round_num, args.num_llms, create_backup=backup_flag)
    else:
        # If no command provided, treat as manual run: use global base/name
        if GLOBAL_ROOT_BASE_DIR:
            if GLOBAL_EXPERIMENT_DIR_NAME:
                backup_flag = config.AUTO_JSON_FIX.get("create_backup", True)
                scan_and_fix_experiment(os.path.join(GLOBAL_ROOT_BASE_DIR, GLOBAL_EXPERIMENT_DIR_NAME), create_backup=backup_flag)
            else:
                backup_flag = config.AUTO_JSON_FIX.get("create_backup", True)
                scan_and_fix_all_experiments(GLOBAL_ROOT_BASE_DIR, create_backup=backup_flag)
        else:
            parser.print_help()


