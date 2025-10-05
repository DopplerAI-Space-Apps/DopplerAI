from flask import Flask, render_template, request, jsonify
import pandas as pd
import joblib
import os
import lightkurve as lk
import numpy as np
from scipy.signal import savgol_filter
import shutil

# --- PROTOCOLO DE EXTERMINIO DE CACHÉ (SE EJECUTA UNA SOLA VEZ) ---
def purge_all_caches():
    home_dir = os.path.expanduser('~')
    global_cache = os.path.join(home_dir, '.lightkurve')
    if os.path.exists(global_cache):
        try:
            shutil.rmtree(global_cache)
        except Exception as e:
            print(f"AVISO: No se pudo destruir la caché. Razón: {e}")

purge_all_caches()
# -----------------------------------------

app = Flask(__name__)
app.secret_key = 'la-redencion-final-te-lo-juro'

try:
    model = joblib.load('exoplanet_detector_model.joblib')
    df_catalog = pd.read_csv('./data/cumulative_koi.csv', comment='#')
    df_catalog['kepid'] = pd.to_numeric(df_catalog['kepid'], errors='coerce').dropna().astype(int)
    df_catalog.set_index('kepid', inplace=True)
except Exception as e:
    model, df_catalog = None, None

N_BINS = 201

def process_known_koi(lc, period, t0):
    lc_cleaned = lc.remove_outliers().normalize()
    folded_lc = lc_cleaned.fold(period=period, epoch_time=t0)
    binned_lc = folded_lc.bin(bins=N_BINS)
    flux_vector = binned_lc.flux.value
    if np.isnan(flux_vector).any():
        flux_vector = np.nan_to_num(flux_vector, nan=1.0)
    
    prediction_proba = model.predict_proba([flux_vector])[0]
    return float(prediction_proba[1] * 100)

def hunt_and_predict(lc):
    lc_clean = lc.remove_nans().remove_outliers(sigma=5.0)
    cadence_days = np.median(np.diff(lc_clean.time.value))
    window_length = int((2.5 / cadence_days))
    if window_length % 2 == 0: window_length += 1
    if window_length < 5: window_length = 5
    trend_model = savgol_filter(lc_clean.flux.value, window_length=window_length, polyorder=3)
    lc_flat = lk.LightCurve(time=lc_clean.time, flux=(lc_clean.flux.value / trend_model))

    results = []
    periodogram = lc_flat.to_periodogram(method='bls')
    for i in range(3): # Buscamos hasta 3 candidatos
        try:
            if np.max(periodogram.power) < 5: break
            period = periodogram.period_at_max_power.value
            t0 = periodogram.transit_time_at_max_power.value
            
            probability = process_known_koi(lc_flat, period, t0)

            results.append({
                'candidate_num': int(i + 1),
                'period': f"{float(period):.4f}",
                'probability': f"{float(probability):.1f}"
            })
            
            periodogram.power[np.abs(periodogram.period.value - period) < 0.2] = 0.0
        except:
            break
    return results

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/predict_koi', methods=['POST'])
def predict_koi():
    if model is None: return jsonify({'error': 'Modelo no disponible.'}), 500
    data = request.get_json()
    kepid = data.get('kepid')
    if not kepid or not kepid.isdigit(): return jsonify({'error': 'Kepler ID inválido.'}), 400

    try:
        search_result = lk.search_lightcurve(f'KIC {kepid}', author='Kepler')
        if not search_result: return jsonify({'error': f'No se encontraron datos para KIC {kepid} en NASA.'}), 404
        
        lc = search_result.download_all().stitch()
        
        if int(kepid) in df_catalog.index:
            koi_info = df_catalog.loc[int(kepid)]
            if isinstance(koi_info, pd.DataFrame): koi_info = koi_info.iloc[0]
            probability = process_known_koi(lc, koi_info['koi_period'], koi_info['koi_time0bk'])
            return jsonify({'probability': float(probability), 'kepid': kepid, 'source': 'NASA KOI Catalog'})
        else:
            results = hunt_and_predict(lc)
            if not results: return jsonify({'error': 'No se encontraron señales de tránsito significativas.'}), 404
            return jsonify({'results': results, 'source': f'Búsqueda a Ciegas (KIC {kepid})'})

    except Exception as e:
        return jsonify({'error': f'Error fatal: {str(e)}'}), 500

@app.route('/predict_fits', methods=['POST'])
def predict_fits():
    if model is None: return jsonify({'error': 'Modelo no disponible.'}), 500
    file = request.files.get('file')
    if not file or not file.filename.lower().endswith('.fits'): return jsonify({'error': 'Sube un archivo .fits válido.'}), 400

    try:
        lc = lk.read(file)
        results = hunt_and_predict(lc)
        if not results: return jsonify({'error': 'No se encontraron señales de tránsito significativas.'}), 404
        return jsonify({'results': results, 'source': f'Archivo: {file.filename}'})
    except Exception as e:
        return jsonify({'error': f'Error fatal: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True)