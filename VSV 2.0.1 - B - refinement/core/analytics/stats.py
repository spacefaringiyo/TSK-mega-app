import pandas as pd
from datetime import timedelta
from collections import defaultdict

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
    if df is None or df.empty: return {}
    stats = {
        'total_runs': len(df),
        'active_time': df['Duration'].sum(),
        'unique_scens': df['Scenario'].nunique(),
        'unique_combos': df.groupby(['Scenario', 'Sens']).ngroups,
        'total_pbs': df['Is_PB'].sum()
    }
    ranks = {}
    for col in df.columns:
        if col.startswith('Rank_'):
            ranks[col.replace('Rank_', '')] = df[col].sum()
    stats['ranks'] = ranks
    stats['top_scens'] = df['Scenario'].value_counts().head(10).to_dict()
    return stats

def analyze_session(session_df, history_df, flow_window=5, stack_pbs=False):
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
        
        # Helper to extract key from row
        def get_key(row):
            if isinstance(grouper, list): return tuple(getattr(row, k) for k in grouper)
            return getattr(row, grouper)

        # 1. PLAYED LIST
        # Sort groups by time of first occurrence to act as default if needed, 
        # though we will inject explicit time.
        for key, g in session_df.groupby(grouper):
            pb = g['Score'].max()
            first_ts = g['Timestamp'].min() # <--- NEW: Capture Time
            
            name = key[0] if isinstance(key, tuple) else key
            sens = key[1] if isinstance(key, tuple) else None
            
            prev = base_max.get(key)
            is_pb = False
            if prev and pb > prev: is_pb = True
            
            played.append({
                'name': name, 'sens': sens, 'count': len(g), 
                'best': pb, 'avg': g['Score'].mean(), 'is_pb': is_pb,
                'time': first_ts # <--- Store it
            })

        # 2. PB LIST
        if not stack_pbs:
            for key, g in session_df.groupby(grouper):
                pb = g['Score'].max()
                prev = base_max.get(key)
                if prev and pb > prev:
                    name = key[0] if isinstance(key, tuple) else key
                    sens = key[1] if isinstance(key, tuple) else None
                    first_ts = g['Timestamp'].min() # <--- NEW
                    
                    pbs.append({
                        'name': name, 'sens': sens, 'score': pb, 
                        'prev': prev, 'imp': pb-prev, 'imp_pct': ((pb-prev)/prev)*100,
                        'time': first_ts # <--- Store it
                    })
        else:
            current_maxes = base_max.copy()
            for row in session_df.sort_values('Timestamp').itertuples():
                key = get_key(row)
                prev = current_maxes.get(key)
                if prev and row.Score > prev:
                    name = key[0] if isinstance(key, tuple) else key
                    sens = key[1] if isinstance(key, tuple) else None
                    
                    pbs.append({
                        'name': name, 'sens': sens, 'score': row.Score, 
                        'prev': prev, 'imp': row.Score-prev, 'imp_pct': ((row.Score-prev)/prev)*100,
                        'time': row.Timestamp # <--- Exact time of the run
                    })
                    current_maxes[key] = row.Score

        # Calculate Averages List
        avgs_list = []
        for key, g in session_df.groupby(grouper):
            name = key[0] if isinstance(key, tuple) else key
            sens = key[1] if isinstance(key, tuple) else None
            first_ts = g['Timestamp'].min() # <--- NEW
            
            sess_avg = g['Score'].mean()
            all_avg = base_grid_avg.get(key, sess_avg) if isinstance(key, tuple) else base_scen_avg.get(key, sess_avg)
            
            if all_avg > 0:
                diff_pct = ((sess_avg - all_avg) / all_avg) * 100
                avgs_list.append({
                    'name': name, 'sens': sens, 
                    'sess_avg': sess_avg, 'all_avg': all_avg, 
                    'diff_pct': diff_pct,
                    'time': first_ts # <--- Store it
                })

        return pbs, avgs_list, played

    g_graph = calc_graph(lambda r: (r.Scenario, r.Sens), base_grid_avg)
    s_graph = calc_graph(lambda r: r.Scenario, base_scen_avg)
    
    pbs_g, avgs_g, played_g = calc_lists(['Scenario', 'Sens'], base_grid_max)
    pbs_s, avgs_s, played_s = calc_lists('Scenario', base_scen_max)

    return {
        "meta": {
            "date_str": session_start.strftime('%B %d, %Y'),
            "duration_str": format_timedelta(session_df['Timestamp'].max() - session_start),
            "active_str": format_timedelta(session_df['Duration'].sum()),
            "play_count": len(session_df)
        },
        "grid": {"graph_data": g_graph, "lists": {"pbs": pbs_g, "played": played_g, "avgs": avgs_g}, "pb_count": len(pbs_g)},
        "scenario": {"graph_data": s_graph, "lists": {"pbs": pbs_s, "played": played_s, "avgs": avgs_s}, "pb_count": len(pbs_s)}
    }