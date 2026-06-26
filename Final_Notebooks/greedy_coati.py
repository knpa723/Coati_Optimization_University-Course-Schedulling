# %% [markdown]
# ## Imports

# %%
import time
import math
import random
import copy
from collections import defaultdict, Counter
import re
import openpyxl
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from tqdm import trange
from IPython.display import display

# %%
random.seed(42)
np.random.seed(42)

# %% [markdown]
# ## Load Data

# %%
courses_raw = pd.read_csv("D:\Berkas UB\SKRIPSI\COATI\Coati_Optimization_University-Course-Schedulling\data\Ganjil\data_mk_DSI_semester_ganjil.csv")
rooms_df = pd.read_csv("D:\Berkas UB\SKRIPSI\COATI\Coati_Optimization_University-Course-Schedulling\data\Ruang Kuliah.csv")
labs_df = pd.read_excel("D:\Berkas UB\SKRIPSI\COATI\Coati_Optimization_University-Course-Schedulling\data\Laboratorium.xlsx")

courses_raw.columns = [c.strip() for c in courses_raw.columns]
rooms_df.columns = [c.strip() for c in rooms_df.columns]
labs_df.columns = [c.strip() for c in labs_df.columns]

# %%
def to_int_safe(x, default=0):
    if pd.isna(x):
        return default
    try:
        return int(float(x))
    except:
        return default


# %%
courses = {}

for idx, row in courses_raw.iterrows():
    key = f"{row.iloc[0]}__{idx}"

    courses[key] = {
        'kode': str(row.iloc[0]).strip(),
        'nama': str(row.iloc[1]).strip(),
        'prodi': str(row.iloc[2]).strip(),
        'prioritas': to_int_safe(row.iloc[3]),
        'dosen': to_int_safe(row.iloc[5], default=0),
        'sks': to_int_safe(row.iloc[7]),
        'praktikum': to_int_safe(row.iloc[8]),
        'kewajiban': to_int_safe(row.iloc[9])
    }

course_keys = list(courses.keys())

for key in course_keys[:4]:
    print(courses[key])


# %% [markdown]
# # ═══════════════════════════════════════════════════════════════
# # TAHAP 1 — GREEDY DOSEN-MK MATCHING
# # ═══════════════════════════════════════════════════════════════
# Mencocokkan dosen dengan MK SEBELUM penjadwalan waktu/ruang dimulai.
#
# Aturan:
#   1. Dosen yang SUDAH terdaftar valid di data (dosen != 0) SELALU dipertahankan
#      — ini prioritas utama, tidak pernah dioverride.
#   2. MK WAJIB diproses LEBIH DULU, baru MK MINAT — supaya kalau ada
#      keterbatasan dosen, MK wajib yang lebih diutamakan terisi lengkap.
#   3. MK yang TIDAK punya dosen terdaftar (dosen=0) disubstitusi dengan
#      dosen yang SKS-nya PALING RENDAH saat itu (paling butuh tambahan jam).
#   4. SKS dihitung HANYA dari porsi TEORI (praktikum tidak masuk hitungan,
#      karena praktikum diajar asisten, bukan dosen) — konsisten dengan
#      cara make_empty_schedule membagi sesi lecture/practicum.
#   5. Minimum 12 SKS = target HARD (diusahakan terpenuhi semua dosen).
#      Maksimum 16 SKS = FLEKSIBEL (tidak dipaksa, dosen boleh melebihi).
#      Greedy ini TIDAK mereshuffle assignment yang sudah valid hanya
#      demi menyeimbangkan SKS — hanya mengisi slot yang benar-benar kosong.

# %%
def teori_sks_of(course_dict):
    """
    SKS porsi teori suatu MK (yang dihitung sebagai beban dosen).
    Konsisten dengan make_empty_schedule: jika praktikum=1, sesi lecture
    yang dibuat sebanyak (sks-1), sisanya 1 sesi practicum (tanpa dosen).
    """
    sks = course_dict['sks']
    pr  = course_dict['praktikum']
    return max(0, sks - 1) if pr == 1 else sks


def greedy_dosen_matching(courses, course_keys):
    """
    TAHAP 1: Greedy matching dosen-MK.

    Return:
        substitution_log : list of dict, catatan tiap substitusi yang terjadi
        dosen_sks_final  : dict {dosen: total_sks_teori} setelah matching
        dosen_kurang_sks : dict {dosen: total_sks} utk dosen yang masih <12
    """
    substitution_log = []

    # Kumpulkan semua dosen yang PERNAH valid terdaftar di data
    all_known_dosen = set(
        courses[k]['dosen'] for k in course_keys
        if courses[k]['dosen'] not in (0, None)
    )

    dosen_sks = defaultdict(int)

    # ── Urutkan: WAJIB dulu, baru MINAT ──────────────────────────────────
    wajib_keys = [k for k in course_keys if courses[k]['kewajiban'] == 1]
    minat_keys = [k for k in course_keys if courses[k]['kewajiban'] == 0]
    ordered_keys = wajib_keys + minat_keys

    # ── Pass 1: pertahankan dosen yang sudah valid, akumulasi SKS-nya ────
    needs_substitution = []
    for k in ordered_keys:
        c = courses[k]
        if c['dosen'] and c['dosen'] != 0:
            dosen_sks[c['dosen']] += teori_sks_of(c)
        else:
            needs_substitution.append(k)

    # ── Pass 2: substitusi MK yang belum punya dosen ─────────────────────
    # (needs_substitution sudah dalam urutan WAJIB dulu, baru MINAT,
    #  karena diturunkan dari ordered_keys)
    for k in needs_substitution:
        c = courses[k]
        if not all_known_dosen:
            substitution_log.append({
                'kode': c['kode'], 'prodi': c['prodi'], 'kewajiban': c['kewajiban'],
                'dosen_pengganti': None,
                'alasan': 'Tidak ada dosen terdaftar di seluruh data utk disubstitusi'
            })
            continue

        # Pilih dosen dgn SKS PALING RENDAH saat ini (paling butuh)
        substitute = min(all_known_dosen, key=lambda d: dosen_sks[d])
        sks_sebelum = dosen_sks[substitute]

        c['dosen'] = substitute
        dosen_sks[substitute] += teori_sks_of(c)

        tipe = 'WAJIB' if c['kewajiban'] == 1 else 'MINAT'
        substitution_log.append({
            'kode': c['kode'], 'prodi': c['prodi'], 'kewajiban': c['kewajiban'],
            'dosen_pengganti': substitute,
            'alasan': (f"[{tipe}] MK {c['kode']} ({c['prodi']}) tidak punya dosen "
                       f"terdaftar; diisi dosen {substitute} "
                       f"(SKS dosen tsb saat itu: {sks_sebelum})")
        })

    dosen_kurang_sks = {d: s for d, s in dosen_sks.items() if s < 12}
    return substitution_log, dict(dosen_sks), dosen_kurang_sks


# %%
substitution_log, dosen_sks_final, dosen_kurang_sks = greedy_dosen_matching(courses, course_keys)

print(f"=== HASIL TAHAP 1: GREEDY DOSEN-MK MATCHING ===")
print(f"Total substitusi dosen     : {len(substitution_log)}")
print(f"Total dosen terlibat       : {len(dosen_sks_final)}")
if dosen_kurang_sks:
    print(f"⚠ Dosen masih kurang dari 12 SKS teori ({len(dosen_kurang_sks)} dosen):")
    for d, s in sorted(dosen_kurang_sks.items()):
        print(f"    Dosen {d}: {s} SKS teori")
else:
    print("✅ Semua dosen sudah memenuhi minimum 12 SKS teori")

if substitution_log:
    print(f"\nContoh substitusi (maks 5 ditampilkan):")
    for entry in substitution_log[:5]:
        print(f"  - {entry['alasan']}")


# %%
def parse_classroom(kode):
    m = re.match(r'([A-Z])(\d+)\.', kode)
    return {
        'kode_ruang': kode,
        'Gedung': m.group(1),
        'Lantai': int(m.group(2))
    }

class_rooms = [parse_classroom(k) for k in rooms_df.iloc[:,0].astype(str)]
class_rooms[:3]

# %%
lab_rooms = []

for _, row in labs_df.iterrows():
    kode = str(row['Kode Ruang']).strip()
    m = re.match(r'([A-Z])(\d+)\.', kode)
    lab_rooms.append({
        'kode_ruang': kode,
        'Gedung'    : m.group(1) if m else 'G',
        'Lantai'    : int(m.group(2)) if m else 1
    })

lab_room_codes = {r['kode_ruang'] for r in lab_rooms}

lab_rooms[:3]

# %%
room_info = {}
for r in class_rooms:
    room_info[r['kode_ruang']] = {'Gedung': r['Gedung'], 'Lantai': r['Lantai']}
for r in lab_rooms:
    room_info[r['kode_ruang']] = {'Gedung': r['Gedung'], 'Lantai': r['Lantai']}

print(f"Total ruangan terdaftar: {len(room_info)}")


# %% [markdown]
# # ═══════════════════════════════════════════════════════════════
# # TAHAP 2 — COA: PENJADWALAN WAKTU & RUANGAN
# # ═══════════════════════════════════════════════════════════════
# Hasil terbaik dari Tahap 1 (dosen sudah fix per MK) dibawa ke sini.
# Semua fungsi COA di bawah TIDAK DIUBAH dari versi sebelumnya —
# tetap sesuai flowchart paper (Eq. 4-11), hanya parameter run yang berbeda
# (iterasi=100, populasi=40).

# %% [markdown]
# ## Timeslot generation

# %%
DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']

# Batas jam operasional (dalam menit sejak 00:00)
LECTURE_START_MIN  = 7 * 60        # 07:00
LECTURE_END_MIN    = 18 * 60       # 18:00  (sesi terakhir harus SELESAI sebelum ini)
PRACT_START_MIN    = 7 * 60        # 07:00
PRACT_END_MIN      = 18 * 60       # 18:00

SKS_DURATION       = 50            # 1 SKS = 50 menit
SLOT_INTERVAL      = 5             # interval antar slot = 5 menit

# Jam istirahat per hari (dalam menit sejak 00:00)
BREAKS_MIN = {
    'Mon': [(11 * 60, 12 * 60)],
    'Tue': [(11 * 60, 12 * 60)],
    'Wed': [(11 * 60, 12 * 60)],
    'Thu': [(11 * 60, 12 * 60)],
    'Fri': [(11 * 60, 13 * 60)],
}

def is_blocked_by_break(start_min, duration_min, breaks):
    end_min = start_min + duration_min
    for b_start, b_end in breaks:
        if start_min < b_end and end_min > b_start:
            return True
    return False


def generate_slots(start_bound, end_bound, sks_per_sess=1):
    duration = sks_per_sess * SKS_DURATION
    slots = []
    for d in DAYS:
        t = start_bound
        while t + duration <= end_bound:
            if not is_blocked_by_break(t, duration, BREAKS_MIN[d]):
                h = t // 60
                m = t % 60
                slots.append((d, h, m))
            t += SLOT_INTERVAL
    return slots


available_slots_lecture  = generate_slots(LECTURE_START_MIN,  LECTURE_END_MIN)
available_slots_practicum = generate_slots(PRACT_START_MIN, PRACT_END_MIN)

available_slots = list(dict.fromkeys(
    available_slots_lecture + available_slots_practicum
))

SLOT_INDEX = {s: i for i, s in enumerate(available_slots)}

lecture_slot_set  = set(available_slots_lecture)
practicum_slot_set = set(available_slots_practicum)

print(f"Slot lecture  : {len(available_slots_lecture)}")
print(f"Slot praktikum: {len(available_slots_practicum)}")
print(f"Total slot    : {len(available_slots)}")
print(f"Contoh slot   : {available_slots[:5]}")


# %%
def sessions_overlap(slot_a, slot_b, dur_a=SKS_DURATION, dur_b=SKS_DURATION):
    day_a, h_a, m_a = slot_a
    day_b, h_b, m_b = slot_b
    if day_a != day_b:
        return False
    start_a = h_a * 60 + m_a
    start_b = h_b * 60 + m_b
    return start_a < start_b + dur_b and start_b < start_a + dur_a

# %% [markdown]
# # Prefensi Waktu Mengajar

# %%
USE_PREFERENCE = False

DAY_MAP = {
    'Senin': 'Mon',  'Mon': 'Mon',
    'Selasa': 'Tue', 'Tue': 'Tue',
    'Rabu': 'Wed',   'Wed': 'Wed',
    'Kamis': 'Thu',  'Thu': 'Thu',
    'Jumat': 'Fri',  'Fri': 'Fri'
}

pref_df = pd.read_csv("..\data\Preferensi_Mengajar.csv")
pref_df.columns = [c.strip() for c in pref_df.columns]

pref_map = defaultdict(set)

for _, r in pref_df.iterrows():
    dosen = int(r['dosen'])
    hari = DAY_MAP[r['hari']]
    jam  = int(r['jam'])

    pref_map[dosen].add((hari, jam))

# %% [markdown]
# ## Struktur Session

# %%
def make_empty_schedule():
    sched = {}
    for k in course_keys:
        sks = courses[k]['sks']
        pr  = courses[k]['praktikum']
        sessions = []

        if pr == 1:
            lecture_count = max(0, sks - 1)
            for _ in range(lecture_count):
                sessions.append({'type':'lecture','slot':None,'room':None})
            sessions.append({'type':'practicum','slot':None,'room':None})
        else:
            for _ in range(sks):
                sessions.append({'type':'lecture','slot':None,'room':None})

        sched[k] = sessions
    return sched

# %% [markdown]
# # Kandidat Ruangan

# %%
room_candidates_per_course = {}

for k in course_keys:
    room_candidates_per_course[k] = {
        'lecture': [r['kode_ruang'] for r in class_rooms],
        'practicum': [r['kode_ruang'] for r in lab_rooms]
    }


# %% [markdown]
# # RANDOM & REPAIR

# %%
def random_schedule():
    sched = make_empty_schedule()

    for k, sessions in sched.items():
        for sess in sessions:
            if sess['type'] == 'lecture':
                valid_indices = [SLOT_INDEX[sl] for sl in available_slots_lecture]
            else:
                valid_indices = [SLOT_INDEX[sl] for sl in available_slots_practicum]

            sess['slot'] = random.choice(valid_indices)

            rlist = room_candidates_per_course[k][sess['type']]
            sess['room'] = random.choice(rlist) if rlist else None

    return sched

# %%
def repair_schedule(schedule):
    """
    Resolusi konflik berbasis OVERLAP WAKTU (pakai sessions_overlap),
    bukan exact slot-index match.
    """
    room_used  = defaultdict(list)
    dosen_used = defaultdict(list)

    for k, sessions in schedule.items():
        mk = courses[k]
        dosen = mk['dosen']

        for s in sessions:
            sess_type = s['type']
            if sess_type == 'lecture':
                valid_indices = [SLOT_INDEX[sl] for sl in available_slots_lecture]
            else:
                valid_indices = [SLOT_INDEX[sl] for sl in available_slots_practicum]

            if s['slot'] is None or s['slot'] not in valid_indices:
                s['slot'] = random.choice(valid_indices)
            if s['room'] is None:
                rlist = room_candidates_per_course[k][sess_type]
                s['room'] = random.choice(rlist)

            for _ in range(30):
                curr_tuple = available_slots[s['slot']]

                room_conflict = any(
                    sessions_overlap(curr_tuple, rs) for rs in room_used[s['room']]
                )
                dosen_conflict = (
                    dosen is not None and
                    any(sessions_overlap(curr_tuple, ds) for ds in dosen_used[dosen])
                )

                if not room_conflict and not dosen_conflict:
                    break
                s['slot'] = random.choice(valid_indices)

            final_tuple = available_slots[s['slot']]
            room_used[s['room']].append(final_tuple)
            if dosen is not None:
                dosen_used[dosen].append(final_tuple)

    return schedule

# %%
def random_neighbor(schedule):
    new = copy.deepcopy(schedule)
    k = random.choice(course_keys)
    if not new[k]:
        return new
    i = random.randrange(len(new[k]))

    sess_type = new[k][i]['type']
    if sess_type == 'lecture':
        valid_indices = [SLOT_INDEX[sl] for sl in available_slots_lecture]
    else:
        valid_indices = [SLOT_INDEX[sl] for sl in available_slots_practicum]

    if random.random() < 0.5:
        new[k][i]['slot'] = random.choice(valid_indices)
    else:
        rlist = room_candidates_per_course[k][sess_type]
        new[k][i]['room'] = random.choice(rlist)

    return new


# %% [markdown]
# ## Fitness evaluation with heavy & light penalties

# %%
def evaluate_schedule_detailed(schedule):
    heavy = defaultdict(int)
    light = defaultdict(int)

    room_sessions  = defaultdict(list)
    dosen_sessions = defaultdict(list)
    dosen_sks      = defaultdict(int)
    dosen_day_sess = defaultdict(list)

    for k, sessions in schedule.items():
        mk = courses[k]

        if len(sessions) != mk['sks']:
            heavy['SKS_Tidak_Terpenuhi'] += 1

        if mk['dosen'] is not None:
            lecture_count = sum(1 for s in sessions if s['type'] == 'lecture')
            dosen_sks[mk['dosen']] += lecture_count

        for sess in sessions:
            if sess['slot'] is None or sess['room'] is None:
                heavy['Tidak_Ada_Ruang'] += 1
                continue

            slot = available_slots[sess['slot']]
            day, hour, minute = slot

            if sess['type'] == 'lecture' and slot not in lecture_slot_set:
                heavy['Diluar_Waktu'] += 1
            if sess['type'] == 'practicum' and slot not in practicum_slot_set:
                heavy['Diluar_Waktu'] += 1

            if sess['type'] == 'lecture'   and sess['room'] in lab_room_codes:
                heavy['Lecture_Pakai_Lab'] += 1
            if sess['type'] == 'practicum' and sess['room'] not in lab_room_codes:
                heavy['Praktikum_Tanpa_Lab'] += 1

            room_sessions[sess['room']].append((slot, k))

            if mk['dosen'] is not None:
                dosen_sessions[mk['dosen']].append((slot, k))

                if sess['type'] == 'lecture':
                    start_min = hour * 60 + minute
                    dosen_day_sess[(mk['dosen'], day)].append((start_min, sess['room']))

    for room, sess_list in room_sessions.items():
        for idx_a in range(len(sess_list)):
            for idx_b in range(idx_a + 1, len(sess_list)):
                slot_a, _ = sess_list[idx_a]
                slot_b, _ = sess_list[idx_b]
                if sessions_overlap(slot_a, slot_b):
                    heavy['Ruang_Bentrok'] += 1

    for dosen, sess_list in dosen_sessions.items():
        for idx_a in range(len(sess_list)):
            for idx_b in range(idx_a + 1, len(sess_list)):
                slot_a, _ = sess_list[idx_a]
                slot_b, _ = sess_list[idx_b]
                if sessions_overlap(slot_a, slot_b):
                    heavy['Dosen_Bentrok'] += 1

    # Hard#3: SKS dosen min 12 (hard) — sebagian besar SUDAH ditangani di
    # Tahap 1 (greedy_dosen_matching), ini hanya double-check & tangkap
    # sisa kasus akibat penjadwalan (mis. jika ada sesi yg gagal terjadwal).
    for dosen, total_sks in dosen_sks.items():
        if total_sks < 12:
            heavy['Dosen_SKS_Diluar_Range'] += (12 - total_sks)
        elif total_sks > 16:
            heavy['Dosen_SKS_Diluar_Range'] += (total_sks - 16)

    for k, sessions in schedule.items():
        mk = courses[k]
        light['Prioritas Mata Kuliah'] += mk['prioritas']

        for sess in sessions:
            if sess['slot'] is None:
                continue
            slot = available_slots[sess['slot']]
            day, hour, _ = slot

            if USE_PREFERENCE:
                if mk['dosen'] is not None:
                    if (day, hour) not in pref_map.get(mk['dosen'], set()):
                        light['Preferensi waktu'] += 1

    for (dosen, day), sess_list in dosen_day_sess.items():
        sess_list.sort(key=lambda x: x[0])
        for idx in range(len(sess_list) - 1):
            room_a = sess_list[idx][1]
            room_b = sess_list[idx + 1][1]
            info_a = room_info.get(room_a, {})
            info_b = room_info.get(room_b, {})
            if info_a.get('Gedung') != info_b.get('Gedung') or info_a.get('Lantai') != info_b.get('Lantai'):
                light['Perpindahan_Gedung_Lantai'] += 1

    total_heavy = sum(heavy.values())
    total_light = sum(light.values())

    return {
        'heavy_total'  : total_heavy,
        'light_total'  : total_light,
        'heavy_detail' : dict(heavy),
        'light_detail' : dict(light),
        'is_feasible'  : total_heavy == 0
    }

# %% [markdown]
# # Fitness Score

# %%
def fitness_score(schedule):
    ev = evaluate_schedule_detailed(schedule)
    total_penalty = (ev['heavy_total'] * 1000) + ev['light_total']
    fitness = 1.0 / (1.0 + total_penalty)

    ev['fitness'] = fitness
    return ev

# %%
def select_best_feasible(results):
    return max(results, key=lambda r: r['eval']['fitness'])


# %%
def init_history():
    return {
        'fitness': [],
        'heavy_total': [],
        'light_detail': defaultdict(list)
    }


# %% [markdown]
# ## get_valid_indices

# %%
def get_valid_indices(sess_type):
    """Return list index slot yang valid sesuai tipe sesi (lecture/practicum)."""
    if sess_type == 'lecture':
        return [SLOT_INDEX[sl] for sl in available_slots_lecture]
    else:
        return [SLOT_INDEX[sl] for sl in available_slots_practicum]

# %% [markdown]
# ## COA implementation
# TIDAK DIUBAH dari versi sebelumnya — tetap sesuai flowchart paper.

# %%
def coati_explore_best(curr, best):
    """
    Analog Eq. (4): X_new = X + rand * (iguana - I * X)
    iguana = Xbest, I = round(1 + rand) ∈ {1, 2}
    """
    new = copy.deepcopy(curr)
    k = random.choice(course_keys)
    if not new[k]:
        return new
    i = random.randrange(len(new[k]))

    sess_type     = new[k][i]['type']
    valid_indices = get_valid_indices(sess_type)
    I = random.randint(1, 2)

    if I == 1:
        new[k][i]['slot'] = best[k][i]['slot']
        new[k][i]['room'] = best[k][i]['room']
    else:
        new[k][i]['slot'] = random.choice(valid_indices)
        rlist = room_candidates_per_course[k][sess_type]
        if rlist:
            new[k][i]['room'] = random.choice(rlist)

    return new

# %%
def coati_explore_random(curr):
    """
    Analog Eq. (5-6): iguana = posisi random, bandingkan fitness lalu gerak.
    """
    new = copy.deepcopy(curr)
    k = random.choice(course_keys)
    if not new[k]:
        return new
    i = random.randrange(len(new[k]))

    sess_type     = new[k][i]['type']
    valid_indices = get_valid_indices(sess_type)
    rlist         = room_candidates_per_course[k][sess_type]

    iguana_slot = random.choice(valid_indices)
    iguana_room = random.choice(rlist) if rlist else new[k][i]['room']

    iguana_sched = copy.deepcopy(new)
    iguana_sched[k][i]['slot'] = iguana_slot
    iguana_sched[k][i]['room'] = iguana_room

    fit_curr   = fitness_score(new)['fitness']
    fit_iguana = fitness_score(iguana_sched)['fitness']
    I = random.randint(1, 2)

    if fit_curr > fit_iguana:
        if I == 1:
            new[k][i]['slot'] = iguana_slot
            new[k][i]['room'] = iguana_room
        else:
            new[k][i]['slot'] = random.choice(valid_indices)
            if rlist:
                new[k][i]['room'] = random.choice(rlist)
    else:
        new[k][i]['slot'] = random.choice(valid_indices)
        if rlist:
            new[k][i]['room'] = random.choice(rlist)

    return new

# %%
def coati_exploit_local(curr, max_perturb):
    """
    Analog Eq. (8-10): area pencarian menyempit seiring iterasi.
    """
    new = copy.deepcopy(curr)
    k = random.choice(course_keys)
    if not new[k]:
        return new
    i = random.randrange(len(new[k]))

    sess_type     = new[k][i]['type']
    valid_indices = get_valid_indices(sess_type)
    n_slots       = len(valid_indices)

    curr_slot = new[k][i]['slot']
    pos = valid_indices.index(curr_slot) if curr_slot in valid_indices else random.randrange(n_slots)

    lo_local = max(0, pos - max_perturb)
    hi_local = min(n_slots - 1, pos + max_perturb)

    new[k][i]['slot'] = valid_indices[random.randint(lo_local, hi_local)]

    return new

# %%
def coati_optimization(iterations=1000, pop_size=40,
                        checkpoint_every=25,
                        checkpoint_path="checkpoint_coa.csv",
                        patience=None):
    """
    Alur utama COA (TIDAK DIUBAH dari versi sebelumnya):
    1. Inisialisasi populasi & tentukan Xbest SEBELUM loop
    2. Per iterasi:
       a. Update Xbest
       b. Fase 1 Kelompok 1 (i = 0 .. N/2-1)  → explore ke Xbest
       c. Fase 1 Kelompok 2 (i = N/2 .. N-1)  → explore ke iguana random
       d. Hitung local bound SEKALI
       e. Fase 2 semua individu                → exploit lokal (area menyempit)
       f. Save best candidate solution found so far
       g. Checkpoint periodik
       h. Early stopping opsional
    """
    population = [repair_schedule(random_schedule()) for _ in range(pop_size)]
    evals = [fitness_score(p) for p in population]

    idx0 = int(np.argmax([e['fitness'] for e in evals]))
    best = copy.deepcopy(population[idx0])
    best_eval = evals[idx0]

    history = init_history()
    half = pop_size // 2
    start = time.time()

    checkpoint_log    = []
    no_improve_count  = 0
    last_best_fitness = best_eval['fitness']

    with open(checkpoint_path, 'w') as f:
        f.write("Iterasi,Fitness,Heavy_Total,Light_Total,Feasible,Runtime_s\n")

    for t in trange(1, iterations + 1, desc="COA"):

        idx = int(np.argmax([e['fitness'] for e in evals]))
        if evals[idx]['fitness'] > best_eval['fitness']:
            best = copy.deepcopy(population[idx])
            best_eval = evals[idx]

        for i in range(half):
            cand = coati_explore_best(population[i], best)
            cand = repair_schedule(cand)
            ev = fitness_score(cand)
            if ev['fitness'] > evals[i]['fitness']:
                population[i] = cand
                evals[i] = ev

        for i in range(half, pop_size):
            cand = coati_explore_random(population[i])
            cand = repair_schedule(cand)
            ev = fitness_score(cand)
            if ev['fitness'] > evals[i]['fitness']:
                population[i] = cand
                evals[i] = ev

        max_perturb = max(1, int(len(available_slots) / t))

        for i in range(pop_size):
            cand = coati_exploit_local(population[i], max_perturb)
            cand = repair_schedule(cand)
            ev = fitness_score(cand)
            if ev['fitness'] > evals[i]['fitness']:
                population[i] = cand
                evals[i] = ev

        idx = int(np.argmax([e['fitness'] for e in evals]))
        if evals[idx]['fitness'] > best_eval['fitness']:
            best = copy.deepcopy(population[idx])
            best_eval = evals[idx]

        history['fitness'].append(best_eval['fitness'])
        history['heavy_total'].append(best_eval['heavy_total'])
        for k, v in best_eval['light_detail'].items():
            history['light_detail'][k].append(v)

        if t % checkpoint_every == 0 or t == iterations:
            row = {
                'Iterasi'    : t,
                'Fitness'    : best_eval['fitness'],
                'Heavy_Total': best_eval['heavy_total'],
                'Light_Total': best_eval['light_total'],
                'Feasible'   : best_eval['is_feasible'],
                'Runtime_s'  : round(time.time() - start, 2)
            }
            checkpoint_log.append(row)
            with open(checkpoint_path, 'a') as f:
                f.write(f"{row['Iterasi']},{row['Fitness']:.8f},"
                        f"{row['Heavy_Total']},{row['Light_Total']},"
                        f"{row['Feasible']},{row['Runtime_s']}\n")

        if patience is not None:
            if best_eval['fitness'] > last_best_fitness:
                last_best_fitness = best_eval['fitness']
                no_improve_count  = 0
            else:
                no_improve_count += 1
            if no_improve_count >= patience:
                print(f"\n⏹ Early stop di iterasi {t} "
                      f"(tidak ada improvement selama {patience} iterasi)")
                break

    return best, best_eval, {
        'history'        : history,
        'runtime_s'      : time.time() - start,
        'checkpoint_log' : checkpoint_log
    }


# %% [markdown]
# ## Run experiments
# Tahap 2 dijalankan dengan iterasi=100, populasi=40 (sesuai permintaan).
# Dosen sudah FIX dari Tahap 1 — COA hanya mengoptimasi slot & ruang.

# %%
USE_PREFERENCE = False
N_ITER  = 1000     # ← Tahap 2: iterasi COA
POP_COA = 40       # ← Tahap 2: populasi COA

random.seed(42)
np.random.seed(42)


results = []

best, best_eval, meta = coati_optimization(
    iterations=N_ITER,
    pop_size=POP_COA
)

results.append({
    'name': 'COA',
    'schedule': best,
    'eval': best_eval,
    'history': meta['history'],
    'runtime': meta['runtime_s']
})


print("=== EXPERIMENT FINISHED ===")
for r in results:
    print(f"{r['name']:>4} | runtime={r['runtime']:.2f}s | fitness={r['eval']['fitness']:.6f}")


# %% [markdown]
# ## Comparative evaluation & visualizations

# %%
rows = []

for r in results:
    rows.append({
        'Algorithm': r['name'],
        'Best Fitness': r['eval']['fitness'],
        'Heavy Penalty': r['eval']['heavy_total'],
        'Light Penalty': r['eval']['light_total'],
        'Feasible': r['eval']['is_feasible'],
        'Runtime (sec)': round(r['runtime'], 2)
    })

df_compare = pd.DataFrame(rows)
df_compare = df_compare.sort_values(
    by=['Feasible', 'Best Fitness'],
    ascending=[False, False]
)

display(df_compare)


# %%
plt.figure(figsize=(10,6))

for r in results:
    if r['history']['fitness']:
        plt.plot(
            range(1, len(r['history']['fitness'])+1),
            r['history']['fitness'],
            label=r['name'],
            marker='o'
        )

plt.xlabel("Iteration")
plt.ylabel("Fitness Score")
plt.title("Fitness Convergence Comparison")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()


# %% [markdown]
# ## Save summary and representative schedule CSVs

# %%
def save_all_results_to_single_txt(results, filename):
    with open(filename, 'w') as f:
        f.write("=== SUMMARY REPORT - OPTIMIZATION RESULTS ===\n")
        f.write(f"Total Algorithms Tested: {len(results)}\n")
        f.write("=" * 45 + "\n\n")

        for i, result in enumerate(results):
            f.write(f"--- RESULT #{i+1}: {result['name']} ---\n")
            f.write(f"Best Fitness : {result['eval']['fitness']:.6f}\n")
            f.write(f"Runtime      : {result['runtime']:.2f} sec\n")
            f.write(f"Status       : {'FEASIBLE' if result['eval']['is_feasible'] else 'NOT FEASIBLE'}\n")
            f.write(f"Heavy Penalty: {result['eval']['heavy_total']}\n")
            f.write(f"Light Penalty: {result['eval']['light_total']}\n\n")

            f.write("=== HEAVY DETAIL ===\n")
            if result['eval']['heavy_detail']:
                for k, v in result['eval']['heavy_detail'].items():
                    f.write(f"  - {k}: {v}\n")
            else:
                f.write("  No heavy penalties.\n")

            f.write("\n=== LIGHT DETAIL ===\n")
            if result['eval']['light_detail']:
                for k, v in result['eval']['light_detail'].items():
                    f.write(f"  - {k}: {v}\n")
            else:
                f.write("  No light penalties.\n")

            f.write("\n" + "=" * 45 + "\n\n")

filename = "all_reports_Gabungan.txt"
save_all_results_to_single_txt(results, filename)
print(f"Laporan lengkap dengan Fitness Score berhasil disimpan ke {filename}")

# %% [markdown]
# ## Laporan Tahap 1 (Substitusi Dosen) — terpisah dari laporan Tahap 2

# %%
def save_stage1_report(filename="laporan_tahap1_dosen_matching.txt"):
    with open(filename, 'w') as f:
        f.write("=== LAPORAN TAHAP 1: GREEDY DOSEN-MK MATCHING ===\n")
        f.write("=" * 50 + "\n\n")

        f.write(f"--- SUBSTITUSI DOSEN ({len(substitution_log)} MK) ---\n")
        if substitution_log:
            for entry in substitution_log:
                f.write(f"\n  {entry['alasan']}\n")
        else:
            f.write("  Tidak ada substitusi dosen.\n")

        f.write(f"\n\n--- SKS TEORI FINAL PER DOSEN ---\n")
        for d, s in sorted(dosen_sks_final.items()):
            status = "KURANG" if s < 12 else ("LEBIH" if s > 16 else "OK")
            f.write(f"  Dosen {d}: {s} SKS teori [{status}]\n")

    print(f"Laporan Tahap 1 tersimpan ke {filename}")

save_stage1_report()

# %%
rows = []

for r in results:
    sched = r['schedule']
    for k, sessions in sched.items():
        for sess in sessions:
            day, hour, minute = available_slots[sess['slot']]
            start_min = hour * 60 + minute
            end_min   = start_min + SKS_DURATION
            rows.append({
                'Algorithm'   : r['name'],
                'Hari'        : day,
                'Jam'         : hour,
                'Menit'       : minute,
                'Durasi_Menit': SKS_DURATION,
                'Jam_Mulai'   : f"{hour:02d}:{minute:02d}",
                'Jam_Selesai' : f"{end_min // 60:02d}:{end_min % 60:02d}",
                'Prodi'       : courses[k]['prodi'],
                'Kode_MK'     : courses[k]['kode'],
                'Nama_MK'     : courses[k]['nama'],
                'Jenis'       : sess['type'],
                'Ruang'       : sess['room'],
                'Dosen'       : courses[k]['dosen'],
                'SKS'         : courses[k]['sks'],
                'Kewajiban'   : courses[k]['kewajiban'],
                'Prioritas'   : courses[k]['prioritas'],
                'Fitness'     : r['eval']['fitness'],
                'Heavy_Total' : r['eval']['heavy_total'],
                'Light_Total' : r['eval']['light_total'],
                'Feasible'    : r['eval']['is_feasible']
            })

df_schedule_all = pd.DataFrame(rows)
df_schedule_all.to_csv("D:\Berkas UB\SKRIPSI\COATI\Coati_Optimization_University-Course-Schedulling\FIX_EXPERIMENT\Gabungan_Schedules.csv", index=False)
print("Kolom CSV:", df_schedule_all.columns.tolist())

# %% [markdown]
# # UJI NORMALITAS (SHAPIRO–WILK)

# %%
from scipy.stats import shapiro

fitness_values = [r['eval']['light_total'] for r in results]

if len(fitness_values) < 3:
    print("Data tidak cukup untuk uji normalitas (minimal 3 sampel)")
else:
    stat, p = shapiro(fitness_values)
    print(f"Shapiro-Wilk: stat={stat:.4f}, p={p:.4f}")
    print("Normal" if p > 0.05 else "Tidak normal")