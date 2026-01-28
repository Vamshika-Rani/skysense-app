from flask import Flask, render_template_string, jsonify, request, send_file
import pandas as pd
import os
import re
from datetime import datetime

app = Flask(__name__)

# --- CONFIGURATION ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- GLOBAL DATA ---
current_data = {
    "aqi": 0, "pm25": 0, "pm10": 0, "no2": 0, "so2": 0, "co": 0,
    "status": "Waiting...", "risk_factors": 0, "health_risks": [],
    "chart_data": { "labels": [], "pm25": [], "pm10": [], "no2": [], "so2": [], "co": [], "gps": [] },
    "preview": []
}

# --- THE WEBSITE (EMBEDDED HTML) ---
# We put the HTML here so Python can never lose it!
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SkySense | Drone Air Quality Monitor</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root { --primary-blue: #2563eb; --bg-gray: #f3f4f6; --text-main: #111827; }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Inter', sans-serif; background: var(--bg-gray); color: var(--text-main); display: flex; justify-content: center; padding: 30px; min-height: 100vh; }
        .main-container { width: 100%; max-width: 1100px; }
        .dashboard-header { text-align: center; margin-bottom: 30px; }
        .logo-area { display: flex; justify-content: center; gap: 10px; color: var(--primary-blue); align-items: center; }
        .logo-icon { font-size: 2rem; }
        h1 { font-size: 2.2rem; font-weight: 800; }
        .nav-pills { display: flex; justify-content: center; gap: 10px; flex-wrap: wrap; background: white; padding: 15px; border-radius: 12px; margin-bottom: 30px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        .nav-item { background: transparent; border: none; padding: 10px 20px; font-weight: 600; color: #6b7280; cursor: pointer; border-radius: 8px; display: flex; gap: 8px; align-items: center; }
        .nav-item:hover { background: #eff6ff; color: var(--primary-blue); }
        .nav-item.active { background: #111827; color: white; }
        .dashboard-grid { display: grid; grid-template-columns: 1fr; gap: 20px; }
        @media(min-width: 800px) { .dashboard-grid { grid-template-columns: 1fr 1fr; } }
        .card { background: white; padding: 25px; border-radius: 16px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }
        .full-width { width: 100%; }
        .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid #f3f4f6; padding-bottom: 15px; }
        .aqi-number { font-size: 5rem; font-weight: 800; color: #ea580c; display: block; text-align: center; }
        .main-aqi-display { text-align: center; padding: 20px 0; }
        .badge-status { padding: 5px 12px; border-radius: 20px; font-weight: 700; font-size: 0.85rem; }
        .p-row { margin-bottom: 15px; }
        .p-info { display: flex; justify-content: space-between; font-weight: 600; font-size: 0.9rem; margin-bottom: 5px; }
        .p-track { background: #f3f4f6; height: 8px; border-radius: 10px; overflow: hidden; }
        .p-fill { background: #111827; height: 100%; width: 0%; transition: width 1s ease; }
        .charts-grid-2x2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .chart-box { background: #f8fafc; padding: 15px; border-radius: 12px; height: 250px; border: 1px solid #e2e8f0; }
        .chart-box h5 { text-align: center; margin-bottom: 10px; color: #6b7280; font-size: 0.9rem; }
        .upload-zone { border: 2px dashed #cbd5e1; padding: 60px; text-align: center; cursor: pointer; display: block; border-radius: 12px; transition: 0.3s; background: #f8fafc; }
        .upload-zone:hover { border-color: var(--primary-blue); background: #eff6ff; }
        .upload-icon { font-size: 3rem; color: #9ca3af; margin-bottom: 15px; }
        .btn-black { background: #111827; color: white; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; }
        .hidden-view { display: none !important; }
        .preview-table { width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 0.9rem; background: white; border-radius: 8px; overflow: hidden; }
        .preview-table th { background: #f1f5f9; padding: 12px; text-align: left; color: #475569; font-weight: 600; }
        .preview-table td { padding: 10px 12px; border-bottom: 1px solid #e2e8f0; color: #334155; }
        .alert-banner { background: #d1fae5; color: #065f46; padding: 15px; border-radius: 8px; display: flex; gap: 10px; align-items: center; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="main-container">
        <header class="dashboard-header">
            <div class="logo-area"><i class="fa-solid fa-drone logo-icon"></i><h1>SkySense</h1></div>
            <p style="color:#6b7280;">Autonomous Drone-Based Air Quality Monitoring System</p>
        </header>
        <nav class="nav-pills">
            <button class="nav-item active" onclick="showView('overview')"><i class="fa-solid fa-chart-line"></i> Overview</button>
            <button class="nav-item" onclick="showView('charts')"><i class="fa-solid fa-map-location-dot"></i> GPS Charts</button>
            <button class="nav-item" onclick="showView('disease')"><i class="fa-solid fa-heart-pulse"></i> Health Risk</button>
            <button class="nav-item" onclick="showView('upload')"><i class="fa-solid fa-cloud-arrow-up"></i> Upload Data</button>
            <button class="nav-item" onclick="showView('export')"><i class="fa-solid fa-file-export"></i> Export</button>
        </nav>
        
        <div id="view-overview" class="view-section">
            <div class="dashboard-grid">
                <div class="card">
                    <div class="card-header"><h3>Real-Time AQI</h3><span class="badge-status">Waiting...</span></div>
                    <div class="main-aqi-display"><span class="aqi-number">--</span><p>Air Quality Index</p></div>
                </div>
                <div class="card">
                    <h3>Pollutant Breakdown</h3>
                    <div class="p-row"><div class="p-info"><span>PM2.5</span><span class="p-val" id="val-pm25">--</span></div><div class="p-track"><div class="p-fill" id="bar-pm25"></div></div></div>
                    <div class="p-row"><div class="p-info"><span>PM10</span><span class="p-val" id="val-pm10">--</span></div><div class="p-track"><div class="p-fill" id="bar-pm10"></div></div></div>
                    <div class="p-row"><div class="p-info"><span>NO₂</span><span class="p-val" id="val-no2">--</span></div><div class="p-track"><div class="p-fill" id="bar-no2"></div></div></div>
                    <div class="p-row"><div class="p-info"><span>SO₂</span><span class="p-val" id="val-so2">--</span></div><div class="p-track"><div class="p-fill" id="bar-so2"></div></div></div>
                    <div class="p-row"><div class="p-info"><span>CO</span><span class="p-val" id="val-co">--</span></div><div class="p-track"><div class="p-fill" id="bar-co"></div></div></div>
                </div>
            </div>
            <div class="alert-banner"><i class="fa-solid fa-circle-check"></i><span>System Status: <strong>Operational</strong>. Ready for drone deployment.</span></div>
        </div>

        <div id="view-charts" class="view-section hidden-view">
            <div class="card full-width">
                <div class="card-header"><h3>Pollutant Levels vs. GPS Flight Path</h3></div>
                <div class="charts-grid-2x2">
                    <div class="chart-box"><h5>PM 2.5 Analysis</h5><canvas id="chart-pm25"></canvas></div>
                    <div class="chart-box"><h5>PM 10 Analysis</h5><canvas id="chart-pm10"></canvas></div>
                    <div class="chart-box"><h5>NO₂ Analysis</h5><canvas id="chart-no2"></canvas></div>
                    <div class="chart-box"><h5>SO₂ Analysis</h5><canvas id="chart-so2"></canvas></div>
                </div>
            </div>
        </div>

        <div id="view-disease" class="view-section hidden-view">
            <div class="card full-width">
                <div class="card-header"><h3>Health Risk Assessment</h3></div>
                <div id="disease-container"><div class="empty-state" style="text-align:center; padding:20px; color:#6b7280;"><i class="fa-solid fa-notes-medical"></i><p>Waiting for sensor data...</p></div></div>
            </div>
        </div>

        <div id="view-upload" class="view-section hidden-view">
            <div class="card">
                <h3>📤 Data Management</h3>
                <label for="fileInput" class="upload-zone">
                    <i class="fa-solid fa-cloud-arrow-up upload-icon"></i>
                    <p class="upload-text">Click here to Upload Data</p>
                    <input type="file" id="fileInput" style="display: none;">
                </label>
                <div id="upload-preview-container" style="display: none; margin-top: 30px;">
                    <div class="card-header"><h3>📄 File Data Preview</h3><button class="btn-black" onclick="showView('overview')">Go to Dashboard</button></div>
                    <div style="overflow-x: auto;"><table class="preview-table"><thead><tr><th>Lat</th><th>Lon</th><th>PM2.5</th><th>PM10</th><th>NO₂</th><th>SO₂</th><th>CO</th></tr></thead><tbody id="preview-body"></tbody></table></div>
                </div>
            </div>
        </div>

        <div id="view-export" class="view-section hidden-view">
            <div class="card"><h3>📥 Generate Reports</h3><button class="btn-black" onclick="window.location.href='/export'">Download Report</button></div>
        </div>
    </div>

    <script>
        let charts = {};
        document.addEventListener('DOMContentLoaded', () => {
            const fileInput = document.getElementById('fileInput');
            if(fileInput) {
                fileInput.addEventListener('change', (e) => {
                    const file = e.target.files[0];
                    if(!file) return;
                    
                    const uploadZone = document.querySelector('.upload-zone');
                    const icon = uploadZone.querySelector('.upload-icon');
                    const text = uploadZone.querySelector('.upload-text');
                    const origText = "Click here to Upload Data";
                    
                    text.innerText = "Analyzing...";
                    icon.className = "fa-solid fa-spinner fa-spin upload-icon";

                    const formData = new FormData();
                    formData.append('file', file);

                    fetch('/upload', { method: 'POST', body: formData })
                    .then(res => res.json())
                    .then(data => {
                        if(data.error) { alert("Error: " + data.error); text.innerText = origText; icon.className = "fa-solid fa-cloud-arrow-up upload-icon"; } 
                        else {
                            icon.className = "fa-solid fa-circle-check upload-icon"; icon.style.color = "#10b981";
                            text.innerText = "Success!";
                            updateDashboard(data.data);
                            if(data.data.preview && data.data.preview.length > 0) {
                                const tbody = document.getElementById('preview-body'); tbody.innerHTML = ''; 
                                data.data.preview.forEach(row => {
                                    const tr = document.createElement('tr');
                                    tr.innerHTML = `<td>${row.lat.toFixed(4)}</td><td>${row.lon.toFixed(4)}</td><td>${row.pm25}</td><td>${row.pm10}</td><td>${row.no2}</td><td>${row.so2}</td><td>${row.co}</td>`;
                                    tbody.appendChild(tr);
                                });
                                document.getElementById('upload-preview-container').style.display = 'block';
                            }
                            setTimeout(() => { icon.className = "fa-solid fa-cloud-arrow-up upload-icon"; icon.style.color = "#9ca3af"; text.innerText = origText; }, 2000);
                        }
                    }).catch(err => alert("Upload failed: " + err));
                });
            }
            fetch('/api/data').then(res => res.json()).then(data => updateDashboard(data));
        });

        function showView(viewName) {
            document.querySelectorAll('.view-section').forEach(el => el.classList.add('hidden-view'));
            document.getElementById('view-' + viewName).classList.remove('hidden-view');
            document.querySelectorAll('.nav-item').forEach(btn => btn.classList.remove('active'));
            const btn = document.querySelector(`.nav-item[onclick*="'${viewName}'"]`);
            if(btn) btn.classList.add('active');
        }

        function updateDashboard(data) {
            document.querySelector('.aqi-number').innerText = data.aqi;
            document.querySelector('.badge-status').innerText = data.status;
            const statusBadge = document.querySelector('.badge-status');
            if(data.status === "Good") statusBadge.style.background = "#d1fae5";
            else if(data.status === "Moderate") statusBadge.style.background = "#ffedd5";
            else statusBadge.style.background = "#fee2e2";

            const keys = ['pm25', 'pm10', 'no2', 'so2', 'co'];
            const limits = [300, 300, 150, 150, 50];
            keys.forEach((key, i) => {
                const valEl = document.getElementById('val-' + key);
                const barEl = document.getElementById('bar-' + key);
                if(valEl && barEl) {
                    valEl.innerText = data[key];
                    const pct = Math.min((data[key] / limits[i]) * 100, 100);
                    barEl.style.width = pct + "%";
                }
            });

            if(data.chart_data) {
                renderChart('chart-pm25', 'PM2.5', data.chart_data.pm25, data.chart_data.gps, '#2563eb');
                renderChart('chart-pm10', 'PM10', data.chart_data.pm10, data.chart_data.gps, '#0ea5e9');
                renderChart('chart-no2', 'NO₂', data.chart_data.no2, data.chart_data.gps, '#f59e0b');
                renderChart('chart-so2', 'SO₂', data.chart_data.so2, data.chart_data.gps, '#ef4444');
            }

            const dContainer = document.getElementById('disease-container');
            dContainer.innerHTML = ''; 
            if(data.health_risks && data.health_risks.length > 0) {
                data.health_risks.forEach(risk => {
                    const div = document.createElement('div');
                    let bg = risk.color === 'red' ? '#fef2f2' : (risk.color === 'orange' ? '#fff7ed' : '#f0fdf4');
                    let text = risk.color === 'red' ? '#991b1b' : (risk.color === 'orange' ? '#9a3412' : '#166534');
                    let precautionList = risk.precautions.map(p => `<li>• ${p}</li>`).join('');
                    div.style.cssText = `background:${bg}; border:1px solid ${risk.color}; padding:20px; border-radius:12px; margin-bottom:15px;`;
                    div.innerHTML = `<div style="margin-bottom:10px;"><strong style="color:${text}; font-size:1.1rem;"><i class="fa-solid ${risk.icon}"></i> ${risk.name}</strong></div><ul style="padding-left:20px; color:#4b5563;">${precautionList}</ul>`;
                    dContainer.appendChild(div);
                });
            } else { dContainer.innerHTML = '<div class="empty-state" style="text-align:center; padding:20px;"><p>Safe Levels. No Risks.</p></div>'; }
        }

        function renderChart(canvasId, label, dataPoints, gpsData, color) {
            const ctx = document.getElementById(canvasId).getContext('2d');
            if(charts[canvasId]) charts[canvasId].destroy();
            charts[canvasId] = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: dataPoints.map((_, i) => i + 1),
                    datasets: [{ label: label, data: dataPoints, borderColor: color, backgroundColor: color + '20', borderWidth: 2, pointRadius: 2, tension: 0.4, fill: true }]
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    plugins: { legend: { display: false }, tooltip: { callbacks: { label: function(context) { let idx = context.dataIndex; let val = context.raw; if(gpsData && gpsData[idx]) { let g = gpsData[idx]; return [`Val: ${val}`, `GPS: ${g.lat.toFixed(4)}, ${g.lon.toFixed(4)}`]; } return `Val: ${val}`; } } } },
                    scales: { x: { display: false }, y: { beginAtZero: true } }
                }
            });
        }
    </script>
</body>
</html>
"""

# --- ROUTES ---

@app.route('/')
def home():
    # MAGIC: This serves the HTML directly from the string above!
    return render_template_string(HTML_TEMPLATE)

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
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)
        
        if file.filename.endswith('.csv'):
            try: df = pd.read_csv(filepath)
            except: df = pd.read_excel(filepath)
        elif file.filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(filepath)
        else: return jsonify({"error": "Invalid file type"}), 400
        
        # Clean Columns
        df.columns = [re.sub(r'[^a-z0-9]', '', c.lower()) for c in df.columns]
        col_map = {
            'pm25': 'pm25', 'pm23': 'pm25', 'pm2_5': 'pm25', 'pm25': 'pm25', 'pm10': 'pm10',
            'no2': 'no2', 'so2': 'so2', 'co': 'co',
            'lat': 'lat', 'latitude': 'lat', 'gpslat': 'lat',
            'lon': 'lon', 'longitude': 'lon', 'gpslon': 'lon', 'long': 'lon'
        }
        df = df.rename(columns={c: col_map[c] for c in df.columns if c in col_map})
        
        for col in ['pm25', 'pm10', 'no2', 'so2', 'co']:
            if col not in df.columns: df[col] = 0
        if 'lat' not in df.columns: df['lat'] = 0.0
        if 'lon' not in df.columns: df['lon'] = 0.0

        val = {
            "pm25": round(df['pm25'].mean(), 1),
            "pm10": round(df['pm10'].mean(), 1),
            "no2": round(df['no2'].mean(), 1),
            "so2": round(df['so2'].mean(), 1),
            "co": round(df['co'].mean(), 1)
        }
        
        new_aqi = int((val['pm25'] * 2) + (val['pm10'] * 0.5))
        
        risks = []
        if val['pm25'] > 150: risks.append({"name": "Severe Respiratory Distress", "level": "Critical", "icon": "fa-lungs-virus", "color": "red", "precautions": ["Wear N95/P100 mask immediately.", "Avoid all outdoor activities.", "Run indoor air purifiers."]})
        elif val['pm25'] > 55: risks.append({"name": "Asthma Aggravation", "level": "High Risk", "icon": "fa-lungs", "color": "orange", "precautions": ["Keep rescue inhalers accessible.", "Limit prolonged outdoor exertion."]})
        if val['pm10'] > 250: risks.append({"name": "Bronchitis & Wheezing", "level": "High Risk", "icon": "fa-head-side-cough", "color": "red", "precautions": ["Stay hydrated to soothe throat.", "Avoid construction/dusty areas."]})
        if val['co'] > 10: risks.append({"name": "Reduced Oxygen Delivery", "level": "High Risk", "icon": "fa-heart-pulse", "color": "red", "precautions": ["Seek fresh air immediately.", "Avoid smoking areas."]})
        if val['no2'] > 100 or val['so2'] > 100: risks.append({"name": "Eye & Throat Irritation", "level": "Medium Risk", "icon": "fa-eye", "color": "orange", "precautions": ["Rinse eyes with cool water.", "Avoid heavy traffic zones."]})
        if not risks: risks.append({"name": "General Well-being", "level": "Safe", "icon": "fa-shield-heart", "color": "green", "precautions": ["Air quality is excellent.", "Safe for outdoor exercise."]})

        chart_df = df.head(100) if len(df) > 100 else df
        chart_data = {
            "labels": [f"{i+1}" for i in range(len(chart_df))],
            "pm25": chart_df['pm25'].tolist(), "pm10": chart_df['pm10'].tolist(), "no2": chart_df['no2'].tolist(), "so2": chart_df['so2'].tolist(), "co": chart_df['co'].tolist(),
            "gps": [{"lat": r['lat'], "lon": r['lon']} for _, r in chart_df.iterrows()]
        }
        preview_data = df.head(5).to_dict(orient='records')

        current_data = { "aqi": new_aqi, **val, "status": "Hazardous" if new_aqi > 300 else "Unhealthy" if new_aqi > 100 else "Good", "risk_factors": len([r for r in risks if r['color'] != 'green']), "health_risks": risks, "chart_data": chart_data, "preview": preview_data }
        return jsonify({"message": "Success", "data": current_data})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/export')
def export_report():
    path = os.path.join(app.config['UPLOAD_FOLDER'], 'Skysense_Report.txt')
    with open(path, 'w') as f:
        f.write(f"SKYSENSE REPORT\nAQI: {current_data['aqi']} ({current_data['status']})\nPM2.5: {current_data['pm25']}\n")
    return send_file(path, as_attachment=True, download_name="Skysense_Report.txt")

if __name__ == '__main__':
    app.run(debug=True, port=5001)
