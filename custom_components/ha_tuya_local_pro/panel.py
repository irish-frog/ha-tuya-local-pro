"""Panel for Tuya Local Pro DPS Builder."""

import logging
import os

from homeassistant.components.panel_iframe import async_register_panel

_LOGGER = logging.getLogger(__name__)

PANEL_TITLE = "Tuya DPS Builder"
PANEL_ICON = "mdi:chip"
PANEL_NAME = "ha_tuya_local_pro_dps_builder"
PANEL_URL_PATH = "/api/ha_tuya_local_pro/panel"

PANEL_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tuya DPS Builder</title>
    <style>
        :root {
            --primary-color: #03a9f4;
            --secondary-color: #018786;
            --background-color: #fafafa;
            --card-background-color: #ffffff;
            --text-primary-color: #333333;
            --text-secondary-color: #666666;
            --border-color: #e0e0e0;
            --error-color: #db4437;
            --success-color: #0f9d58;
            --warning-color: #f4b400;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            font-family: 'Roboto', 'Segoe UI', sans-serif;
            background-color: var(--background-color);
            color: var(--text-primary-color);
            line-height: 1.6;
        }

        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }

        header {
            background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
            color: white; padding: 20px 30px; border-radius: 12px;
            margin-bottom: 24px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        }

        header h1 { font-size: 28px; font-weight: 500; margin-bottom: 8px; }
        header p { opacity: 0.9; font-size: 14px; }

        .card {
            background: var(--card-background-color); border-radius: 12px;
            padding: 24px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
            border: 1px solid var(--border-color);
        }

        .card h2 {
            font-size: 18px; font-weight: 500; margin-bottom: 16px;
            color: var(--primary-color); display: flex; align-items: center; gap: 8px;
        }

        .btn {
            display: inline-flex; align-items: center; justify-content: center;
            padding: 12px 24px; border: none; border-radius: 8px;
            font-size: 14px; font-weight: 500; cursor: pointer; transition: all 0.2s; gap: 8px;
        }

        .btn-primary { background: var(--primary-color); color: white; }
        .btn-primary:hover { background: #0288d1; box-shadow: 0 4px 12px rgba(3, 169, 244, 0.3); }
        .btn-success { background: var(--success-color); color: white; }
        .btn-success:hover { background: #0b8043; }
        .btn-secondary { background: #e0e0e0; color: var(--text-primary-color); }
        .btn-secondary:hover { background: #d0d0d0; }
        .btn-danger { background: var(--error-color); color: white; }
        .btn-danger:hover { background: #c62828; }

        .btn-group { display: flex; gap: 12px; margin-top: 16px; flex-wrap: wrap; }

        .dps-table, .mapping-table {
            width: 100%; border-collapse: collapse; margin-top: 16px;
        }

        .dps-table th, .dps-table td,
        .mapping-table th, .mapping-table td {
            padding: 12px 16px; text-align: left; border-bottom: 1px solid var(--border-color);
        }

        .dps-table th, .mapping-table th {
            background: #f5f5f5; font-weight: 500; color: var(--text-secondary-color);
            font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;
        }

        .dps-table tr:hover, .mapping-table tr:hover { background: #f9f9f9; }

        .dps-value {
            font-family: 'Roboto Mono', monospace; font-weight: 500; padding: 4px 8px;
            background: #e3f2fd; border-radius: 4px; display: inline-block;
        }

        .status-badge {
            display: inline-flex; align-items: center; padding: 4px 12px;
            border-radius: 16px; font-size: 12px; font-weight: 500;
        }

        .status-connected { background: #e8f5e9; color: #2e7d32; }
        .status-disconnected { background: #ffebee; color: #c62828; }

        .status-badge::before {
            content: ''; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px;
        }

        .status-connected::before { background: #2e7d32; }
        .status-disconnected::before { background: #c62828; }

        .mapping-table input, .mapping-table select {
            padding: 8px 10px; border: 1px solid var(--border-color);
            border-radius: 6px; font-size: 13px; width: 100%;
        }

        .mapping-table input:focus, .mapping-table select:focus {
            outline: none; border-color: var(--primary-color);
        }

        .device-selector { display: flex; align-items: center; gap: 16px; margin-bottom: 20px; }

        .device-selector select {
            flex: 1; max-width: 400px; padding: 12px 14px;
            border: 1px solid var(--border-color); border-radius: 8px; font-size: 14px;
        }

        .empty-state { text-align: center; padding: 40px; color: var(--text-secondary-color); }
        .empty-state .icon { font-size: 48px; margin-bottom: 16px; }

        .notification {
            position: fixed; top: 20px; right: 20px; padding: 16px 24px;
            border-radius: 8px; color: white; font-weight: 500; z-index: 1000;
            animation: slideIn 0.3s ease-out;
        }

        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }

        .notification.success { background: var(--success-color); }
        .notification.error { background: var(--error-color); }
        .notification.warning { background: var(--warning-color); color: #333; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🔧 Tuya DPS Builder</h1>
            <p>Configure and map DPS (Data Point Sets) from your Tuya devices to Home Assistant entities</p>
        </header>

        <div class="card">
            <h2><span class="icon">📡</span> Device Selection</h2>
            <div class="device-selector">
                <select id="deviceSelect"><option value="">Select a device...</option></select>
                <span id="connectionStatus" class="status-badge status-disconnected">Disconnected</span>
            </div>
        </div>

        <div class="card">
            <h2><span class="icon">📊</span> Live DPS Values</h2>
            <p style="margin-bottom: 16px; color: var(--text-secondary-color); font-size: 14px;">
                Real-time DPS values from the selected device.
            </p>
            <div class="btn-group">
                <button class="btn btn-primary" onclick="refreshDps()">🔄 Refresh</button>
                <button class="btn btn-secondary" onclick="autoRefreshToggle()">
                    ⏱️ Auto Refresh: <span id="autoRefreshStatus">OFF</span>
                </button>
            </div>
            <div id="dpsTableContainer" style="margin-top: 16px;">
                <div class="empty-state"><div class="icon">📡</div><p>Select a device to view DPS values</p></div>
            </div>
        </div>

        <div class="card">
            <h2><span class="icon">🗺️</span> DPS Mapping Configuration</h2>
            <p style="margin-bottom: 16px; color: var(--text-secondary-color); font-size: 14px;">
                Map DPS values to Home Assistant entities.
            </p>
            <div class="btn-group">
                <button class="btn btn-success" onclick="addMapping()">➕ Add Mapping</button>
                <button class="btn btn-primary" onclick="saveMappings()">💾 Save Mappings</button>
                <button class="btn btn-secondary" onclick="loadMappings()">📂 Load Mappings</button>
                <button class="btn btn-secondary" onclick="autoMapDps()">🤖 Auto-Map DPS</button>
            </div>
            <div id="mappingTableContainer" style="margin-top: 16px;">
                <div class="empty-state"><div class="icon">🗺️</div><p>No mappings configured.</p></div>
            </div>
        </div>

        <div class="card">
            <h2><span class="icon">📦</span> Profile Export/Import</h2>
            <p style="margin-bottom: 16px; color: var(--text-secondary-color); font-size: 14px;">
                Export or import device profiles.
            </p>
            <div class="btn-group">
                <button class="btn btn-primary" onclick="exportProfile()">📤 Export Profile</button>
                <button class="btn btn-secondary" onclick="document.getElementById('importFile').click()">📥 Import Profile</button>
                <input type="file" id="importFile" accept=".json" style="display: none;" onchange="importProfile(event)">
            </div>
        </div>
    </div>

    <script>
        let currentDeviceId = null;
        let currentDpsValues = {};
        let mappings = [];
        let autoRefreshInterval = null;
        let wsConnection = null;
        let wsRequestId = 1;

        document.addEventListener('DOMContentLoaded', () => { loadDevices(); });

        function getAccessToken() {
            try {
                const ha = document.querySelector('home-assistant');
                if (ha && ha.hass && ha.hass.auth) return ha.hass.auth.data.access_token;
            } catch (e) {}
            return new URLSearchParams(window.location.search).get('token') || '';
        }

        function escapeHtml(value) {
            return String(value ?? '').replace(/[&<>"']/g, (char) => ({
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                '"': '&quot;',
                "'": '&#39;',
            }[char]));
        }

        function escapeJsString(value) {
            return String(value ?? '').replace(/\\/g, '\\\\').replace(/'/g, "\\'");
        }

        async function loadDevices() {
            try {
                const token = getAccessToken();
                const response = await fetch('/api/states', { headers: { 'Authorization': 'Bearer ' + token } });
                const states = await response.json();
                const tuyaDevices = states.filter(s => s.entity_id.startsWith('ha_tuya_local_pro_'));
                const select = document.getElementById('deviceSelect');
                select.innerHTML = '<option value="">Select a device...</option>';
                const deviceIds = new Set();
                tuyaDevices.forEach(device => {
                    const deviceId = device.attributes.device_id;
                    if (deviceId && !deviceIds.has(deviceId)) {
                        deviceIds.add(deviceId);
                        const option = document.createElement('option');
                        option.value = deviceId;
                        option.textContent = device.attributes.friendly_name || deviceId;
                        select.appendChild(option);
                    }
                });
                select.addEventListener('change', (e) => { currentDeviceId = e.target.value; if (currentDeviceId) connectToDevice(currentDeviceId); });
            } catch (error) { showNotification('Failed to load devices: ' + error.message, 'error'); }
        }

        function connectToDevice(deviceId) {
            if (wsConnection) wsConnection.close();
            const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
            wsConnection = new WebSocket(`${protocol}//${location.host}/api/websocket`);
            wsConnection.onopen = () => { wsConnection.send(JSON.stringify({ type: 'auth', access_token: getAccessToken() })); };
            wsConnection.onmessage = (event) => {
                const msg = JSON.parse(event.data);
                if (msg.type === 'auth_ok') {
                    wsConnection.send(JSON.stringify({ id: wsRequestId++, type: 'ha_tuya_local_pro/dps_stream', device_id: deviceId }));
                } else if (msg.type === 'event' && msg.event && msg.event.dps) {
                    currentDpsValues = { ...currentDpsValues, ...msg.event.dps };
                    updateDpsTable();
                } else if (msg.type === 'result' && msg.result && msg.result.dps) {
                    currentDpsValues = msg.result.dps;
                    updateDpsTable();
                    updateConnectionStatus(true);
                }
            };
            wsConnection.onerror = () => { updateConnectionStatus(false); };
            wsConnection.onclose = () => { updateConnectionStatus(false); };
        }

        function updateConnectionStatus(connected) {
            const s = document.getElementById('connectionStatus');
            s.className = connected ? 'status-badge status-connected' : 'status-badge status-disconnected';
            s.textContent = connected ? 'Connected' : 'Disconnected';
        }

        function updateDpsTable() {
            const c = document.getElementById('dpsTableContainer');
            if (!Object.keys(currentDpsValues).length) { c.innerHTML = '<div class="empty-state"><div class="icon">📡</div><p>No DPS data</p></div>'; return; }
            let html = '<table class="dps-table"><thead><tr><th>DPS ID</th><th>Value</th><th>Type</th><th>Actions</th></tr></thead><tbody>';
            for (const [id, val] of Object.entries(currentDpsValues)) {
                const t = typeof val;
                const canToggle = t === 'boolean' || (t === 'number' && (val === 0 || val === 1));
                const safeId = escapeHtml(id);
                const safeType = escapeHtml(t);
                const safeValue = escapeHtml(val);
                const jsId = escapeHtml(escapeJsString(id));
                html += `<tr><td><strong>DPS ${safeId}</strong></td><td><span class="dps-value">${safeValue}</span></td><td>${safeType}</td><td><button class="btn btn-secondary" style="padding:6px 12px;font-size:12px" onclick="quickMap('${jsId}','${t}')">🗺️ Map</button>${canToggle ? ` <button class="btn btn-secondary" style="padding:6px 12px;font-size:12px" onclick="toggleDps('${jsId}',${JSON.stringify(val)})">🔄 Toggle</button>` : ''}</td></tr>`;
            }
            c.innerHTML = html + '</tbody></table>';
        }

        function refreshDps() { if (currentDeviceId) connectToDevice(currentDeviceId); }

        function autoRefreshToggle() {
            if (autoRefreshInterval) { clearInterval(autoRefreshInterval); autoRefreshInterval = null; document.getElementById('autoRefreshStatus').textContent = 'OFF'; }
            else { autoRefreshInterval = setInterval(refreshDps, 2000); document.getElementById('autoRefreshStatus').textContent = 'ON'; }
        }

        function quickMap(dpsId, valueType) {
            mappings.push({ dps_id: dpsId, name: `DPS ${dpsId}`, entity_type: valueType === 'boolean' ? 'switch' : 'sensor', scale: 1.0, offset: 0.0, unit: '', device_class: '', state_class: '', icon: '' });
            updateMappingTable();
            showNotification(`DPS ${dpsId} added`, 'success');
        }

        function toggleDps(dpsId, val) { showNotification(`Toggle DPS ${dpsId} requires service call`, 'warning'); }

        function addMapping() {
            mappings.push({ dps_id: '', name: '', entity_type: 'sensor', scale: 1.0, offset: 0.0, unit: '', device_class: '', state_class: '', icon: '' });
            updateMappingTable();
        }

        function updateMappingTable() {
            const c = document.getElementById('mappingTableContainer');
            if (!mappings.length) { c.innerHTML = '<div class="empty-state"><div class="icon">🗺️</div><p>No mappings configured.</p></div>'; return; }
            let html = '<table class="mapping-table"><thead><tr><th>DPS ID</th><th>Name</th><th>Type</th><th>Scale</th><th>Offset</th><th>Unit</th><th>Device Class</th><th>State Class</th><th></th></tr></thead><tbody>';
            mappings.forEach((m, i) => {
                html += `<tr><td><input value="${escapeHtml(m.dps_id)}" onchange="mappings[${i}].dps_id=this.value" placeholder="1"></td><td><input value="${escapeHtml(m.name)}" onchange="mappings[${i}].name=this.value" placeholder="Power"></td><td><select onchange="mappings[${i}].entity_type=this.value"><option value="sensor"${m.entity_type==='sensor'?' selected':''}>Sensor</option><option value="switch"${m.entity_type==='switch'?' selected':''}>Switch</option><option value="binary_sensor"${m.entity_type==='binary_sensor'?' selected':''}>Binary</option></select></td><td><input type="number" value="${escapeHtml(m.scale)}" step="0.001" onchange="mappings[${i}].scale=parseFloat(this.value)"></td><td><input type="number" value="${escapeHtml(m.offset)}" step="0.01" onchange="mappings[${i}].offset=parseFloat(this.value)"></td><td><input value="${escapeHtml(m.unit)}" onchange="mappings[${i}].unit=this.value" placeholder="W"></td><td><input value="${escapeHtml(m.device_class)}" onchange="mappings[${i}].device_class=this.value" placeholder="power"></td><td><input value="${escapeHtml(m.state_class)}" onchange="mappings[${i}].state_class=this.value" placeholder="measurement"></td><td><button class="btn btn-danger" style="padding:6px 10px;font-size:11px" onclick="removeMapping(${i})">🗑️</button></td></tr>`;
            });
            c.innerHTML = html + '</tbody></table>';
        }

        function removeMapping(i) { mappings.splice(i, 1); updateMappingTable(); }

        function saveMappings() {
            if (!currentDeviceId) { showNotification('Select a device first', 'warning'); return; }
            wsConnection.send(JSON.stringify({ id: wsRequestId++, type: 'ha_tuya_local_pro/dps_mapping_save', device_id: currentDeviceId, mappings: mappings.filter(m => m.dps_id && m.name) }));
            showNotification('Mappings saved', 'success');
        }

        function loadMappings() {
            if (!currentDeviceId) { showNotification('Select a device first', 'warning'); return; }
            wsConnection.send(JSON.stringify({ id: wsRequestId++, type: 'ha_tuya_local_pro/dps_mapping_load', device_id: currentDeviceId }));
        }

        function autoMapDps() {
            if (!Object.keys(currentDpsValues).length) { showNotification('Connect to device first', 'warning'); return; }
            mappings = [];
            const p = { '1': { n: 'Switch', t: 'switch' }, '4': { n: 'Fault', t: 'binary_sensor', d: 'problem' }, '7': { n: 'Child Lock', t: 'switch', i: 'mdi:lock' }, '18': { n: 'Current', t: 'sensor', d: 'current', u: 'A', s: 0.001 }, '19': { n: 'Power', t: 'sensor', d: 'power', u: 'W', s: 0.1 }, '20': { n: 'Voltage', t: 'sensor', d: 'voltage', u: 'V', s: 0.1 }, '101': { n: 'Energy', t: 'sensor', d: 'energy', u: 'kWh', s: 0.01 }, '102': { n: 'Overcharge', t: 'switch', i: 'mdi:flash-alert' } };
            for (const [id, val] of Object.entries(currentDpsValues)) {
                const pat = p[id];
                if (pat) mappings.push({ dps_id: id, name: pat.n, entity_type: pat.t, scale: pat.s || 1.0, offset: 0.0, unit: pat.u || '', device_class: pat.d || '', state_class: pat.d ? 'measurement' : '', icon: pat.i || '' });
                else mappings.push({ dps_id: id, name: `DPS ${id}`, entity_type: typeof val === 'boolean' ? 'switch' : 'sensor', scale: 1.0, offset: 0.0, unit: '', device_class: '', state_class: '', icon: '' });
            }
            updateMappingTable();
            showNotification(`Auto-mapped ${mappings.length} DPS`, 'success');
        }

        function exportProfile() {
            if (!currentDeviceId) { showNotification('Select a device first', 'warning'); return; }
            const blob = new Blob([JSON.stringify({ device_id: currentDeviceId, mappings, exported_at: new Date().toISOString() }, null, 2)], { type: 'application/json' });
            const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = `tuya_profile_${currentDeviceId}.json`; a.click();
            showNotification('Profile exported', 'success');
        }

        function importProfile(e) {
            const file = e.target.files[0]; if (!file) return;
            const reader = new FileReader();
            reader.onload = (ev) => { try { const p = JSON.parse(ev.target.result); if (p.mappings) { mappings = p.mappings; updateMappingTable(); showNotification(`Imported ${mappings.length} mappings`, 'success'); } } catch (err) { showNotification('Parse error: ' + err.message, 'error'); } };
            reader.readAsText(file);
        }

        function showNotification(msg, type = 'success') {
            const n = document.createElement('div'); n.className = `notification ${type}`; n.textContent = msg;
            document.body.appendChild(n); setTimeout(() => n.remove(), 3000);
        }
    </script>
</body>
</html>"""


async def async_register_dps_builder_panel(hass) -> None:
    """Register the DPS Builder panel as an iframe panel."""
    # Write HTML to a file that can be served
    panel_dir = os.path.join(os.path.dirname(__file__), "www")
    os.makedirs(panel_dir, exist_ok=True)
    panel_file = os.path.join(panel_dir, "dps_builder.html")

    try:
        with open(panel_file, "w", encoding="utf-8") as f:
            f.write(PANEL_HTML)
    except OSError as e:
        _LOGGER.error("Failed to write panel HTML: %s", e)
        return

    # Register static path to serve the panel
    hass.http.register_static_path(PANEL_URL_PATH, panel_dir)

    # Register iframe panel
    async_register_panel(
        hass,
        frontend_url_path=PANEL_NAME,
        title=PANEL_TITLE,
        icon=PANEL_ICON,
        url=PANEL_URL_PATH,
        config={"embedded": True},
        require_admin=True,
    )
    _LOGGER.info("Registered Tuya DPS Builder panel at %s", PANEL_URL_PATH)
