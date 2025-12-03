import os
import pandas as pd
from pathlib import Path
import json
import bisect
from core.analytics.parsers import parse_kovaaks_stats_file

APP_DATA_DIR = Path.home() / '.kovaaks_stats_viewer'
APP_DATA_DIR.mkdir(exist_ok=True) 
CACHE_HISTORY_PATH = APP_DATA_DIR / 'kovaaks_history_cache.pkl'
CACHE_INFO_PATH = APP_DATA_DIR / 'kovaaks_cache_info.json'

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

def enrich_history_with_stats(df):
    """Calculates PBs and Assigns Ranks"""
    if df is None or df.empty: return df
    
    df = df.sort_values('Timestamp').reset_index(drop=True)
    
    ranks = [("SINGULARITY", 100), ("ARCADIA", 95), ("UBER", 90), ("EXALTED", 82), ("BLESSED", 75), ("TRANSMUTE", 55)]
    gated = {"SINGULARITY", "ARCADIA", "UBER"}
    
    for r, _ in ranks: df[f'Rank_{r}'] = 0
    df['Is_PB'] = False      # Sens PB
    df['Is_Scen_PB'] = False # Scenario PB (Any Sens)
    df['Is_First'] = False 

    updates = []
    
    # 1. PER SENSITIVITY PASS (Existing Logic)
    for (scen, sens), group in df.groupby(['Scenario', 'Sens']):
        history = []
        indices = group.index
        scores = group['Score'].values
        
        for i, score in enumerate(scores):
            idx = indices[i]
            run_count = i + 1
            
            is_pb = False
            is_first = False
            
            if not history: 
                is_first = True
                is_pb = True 
            elif score > history[-1]: 
                is_pb = True
            
            if is_pb: updates.append((idx, 'Is_PB', True))
            if is_first: updates.append((idx, 'Is_First', True))
            
            # Rank Logic (Same as before)
            if not history: percentile = 100
            elif score >= history[-1]: percentile = 100
            else:
                pos = bisect.bisect_left(history, score)
                percentile = (pos / len(history)) * 100
            bisect.insort(history, score)
            
            for r_name, r_val in ranks:
                if r_name in gated and run_count < 10: continue
                if percentile >= r_val: updates.append((idx, f'Rank_{r_name}', 1))

    # 2. PER SCENARIO PASS (New Logic)
    # Group only by Scenario Name to find global maxes
    for scen, group in df.groupby('Scenario'):
        history = []
        indices = group.index
        scores = group['Score'].values
        
        for i, score in enumerate(scores):
            # If it's the first run ever, it's a PB, but we might filter 'Firsts' later
            # Logic: If Score > Max(History), it's a Scen PB
            if not history:
                updates.append((indices[i], 'Is_Scen_PB', True))
                history.append(score) # Optimization: Only keep max?
                # Actually bisect is cheap. Let's keep history sorted.
            else:
                current_max = history[-1]
                if score > current_max:
                    updates.append((indices[i], 'Is_Scen_PB', True))
                
                bisect.insort(history, score)

    # Apply
    for col in ['Is_PB', 'Is_Scen_PB', 'Is_First'] + [f'Rank_{r[0]}' for r in ranks]:
        df[col] = df[col].astype(int) 
        
    for idx, col, val in updates:
        df.at[idx, col] = val
        
    return df