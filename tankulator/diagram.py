import re
import pandas as pd
import matplotlib.pyplot as plt

LOG_FILE = "experiment_results.log"

runs = {}
current_volume = None

with open(LOG_FILE, "r", encoding="utf-8") as f:
    for line in f:

        if "CSP_GENERATION" in line:
            volume = int(re.search(r"VOLUME=(\d+)", line).group(1))
            generated = int(re.search(r"GENERATED=(\d+)", line).group(1))

            current_volume = volume

            runs.setdefault(volume, {})
            runs[volume]["volume"] = volume
            runs[volume]["generated"] = generated

        elif "CSP_HEURISTIC" in line:
            selected = int(re.search(r"SELECTED=(\d+)", line).group(1))

            if current_volume is not None:
                runs.setdefault(current_volume, {})
                runs[current_volume]["selected"] = selected

        elif "CSP_SOLVE" in line:
            volume = int(re.search(r"VOLUME=(\d+)", line).group(1))
            csp_time = float(re.search(r"TIME=([\d.]+)", line).group(1))
            solutions = int(re.search(r"SOLUTIONS=(\d+)", line).group(1))

            runs.setdefault(volume, {})
            runs[volume]["volume"] = volume
            runs[volume]["csp_time"] = csp_time
            runs[volume]["solutions"] = solutions

        elif "TOTAL_RUN" in line:
            volume = int(re.search(r"VOLUME=(\d+)", line).group(1))
            candidates = int(re.search(r"CANDIDATES=(\d+)", line).group(1))
            total_time = float(re.search(r"TIME=([\d.]+)", line).group(1))

            runs.setdefault(volume, {})
            runs[volume]["volume"] = volume
            runs[volume]["candidates"] = candidates
            runs[volume]["total_time"] = total_time

# =====================================================
# DATAFRAME
# =====================================================

df = pd.DataFrame(
    sorted(runs.values(), key=lambda x: x["volume"])
)

required_columns = [
    "generated",
    "selected",
    "candidates",
    "csp_time",
    "solutions",
    "total_time"
]

for col in required_columns:
    if col not in df.columns:
        df[col] = 0

df["reduction_percent"] = (
    (1 - df["selected"] / df["generated"]) * 100
)

df["reduction_percent"] = (
    df["reduction_percent"]
    .replace([float("inf"), -float("inf")], 0)
    .fillna(0)
)

print(df)

df.to_csv("experiment_summary.csv", index=False)

# =====================================================
# WYKRES 1
# Kandydaci po preprocessingu
# =====================================================

plt.figure(figsize=(8, 5))
plt.plot(df["volume"], df["candidates"], marker="o")
plt.title("Liczba kandydatów po preprocessingu")
plt.xlabel("Objętość akwarium [L]")
plt.ylabel("Liczba kandydatów")
plt.grid(True)
plt.tight_layout()
plt.savefig("wykres_kandydaci.png", dpi=300)
plt.close()

# =====================================================
# WYKRES 2
# Wygenerowane kombinacje
# =====================================================

plt.figure(figsize=(8, 5))
plt.plot(df["volume"], df["generated"], marker="o")
plt.title("Liczba wygenerowanych kombinacji")
plt.xlabel("Objętość akwarium [L]")
plt.ylabel("Liczba kombinacji")
plt.grid(True)
plt.tight_layout()
plt.savefig("wykres_kombinacje.png", dpi=300)
plt.close()

# =====================================================
# WYKRES 3
# Czas CSP
# =====================================================

plt.figure(figsize=(8, 5))
plt.plot(df["volume"], df["csp_time"], marker="o")
plt.title("Czas działania modułu CSP")
plt.xlabel("Objętość akwarium [L]")
plt.ylabel("Czas [s]")
plt.grid(True)
plt.tight_layout()
plt.savefig("wykres_csp.png", dpi=300)
plt.close()

# =====================================================
# WYKRES 4
# Czas całkowity
# =====================================================

plt.figure(figsize=(8, 5))
plt.plot(df["volume"], df["total_time"], marker="o")
plt.title("Całkowity czas generowania rekomendacji")
plt.xlabel("Objętość akwarium [L]")
plt.ylabel("Czas [s]")
plt.grid(True)
plt.tight_layout()
plt.savefig("wykres_total.png", dpi=300)
plt.close()

# =====================================================
# WYKRES 5
# Skuteczność heurystyki
# =====================================================

plt.figure(figsize=(8, 5))

bars = plt.bar(
    df["volume"],
    df["reduction_percent"]
)

plt.title("Redukcja przestrzeni przeszukiwania przez heurystykę")
plt.xlabel("Objętość akwarium [L]")
plt.ylabel("Redukcja [%]")
plt.ylim(0, 100)
plt.grid(True, axis="y")

for bar in bars:
    height = bar.get_height()

    plt.text(
        bar.get_x() + bar.get_width() / 2,
        height + 1,
        f"{height:.1f}%",
        ha="center"
    )

plt.tight_layout()
plt.savefig("wykres_heurystyka.png", dpi=300)
plt.close()

# =====================================================
# WYKRES 6
# Liczba rozwiązań
# =====================================================

plt.figure(figsize=(8, 5))
plt.plot(df["volume"], df["solutions"], marker="o")
plt.title("Liczba znalezionych rozwiązań")
plt.xlabel("Objętość akwarium [L]")
plt.ylabel("Liczba rozwiązań")
plt.grid(True)
plt.tight_layout()
plt.savefig("wykres_rozwiazania.png", dpi=300)
plt.close()

print("\nWygenerowano:")
print(" - experiment_summary.csv")
print(" - wykres_kandydaci.png")
print(" - wykres_kombinacje.png")
print(" - wykres_csp.png")
print(" - wykres_total.png")
print(" - wykres_heurystyka.png")
print(" - wykres_rozwiazania.png")