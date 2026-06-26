#!/usr/bin/env python3
"""
Visualisasi.py
Membuat visualisasi HTML jadwal kuliah dari Gabungan_Schedules.csv
Output: Visualisasi.html
"""

import pandas as pd
import html as html_lib
from collections import defaultdict, Counter

# ═══════════════════════════════════════════════════════
# 1. LOAD DATA
# ═══════════════════════════════════════════════════════
CSV_PATH  = 'D:\\Berkas UB\\SKRIPSI\\COATI\\Coati_Optimization_University-Course-Schedulling\\FIX_EXPERIMENT\\Gabungan_Schedules.csv'
HTML_PATH = 'D:\\Berkas UB\\SKRIPSI\\COATI\\Coati_Optimization_University-Course-Schedulling\\Visualisasi\\Visualisasi.html'

df = pd.read_csv(CSV_PATH)
df['Dosen'] = df['Dosen'].fillna(0).astype(int)

has_sks       = 'SKS'       in df.columns
has_kewajiban = 'Kewajiban' in df.columns

# ═══════════════════════════════════════════════════════
# 2. KONSTANTA
# ═══════════════════════════════════════════════════════
DAY_ORDER = {'Mon': 0, 'Tue': 1, 'Wed': 2, 'Thu': 3, 'Fri': 4}
DAY_LABEL = {'Mon': 'Senin', 'Tue': 'Selasa', 'Wed': 'Rabu',
             'Thu': 'Kamis', 'Fri': 'Jumat'}
LECTURE_END = 16
PRACT_END   = 18

HEAVY_TOTAL = int(df['Heavy_Total'].iloc[0]) if len(df) else 0
LIGHT_TOTAL = int(df['Light_Total'].iloc[0]) if len(df) else 0
IS_FEASIBLE = bool(df['Feasible'].iloc[0])   if len(df) else False

# ═══════════════════════════════════════════════════════
# 3. DETEKSI PELANGGARAN
# ═══════════════════════════════════════════════════════
violations = []

def add_v(row, tipe, pelanggaran, detail):
    sks_val       = int(row['SKS'])       if has_sks       else 'N/A'
    kewajiban_val = int(row['Kewajiban']) if has_kewajiban else 'N/A'
    violations.append({
        'kode_mk'    : str(row['Kode_MK']),
        'nama_mk'    : str(row['Nama_MK']),
        'dosen'      : int(row['Dosen']),
        'hari'       : str(row['Hari']),
        'jam'        : int(row['Jam']),
        'jenis'      : str(row['Jenis']),
        'ruang'      : str(row['Ruang']),
        'sks'        : sks_val,
        'kewajiban'  : kewajiban_val,
        'tipe'       : tipe,
        'pelanggaran': pelanggaran,
        'detail'     : detail,
    })

# 3a. Ruang Bentrok
for (hari, jam, ruang), grp in df.groupby(['Hari', 'Jam', 'Ruang']):
    if len(grp) > 1:
        for _, row in grp.iterrows():
            add_v(row, 'Hard', 'Ruang_Bentrok',
                  'Ruang %s dipakai %d kelas di %s %02d:00' % (ruang, len(grp), DAY_LABEL[hari], jam))

# 3b. Dosen Bentrok (lecture only)
lec_df = df[df['Jenis'] == 'lecture']
for (hari, jam, dosen), grp in lec_df.groupby(['Hari', 'Jam', 'Dosen']):
    if len(grp) > 1:
        for _, row in grp.iterrows():
            add_v(row, 'Hard', 'Dosen_Bentrok',
                  'Dosen %s mengajar %d kelas bersamaan di %s %02d:00' % (dosen, len(grp), DAY_LABEL[hari], jam))

# 3c. Diluar Waktu
for _, row in df.iterrows():
    if row['Jenis'] == 'lecture' and int(row['Jam']) >= LECTURE_END:
        add_v(row, 'Hard', 'Diluar_Waktu',
              'Lecture jam %02d:00 melebihi batas jam %02d:00' % (row['Jam'], LECTURE_END))
    elif row['Jenis'] == 'practicum' and int(row['Jam']) >= PRACT_END:
        add_v(row, 'Hard', 'Diluar_Waktu',
              'Praktikum jam %02d:00 melebihi batas jam %02d:00' % (row['Jam'], PRACT_END))

# 3d. Lecture Pakai Lab
for _, row in df.iterrows():
    if row['Jenis'] == 'lecture' and str(row['Ruang']).startswith('LAB'):
        add_v(row, 'Hard', 'Lecture_Pakai_Lab',
              'Sesi lecture menggunakan ruang lab: %s' % row['Ruang'])

# 3e. Praktikum Tanpa Lab
for _, row in df.iterrows():
    if row['Jenis'] == 'practicum' and not str(row['Ruang']).startswith('LAB'):
        add_v(row, 'Hard', 'Praktikum_Tanpa_Lab',
              'Sesi praktikum tidak menggunakan lab: %s' % row['Ruang'])

# ── Soft violations ──────────────────────────────────────────
# Soft: Prioritas MK — jika kolom tersedia, MK dengan prioritas > 0 dicatat
# (semakin kecil angka = semakin penting; 0 = sangat penting, 999 = tidak ada prioritas)
HAS_PRIORITAS = 'Prioritas' in df.columns

if HAS_PRIORITAS:
    # Ambil prioritas unik per MK (bukan per sesi)
    mk_prio = df[['Kode_MK','Nama_MK','Prodi','Prioritas']].drop_duplicates('Kode_MK')
    for _, row_p in mk_prio.iterrows():
        prio = int(row_p['Prioritas'])
        if prio > 0:
            # Cari satu sesi representatif dari MK ini
            sample = df[df['Kode_MK'] == row_p['Kode_MK']].iloc[0]
            # Hanya lecture (bukan praktikum) yang dicatat sebagai soft
            lec_sample = df[(df['Kode_MK'] == row_p['Kode_MK']) &
                            (df['Jenis'] == 'lecture')]
            if len(lec_sample) == 0:
                lec_sample = df[df['Kode_MK'] == row_p['Kode_MK']]
            for _, s_row in lec_sample.iterrows():
                add_v(s_row, 'Soft', 'Prioritas_MK',
                      'Prioritas MK = %d (kontribusi soft penalty: %d)' % (prio, prio))

viol_counts   = Counter(v['pelanggaran'] for v in violations)
hard_detected = sum(c for v, c in viol_counts.items()
                    if any(x['tipe'] == 'Hard' and x['pelanggaran'] == v
                           for x in violations))
soft_detected = sum(c for v, c in viol_counts.items()
                    if any(x['tipe'] == 'Soft' and x['pelanggaran'] == v
                           for x in violations))

# ═══════════════════════════════════════════════════════
# 4. DATA TIMETABLE
# ═══════════════════════════════════════════════════════
conflict_keys      = set((v['hari'], v['jam'], v['ruang']) for v in violations if v['tipe'] == 'Hard')
soft_conflict_keys = set((v['hari'], v['jam'], v['ruang']) for v in violations if v['tipe'] == 'Soft' and v['tipe'] != 'Hard')

def cell_info(row):
    dosen_disp = 'Praktikum' if row['Jenis'] == 'practicum' else str(int(row['Dosen']))
    sks_disp   = str(int(row['SKS']))       if has_sks       else 'N/A'
    kew_disp   = str(int(row['Kewajiban'])) if has_kewajiban else 'N/A'
    return {
        'kode'     : row['Kode_MK'],
        'nama'     : row['Nama_MK'],
        'dosen'    : dosen_disp,
        'sks'      : sks_disp,
        'kewajiban': kew_disp,
        'jenis'    : row['Jenis'],
        'prodi'    : row['Prodi'],
        'conflict' : (row['Hari'], int(row['Jam']), row['Ruang']) in conflict_keys,
        'viol_type': ('hard' if (row['Hari'], int(row['Jam']), row['Ruang']) in conflict_keys
                      else 'soft' if (row['Hari'], int(row['Jam']), row['Ruang']) in soft_conflict_keys
                      else 'none'),
    }

# schedule[hari][jam][ruang] = list of cells
schedule = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
for _, row in df.iterrows():
    schedule[row['Hari']][int(row['Jam'])][row['Ruang']].append(cell_info(row))

# Rooms & jams per day
day_rooms = {}
day_jams  = {}
for day in DAY_ORDER:
    day_df = df[df['Hari'] == day]
    if len(day_df) == 0:
        day_rooms[day] = []
        day_jams[day]  = []
        continue
    all_r    = sorted(day_df['Ruang'].unique())
    classes  = sorted([r for r in all_r if not r.startswith('LAB')])
    labs     = sorted([r for r in all_r if r.startswith('LAB')])
    day_rooms[day] = classes + labs
    day_jams[day]  = sorted(day_df['Jam'].unique())

# ═══════════════════════════════════════════════════════
# 5. HTML BUILDER HELPERS
# ═══════════════════════════════════════════════════════
def e(s):
    return html_lib.escape(str(s))

def render_cell(cells):
    if not cells:
        return '<td class="empty"></td>'
    is_conflict = any(c['conflict'] for c in cells)
    parts = []
    for c in cells:
        # jenis info kept for reference only, color driven by viol_type
        badge = '<span class="badge-conflict">&#9888; Konflik</span>' if c['conflict'] else ''
        vt    = c.get('viol_type', 'none')
        vt_cls = 'slot-hard' if vt == 'hard' else ('slot-soft' if vt == 'soft' else 'slot-clean')
        parts.append(
            '<div class="slot-item %s">%s'
            '<div class="slot-kode">%s</div>'
            '<div class="slot-nama">%s</div>'
            '<div class="slot-meta">Dosen: %s</div>'
            '<div class="slot-meta">SKS: %s &nbsp;|&nbsp; Kewajiban: %s</div>'
            '<div class="slot-prodi">%s</div>'
            '</div>' % (vt_cls, badge, e(c['kode']), e(c['nama']),
                        e(c['dosen']), e(c['sks']), e(c['kewajiban']), e(c['prodi']))
        )
    td_cls = 'has-content conflict-cell' if is_conflict else 'has-content'
    return '<td class="%s">%s</td>' % (td_cls, ''.join(parts))

def render_day_table(day):
    rooms = day_rooms[day]
    jams  = day_jams[day]
    if not rooms:
        return '<p style="color:#9ca3af;padding:12px">Tidak ada jadwal hari ini.</p>'
    hdrs = ''.join('<th class="jam-header">%02d:00</th>' % j for j in jams)
    rows = []
    for room in rooms:
        room_cls = 'lab-room' if room.startswith('LAB') else 'class-room'
        cells = ''.join(render_cell(schedule[day][jam][room]) for jam in jams)
        rows.append('<tr><td class="room-label %s">%s</td>%s</tr>' % (room_cls, e(room), cells))
    return (
        '<div class="table-scroll">'
        '<table class="timetable">'
        '<thead><tr><th class="room-header">Ruangan</th>%s</tr></thead>'
        '<tbody>%s</tbody>'
        '</table></div>'
    ) % (hdrs, ''.join(rows))

def render_summary_table():
    types = [
        ('Ruang_Bentrok',       'Hard', '2 kelas di ruang yang sama'),
        ('Dosen_Bentrok',       'Hard', 'Dosen mengajar 2 kelas bersamaan'),
        ('Diluar_Waktu',        'Hard', 'Jadwal di luar jam operasional'),
        ('Lecture_Pakai_Lab',   'Hard', 'Kuliah menggunakan ruang lab'),
        ('Praktikum_Tanpa_Lab', 'Hard', 'Praktikum tidak di lab'),
    ]
    rows = []
    for ptype, tipe, desc in types:
        count = viol_counts.get(ptype, 0)
        cnt_cls = 'count-zero' if count == 0 else 'count-nonzero'
        badge   = '<span class="badge badge-%s">%s</span>' % (tipe.lower(), tipe)
        ok_icon = '&#9989;' if count == 0 else '&#10060;'
        rows.append(
            '<tr><td>%s</td><td><strong>%s</strong></td><td>%s</td>'
            '<td class="count %s">%s %s</td></tr>' % (badge, e(ptype), e(desc), cnt_cls, ok_icon, count)
        )
    # Soft rows
    soft_types = [t for t in viol_counts if any(v['tipe']=='Soft' and v['pelanggaran']==t for v in violations)]
    if soft_types:
        for ptype in soft_types:
            count = viol_counts.get(ptype, 0)
            cnt_cls = 'count-zero' if count == 0 else 'count-soft'
            badge   = '<span class="badge badge-soft">Soft</span>'
            ok_icon = '&#10060;' if count > 0 else '&#9989;'
            rows.append(
                '<tr><td>%s</td><td><strong>%s</strong></td>'
                '<td>Penalti prioritas per sesi MK</td>'
                '<td class="count %s">%s %d</td></tr>' % (badge, e(ptype), cnt_cls, ok_icon, count)
            )
    else:
        rows.append(
            '<tr><td><span class="badge badge-soft">Soft</span></td>'
            '<td><strong>Soft Penalty Score</strong></td>'
            '<td>Total penalti soft constraint (kolom Prioritas tidak tersedia di CSV)</td>'
            '<td class="count count-soft">%d</td></tr>' % LIGHT_TOTAL
        )
    return (
        '<table class="summary-table">'
        '<thead><tr><th>Tipe</th><th>Constraint</th><th>Deskripsi</th><th>Jumlah</th></tr></thead>'
        '<tbody>%s</tbody></table>'
    ) % ''.join(rows)

def render_detail_table():
    if not violations:
        return '<p class="no-viol">&#9989; Tidak ada pelanggaran hard constraint terdeteksi.</p>'
    rows = []
    for v in violations:
        row_cls  = 'viol-row-hard' if v['tipe'] == 'Hard' else 'viol-row-soft'
        badge    = '<span class="badge badge-%s">%s</span>' % (v['tipe'].lower(), v['tipe'])
        rows.append(
            '<tr class="%s">'
            '<td>%s</td><td>%s</td><td>%s</td>'
            '<td>%s&nbsp;%02d:00</td>'
            '<td>%s</td><td>%s</td><td>%s</td>'
            '<td>%s</td><td>%s</td><td>%s</td>'
            '</tr>' % (
                row_cls,
                e(v['kode_mk']), e(v['nama_mk']), e(v['dosen']),
                e(DAY_LABEL[v['hari']]), v['jam'],
                e(v['sks']), e(v['kewajiban']), e(v['jenis']),
                e(v['pelanggaran']), e(v['detail']), badge
            )
        )
    return (
        '<table class="detail-table" id="detail-table">'
        '<thead><tr>'
        '<th>Kode MK</th><th>Nama MK</th><th>Dosen</th>'
        '<th>Waktu</th><th>SKS</th><th>Kewajiban</th>'
        '<th>Jenis Sesi</th><th>Pelanggaran</th><th>Detail</th><th>Tipe</th>'
        '</tr></thead>'
        '<tbody>%s</tbody></table>'
    ) % ''.join(rows)

def render_day_tabs():
    parts = []
    for day in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']:
        active = 'active' if day == 'Mon' else ''
        n_rooms = len(day_rooms[day])
        parts.append(
            '<button class="day-tab %s" onclick="showDay(\'%s\')" id="tab-%s">'
            '%s<span style="font-size:10px;margin-left:6px;opacity:.7">(%d ruang)</span>'
            '</button>' % (active, day, day, DAY_LABEL[day], n_rooms)
        )
    return ''.join(parts)

def render_day_panels():
    parts = []
    for day in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']:
        active = 'active' if day == 'Mon' else ''
        parts.append(
            '<div class="day-panel %s" id="panel-%s">'
            '<h3 class="day-title">%s (%d ruang, %d slot waktu)</h3>'
            '%s'
            '</div>' % (active, day, DAY_LABEL[day],
                        len(day_rooms[day]), len(day_jams[day]),
                        render_day_table(day))
        )
    return ''.join(parts)

# ═══════════════════════════════════════════════════════
# 6. CSS
# ═══════════════════════════════════════════════════════
CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
       background: #f4f6f9; color: #1a1a2e; font-size: 13px; line-height: 1.5; }
h1 { font-size: 22px; font-weight: 600; }
h2 { font-size: 17px; font-weight: 600; margin-bottom: 14px; }
h3 { font-size: 14px; font-weight: 600; }

.page { max-width: 1600px; margin: 0 auto; padding: 20px; }
.section { background: #fff; border-radius: 12px; padding: 24px;
           box-shadow: 0 2px 8px rgba(0,0,0,.08); margin-bottom: 24px; }
.page-header { margin-bottom: 20px; }
.page-header p { color: #6b7280; margin-top: 4px; font-size: 13px; }

/* Cards */
.cards { display: flex; gap: 14px; margin-bottom: 22px; flex-wrap: wrap; }
.card { flex: 1; min-width: 180px; border-radius: 10px; padding: 18px 20px; }
.card-label { font-size: 11px; font-weight: 600; text-transform: uppercase;
              letter-spacing: .06em; opacity: .7; margin-bottom: 6px; }
.card-value { font-size: 30px; font-weight: 700; line-height: 1; }
.card-desc  { font-size: 11px; margin-top: 6px; opacity: .65; }
.card-hard     { background: #fef2f2; color: #991b1b; border: 1.5px solid #fca5a5; }
.card-soft     { background: #fffbeb; color: #92400e; border: 1.5px solid #fcd34d; }
.card-feasible   { background: #f0fdf4; color: #166534; border: 1.5px solid #86efac; }
.card-infeasible { background: #fef2f2; color: #991b1b; border: 1.5px solid #fca5a5; }
.card-slot     { background: #eff6ff; color: #1e40af; border: 1.5px solid #93c5fd; }

/* Summary table */
.summary-table { width: 100%; border-collapse: collapse; margin-bottom: 18px; font-size: 13px; }
.summary-table th { background: #f9fafb; padding: 10px 14px; text-align: left;
                    font-weight: 600; font-size: 12px; border-bottom: 2px solid #e5e7eb; }
.summary-table td { padding: 9px 14px; border-bottom: 1px solid #f3f4f6; }
.summary-table tr:last-child td { border-bottom: none; }
.count { font-weight: 700; font-size: 15px; text-align: right; white-space: nowrap; }
.count-zero    { color: #16a34a; }
.count-nonzero { color: #dc2626; }
.count-soft    { color: #d97706; }

/* Badges */
.badge { display: inline-block; padding: 2px 8px; border-radius: 4px;
         font-size: 11px; font-weight: 600; }
.badge-hard   { background: #fef2f2; color: #dc2626; border: 1px solid #fca5a5; }
.badge-soft   { background: #fffbeb; color: #d97706; border: 1px solid #fde68a; }
.badge-conflict { background: #dc2626; color: #fff; font-size: 10px;
                  padding: 1px 5px; border-radius: 3px; margin-bottom: 3px;
                  display: block; width: fit-content; }

/* Details */
details { margin-top: 16px; }
summary { cursor: pointer; user-select: none; padding: 10px 16px;
          background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px;
          font-weight: 600; font-size: 13px; display: flex; align-items: center; gap: 8px; }
summary::-webkit-details-marker { display: none; }
summary::before { content: "\\25B6"; font-size: 10px; transition: transform .2s; }
details[open] summary::before { transform: rotate(90deg); }
details[open] summary { border-radius: 8px 8px 0 0; border-bottom: none; }
.details-body { border: 1px solid #e5e7eb; border-top: none;
                border-radius: 0 0 8px 8px; overflow-x: auto; }
.filter-bar { padding: 10px 14px; background: #f9fafb;
              display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.filter-bar input, .filter-bar select {
  padding: 6px 10px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 12px; }
.filter-bar input { flex: 1; min-width: 180px; }
.filter-bar input:focus, .filter-bar select:focus { outline: 2px solid #3b82f6; border-color: #3b82f6; }

/* Detail table */
.detail-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.detail-table th { background: #1e3a5f; color: #fff; padding: 9px 12px; text-align: left;
                   font-weight: 600; font-size: 11px; white-space: nowrap; }
.detail-table td { padding: 8px 12px; border-bottom: 1px solid #f3f4f6; vertical-align: top; }
.viol-row-hard td { background: #fff5f5; }
.viol-row-soft td { background: #fffdf0; }
.detail-table tr:hover td { background: #e0f2fe !important; }
.no-viol { color: #16a34a; font-weight: 600; padding: 16px; }

/* Day tabs */
.day-tabs { display: flex; gap: 6px; margin-bottom: 16px; flex-wrap: wrap; }
.day-tab { padding: 8px 18px; border-radius: 8px; border: 1px solid #e5e7eb;
           cursor: pointer; font-weight: 600; font-size: 13px; background: #f9fafb;
           color: #374151; transition: background .15s, color .15s; }
.day-tab:hover  { background: #e5e7eb; }
.day-tab.active { background: #1d4ed8; color: #fff; border-color: #1d4ed8; }
.day-panel { display: none; }
.day-panel.active { display: block; }
.day-title { margin-bottom: 12px; color: #374151; font-size: 15px; }

/* Timetable */
.table-scroll { overflow-x: auto; border-radius: 8px; border: 1px solid #e5e7eb; }
.timetable { border-collapse: collapse; font-size: 11px; }
.timetable th, .timetable td { border: 1px solid #e5e7eb; }
.room-header { background: #1e3a5f; color: #fff; padding: 8px 12px; min-width: 88px;
               white-space: nowrap; font-size: 12px; position: sticky; left: 0; z-index: 3; }
.jam-header  { background: #1e3a5f; color: #fff; padding: 8px 14px; min-width: 135px;
               white-space: nowrap; text-align: center; font-size: 12px; }
.room-label  { background: #f8fafc; font-weight: 600; padding: 6px 10px;
               white-space: nowrap; font-size: 11px; position: sticky; left: 0; z-index: 1;
               border-right: 2px solid #cbd5e1; }
.class-room  { color: #1e40af; }
.lab-room    { color: #065f46; }
.empty       { background: #fafafa; min-width: 135px; height: 26px; }
.has-content { vertical-align: top; padding: 0; min-width: 135px; }
.conflict-cell { outline: 2px solid #dc2626; outline-offset: -2px; position: relative; }

/* Slot items — color by violation type */
.slot-item   { padding: 5px 7px; border-bottom: 1px solid rgba(0,0,0,.05); }
.slot-item:last-child { border-bottom: none; }
.slot-clean  { background: #eff6ff; border-left: 3px solid #3b82f6; }
.slot-hard   { background: #fef2f2; border-left: 3px solid #dc2626; }
.slot-soft   { background: #fffbeb; border-left: 3px solid #d97706; }
.slot-kode { font-weight: 700; font-size: 11px; color: #1e3a5f; }
.slot-nama { font-size: 11px; color: #374151; line-height: 1.3; margin: 2px 0;
             max-width: 155px; word-wrap: break-word; }
.slot-meta  { font-size: 10px; color: #6b7280; }
.slot-prodi { font-size: 10px; color: #9ca3af; font-style: italic; }

/* Legend & search */
.legend { display: flex; gap: 16px; margin-bottom: 14px; flex-wrap: wrap; align-items: center; }
.legend-item { display: flex; align-items: center; gap: 6px; font-size: 12px; }
.legend-box { width: 14px; height: 14px; border-radius: 3px; flex-shrink: 0; }
.search-row { display: flex; gap: 10px; margin-bottom: 12px; align-items: center; flex-wrap: wrap; }
.search-row input { padding: 7px 12px; border: 1px solid #d1d5db; border-radius: 8px;
                    font-size: 12px; width: 220px; }
.search-row label { font-size: 12px; color: #6b7280; display: flex; align-items: center; gap: 4px; }
"""

# ═══════════════════════════════════════════════════════
# 7. JAVASCRIPT
# ═══════════════════════════════════════════════════════
JS = """
function showDay(day) {
  document.querySelectorAll('.day-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.day-tab').forEach(t => t.classList.remove('active'));
  document.getElementById('panel-' + day).classList.add('active');
  document.getElementById('tab-' + day).classList.add('active');
  applyRoomFilter();
}

function filterTable() {
  const q    = document.getElementById('filter-input').value.toLowerCase();
  const tipe = document.getElementById('filter-tipe').value.toLowerCase();
  const pv   = document.getElementById('filter-pv').value.toLowerCase();
  document.querySelectorAll('#detail-table tbody tr').forEach(r => {
    const txt    = r.innerText.toLowerCase();
    const tipeTd = (r.cells[9] || {innerText: ''}).innerText.toLowerCase();
    const pelTd  = (r.cells[7] || {innerText: ''}).innerText.toLowerCase();
    r.style.display = (
      (!q || txt.includes(q)) &&
      (!tipe || tipeTd.includes(tipe)) &&
      (!pv   || pelTd.includes(pv))
    ) ? '' : 'none';
  });
}

function applyRoomFilter() {
  const q     = (document.getElementById('room-search').value || '').toLowerCase();
  const hideE = document.getElementById('hide-empty') &&
                document.getElementById('hide-empty').checked;
  const panel = document.querySelector('.day-panel.active');
  if (!panel) return;
  panel.querySelectorAll('tbody tr').forEach(r => {
    const roomName = (r.cells[0] ? r.cells[0].innerText : '').toLowerCase();
    const hasContent = Array.from(r.cells).slice(1).some(
      c => c.classList.contains('has-content'));
    r.style.display = (
      (!q || roomName.includes(q)) && (!hideE || hasContent)
    ) ? '' : 'none';
  });
}
"""

# ═══════════════════════════════════════════════════════
# 8. RENDER STATUS CARD CLASS
# ═══════════════════════════════════════════════════════
status_class = 'feasible'    if IS_FEASIBLE else 'infeasible'
status_label = 'FEASIBLE &#10003;' if IS_FEASIBLE else 'NOT FEASIBLE &#10007;'
status_desc  = ('Semua hard constraint terpenuhi' if IS_FEASIBLE
                else '%d pelanggaran hard constraint' % HEAVY_TOTAL)

# ═══════════════════════════════════════════════════════
# 9. ASSEMBLE HTML
# ═══════════════════════════════════════════════════════
HTML_PARTS = []
HTML_PARTS.append('<!DOCTYPE html>')
HTML_PARTS.append('<html lang="id">')
HTML_PARTS.append('<head>')
HTML_PARTS.append('<meta charset="UTF-8">')
HTML_PARTS.append('<meta name="viewport" content="width=device-width, initial-scale=1.0">')
HTML_PARTS.append('<title>Visualisasi Jadwal Kuliah</title>')
HTML_PARTS.append('<style>%s</style>' % CSS)
HTML_PARTS.append('</head>')
HTML_PARTS.append('<body>')
HTML_PARTS.append('<div class="page">')

# ── Page header
HTML_PARTS.append('<div class="page-header">')
HTML_PARTS.append('<h1>&#128197; Visualisasi Jadwal Kuliah</h1>')
HTML_PARTS.append('<p>Hasil optimasi Coati Optimization Algorithm (COA) &mdash; %d sesi dijadwalkan dari %d mata kuliah</p>' % (len(df), df['Kode_MK'].nunique()))
HTML_PARTS.append('</div>')

# ── BAGIAN 1
HTML_PARTS.append('<div class="section">')
HTML_PARTS.append('<h2>&#128269; Bagian 1 &mdash; Analisis Pelanggaran Constraint</h2>')

# Cards
HTML_PARTS.append('<div class="cards">')
HTML_PARTS.append(
    '<div class="card card-hard">'
    '<div class="card-label">Hard Penalty</div>'
    '<div class="card-value">%d</div>'
    '<div class="card-desc">Total nilai penalti hard constraint</div>'
    '</div>' % HEAVY_TOTAL
)
HTML_PARTS.append(
    '<div class="card card-soft">'
    '<div class="card-label">Soft Penalty</div>'
    '<div class="card-value">%d</div>'
    '<div class="card-desc">Total nilai penalti soft constraint</div>'
    '</div>' % LIGHT_TOTAL
)
HTML_PARTS.append(
    '<div class="card card-slot">'
    '<div class="card-label">Total Slot Dijadwalkan</div>'
    '<div class="card-value">%d</div>'
    '<div class="card-desc">%d MK &middot; %d sesi unik (hari, jam, ruang)</div>'
    '</div>' % (len(df), df["Kode_MK"].nunique(),
                df.groupby(["Hari","Jam","Ruang"]).ngroups)
)
HTML_PARTS.append(
    '<div class="card card-%s">'
    '<div class="card-label">Status Jadwal</div>'
    '<div class="card-value" style="font-size:18px">%s</div>'
    '<div class="card-desc">%s</div>'
    '</div>' % (status_class, status_label, status_desc)
)
HTML_PARTS.append('</div>')  # .cards

# Summary table
HTML_PARTS.append('<h3 style="margin-bottom:10px">Jumlah Pelanggaran per Jenis Constraint</h3>')
HTML_PARTS.append(render_summary_table())

# Details
HTML_PARTS.append('<details>')
HTML_PARTS.append(
    '<summary>&#128196; Details &mdash; Mata Kuliah Bermasalah'
    '&nbsp;<span class="badge badge-hard">%d hard</span>'
    '&nbsp;<span class="badge badge-soft">%d soft</span>'
    '</summary>' % (hard_detected, soft_detected)
)
HTML_PARTS.append('<div class="details-body">')
HTML_PARTS.append(
    '<div class="filter-bar">'
    '<input type="text" id="filter-input" placeholder="Cari kode MK, nama MK, dosen..." oninput="filterTable()">'
    '<select id="filter-tipe" onchange="filterTable()">'
    '<option value="">Semua Tipe</option>'
    '<option value="Hard">Hard</option>'
    '<option value="Soft">Soft</option>'
    '</select>'
    '<select id="filter-pv" onchange="filterTable()">'
    '<option value="">Semua Pelanggaran</option>'
    '<option value="Ruang_Bentrok">Ruang_Bentrok</option>'
    '<option value="Dosen_Bentrok">Dosen_Bentrok</option>'
    '<option value="Diluar_Waktu">Diluar_Waktu</option>'
    '<option value="Lecture_Pakai_Lab">Lecture_Pakai_Lab</option>'
    '<option value="Praktikum_Tanpa_Lab">Praktikum_Tanpa_Lab</option>'
    '</select>'
    '</div>'
)
HTML_PARTS.append(render_detail_table())
HTML_PARTS.append('</div>')  # .details-body
HTML_PARTS.append('</details>')
HTML_PARTS.append('</div>')  # .section bagian 1

# ── BAGIAN 2
HTML_PARTS.append('<div class="section">')
HTML_PARTS.append('<h2>&#128203; Bagian 2 &mdash; Jadwal Perkuliahan per Hari</h2>')

# Legend
HTML_PARTS.append('<div class="legend">')
HTML_PARTS.append(
    '<div class="legend-item">'
    '<div class="legend-box" style="background:#eff6ff;border-left:3px solid #3b82f6"></div>'
    '<span>Tidak ada pelanggaran</span></div>'
)
HTML_PARTS.append(
    '<div class="legend-item">'
    '<div class="legend-box" style="background:#fef2f2;border-left:3px solid #dc2626"></div>'
    '<span>Pelanggaran Hard</span></div>'
)
HTML_PARTS.append(
    '<div class="legend-item">'
    '<div class="legend-box" style="background:#fffbeb;border-left:3px solid #d97706"></div>'
    '<span>Pelanggaran Soft</span></div>'
)
HTML_PARTS.append('</div>')  # .legend

# Search row
HTML_PARTS.append(
    '<div class="search-row">'
    '<input type="text" id="room-search" placeholder="&#128269; Cari ruangan (mis: F2.5 atau LAB-10)" oninput="applyRoomFilter()">'
    '<label><input type="checkbox" id="hide-empty" onchange="applyRoomFilter()"> Sembunyikan ruangan kosong</label>'
    '</div>'
)

# Tabs
HTML_PARTS.append('<div class="day-tabs">%s</div>' % render_day_tabs())

# Panels
HTML_PARTS.append(render_day_panels())

HTML_PARTS.append('</div>')  # .section bagian 2
HTML_PARTS.append('</div>')  # .page
HTML_PARTS.append('<script>%s</script>' % JS)
HTML_PARTS.append('</body>')
HTML_PARTS.append('</html>')

# ═══════════════════════════════════════════════════════
# 10. TULIS FILE
# ═══════════════════════════════════════════════════════
html_content = '\n'.join(HTML_PARTS)
with open(HTML_PATH, 'w', encoding='utf-8') as f:
    f.write(html_content)

print("=" * 50)
print("  Visualisasi.html berhasil dibuat!")
print("=" * 50)
print("  Total sesi     : %d" % len(df))
print("  Total MK       : %d" % df['Kode_MK'].nunique())
print("  Hard penalty   : %d" % HEAVY_TOTAL)
print("  Soft penalty   : %d" % LIGHT_TOTAL)
print("  Feasible       : %s" % IS_FEASIBLE)
print("  Hard terdeteksi: %d" % hard_detected)
for k, v in sorted(viol_counts.items()):
    print("    %-25s: %d" % (k, v))
print("=" * 50)
