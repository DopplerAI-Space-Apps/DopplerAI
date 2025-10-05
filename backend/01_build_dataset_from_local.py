import pandas as pd
import lightkurve as lk
from tqdm import tqdm
import os
import csv
import glob
import numpy as np

# --- CONFIGURACIÓN ---
INPUT_CSV = './data/cumulative_koi.csv'
OUTPUT_CSV = './data/processed_lightcurves_FINAL.csv'
LOCAL_DATA_PATH = './DOWNLOADED_DATA/exoplanetarchive.ipac.caltech.edu'
N_BINS = 201

def build_dataset_from_harvest():
    df_koi = pd.read_csv(INPUT_CSV, comment='#')
    
    df_koi.drop_duplicates(subset=['kepoi_name'], keep='first', inplace=True)
    
    required_cols = ['kepid', 'kepoi_name', 'koi_disposition', 'koi_period', 'koi_duration', 'koi_time0bk']
    df_koi = df_koi.dropna(subset=required_cols)
    df_koi['kepid'] = df_koi['kepid'].astype(int)

    with open(OUTPUT_CSV, 'w', newline='') as f:
        writer = csv.writer(f)
        header = ['kepid', 'kepoi_name', 'label'] + [f'flux_{i+1}' for i in range(N_BINS)]
        writer.writerow(header)
        
        all_fits_files = glob.glob(os.path.join(LOCAL_DATA_PATH, '**/*_llc.fits'), recursive=True)
        kepids_found = set(int(os.path.basename(f)[4:13]) for f in all_fits_files)
        
        for kepid in tqdm(kepids_found):
            try:
                matching_kois = df_koi[df_koi['kepid'] == kepid]
                if matching_kois.empty: continue

                file_paths = glob.glob(os.path.join(LOCAL_DATA_PATH, f'**/*{kepid:09d}*llc.fits'), recursive=True)
                if not file_paths or any(os.path.getsize(p) == 0 for p in file_paths): continue

                lc_collection = lk.LightCurveCollection([lk.read(path) for path in file_paths])
                lc_stitched = lc_collection.stitch()
                if lc_stitched is None: continue
                lc_cleaned = lc_stitched.remove_outliers().normalize()

                for index, koi_row in matching_kois.iterrows():
                    kepoi_name = koi_row['kepoi_name']
                    
                    folded_lc = lc_cleaned.fold(period=koi_row['koi_period'], epoch_time=koi_row['koi_time0bk'])
                    binned_lc = folded_lc.bin(bins=N_BINS)
                    flux_vector = binned_lc.flux.value

                    if np.isnan(flux_vector).any():
                        flux_vector = np.nan_to_num(flux_vector, nan=1.0)
                    
                    disposition = koi_row['koi_disposition']
                    if disposition == 'CONFIRMED':
                        label = 1
                    elif disposition == 'FALSE POSITIVE':
                        label = 0
                    else:
                        continue
                    
                    writer.writerow([kepid, kepoi_name, label] + list(flux_vector))
                    f.flush()
            except Exception as e:
                continue

    try:
        df_final = pd.read_csv(OUTPUT_CSV)
    except (pd.errors.EmptyDataError, FileNotFoundError):
        print("No se procesó ninguna curva de luz con éxito.")

if __name__ == '__main__':
    build_dataset_from_harvest()