import os
import joblib
import numpy as np

def preprocess(Open, High, Low, Volume):
    base = os.path.dirname(__file__)
    model_path = os.path.join(base, 'model.pkl')
    try:
        model = joblib.load(model_path)
        arr = np.array([[Open, High, Low, Volume]])
        pred = model.predict(arr)
        return float(pred[0])
    except Exception:
        # fallback
        return float((Open+High+Low)/3)
