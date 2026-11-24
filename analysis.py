"""EF 測驗計分程式：Flanker (F)、N-back (N)、DCCS (D)、WCST (W)。

內容和 Colab 版 FlankerNbackDCCSWCST_analysis.ipynb 的分析 cell 相同。
要改計分邏輯就改這個檔案，並先在 Colab 驗證結果，再上傳到 GitHub。
"""
import os, re
from pathlib import Path
import pandas as pd
import numpy as np


def load_data(path):
    base_name = os.path.splitext(os.path.basename(path))[0]
    last_char = base_name[-1].upper()
    if last_char == 'F':
        raw_data = pd.read_csv(path, sep = '\t', encoding = 'utf-16', header = 1).set_index('Trial').iloc[16:, 45:]
    elif last_char == 'N':
        raw_data = pd.read_csv(path, sep = '\t', encoding = 'utf-16', header = 1).set_index('Trial').iloc[1:, 75:]
    elif last_char == 'D':
        raw_data = pd.read_csv(path, sep = '\t', encoding = 'utf-16', header = 1).set_index('Running').iloc[15:, 71:]
    elif last_char == 'W':
        raw_data = pd.read_csv(path, sep = '\t', encoding = 'utf-16', header = 1).set_index('Trial').iloc[:, 27:]
    else:
        raise ValueError(f'無法判斷測驗名，請檢視檔名')

    return last_char, raw_data


# extract relevant information from raw data to form the participant's response
# skip missing data from exp1 to exp7
def extract_raw_data(last_char, raw_data):
    extract_temp = []
    if last_char == 'F':
        for _, row in raw_data.iterrows():
            for c in range(1, 5):
                sti = f'Stimulus{c}'
                accuracy = row[f'{sti}.ACC']
                correct_resp = row[f'{sti}.CRESP']
                resp = row[f'{sti}.RESP']
                reaction_time = row[f'{sti}.RT']

                if pd.notna(accuracy) and pd.notna(correct_resp) and pd.notna(reaction_time):
                    extract_temp.append({
                        'stimuli': row['Sti[Trial]'].split('\\')[-1],
                        'resp': resp,
                        'correct_resp': correct_resp,
                        'accuracy': accuracy,
                        'reaction_time': reaction_time
                    })
    elif last_char == 'N':
        available_back = []
        for c in [1, 2, 3]:
            sti = f'GetVisualResponse{c}'
            required_cols = [f'{sti}.ACC', f'{sti}.CRESP', f'{sti}.RESP', f'{sti}.RT']
            if all(col in raw_data.columns for col in required_cols):
                available_back.append(c)

        for _, row in raw_data.iterrows():
            for c in available_back:
                sti = f'GetVisualResponse{c}'
                accuracy = row[f'{sti}.ACC']
                correct_resp = row[f'{sti}.CRESP']
                resp = row[f'{sti}.RESP']
                reaction_time = row[f'{sti}.RT']

                if pd.notna(accuracy) and pd.notna(reaction_time):
                    extract_temp.append({
                        'stimuli': row['position'],
                        'resp': resp,
                        'correct_resp': correct_resp,
                        'accuracy': accuracy,
                        'reaction_time': reaction_time
                    })
    elif last_char == 'D':
        for _, row in raw_data.iterrows():
            for c in range(1, 8):
                sti = f'Sti{c}'
                stimuli = row[sti]
                accuracy = row[f'{sti}.ACC']
                correct_resp = row[f'{sti}.CRESP']
                resp = row[f'{sti}.RESP']
                reaction_time = row[f'{sti}.RT']

                if pd.notna(accuracy) and pd.notna(correct_resp) and pd.notna(resp) and pd.notna(reaction_time):
                    extract_temp.append({
                        'stimuli': stimuli.split('\\')[-1],
                        'resp': resp,
                        'correct_resp': correct_resp,
                        'accuracy': accuracy,
                        'reaction_time': reaction_time
                    })
    elif last_char == 'W':
        available_rules = []
        for c in ['Color', 'Shape', 'Number']:
            sti = f'{c}Stimulus'
            required_cols = [f'{sti}.ACC', f'{sti}.CRESP', f'{sti}.RESP', f'{sti}.RT']
            if all(col in raw_data.columns for col in required_cols):
                available_rules.append(c)

        for _, row in raw_data.iterrows():
            for c in available_rules:
                sti = f'{c}Stimulus'
                stimuli = row['Stim']
                rule = c.lower()
                accuracy = row[f'{sti}.ACC']
                correct_resp = row[f'{sti}.CRESP']
                resp = row[f'{sti}.RESP']
                reaction_time = row[f'{sti}.RT']

                if pd.notna(accuracy) and pd.notna(correct_resp) and pd.notna(resp) and pd.notna(reaction_time):
                    extract_temp.append({
                        'rule': rule,
                        'stimuli': str(stimuli).split('\\')[-1],
                        'resp': resp,
                        'correct_resp': correct_resp,
                        'accuracy': accuracy,
                        'reaction_time': reaction_time
                    })
    return last_char, extract_temp, raw_data

# clean and structure the extracted data
# replace button labels
def results(last_char, extract_temp, raw_data):
    if last_char == 'F':
        clean = pd.DataFrame(extract_temp, index = range(1, 33))
        clean.index.name = 'trial'
        clean['resp'] = clean['resp'].where(clean['resp'].isna(), clean['resp'].astype(str).str.strip().str.replace(r'\.0$', '', regex = True))
        clean['correct_resp'] = clean['correct_resp'].where(clean['correct_resp'].isna(), clean['correct_resp'].astype(str).str.strip().str.replace(r'\.0$', '', regex = True))
        clean['resp'] = clean['resp'].replace({'7': 'L', '{+}': 'R'})
        clean['correct_resp'] = clean['correct_resp'].replace({'7': 'L', '{+}': 'R'})
    elif last_char == 'N':
        clean = pd.DataFrame(extract_temp, index = ['1back'] * 21 + ['2back'] * 22 + (['3back'] * 23 if len(extract_temp) == 66 else []))
        clean.index.name = 'trial'
        clean['resp'] = clean['resp'].where(clean['resp'].isna(), clean['resp'].astype(str).str.strip().str.replace(r'\.0$', '', regex = True))
        mask = clean['resp'].notna() & clean['correct_resp'].notna()
        clean.loc[mask, 'accuracy'] = clean[mask].apply(lambda row: 1 if str(row['resp']) in str(row['correct_resp']) else row['accuracy'], axis = 1)
    elif last_char == 'D':
        clean = pd.DataFrame(extract_temp, index = ['exp1'] * 10 + ['exp2'] * 10 + ['exp3'] * 10 + ['exp4'] * 20 + ['exp5'] * 10 + ['exp6'] * 10 + ['exp7'] * 10)
        clean.index.name = 'trial'
        clean['resp'] = clean['resp'].where(clean['resp'].isna(), clean['resp'].astype(str).str.strip().str.replace(r'\.0$', '', regex = True))
        clean['correct_resp'] = clean['correct_resp'].where(clean['correct_resp'].isna(), clean['correct_resp'].astype(str).str.strip().str.replace(r'\.0$', '', regex = True))
        clean['resp'] = clean['resp'].replace({'{+}': 'BR', '7': 'RB'})
        clean['correct_resp'] = clean['correct_resp'].replace({'{+}': 'BR', '7': 'RB'})
    elif last_char == 'W':
        clean = pd.DataFrame(extract_temp, index = range(1, 129))
        clean.index.name = 'trial'
        clean['resp'] = clean['resp'].where(clean['resp'].isna(), clean['resp'].astype(str).str.strip().str.replace(r'\.0$', '', regex = True))
        clean['correct_resp'] = clean['correct_resp'].where(clean['correct_resp'].isna(), clean['correct_resp'].astype(str).str.strip().str.replace(r'\.0$', '', regex = True))
        clean['resp'] = clean['resp'].replace({'7': 'RedTriangle1', '8': 'GreenStar2', '9': 'YellowCross3', '{+}': 'BlueCircle4'})
        clean['correct_resp'] = clean['correct_resp'].replace({'7': 'RedTriangle1', '8': 'GreenStar2', '9': 'YellowCross3', '{+}': 'BlueCircle4'})
        color, shape, number, other = [], [], [], []
        for _, row in clean.iterrows():
            c = int(row['stimuli'][:3] == row['resp'][:3])
            s = int(row['stimuli'].split('.')[0][3:-1] == row['resp'][3:-1])
            n = int(row['stimuli'].split('.')[0][-1] == row['resp'][-1])
            o = int((c + s + n) == 0)
            color.append(c)
            shape.append(s)
            number.append(n)
            other.append(o)
        clean['color'] = color
        clean['shape'] = shape
        clean['number'] = number
        clean['other'] = other
    return last_char, clean

WCST_RULE_MAP = {
    'color': 'C', 'colour': 'C', 'c': 'C',
    'shape': 'F', 'form': 'F', 'f': 'F',
    'number': 'N', 'num': 'N', 'n': 'N'
}
WCST_RULE_LABEL = {'C': 'color', 'F': 'form', 'N': 'number'}
WCST_COLORS = ('Red', 'Green', 'Yellow', 'Blue')
WCST_SHAPES = ('Triangle', 'Star', 'Cross', 'Circle')


def wcst_to_int01(x):
    if pd.isna(x):
        return 0
    if isinstance(x, str) and x.strip() == '':
        return 0
    return int(float(x))


def wcst_rule_code(value):
    key = str(value).strip().lower()
    if key not in WCST_RULE_MAP:
        raise ValueError(f'Unknown WCST rule value: {value!r}. Expected color/shape/form/number.')
    return WCST_RULE_MAP[key]


def wcst_parse_card(card):
    """Parse card names such as BlueCross1.bmp or RedTriangle1."""
    s = str(card).split('\\')[-1].split('/')[-1].strip().replace('.bmp', '')
    color = next((c for c in WCST_COLORS if s.startswith(c)), None)
    if color is None:
        raise ValueError(f'Cannot parse WCST card color from {card!r}')
    rest = s[len(color):]
    m = re.search(r'(\d+)$', rest)
    if not m:
        raise ValueError(f'Cannot parse WCST card number from {card!r}')
    number = m.group(1)
    shape = rest[:-len(number)]
    if shape not in WCST_SHAPES:
        raise ValueError(f'Cannot parse WCST card shape from {card!r}')
    return color, shape, number


def wcst_response_set_from_cards(stimulus, response):
    sc, sf, sn = wcst_parse_card(stimulus)
    rc, rf, rn = wcst_parse_card(response)
    out = set()
    if sc == rc:
        out.add('C')
    if sf == rf:
        out.add('F')
    if sn == rn:
        out.add('N')
    return out


def wcst_prepare_trials(clean):
    """Normalize the cleaned WCST table and create response-set columns."""
    trials = clean.copy().reset_index()
    trials.columns = [str(c).strip().lower() for c in trials.columns]

    # Alias support for older output files, while original raw-to-clean path already uses rule/shape.
    if 'recentrule' in trials.columns and 'rule' not in trials.columns:
        trials = trials.rename(columns={'recentrule': 'rule'})
    if 'form' in trials.columns and 'shape' not in trials.columns:
        trials = trials.rename(columns={'form': 'shape'})

    if 'trial' not in trials.columns:
        trials.insert(0, 'trial', range(1, len(trials) + 1))

    required = {'rule', 'accuracy'}
    missing = required - set(trials.columns)
    if missing:
        raise ValueError(f'Missing required WCST columns: {sorted(missing)}')

    trials['trial'] = range(1, len(trials) + 1)
    trials['accuracy'] = trials['accuracy'].apply(wcst_to_int01)
    trials['rule_code'] = trials['rule'].apply(wcst_rule_code)

    has_cards = all(c in trials.columns for c in ['stimuli', 'resp'])
    has_dims = all(c in trials.columns for c in ['color', 'shape', 'number'])

    response_sets = []
    if has_cards:
        # Prefer card parsing. It is safer when color/shape/number columns were made by task labels.
        for _, row in trials.iterrows():
            response_sets.append(wcst_response_set_from_cards(row['stimuli'], row['resp']))
    elif has_dims:
        for _, row in trials.iterrows():
            s = set()
            if wcst_to_int01(row['color']):
                s.add('C')
            if wcst_to_int01(row['shape']):
                s.add('F')
            if wcst_to_int01(row['number']):
                s.add('N')
            response_sets.append(s)
    else:
        raise ValueError('WCST scoring needs either stimuli/resp or color/shape/number columns.')

    trials['response_set'] = response_sets
    trials['response_code'] = [''.join(d for d in 'CFN' if d in s) or 'O' for s in response_sets]
    trials['is_unambiguous'] = [len(s) == 1 for s in response_sets]
    trials['is_ambiguous'] = [len(s) > 1 for s in response_sets]
    return trials


def wcst_make_stages(trials):
    """Create category stages from changes in the current correct rule."""
    if len(trials) == 0:
        return []
    stages = []
    rules = trials['rule_code'].tolist()
    start = 0
    for i in range(1, len(rules)):
        if rules[i] != rules[i - 1]:
            stages.append({'stage': len(stages) + 1, 'start_idx': start, 'end_idx': i - 1, 'rule': rules[i - 1]})
            start = i
    stages.append({'stage': len(stages) + 1, 'start_idx': start, 'end_idx': len(trials) - 1, 'rule': rules[-1]})
    return stages


def wcst_find_completion_trial(stage, accuracy):
    """Return 1-based trial number where a category reaches 10 consecutive correct responses."""
    run = 0
    for offset, x in enumerate(accuracy[stage['start_idx']: stage['end_idx'] + 1]):
        if x == 1:
            run += 1
            if run >= 10:
                return stage['start_idx'] + offset + 1
        else:
            run = 0
    return None


def wcst_scoring_cutoff_trial(stages, accuracy, max_categories=6):
    """Stop scoring at the trial where the 6th category is completed; otherwise score all trials."""
    completed_count = 0
    for st in stages:
        completion = wcst_find_completion_trial(st, accuracy)
        if completion is not None:
            completed_count += 1
            if completed_count >= max_categories:
                return int(completion)
    return int(len(accuracy))


def wcst_mark_conceptual_level(accuracy):
    """Correct responses that belong to runs of at least 3 consecutive correct responses."""
    n = len(accuracy)
    flags = [False] * n
    i = 0
    while i < n:
        if accuracy[i] != 1:
            i += 1
            continue
        j = i
        while j < n and accuracy[j] == 1:
            j += 1
        if j - i >= 3:
            for k in range(i, j):
                flags[k] = True
        i = j
    return flags


def wcst_mark_failure_to_maintain_set(stages, accuracy):
    """Error after 5-9 consecutive correct responses before completing that category."""
    flags = [False] * len(accuracy)
    for st in stages:
        run = 0
        completed = False
        for i in range(st['start_idx'], st['end_idx'] + 1):
            if accuracy[i] == 1:
                run += 1
                if run >= 10:
                    completed = True
            else:
                if not completed and 5 <= run <= 9:
                    flags[i] = True
                run = 0
    return flags


def wcst_stage_summary(stages, accuracy):
    rows = []
    for st in stages:
        acc = list(accuracy[st['start_idx']: st['end_idx'] + 1])
        errors = sum(1 for x in acc if x == 0)
        trials_n = len(acc)
        percent_errors = round(errors / trials_n * 100, 2) if trials_n else np.nan
        completion_trial = wcst_find_completion_trial(st, accuracy)
        rows.append({
            'stage': st['stage'],
            'rule': WCST_RULE_LABEL[st['rule']],
            'start_trial': st['start_idx'] + 1,
            'end_trial': st['end_idx'] + 1,
            'trials': trials_n,
            'errors': errors,
            'percent_errors': percent_errors,
            'completed': completion_trial is not None,
            'completion_trial': completion_trial
        })

    out = pd.DataFrame(rows)
    if out.empty:
        out['ltl_difference_from_previous'] = []
        return out

    diffs = [' ']
    for i in range(1, len(out)):
        prev = out.loc[i - 1, 'percent_errors']
        curr = out.loc[i, 'percent_errors']
        diffs.append(' ' if pd.isna(prev) or pd.isna(curr) else round(prev - curr, 2))
    out['ltl_difference_from_previous'] = diffs
    return out


def wcst_learning_to_learn(stage_df):
    """Mean of adjacent percent-error differences among scored completed/attempted stages."""
    if stage_df.empty:
        return 'NA'
    use = stage_df[(stage_df['completed'] == True) | (stage_df['trials'] >= 10)].reset_index(drop=True)
    if len(use) < 2:
        return 'NA'
    diffs = []
    for i in range(1, len(use)):
        diffs.append(float(use.loc[i - 1, 'percent_errors']) - float(use.loc[i, 'percent_errors']))
    return round(sum(diffs) / len(diffs), 2)


def wcst_make_learning_to_learn_record(stage_df, scoring_cutoff):
    if stage_df.empty:
        return pd.DataFrame(columns=[
            'Category Number', 'Number of Trials', 'Errors', 'Percent errors',
            'Percent errors difference score', 'Included in scored trials', 'Used in Learning to Learn'
        ])

    record = pd.DataFrame({
        'Category Number': stage_df['stage'].astype(int),
        'Number of Trials': stage_df['trials'].astype(int),
        'Errors': stage_df['errors'].astype(int),
        'Percent errors': stage_df['percent_errors'],
        'Percent errors difference score': stage_df['ltl_difference_from_previous'],
        'Included in scored trials': stage_df['start_trial'].astype(int) <= scoring_cutoff,
        'Used in Learning to Learn': (stage_df['completed'] == True) | (stage_df['trials'] >= 10)
    })
    record.loc[record['Included in scored trials'] == False, 'Used in Learning to Learn'] = False
    return record


def wcst_score_perseveration(trials, stages, allow_p_shifts=True):
    n = len(trials)
    response_sets = trials['response_set'].tolist()
    accuracy = trials['accuracy'].astype(int).tolist()
    is_unambig = trials['is_unambiguous'].tolist()
    is_ambig = trials['is_ambiguous'].tolist()

    pr = [False] * n
    direct_pr = [False] * n
    sandwich_pr = [False] * n
    p_shift_pr = [False] * n
    p_principle = [None] * n
    p_setter = [False] * n

    previous_rule = None
    for stage_number, st in enumerate(stages):
        p = None if stage_number == 0 else previous_rule
        direct_groups = {'C': [], 'F': [], 'N': []}
        alt_runs = {'C': [], 'F': [], 'N': []}

        for i in range(st['start_idx'], st['end_idx'] + 1):
            s = response_sets[i]
            p_principle[i] = p

            if is_unambig[i] and accuracy[i] == 0:
                q = next(iter(s))

                if p is None:
                    p = q
                    p_principle[i] = p
                    p_setter[i] = True
                    alt_runs = {'C': [], 'F': [], 'N': []}

                elif q == p:
                    pr[i] = True
                    direct_pr[i] = True
                    direct_groups[p].append(i)
                    alt_runs = {'C': [], 'F': [], 'N': []}

                else:
                    if allow_p_shifts:
                        for dim in 'CFN':
                            if dim == q:
                                alt_runs[dim].append(i)
                            else:
                                alt_runs[dim] = []

                        if len(alt_runs[q]) >= 3:
                            second = alt_runs[q][-2]
                            third = alt_runs[q][-1]
                            for j in range(second, third + 1):
                                if q in response_sets[j]:
                                    pr[j] = True
                                    p_shift_pr[j] = True
                                    p_principle[j] = q
                            p = q
                            direct_groups = {'C': [], 'F': [], 'N': []}
                            direct_groups[q].append(third)
                            alt_runs = {'C': [], 'F': [], 'N': []}

            else:
                if allow_p_shifts and is_ambig[i]:
                    for dim in 'CFN':
                        if alt_runs[dim] and dim not in s:
                            alt_runs[dim] = []

        # Sandwich rule within the same category and same p-principle.
        for dim, idxs in direct_groups.items():
            idxs = sorted(set(idxs))
            for left, right in zip(idxs, idxs[1:]):
                if all(dim in response_sets[j] for j in range(left + 1, right)):
                    for j in range(left + 1, right):
                        if is_ambig[j] and dim in response_sets[j]:
                            pr[j] = True
                            sandwich_pr[j] = True
                            if p_principle[j] is None:
                                p_principle[j] = dim

        previous_rule = st['rule']

    pe = [bool(pr[i] and accuracy[i] == 0) for i in range(n)]
    return {
        'pr': pr,
        'pe': pe,
        'direct_pr': direct_pr,
        'sandwich_pr': sandwich_pr,
        'p_shift_pr': p_shift_pr,
        'p_principle': p_principle,
        'p_setter': p_setter
    }


def wcst_score_clean_dataframe(clean):
    """Score the cleaned WCST dataframe and return analysis table inputs plus learning-to-learn record."""
    full_trials = wcst_prepare_trials(clean)
    full_accuracy = full_trials['accuracy'].astype(int).tolist()
    full_stages = wcst_make_stages(full_trials)

    cutoff = wcst_scoring_cutoff_trial(full_stages, full_accuracy, max_categories=6)
    trials = full_trials.iloc[:cutoff].copy().reset_index(drop=True)
    stages = wcst_make_stages(trials)
    accuracy = trials['accuracy'].astype(int).tolist()

    persp = wcst_score_perseveration(trials, stages, allow_p_shifts=True)
    clr_flags = wcst_mark_conceptual_level(accuracy)
    fms_flags = wcst_mark_failure_to_maintain_set(stages, accuracy)

    effective_stage_df = wcst_stage_summary(stages, accuracy)
    full_stage_df = wcst_stage_summary(full_stages, full_accuracy)
    learning2learnSht = wcst_make_learning_to_learn_record(full_stage_df, scoring_cutoff=cutoff)
    learning2learn = wcst_learning_to_learn(effective_stage_df)

    nta = int(len(accuracy))
    tnc = int(sum(accuracy))
    tne = int(nta - tnc)
    pr = int(sum(persp['pr']))
    pe = int(sum(persp['pe']))
    npe = int(tne - pe)
    clr = int(sum(clr_flags))
    fms = int(sum(fms_flags))
    ncc = int(effective_stage_df['completed'].sum()) if not effective_stage_df.empty else 0

    first_completed = effective_stage_df.loc[effective_stage_df['completed'] == True, 'completion_trial']
    tcfc = int(first_completed.iloc[0]) if not first_completed.empty else None

    def pct(num, den):
        return round(float(num) / float(den) * 100, 2) if den else np.nan

    data = {
        'Number of Trials Administered': nta,
        'Total Number Correct': tnc,
        'Total Number Errors': tne,
        'Percent Errors': round(pct(tne, nta), 0),
        'Perseverative Responses': pr,
        'Percent Perseverative Responses': round(pct(pr, nta), 0),
        'Perseverative Errors': pe,
        'Percent Perseverative Errors': round(pct(pe, nta), 0),
        'Nonperseverative Errors': npe,
        'Percent Nonperseverative Errors': round(pct(npe, nta), 0),
        'Conceptual Level Responses': clr,
        'Percent Conceptual Level Responses': round(pct(clr, nta), 0),
        'Number of Categories Completed': ncc,
        'Trials to Complete First Category': tcfc,
        'Failure to Maintain Set': fms,
        'Learning to Learn': learning2learn
    }
    return data, learning2learnSht

# analyze the results to compute accuracy and reaction time
def analyze_results(last_char, clean):
    if last_char == 'F':
        con_mask = clean['stimuli'].str.contains('CON')
        incon_mask = clean['stimuli'].str.contains('IN')
        con_acc = round(np.mean(clean.loc[con_mask, 'accuracy']), 2)
        incon_acc = round(np.mean(clean.loc[incon_mask, 'accuracy']), 2)
        conRt = round(np.mean(clean.loc[con_mask & (clean['accuracy'] == 1), 'reaction_time']), 2)
        inconRt = round(np.mean(clean.loc[incon_mask & (clean['accuracy'] == 1), 'reaction_time']), 2)
        conflictRt = inconRt - conRt
        analysis = pd.DataFrame(data = np.reshape([con_acc, conRt, incon_acc, inconRt, conflictRt], (1, -1)), columns = ['CngAcc', 'CngRT', 'IncngAcc', 'IncngRT', 'Cnf'])
        return analysis, None
    elif last_char == 'N':
        one_acc = round(clean.loc['1back', 'accuracy'].iloc[1:].mean(), 2)
        two_acc = round(clean.loc['2back', 'accuracy'].iloc[2:].mean(), 2)
        one_rt_trials = (clean['accuracy'] == 1) & clean.index.isin(['1back']) & (clean['reaction_time'] != 0)
        two_rt_trials = (clean['accuracy'] == 1) & clean.index.isin(['2back']) & (clean['reaction_time'] != 0)
        if one_rt_trials.any():
            one_rt = round(np.mean(clean.loc[one_rt_trials, 'reaction_time']), 2)
        else:
            one_rt = 'NA'
        if two_rt_trials.any():
            two_rt = round(np.mean(clean.loc[two_rt_trials, 'reaction_time']), 2)
        else:
            two_rt = 'NA'
        acc_list = [one_acc, two_acc]
        rt_list = [one_rt, two_rt]
        idx_list = ['1back', '2back']
        if len(clean) == 66:
            three_acc = round(clean.loc['3back', 'accuracy'].iloc[3:].mean(), 2)
            three_rt_trials = (clean['accuracy'] == 1) & clean.index.isin(['3back']) & (clean['reaction_time'] != 0)
            if one_rt_trials.any():
                three_rt = round(np.mean(clean.loc[three_rt_trials, 'reaction_time']), 2)
            else:
                three_rt = 'NA'
            acc_list.append(three_acc)
            rt_list.append(three_rt)
            idx_list.append('3back')
        data = np.column_stack([acc_list, rt_list])
        analysis = pd.DataFrame(data = data, columns = ['acc', 'rt'], index = idx_list)
        return analysis, None
    elif last_char == 'D':
        uni_acc_trials = clean.loc[:, 'accuracy'].sum() - clean.loc['exp4', 'accuracy'].sum()
        bi_acc_trials = clean.loc['exp4', 'accuracy'].sum()
        uni_acc = round(uni_acc_trials / 60, 2)
        bi_acc = round(bi_acc_trials / 20, 2)
        mean_rt = np.mean(clean['reaction_time'])
        sd_rt = np.std(clean['reaction_time'])
        mask = (
                (clean['accuracy'] == 1) &
                (clean['reaction_time'] <= mean_rt + 2.5*sd_rt) &
                (clean['reaction_time'] >= 200)
            )
        uni_rt_trials = mask & clean.index.isin(['exp1', 'exp2', 'exp3', 'exp5', 'exp6', 'exp7'])
        bi_rt_trials = mask & (clean.index == 'exp4')
        uni_rt = round(np.mean(clean.loc[uni_rt_trials, 'reaction_time']), 2)
        bi_rt = round(np.mean(clean.loc[bi_rt_trials, 'reaction_time']), 2)
        analysis = pd.DataFrame(data = np.reshape([uni_acc, uni_rt, bi_acc, bi_rt], (2, -1)), columns = ['acc', 'rt'], index = ['uni', 'bi'])
        return analysis, None
    elif last_char == 'W':
        data, learning2learnSht = wcst_score_clean_dataframe(clean)
        analysis = pd.DataFrame(data = data, index = [0]).T.rename(columns = {0: 'Raw score'})
    return analysis, learning2learnSht
