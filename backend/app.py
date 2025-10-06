from flask import Flask, render_template, request, jsonify
import pandas as pd
import joblib
import os
import lightkurve as lk
import numpy as np
from scipy.signal import savgol_filter
from werkzeug.utils import secure_filename
import shutil

app = Flask(__name__, template_folder='../frontend/templates',
    static_folder='../frontend/static')
app.secret_key = 'we-will-win'
app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# --- RESOURCE LOADING ---
try:
    model = joblib.load('exoplanet_detector_model.joblib')
    df_catalog = pd.read_csv('./data/cumulative_koi.csv', comment='#')
    df_catalog['kepid'] = pd.to_numeric(df_catalog['kepid'], errors='coerce').dropna().astype(int)
    df_catalog.set_index('kepid', inplace=True)
except Exception as e:
    model, df_catalog = None, None
    print(f"CRITICAL ERROR WHEN STARTING UP: {e}")

# --- CONSTANTS ---
N_BINS = 201

# --- ENGINE 1: SIMPLE AND RELIABLE PROCESSING ---
def process_and_predict(lc, period, t0):
    lc_cleaned = lc.remove_outliers().normalize()
    folded_lc = lc_cleaned.fold(period=period, epoch_time=t0)
    binned_lc = folded_lc.bin(bins=N_BINS)
    flux_vector = binned_lc.flux.value
    if np.isnan(flux_vector).any():
        flux_vector = np.nan_to_num(flux_vector, nan=1.0)
    prediction_proba = model.predict_proba([flux_vector])[0]
    return float(prediction_proba[1] * 100)

# --- ENGINE 2: DEMO-PROOF ---
def hunt_and_predict(lc):
    lc_clean = lc.remove_nans().remove_outliers(sigma=5.0)
    cadence_days = np.median(np.diff(lc_clean.time.value))
    window_length = int(2.5 / cadence_days) if cadence_days > 0 else 21
    if window_length % 2 == 0: window_length += 1
    if window_length < 5: window_length = 5
    trend_model = savgol_filter(lc_clean.flux.value, window_length=window_length, polyorder=3)
    lc_flat = lk.LightCurve(time=lc_clean.time, flux=(lc_clean.flux.value / trend_model))
    results = []
    periodogram = lc_flat.to_periodogram(method='bls')
    for i in range(3):
        try:
            if np.max(periodogram.power) == 0: break
            
            period = periodogram.period_at_max_power.value
            t0 = periodogram.transit_time_at_max_power.value
            
            probability = process_and_predict(lc_flat, period, t0)
            
            results.append({
                'candidate_num': int(i + 1),
                'period': f"{float(period):.4f}",
                'probability': f"{float(probability):.1f}"
            })
            
            periodogram.power[np.abs(periodogram.period.value - period) < 0.2] = 0.0
        except Exception:
            break
    return results

# --- APPLICATION ROUTES ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/predict_koi', methods=['POST'])
def predict_koi():
    if model is None: return jsonify({'error': 'Model not available.'}), 500
    data = request.get_json()
    kepid = data.get('kepid')
    if not kepid or not kepid.isdigit(): return jsonify({'error': 'invalid Kepler ID.'}), 400
    try:
        search_result = lk.search_lightcurve(f'KIC {kepid}', author='Kepler')
        if not search_result: return jsonify({'error': f'No data was found for KIC {kepid} at NASA.'}), 404
        lc = search_result.download_all().stitch()
        if int(kepid) in df_catalog.index:
            koi_info = df_catalog.loc[int(kepid)]
            if isinstance(koi_info, pd.DataFrame): koi_info = koi_info.iloc[0]
            probability = process_and_predict(lc, koi_info['koi_period'], koi_info['koi_time0bk'])
            return jsonify({'probability': probability, 'kepid': kepid, 'source': 'NASA KOI Catalog'})
        else:
            results = hunt_and_predict(lc)
            if not results: return jsonify({'error': 'No significant traffic signs were found.'}), 404
            return jsonify({'results': results, 'source': f'Blind Search (KIC {kepid})'})
    except Exception as e:
        return jsonify({'error': f'Fatal error: {str(e)}'}), 500

@app.route('/predict_fits', methods=['POST'])
def predict_fits():
    if model is None: return jsonify({'error': 'Model not available'}), 500
    file = request.files.get('file')
    if not file or not file.filename.lower().endswith('.fits'): return jsonify({'error': 'Upload a valid .fits file.'}), 400
    
    temp_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
    try:
        file.save(temp_path)
        lc = lk.read(temp_path)
        results = hunt_and_predict(lc)
        
        if not results:
            return jsonify({'error': 'The BLS algorithm could not find any period dip. The light curve may be too short or noisy.'}), 404

        return jsonify({'results': results, 'source': f'File: {file.filename}'})
    except Exception as e:
        return jsonify({'error': f'Fatal error processing file: {str(e)}'}), 500
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

if __name__ == '__main__':

    app.run(debug=True)

