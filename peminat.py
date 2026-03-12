import pandas as pd
import numpy as np

# Load data
df = pd.read_csv('data_final_teoriprak.csv')

# Seed untuk reproducibility (opsional, hapus jika ingin benar-benar random setiap run)
rng = np.random.default_rng(seed=42)

# Buat mapping jumlah peminat per kombinasi (Kode MK, Prodi MK)
# Agar setiap baris dengan Kode MK + Prodi yang sama punya nilai yang sama
mk_prodi_pairs = df[['Kode MK', 'Prodi MK', 'Kewajiban']].drop_duplicates(subset=['Kode MK', 'Prodi MK'])

def generate_peminat(kewajiban):
    if kewajiban == 1:
        return 200
    else:
        # Pilih random dari kelipatan 40: [40, 80, 120, 160]
        # (tidak termasuk 200 karena itu khusus wajib)
        choices = [40, 80, 120, 160]
        return int(rng.choice(choices))

mk_prodi_pairs['Jumlah Peminat'] = mk_prodi_pairs['Kewajiban'].apply(generate_peminat)

# Merge kembali ke dataframe utama berdasarkan Kode MK + Prodi MK
df = df.merge(
    mk_prodi_pairs[['Kode MK', 'Prodi MK', 'Jumlah Peminat']],
    on=['Kode MK', 'Prodi MK'],
    how='left'
)

# Simpan ke file baru
df.to_csv('data_final_with_peminat.csv', index=False)

print("Selesai! Kolom 'Jumlah Peminat' berhasil ditambahkan.")
print(f"Total baris: {len(df)}")
print("\nContoh hasil (10 baris pertama):")
print(df[['Kode MK', 'Prodi MK', 'Kewajiban', 'Jumlah Peminat']].head(10).to_string(index=False))

print("\nDistribusi Jumlah Peminat:")
print(df.drop_duplicates(subset=['Kode MK', 'Prodi MK'])['Jumlah Peminat'].value_counts().sort_index())