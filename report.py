"""報告書產生程式（網頁版）

format_value、generate_srs_plot、insert_plot、generate_report 和 Colab 版
report_generator.ipynb 相同，只有下面兩處不同：
- 資料改由網頁用 Google 登入讀取共享試算表的「report」工作表（和 gspread 的
  get_all_values() 一樣讀成文字），範本改從 Google Drive 讀取
- 圖表字型改用網站附帶的思源黑體（fonts/NotoSansTC-report.otf）
"""
import io
import os
import json
import shutil
import zipfile
import traceback

os.environ.setdefault('MPLBACKEND', 'Agg')
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

from mailmerge import MailMerge
from docx import Document
from docx.shared import Inches

# docx-mailmerge 預設用 ASCII 輸出 Word 的 XML。瀏覽器版 lxml 附帶的 libxml2 比較舊，
# 中文內容很長時會出現「SerialisationError: IO_ENCODER」。
# 改用 UTF-8 輸出（Word 本身用的就是 UTF-8），報告書內容完全相同。
import mailmerge as _mailmerge
from lxml import etree as _etree


class _Utf8Etree:
    def __getattr__(self, name):
        return getattr(_etree, name)

    @staticmethod
    def tostring(element, **kw):
        kw.setdefault('encoding', 'UTF-8')
        kw.setdefault('xml_declaration', True)
        kw.setdefault('standalone', True)
        return _etree.tostring(element, **kw)


_mailmerge.etree = _Utf8Etree()

REPORT_ROOT = '/work/report'
TEMPLATE = REPORT_ROOT + '/template.docx'
REPORT_DIR = REPORT_ROOT + '/out'
FONT_PATH = REPORT_ROOT + '/NotoSansTC-report.otf'
raw_data = None

fm.fontManager.addfont(FONT_PATH)
plt.rcParams['font.family'] = fm.FontProperties(fname=FONT_PATH).get_name()
plt.rcParams['font.size'] = 14


# ---- 以下四個函式和 Colab 版相同 ----

def format_value(field, value):
    # if ToMI2 or CARS2, get one decimal place
    if ('ToMI2' in field or 'CARS2' in field) and isinstance(value, float):
        return f'{value:.1f}'
    # if is note or nan
    if isinstance(value, str) or (isinstance(value, float) and np.isnan(value)):
        return str(value)
    # other int
    if isinstance(value, (int, float, np.integer, np.floating)):
        return str(int(value))
    # others
    return str(value)


def generate_srs_plot(scores):
    xs = [1, 2, 3, 4, 5]
    labels = ['社會知覺', '社會認知', '社會溝通', '社會動機', '自閉症特質']

    buf = io.BytesIO()
    plt.figure(figsize=(11, 6))

    ax = plt.gca()

    ax.axhspan(76, 120, facecolor='#F2F2F2', alpha=0.7) #高度差異
    ax.axhspan(66, 75, facecolor='#F2F2F2', alpha=0.7) #中度差異
    ax.axhspan(60, 65, facecolor='#F2F2F2', alpha=0.7) #輕微差異
    ax.axhspan(30, 59, facecolor='#F2F2F2', alpha=0.7) #與同齡孩童表現相近

    ax.plot(xs, scores, color='black', linestyle='-', linewidth=2, marker='o', markersize=5, zorder=5)
    ax.set_xticks(xs)
    ax.set_xticklabels(labels, fontsize=14)
    ax.set_ylim([30, 120])

    for x, y in zip(xs, scores):
        ax.annotate(str(y), (x, y),
                    textcoords='offset points',
                    xytext=(0, 10),
                    ha='center',
                    fontsize=12)

    ax.set_ylabel('標準分數', fontsize=14)
    ax.grid(True, axis='y', alpha=0.2)

    ymin, ymax = ax.get_ylim()
    def norm_y(y):
        return (y - ymin) / (ymax - ymin)

    ax.text(1.02, norm_y(98), '高度差異', va='center', ha='left', transform=ax.transAxes, fontsize=14)
    ax.text(1.02, norm_y(70.5), '中度差異', va='center', ha='left', transform=ax.transAxes, fontsize=14)
    ax.text(1.02, norm_y(62.5), '輕微差異', va='center', ha='left', transform=ax.transAxes, fontsize=14)
    ax.text(1.02, norm_y(40), '與同齡孩童表現相近', va='center', ha='left', transform=ax.transAxes, fontsize=14)


    plt.tight_layout()
    plt.savefig(buf, format='png', dpi=150)
    plt.close()
    buf.seek(0)
    return buf


def insert_plot(doc_obj, placeholder, plot_buf):
    for table in doc_obj.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    if placeholder in p.text:
                        p.text = p.text.replace(placeholder, "")
                        plot_buf.seek(0)
                        p.add_run().add_picture(plot_buf, width=Inches(5.5))
                        return
    return


def generate_report(idx, out_dir=REPORT_DIR):
    if idx not in raw_data.index:
        print(f'ID {idx} 不在資料表中，已略過')
        return

    doc = MailMerge(TEMPLATE)
    fieldL = list(doc.get_merge_fields())

    data_dict = {}
    for field in fieldL:
        if field == 'SRS2plot':
            data_dict['SRS2plot'] = '_plot_'
            continue
        value = raw_data.loc[idx, field]
        data_dict[field] = format_value(field, value)

    doc.merge_templates([data_dict], separator='continuous_section')
    temp_buffer = io.BytesIO()
    doc.write(temp_buffer)
    doc.close()

    srs_cols = ['SRS2AwrT', 'SRS2CgnT', 'SRS2CmcT', 'SRS2MtvT', 'SRS2RRBT']
    srsT = pd.to_numeric(raw_data.loc[idx, srs_cols])
    plot_buf = generate_srs_plot(srsT)

    temp_buffer.seek(0)
    final_doc = Document(temp_buffer)
    insert_plot(final_doc, '_plot_', plot_buf)

    out_path = os.path.join(out_dir, f'{idx}R.docx')
    final_doc.save(out_path)

    return f'{idx}報告書已產生'


# ---- 網頁用的外層程式 ----

def load_sheet(values_json):
    """values_json：Sheets API 回傳的 values（二維文字陣列，第一列是欄位名稱）"""
    global raw_data
    data = json.loads(values_json)
    if not data:
        raise ValueError('試算表的report工作表是空的')
    header = data[0]
    if 'id' not in header:
        raise ValueError('report工作表的第一列找不到「id」欄位')
    n = len(header)
    # Sheets API 會省略每列最後的空白格，補回來，和 get_all_values() 一致
    rows = [(list(r) + [''] * n)[:n] for r in data[1:]]
    raw_data = pd.DataFrame(rows, columns=header).set_index('id')


def reset_reports():
    shutil.rmtree(REPORT_DIR, ignore_errors=True)
    os.makedirs(REPORT_DIR, exist_ok=True)


def make_one(idx):
    rec = {'id': idx}
    try:
        if idx not in raw_data.index:
            rec.update(ok=False, error='這個ID不在試算表的report工作表中')
            return json.dumps(rec)
        generate_report(idx, REPORT_DIR)
        out = os.path.join(REPORT_DIR, f'{idx}R.docx')
        rec.update(ok=True, out=os.path.basename(out), out_path=out)
    except KeyError as e:
        rec.update(ok=False, error=f'試算表找不到範本需要的欄位：{e}', trace=traceback.format_exc()[-1200:])
    except Exception as e:
        rec.update(ok=False, error=f'{type(e).__name__}: {e}', trace=traceback.format_exc()[-1200:])
    finally:
        plt.close('all')
    return json.dumps(rec, default=str)


def zip_reports():
    docs = sorted(f for f in os.listdir(REPORT_DIR) if f.endswith('.docx'))
    if not docs:
        return ''
    zpath = REPORT_ROOT + '/reports.zip'
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in docs:
            z.write(os.path.join(REPORT_DIR, f), arcname=f)
    return zpath
