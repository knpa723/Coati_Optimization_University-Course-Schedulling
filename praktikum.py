import pandas as pd

# Load data
df = pd.read_csv('data\data_final.csv')

# kondisi praktikum
praktikum_mask = df["Praktikum"] == 1

# sks praktikum
df["SKS Praktikum"] = 0
df.loc[praktikum_mask & (df["SKS"] < 4), "SKS Praktikum"] = 1
df.loc[praktikum_mask & (df["SKS"] >= 4), "SKS Praktikum"] = 2

# sks teori
df["SKS Teori"] = df["SKS"] - df["SKS Praktikum"]

# jika bukan praktikum
df.loc[~praktikum_mask, "SKS Praktikum"] = 0
df.loc[~praktikum_mask, "SKS Teori"] = df["SKS"]

df
# simpan
df.to_csv("data_final_teoriprak.csv", index=False)