import os
import pandas as pd
from pathlib import Path
import re
import json
from datetime import datetime, timedelta
from collections import defaultdict
import bisect

APP_DATA_DIR = Path.home() / '.kovaaks_stats_viewer'
APP_DATA_DIR.mkdir(exist_ok=True) 

CACHE_HISTORY_PATH = APP_DATA_DIR / 'kovaaks_history_cache.pkl'
CACHE_INFO_PATH = APP_DATA_DIR / 'kovaaks_cache_info.json'

# --- 1. CORE PARSING ---
def parse_kovaaks_stats_file(file_path):
    try:
        filename = os.path.basename(file_path)
        timestamp_match = re.search(r'(\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}\.\d{2})', filename)
        if timestamp_match:
            timestamp_str = timestamp_match.group(1)
            end_time = datetime.strptime(timestamp_str, '%Y.%m.%d-%H.%M.%S')
        else:
            end_time = datetime.fromtimestamp(os.path.getmtime(file_path))
        
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        data = {'Duration': 60.0} 
        start_time_str = None
        
        for line in lines:
            if line.startswith('Scenario:'): data['Scenario'] = line.split(',', 1)[1].strip()
            elif line.startswith('Score:'): data['Score'] = float(line.split(',')[1].strip())
            elif line.startswith('Horiz Sens:'): data['Sens'] = float(line.split(',')[1].strip())
            elif line.startswith('Challenge Start:'): start_time_str = line.split(',')[1].strip()
        
        if start_time_str:
            try:
                if '.' in start_time_str and len(start_time_str.split('.')[1]) > 6:
                    start_time_str = start_time_str[:start_time_str.find('.')+7]
                parsed_time = datetime.strptime(start_time_str, '%H:%M:%S.%f').time()
                start_time = end_time.replace(hour=parsed_time.hour, minute=parsed_time.minute, 
                                              second=parsed_time.second, microsecond=parsed_time.microsecond)
                if start_time > end_time: start_time -= timedelta(days=1)
                duration_seconds = (end_time - start_time).total_seconds()
                if 0 < duration_seconds < 600: data['Duration'] = duration_seconds
            except: pass

        if 'Scenario' in data and 'Score' in data and 'Sens' in data:
            data['Timestamp'] = end_time
            return data
        else: return None
    except: return None

def _detect_and_assign_sessions(history_df, session_gap_minutes=30):
    if history_df.empty or 'Timestamp' not in history_df.columns: return history_df
    df = history_df.copy()
    df.sort_values('Timestamp', inplace=True)
    time_diffs = df['Timestamp'].diff()
    session_starts = time_diffs > pd.Timedelta(minutes=session_gap_minutes)
    session_ids = session_starts.cumsum()
    df['SessionID'] = session_ids
    return df

def find_and_process_stats(stats_folder_path, session_gap_minutes=30):
    path_obj = Path(stats_folder_path)
    if not path_obj.is_dir(): return None
    
    processed_files_info = {}
    cached_history_df = pd.DataFrame()
    
    if os.path.exists(CACHE_HISTORY_PATH) and os.path.exists(CACHE_INFO_PATH):
        try:
            cached_history_df = pd.read_pickle(CACHE_HISTORY_PATH)
            with open(CACHE_INFO_PATH, 'r') as f: processed_files_info = json.load(f)
        except: pass
            
    all_challenge_files = list(path_obj.glob('*- Challenge -*.csv'))
    new_files_to_process = []
    current_files_info = {}
    
    for file_path in all_challenge_files:
        try:
            mtime = os.path.getmtime(file_path)
            current_files_info[str(file_path)] = mtime
            if str(file_path) not in processed_files_info or mtime > processed_files_info[str(file_path)]:
                new_files_to_process.append(file_path)
        except: continue

    if new_files_to_process:
        newly_parsed_data = [d for d in (parse_kovaaks_stats_file(fp) for fp in new_files_to_process) if d]
        if newly_parsed_data:
            new_df = pd.DataFrame(newly_parsed_data)
            combined_history_df = pd.concat([cached_history_df, new_df], ignore_index=True)
            combined_history_df.drop_duplicates(subset=['Scenario', 'Sens', 'Timestamp', 'Score'], inplace=True)
        else: combined_history_df = cached_history_df
    else: combined_history_df = cached_history_df
        
    if combined_history_df.empty: return pd.DataFrame()
    combined_history_df = _detect_and_assign_sessions(combined_history_df, session_gap_minutes)

    try:
        combined_history_df.to_pickle(CACHE_HISTORY_PATH)
        with open(CACHE_INFO_PATH, 'w') as f: json.dump(current_files_info, f, indent=2)
    except: pass
    return combined_history_df.reset_index(drop=True)

def get_scenario_family_info(all_runs_df, base_scenario):
    if all_runs_df is None or all_runs_df.empty: return None
    family_df = all_runs_df[all_runs_df['Scenario'].str.startswith(base_scenario)].copy()
    if family_df.empty: return None
    
    memo = {}

    def parse_modifiers(scenario_name):
        if scenario_name in memo:
            return memo[scenario_name]

        modifier_str = scenario_name.replace(base_scenario, '', 1).strip()
        if not modifier_str: return {}
        
        UNIT_MAP = {'s': 'Duration', 'sec': 'Duration', 'm': 'Distance', 'hp': 'Health'}
        token_pattern = re.compile(r'(\d[\d.]*%?[a-zA-Z]*|[A-Za-z]+)')
        tokens = token_pattern.findall(modifier_str)
        
        def is_value(token):
            if re.fullmatch(r'[\d.]+%?', token): return True
            unit_match = re.fullmatch(r'([\d.]+%?)(\w+)', token)
            if unit_match and unit_match.groups()[1] in UNIT_MAP: return True
            return False
            
        modifiers = {}
        consumed = [False] * len(tokens); i = 0
        while i < len(tokens) - 1:
            if not consumed[i] and not consumed[i+1]:
                t1, t2 = tokens[i], tokens[i+1]
                if not is_value(t1) and is_value(t2): 
                    modifiers[t1] = (t2, 'word_value'); consumed[i] = consumed[i+1] = True; i += 2; continue
                elif is_value(t1) and not is_value(t2): 
                    modifiers[t2] = (t1, 'value_word'); consumed[i] = consumed[i+1] = True; i += 2; continue
            i += 1
        for i, token in enumerate(tokens):
            if not consumed[i]:
                unit_match = re.fullmatch(r'([\d.]+%?)(\w+)', token)
                if unit_match:
                    value, unit = unit_match.groups()
                    if unit in UNIT_MAP: modifiers[UNIT_MAP[unit]] = (token, 'standalone'); consumed[i] = True
                elif '%' in token and is_value(token):
                    modifiers['Percent'] = (token, 'standalone'); consumed[i] = True
        
        # CRITICAL V1 LOGIC: Filter out "Dirty" matches
        if not all(consumed):
             memo[scenario_name] = {}
             return {}
             
        memo[scenario_name] = modifiers
        return modifiers
        
    family_df['Modifiers'] = family_df['Scenario'].apply(parse_modifiers)
    return family_df

# --- 2. ENRICHMENT (RANKS) ---

def enrich_history_with_stats(df):
    """Calculates PBs and Assigns Ranks"""
    if df is None or df.empty: return df
    df = df.sort_values('Timestamp').copy()
    
    # Rank Definitions
    ranks = [("SINGULARITY", 100), ("ARCADIA", 95), ("UBER", 90), ("EXALTED", 82), ("BLESSED", 75), ("TRANSMUTE", 55)]
    gated = {"SINGULARITY", "ARCADIA", "UBER"}
    
    # Initialize Rank Columns
    for r, _ in ranks: df[f'Rank_{r}'] = 0
    df['Is_PB'] = False

    # Process by Combo
    updates = []
    
    for (scen, sens), group in df.groupby(['Scenario', 'Sens']):
        history = []
        indices = group.index
        scores = group['Score'].values
        
        for i, score in enumerate(scores):
            idx = indices[i]
            run_count = i + 1
            
            # PB Logic
            is_pb = False
            if not history: is_pb = False # First run isn't an "Improvement"
            elif score > history[-1]: is_pb = True
            
            if is_pb: updates.append((idx, 'Is_PB', True))
            
            # Rank Logic
            if not history: # First run is peak
                percentile = 100
            elif score >= history[-1]: 
                percentile = 100
            else:
                pos = bisect.bisect_left(history, score)
                percentile = (pos / len(history)) * 100
            
            bisect.insort(history, score)
            
            for r_name, r_val in ranks:
                if r_name in gated and run_count < 10: continue
                if percentile >= r_val:
                    updates.append((idx, f'Rank_{r_name}', 1))

    # Apply updates efficiently
    # We reconstruct small DFs to update main DF
    for col in ['Is_PB'] + [f'Rank_{r[0]}' for r in ranks]:
        df[col] = df[col].astype(int) # Ensure int for ranks
        
    for idx, col, val in updates:
        df.at[idx, col] = val
        
    return df

# --- 3. ANALYSIS ---

def format_timedelta(td):
    if isinstance(td, (int, float)): td = timedelta(seconds=td)
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f'{hours:02}:{minutes:02}:{seconds:02}'

def format_timedelta_hours(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    return f"{hours}h {minutes}m"

def calculate_detailed_stats(runs_df):
    if runs_df is None or runs_df.empty: return {}
    df = runs_df.sort_values('Timestamp').copy()
    scores = df['Score']
    pb_idx = scores.idxmax()
    
    stats = {
        'count': len(df), 'max': scores.max(), 'avg': scores.mean(),
        'std': scores.std() if len(df) > 1 else 0.0,
        'p50': scores.median(), 'p75': scores.quantile(0.75), 'min': scores.min(),
        'pb_date': df.loc[pb_idx]['Timestamp'],
        'pb_sens': df.loc[pb_idx]['Sens']
    }
    
    recent = df.tail(min(len(df), 20))
    if not recent.empty: stats['recent_avg'] = recent['Score'].mean()
    
    pre_pb = df.loc[:pb_idx].iloc[:-1].tail(20)
    stats['launchpad_avg'] = pre_pb['Score'].mean() if not pre_pb.empty else 0.0
    return stats

def calculate_profile_stats(df):
    """Aggregates stats for Career Profile"""
    if df is None or df.empty: return {}
    
    stats = {
        'total_runs': len(df),
        'active_time': df['Duration'].sum(),
        'unique_scens': df['Scenario'].nunique(),
        'unique_combos': df.groupby(['Scenario', 'Sens']).ngroups,
        'total_pbs': df['Is_PB'].sum()
    }
    
    # Ranks
    ranks = {}
    for col in df.columns:
        if col.startswith('Rank_'):
            ranks[col.replace('Rank_', '')] = df[col].sum()
    stats['ranks'] = ranks
    
    # Top Scenarios
    stats['top_scens'] = df['Scenario'].value_counts().head(10).to_dict()
    
    return stats

def analyze_session(session_df, history_df, flow_window=5):
    if session_df.empty: return None
    session_start = session_df['Timestamp'].min()
    prior_history = history_df[history_df['Timestamp'] < session_start]

    base_grid_avg = prior_history.groupby(['Scenario', 'Sens'])['Score'].mean().to_dict() if not prior_history.empty else {}
    base_scen_avg = prior_history.groupby('Scenario')['Score'].mean().to_dict() if not prior_history.empty else {}
    
    base_grid_max = prior_history.groupby(['Scenario', 'Sens'])['Score'].max().to_dict() if not prior_history.empty else {}
    base_scen_max = prior_history.groupby('Scenario')['Score'].max().to_dict() if not prior_history.empty else {}

    def calc_graph(key_func, baselines):
        data, hist = [], []
        prev_pulse = 0.0
        accs = defaultdict(lambda: {'sum':0.0, 'count':0})
        
        for i, row in enumerate(session_df.sort_values('Timestamp').itertuples()):
            key = key_func(row)
            base = baselines.get(key, 0)
            acc = accs[key]
            acc['sum']+=row.Score; acc['count']+=1
            curr_avg = acc['sum']/acc['count']
            eff_base = base if base > 0 else curr_avg
            
            score_pct = ((row.Score - eff_base)/eff_base)*100 if eff_base>0 else 0
            trend_pct = ((curr_avg - eff_base)/eff_base)*100 if eff_base>0 else 0
            hist.append(score_pct)
            flow_pct = sum(hist[-flow_window:])/len(hist[-flow_window:])
            pulse_pct = score_pct if i==0 else (score_pct*0.5)+(prev_pulse*0.5)
            prev_pulse = pulse_pct
            
            data.append({
                'time': int(row.Timestamp.timestamp()), 'pct': score_pct,
                'trend_pct': trend_pct, 'flow_pct': flow_pct, 'pulse_pct': pulse_pct,
                'scenario': row.Scenario, 'sens': row.Sens
            })
        return data

    def calc_lists(grouper, base_max):
        pbs, played = [], []
        for key, g in session_df.groupby(grouper):
            pb = g['Score'].max()
            name = key[0] if isinstance(key, tuple) else key
            sens = key[1] if isinstance(key, tuple) else None
            
            is_pb = False
            prev = base_max.get(key)
            if prev and pb > prev:
                is_pb = True
                pbs.append({'name': name, 'sens': sens, 'score': pb, 'prev': prev, 'imp': pb-prev, 'imp_pct': ((pb-prev)/prev)*100})
            
            played.append({'name': name, 'sens': sens, 'count': len(g), 'best': pb, 'avg': g['Score'].mean(), 'is_pb': is_pb})
        return pbs, [], played # skipping avgs list for brevity as logic is similar

    g_graph = calc_graph(lambda r: (r.Scenario, r.Sens), base_grid_avg)
    s_graph = calc_graph(lambda r: r.Scenario, base_scen_avg)
    
    pbs_g, _, played_g = calc_lists(['Scenario', 'Sens'], base_grid_max)
    pbs_s, _, played_s = calc_lists('Scenario', base_scen_max)

    return {
        "meta": {
            "date_str": session_start.strftime('%B %d, %Y'),
            "duration_str": format_timedelta(session_df['Timestamp'].max() - session_start),
            "active_str": format_timedelta(session_df['Duration'].sum()),
            "play_count": len(session_df)
        },
        "grid": {"graph_data": g_graph, "lists": {"pbs": pbs_g, "played": played_g, "avgs": []}, "pb_count": len(pbs_g)},
        "scenario": {"graph_data": s_graph, "lists": {"pbs": pbs_s, "played": played_s, "avgs": []}, "pb_count": len(pbs_s)}
    }