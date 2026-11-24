"""網頁用的外層程式：逐檔呼叫 analysis.py 的函式、輸出 Excel、打包 zip。
一般不需要修改；要改計分請改 analysis.py。"""
import json, shutil, zipfile, traceback
from pathlib import Path
import pandas as pd

TEST_NAMES = {'F': 'Flanker', 'N': 'N-back', 'D': 'DCCS', 'W': 'WCST'}
OUT_DIR = Path('/work/out')


def reset_outputs():
    shutil.rmtree(OUT_DIR, ignore_errors=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)


def _fmt(x):
    x = float(x)
    return f'{x:.0f}' if x.is_integer() else f'{x:.2f}'.rstrip('0').rstrip('.')


def run_one(f):
    """Same steps as the notebook's export cell, for one file."""
    stem = Path(f).stem
    rec = {'file': Path(f).name, 'test': TEST_NAMES.get(stem[-1].upper(), '?')}
    try:
        last_char, raw_data = load_data(f)
        last_char, extracted_data, raw_data = extract_raw_data(last_char, raw_data)
        last_char, cleaned_data = results(last_char, extracted_data, raw_data)
        analysis_data, learning2learn_data = analyze_results(last_char, cleaned_data)

        outXlsx = OUT_DIR / f'{stem}final.xlsx'
        with pd.ExcelWriter(outXlsx, engine='openpyxl') as writer:
            cleaned_data.to_excel(writer, sheet_name='results')
            analysis_data.to_excel(writer, sheet_name='analysis')
            if learning2learn_data is not None:
                learning2learn_data.to_excel(writer, sheet_name='learning to learn index', index=False)

        prev = analysis_data
        if prev.shape[0] == 1 and prev.shape[1] > 3:   # e.g. Flanker: show as one column so it fits
            prev = prev.T.set_axis(['value'], axis=1)
        rec.update(ok=True, out=outXlsx.name, out_path=str(outXlsx),
                   preview=prev.to_html(border=0, na_rep='', classes='prev', float_format=_fmt))
    except Exception as e:
        tb = traceback.format_exc().strip().splitlines()
        rec.update(ok=False, error=f'{type(e).__name__}: {e}', trace='\n'.join(tb[-6:]))
    return json.dumps(rec, default=str)


def make_zip():
    files_ = sorted(OUT_DIR.glob('*.xlsx'))
    if not files_:
        return ''
    zpath = Path('/work/outputs.zip')
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in files_:
            z.write(p, arcname=p.name)
    return str(zpath)
