from flask import Flask, render_template, jsonify, request, send_file
import pandas as pd
import io
import re
from datetime import datetime

app = Flask(__name__)

# --- GLOBAL DATA ---
current_data = {
    "aqi": 0, "pm25": 0, "pm10": 0, "no2": 0, "so2": 0, "co": 0,
    "status": "Waiting...", "risk_factors": 0, "health_risks": [],
    "chart_data": { "labels": [], "pm25": [], "pm10": [], "no2": [], "so2": [], "co": [], "gps": [] },
    "preview": [] 
}

@app.route('/')
def home():
    # If you are using the folder structure (templates/index.html), keep this:
    return render_template('index.html')
    
    # IF you are using the Single-File method I gave you before, 
    # replace the line above with: return render_template_string(HTML_TEMPLATE)

@app.route('/api/data')
def get_data():
    return jsonify(current_data)

@app.route('/upload', methods=['POST'])
def upload_file():
    global current_data
    
    if 'file' not in request.files: return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '': return jsonify({"error": "No selected file"}), 400

    try:
        # --- THE FIX: READ FROM MEMORY (NO SAVING TO DISK) ---
        if file.filename.endswith('.csv'):
            # Read CSV directly from the file stream
            df = pd.read_csv(file)
        elif file.filename.endswith(('.xlsx', '.xls')):
            # Read Excel directly from the file stream
            df = pd.read_excel(file)
        else:
            return jsonify({"error": "Invalid file type. Use CSV or Excel."}), 400
        
        # --- DATA CLEANING ---
        # Normalize column names (remove spaces, dots, special chars)
        df.columns = [re.sub(r'[^a-z0-9]', '', c.lower()) for c in df.columns]
        
        col_map = {
            'pm25': 'pm25', 'pm23': 'pm25', 'pm2_5': 'pm25', 'pm25': 'pm25', 
            'pm10': 'pm10', 'no2': 'no2', 'so2': 'so2', 'co': 'co',
            'lat': 'lat', 'latitude': 'lat', 'gpslat': 'lat',
            'lon': 'lon', 'longitude': 'lon', 'gpslon': 'lon', 'long': 'lon'
        }
        df = df.rename(columns={c: col_map[c] for c in df.columns if c in col_map})
        
        # Fill missing data
        for col in ['pm25', 'pm10', 'no2', 'so2', 'co']:
            if col not in df.columns: df[col] = 0
        if 'lat' not in df.columns: df['lat'] = 0.0
        if 'lon' not in df.columns: df['lon'] = 0.0

        # Calculate Stats
        val = {
            "pm25": round(df['pm25'].mean(), 1),
            "pm10": round(df['pm10'].mean(), 1),
            "no2": round(df['no2'].mean(), 1),
            "so2": round(df['so2'].mean(), 1),
            "co": round(df['co'].mean(), 1)
        }
        new_aqi = int((val['pm25'] * 2) + (val['pm10'] * 0.5))
        
        # Risk Engine
        risks = []
        if val['pm25'] > 150: risks.append({"name": "Severe Respiratory Distress", "level": "Critical", "icon": "fa-lungs-virus", "color": "red", "precautions": ["Wear N95 masks.", "Avoid outdoors."]})
        elif val['pm25'] > 55: risks.append({"name": "Asthma Aggravation", "level": "High Risk", "icon": "fa-lungs", "color": "orange", "precautions": ["Keep inhaler ready.", "Limit exertion."]})
        if val['co'] > 10: risks.append({"name": "Reduced Oxygen Delivery", "level": "High Risk", "icon": "fa-heart-pulse", "color": "red", "precautions": ["Seek fresh air.", "No smoking."]})
        if not risks: risks.append({"name": "General Well-being", "level": "Safe", "icon": "fa-shield-heart", "color": "green", "precautions": ["Air is safe.", "Enjoy outdoors."]})

        # Prepare Charts & Preview
        chart_df = df.head(100) if len(df) > 100 else df
        chart_data = {
            "labels": [f"{i+1}" for i in range(len(chart_df))],
            "pm25": chart_df['pm25'].tolist(), "pm10": chart_df['pm10'].tolist(), "no2": chart_df['no2'].tolist(), "so2": chart_df['so2'].tolist(), "co": chart_df['co'].tolist(),
            "gps": [{"lat": r['lat'], "lon": r['lon']} for _, r in chart_df.iterrows()]
        }
        preview_data = df.head(5).to_dict(orient='records')

        current_data = { "aqi": new_aqi, **val, "status": "Hazardous" if new_aqi > 300 else "Unhealthy" if new_aqi > 100 else "Good", "risk_factors": len(risks), "health_risks": risks, "chart_data": chart_data, "preview": preview_data }
        
        return jsonify({"message": "Success", "data": current_data})

    except Exception as e:
        print(f"ERROR: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/export')
def export_report():
    # Generate text file in memory (No saving to disk!)
    report_text = f"SKYSENSE REPORT\nDate: {datetime.now()}\nAQI: {current_data['aqi']} ({current_data['status']})\n"
    return send_file(
        io.BytesIO(report_text.encode()),
        mimetype='text/plain',
        as_attachment=True,
        download_name='Skysense_Report.txt'
    )

if __name__ == '__main__':
    app.run(debug=True, port=5001)
