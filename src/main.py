import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
from scipy import stats
import warnings
import os

warnings.filterwarnings('ignore')

plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams['figure.figsize'] = [12, 6]
plt.rcParams['font.size'] = 12

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

csv_files = {
    '1': os.path.join(DATA_DIR, 'van_earthquake.csv'),
    '2': os.path.join(DATA_DIR, 'aegean_earthquake.csv'),
    '3': os.path.join(DATA_DIR, 'kahramanmaras_earthquake.csv'),
    '4': os.path.join(DATA_DIR, 'golcuk_earthquake.csv'),
    '5': os.path.join(DATA_DIR, 'tohoku_earthquake.csv')
}

print("Available CSV files:")
for key, value in csv_files.items():
    print(f"{key}. {os.path.basename(value)}")

selected = input("Select one of the source files above (1-5): ").strip()

if selected not in csv_files:
    print("Invalid selection! Using 'van_earthquake.csv' as default.")
    selected = '1'

selected_file = csv_files[selected]

if not os.path.exists(selected_file):
    print(f"Error: '{selected_file}' file not found!")
    exit()

print(f"Selected file: {os.path.basename(selected_file)}")

try:
    df = pd.read_csv(selected_file, encoding='utf-8', low_memory=False)
except UnicodeDecodeError:
    try:
        df = pd.read_csv(selected_file, encoding='latin-1', low_memory=False)
    except Exception as e:
        print(f"CSV reading error: {e}")
        exit()
except Exception as e:
    print(f"Unexpected error: {e}")
    exit()

df.columns = df.columns.str.lower().str.replace(' ', '_')

df['time_datetime'] = pd.to_datetime(df['time'], errors='coerce', utc=True)
df['magnitude'] = pd.to_numeric(df['mag'], errors='coerce')
df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')

valid_df = df[df['time_datetime'].notnull() & df['magnitude'].notnull()].copy()

main_shock_idx = valid_df['magnitude'].idxmax()
main_shock = valid_df.loc[main_shock_idx]
main_shock_time = main_shock['time_datetime']
main_shock_mag = main_shock['magnitude']

print(f"Main shock: {main_shock_time}, M{main_shock_mag:.1f}")

valid_df['days_after_main_shock'] = (
                                            valid_df['time_datetime'] - main_shock_time
                                    ).dt.total_seconds() / (24 * 3600)

aftershocks_df = valid_df[valid_df['days_after_main_shock'] > 0].copy()

aftershocks_df['day_int'] = np.floor(aftershocks_df['days_after_main_shock'])
daily_counts = aftershocks_df['day_int'].value_counts().sort_index()

daily_df = pd.DataFrame({
    'day': daily_counts.index,
    'count': daily_counts.values
})

daily_df = daily_df[daily_df['day'] >= 0]
daily_df['day_for_fit'] = daily_df['day'] + 1

print(f"Total aftershocks: {len(aftershocks_df)}")
print(f"Days analyzed: {len(daily_df)}")


def omori_law(t, k, c, p):
    return k / (c + t) ** p


try:
    if len(daily_df) < 3:
        raise ValueError("Not enough data for Omori's Law (at least 3 days required)")

    initial_params = [daily_df['count'].max() * 2, 0.1, 1.0]

    params, covariance = curve_fit(
        omori_law,
        daily_df['day_for_fit'],
        daily_df['count'],
        p0=initial_params,
        maxfev=10000
    )[:2]

    k_fit, c_fit, p_fit = params

    daily_df['predicted_count'] = omori_law(
        daily_df['day_for_fit'], k_fit, c_fit, p_fit
    )

    ss_res = np.sum((daily_df['count'] - daily_df['predicted_count']) ** 2)
    ss_tot = np.sum((daily_df['count'] - np.mean(daily_df['count'])) ** 2)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0

    correlation, p_value = stats.pearsonr(
        daily_df['count'], daily_df['predicted_count']
    )

    fig, axes = plt.subplots(2, 2, figsize=(15, 12))

    axes[0, 0].plot(
        daily_df['day'], daily_df['count'], 'o-', alpha=0.7,
        label='Actual', markersize=4
    )
    axes[0, 0].plot(
        daily_df['day'], daily_df['predicted_count'], 'r--',
        label=f'Omori (p={p_fit:.2f})', linewidth=2
    )
    axes[0, 0].set_xlabel('Days After Main Shock')
    axes[0, 0].set_ylabel('Daily Aftershock Count')
    axes[0, 0].legend()
    axes[0, 0].grid(True, alpha=0.3)

    axes[0, 1].loglog(
        daily_df['day_for_fit'], daily_df['count'], 'o',
        alpha=0.7, label='Actual'
    )
    axes[0, 1].loglog(
        daily_df['day_for_fit'], daily_df['predicted_count'], 'r--',
        label=f'Omori (p={p_fit:.2f})', linewidth=2
    )
    axes[0, 1].set_xlabel('Days After Main Shock (Log)')
    axes[0, 1].set_ylabel('Aftershock Count (Log)')
    axes[0, 1].legend()
    axes[0, 1].grid(True, alpha=0.3)

    daily_df['residual'] = daily_df['count'] - daily_df['predicted_count']
    axes[1, 0].plot(daily_df['day'], daily_df['residual'], 'o', alpha=0.7)
    axes[1, 0].axhline(y=0, color='r', linestyle='--', alpha=0.7)
    axes[1, 0].set_xlabel('Days After Main Shock')
    axes[1, 0].set_ylabel('Residual (Actual - Predicted)')
    axes[1, 0].grid(True, alpha=0.3)

    axes[1, 1].scatter(
        aftershocks_df['days_after_main_shock'],
        aftershocks_df['magnitude'],
        alpha=0.6, s=15, c='green'
    )
    axes[1, 1].set_xlabel('Days After Main Shock')
    axes[1, 1].set_ylabel('Magnitude (M)')
    axes[1, 1].grid(True, alpha=0.3)

    title_text = (
        f'Earthquake Aftershock Analysis - {os.path.basename(selected_file)[:-4].upper()} (M{main_shock_mag:.1f})\n'
        f'Omori Law: n(t) = {k_fit:.1f}/({c_fit:.3f}+t)^{p_fit:.3f}, R² = {r_squared:.3f}'
    )
    plt.suptitle(title_text, fontsize=14, fontweight='bold')

    plt.tight_layout()

    output_png = os.path.join(
        OUTPUT_DIR,
        f'omori_analysis_{os.path.basename(selected_file)[:-4]}_results.png'
    )
    plt.savefig(output_png, dpi=300, bbox_inches='tight')
    plt.show()

    output_txt = os.path.join(
        OUTPUT_DIR,
        f'omori_analysis_{os.path.basename(selected_file)[:-4]}_summary.txt'
    )
    with open(output_txt, "w", encoding="utf-8") as f:
        f.write(f"Main shock: {main_shock_time}, M{main_shock_mag:.1f}\n")
        f.write(f"Total aftershocks: {len(aftershocks_df)}\n")
        f.write(f"Days analyzed: {len(daily_df)}\n")
        f.write(f"k = {k_fit:.3f}\n")
        f.write(f"c = {c_fit:.3f}\n")
        f.write(f"p = {p_fit:.3f}\n")
        f.write(f"R² = {r_squared:.3f}\n")

except Exception as e:
    print(f"Model fitting error: {e}")
    import traceback

    traceback.print_exc()
