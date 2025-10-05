import pandas as pd
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import joblib

df = pd.read_csv('./data/processed_lightcurves_FINAL.csv', encoding='latin1')

X = df.drop(['kepid', 'kepoi_name', 'label'], axis=1)
y = df['label']

for col in X.columns:
    X[col] = pd.to_numeric(X[col], errors='coerce')
X.fillna(0, inplace=True)

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=42, stratify=y)

print(f"Entrenando el modelo con {len(X_train)} muestras...")
model = XGBClassifier(use_label_encoder=False, eval_metric='logloss', n_estimators=300, max_depth=5, learning_rate=0.1)
model.fit(X_train, y_train)

print("\nEvaluando rendimiento del modelo...")
y_pred = model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)
report = classification_report(y_test, y_pred, target_names=['No Planeta', 'Planeta'])

print(f"\n¡Precisión del Modelo: {accuracy * 100:.2f}%!")
print("\nReporte de Clasificación:")
print(report)

print("Guardando el modelo...")
joblib.dump(model, 'exoplanet_detector_model.joblib')
print("¡Modelo guardado!")