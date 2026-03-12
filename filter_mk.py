import pandas as pd

# =========================
# 1. Load data
# =========================
data1 = pd.read_csv("Data\data_final.csv")  # data semua MK
data_filter = pd.read_csv("Data\Preferensi Mata Kuliah.xlsx - mk_dsi_ganjil.csv")  # data MK semester ganjil

# =========================
# 2. Ambil kode MK dari data_filter
# =========================
kode_mk_filter = data_filter["course_id"].astype(str).unique()

# =========================
# 3. Filter data1
# =========================
data_filtered = data1[data1["Kode MK"].astype(str).isin(kode_mk_filter)]

# =========================
# 4. Simpan ke CSV
# =========================
output_file = "data_mk_semester_ganjil.csv"
data_filtered.to_csv(output_file, index=False)

print("Jumlah data setelah filter:", len(data_filtered))
print("File disimpan di:", output_file)