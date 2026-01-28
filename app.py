from flask import Flask, render_template, jsonify, request, send_file
import pandas as pd
import os
import re
from datetime import datetime

app = Flask(__name__)

# --- BULLETPROOF FOLDER SETUP ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Global Data Storage
current_data = {
    "aqi": 0, "pm25": 0, "pm10": 0, "no2": 0, "so2": 0, "co": 0,
    "status": "Waiting...", "risk_factors": 0, "health_risks": [],
    "chart_data": { "labels": [], "pm25": [], "pm10": [], "no2": [], "so2": [], "co": [], "gps": [] },
    "preview": [] 
}

@app.route('/')
def home():
    return render_template('index.html')

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
        # 1. Save File
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)
        
        # 2. Read File (Smart Reader)
        if file.filename.endswith('.csv'):
            try: df = pd.read_csv(filepath)
            except: df = pd.read_excel(filepath)
        elif file.filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(filepath)
        else:
            return jsonify({"error": "Invalid file type"}), 400
        
        # 3. Clean & Map Columns
        # Remove special chars and lowercase everything
        df.columns = [re.sub(r'[^a-z0-9]', '', c.lower()) for c in df.columns]
        
        col_map = {
            'pm25': 'pm25', 'pm23': 'pm25', 'pm2_5': 'pm25', 'pm25': 'pm25',
            'pm10': 'pm10',
            'no2': 'no2', 'so2': 'so2', 'co': 'co',
            'lat': 'lat', 'latitude': 'lat', 'gpslat': 'lat',
            'lon': 'lon', 'longitude': 'lon', 'gpslon': 'lon', 'long': 'lon'
        }
        df = df.rename(columns={c: col_map[c] for c in df.columns if c in col_map})
        
        # Fill missing columns with 0
        for col in ['pm25', 'pm10', 'no2', 'so2', 'co']:
            if col not in df.columns: df[col] = 0
            
        if 'lat' not in df.columns: df['lat'] = 0.0
        if 'lon' not in df.columns: df['lon'] = 0.0

        # 4. Calculate Averages
        val = {
            "pm25": round(df['pm25'].mean(), 1),
            "pm10": round(df['pm10'].mean(), 1),
            "no2": round(df['no2'].mean(), 1),
            "so2": round(df['so2'].mean(), 1),
            "co": round(df['co'].mean(), 1)
        }
        
        # 5. Calculate AQI
        new_aqi = int((val['pm25'] * 2) + (val['pm10'] * 0.5))
        
        # 6. Advanced Health Risk Engine
        risks = []
        
        # Respiratory Risks
        if val['pm25'] > 150:
            risks.append({
                "name": "Severe Respiratory Distress",
                "level": "Critical",
                "icon": "fa-lungs-virus",
                "color": "red",
                "precautions": ["Wear N95/P100 mask immediately.", "Avoid all outdoor activities.", "Run indoor air purifiers on high."]
            })
        elif val['pm25'] > 55:
            risks.append({
                "name": "Asthma Aggravation",
                "level": "High Risk",
                "icon": "fa-lungs",
                "color": "orange",
                "precautions": ["Keep rescue inhalers accessible.", "Limit prolonged outdoor exertion.", "Close windows to block smog."]
            })

        if val['pm10'] > 250:
             risks.append({
                "name": "Bronchitis & Wheezing",
                "level": "High Risk",
                "icon": "fa-head-side-cough",
                "color": "red",
                "precautions": ["Stay hydrated to soothe throat.", "Avoid construction/dusty areas.", "Wear a mask if coughing occurs."]
            })

        # Cardiovascular Risks
        if val['co'] > 10:
            risks.append({
                "name": "Reduced Oxygen Delivery",
                "level": "High Risk",
                "icon": "fa-heart-pulse",
                "color": "red",
                "precautions": ["Seek fresh air immediately.", "Avoid smoking areas.", "Monitor for dizziness/headache."]
            })

        # Irritation Risks
        if val['no2'] > 100 or val['so2'] > 100:
            risks.append({
                "name": "Eye & Throat Irritation",
                "level": "Medium Risk",
                "icon": "fa-eye",
                "color": "orange",
                "precautions": ["Rinse eyes with cool water.", "Avoid heavy traffic zones.", "Use lubricating eye drops."]
            })

        # Safe State
        if not risks:
            risks.append({
                "name": "General Well-being",
                "level": "Safe",
                "icon": "fa-shield-heart",
                "color": "green",
                "precautions": ["Air quality is excellent.", "Safe for outdoor exercise.", "Ventilate indoor spaces."]
            })

        # 7. Prepare Chart Data (Downsample to 100 points for performance)
        chart_df = df.head(100) if len(df) > 100 else df
        
        chart_data = {
            "labels": [f"{i+1}" for i in range(len(chart_df))],
            "pm25": chart_df['pm25'].tolist(),
            "pm10": chart_df['pm10'].tolist(),
            "no2": chart_df['no2'].tolist(),
            "so2": chart_df['so2'].tolist(),
            "co": chart_df['co'].tolist(),
            "gps": [{"lat": r['lat'], "lon": r['lon']} for _, r in chart_df.iterrows()]
        }

        # 8. Create Preview Data (First 5 Rows)
        preview_data = df.head(5).to_dict(orient='records')

        # 9. Update Global State
        current_data = {
            "aqi": new_aqi,
            **val,
            "status": "Hazardous" if new_aqi > 300 else "Very Unhealthy" if new_aqi > 200 else "Unhealthy" if new_aqi > 100 else "Moderate" if new_aqi > 50 else "Good",
            "risk_factors": len([r for r in risks if r['color'] != 'green']),
            "health_risks": risks,
            "chart_data": chart_data,
            "preview": preview_data
        }
        
        return jsonify({"message": "Success", "data": current_data})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/export')
def export_report():
    # --- PROFESSIONAL TEXT REPORT ---
    path = os.path.join(app.config['UPLOAD_FOLDER'], 'Skysense_Analysis_Report.txt')
    
    with open(path, 'w') as f:
        f.write("="*60 + "\n")
        f.write(f"      SKYSENSE | DRONE AIR QUALITY ANALYSIS REPORT\n")
        f.write("="*60 + "\n\n")
        
        f.write(f"DATE: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"STATUS: {current_data['status'].upper()}\n")
        f.write(f"AQI LEVEL: {current_data['aqi']}\n\n")
        
        f.write("-" * 30 + "\n")
        f.write("SENSOR AVERAGES\n")
        f.write("-" * 30 + "\n")
        f.write(f"PM 2.5 : {current_data['pm25']} ug/m3\n")
        f.write(f"PM 10  : {current_data['pm10']} ug/m3\n")
        f.write(f"NO2    : {current_data['no2']} ug/m3\n")
        f.write(f"SO2    : {current_data['so2']} ug/m3\n")
        f.write(f"CO     : {current_data['co']} mg/m3\n\n")
        
        f.write("-" * 30 + "\n")
        f.write("HEALTH RISK ASSESSMENT\n")
        f.write("-" * 30 + "\n")
        
        for risk in current_data['health_risks']:
            f.write(f"\n[!] CONDITION: {risk['name']} ({risk['level']})\n")
            f.write("    RECOMMENDED PRECAUTIONS:\n")
            for p in risk['precautions']:
                f.write(f"    - {p}\n")
                
        f.write("\n" + "="*60 + "\n")
        f.write("Generated by SkySense Autonomous System\n")
        f.write("="*60 + "\n")

    return send_file(path, as_attachment=True, download_name="Skysense_Report.txt")

if __name__ == '__main__':
    app.run(debug=True, port=5001)