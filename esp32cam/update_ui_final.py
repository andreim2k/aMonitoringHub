
import sys

file_path = 'src/modules/webserver.cpp'
start_marker = 'static const char html_content[] = R"rawliteral('
end_marker = ')rawliteral";'

new_html = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>ESP32-CAM Control</title>
<style>
*{box-sizing:border-box}
body{margin:0;font-family:system-ui,-apple-system,Segoe UI,sans-serif;background:#121826;color:#f7fafc;line-height:1.4}
.wrap{max-width:1240px;margin:0 auto;padding:16px;display:grid;grid-template-columns:minmax(0,2fr) 360px;gap:16px}
main{display:grid;gap:16px}
.panel{background:#1f2937;border:1px solid #374151;border-radius:12px;padding:16px;height:fit-content}
.captureHead,.panelHead{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:16px}
.field{margin:0 0 12px}
.field label,.rangeLabel{display:block;margin:0 0 6px;color:#cbd5e1;font-size:12px;font-weight:600}
.rangeLabel{display:flex;align-items:center;justify-content:space-between;gap:6px}
.value{min-width:38px;text-align:right;color:#f8fafc;background:#0f172a;border:1px solid #334155;border-radius:5px;padding:2px 6px;font-size:11px;font-weight:700;font-variant-numeric:tabular-nums}
input,select,button{width:100%;border:1px solid #4b5563;border-radius:8px;background:#111827;color:#f9fafb;padding:10px;font-size:14px;-webkit-appearance:none}
select{background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23f9fafb' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:right 10px center;background-size:14px;padding-right:32px}
input[type=range]{height:28px;padding:0;accent-color:#3b82f6;cursor:pointer}
button{cursor:pointer;background:#2563eb;border-color:#2563eb;font-weight:700;transition:all 0.2s;display:flex;align-items:center;justify-content:center;min-height:42px}
button:hover{opacity:0.9;transform:translateY(-1px)}
button:active{transform:translateY(0)}
button:disabled{opacity:0.5;cursor:not-allowed;transform:none}
.secondary{background:#374151;border-color:#4b5563}
.smallBtn{width:auto;padding:6px 14px;font-size:12px;min-height:34px}
.grid{display:grid;grid-template-columns:repeat(auto-fit, minmax(140px, 1fr));gap:10px}
.settingsStack{display:grid;gap:16px}
.settingsBlock{border-top:1px solid #334155;padding-top:16px}
.settingsBlock:first-child{border-top:0;padding-top:0}
.sectionTitle{margin:0 0 10px;color:#93c5fd;font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:1px}
.imageBox{position:relative;background:#0f172a;border-radius:8px;min-height:200px;display:flex;align-items:center;justify-content:center;overflow:hidden;border:1px solid #334155;aspect-ratio:4/3}
#photo{width:100%;height:100%;object-fit:contain;display:none}
.watermark{position:absolute;bottom:10px;right:10px;background:rgba(15,23,42,0.85);backdrop-filter:blur(4px);padding:4px 10px;border-radius:5px;font-size:10px;font-weight:700;color:#f8fafc;border:1px solid #334155;z-index:10;pointer-events:none}
.error{color:#f87171;border-color:#ef4444}
.muted{color:#94a3b8;font-size:13px}
.stat{display:flex;flex-direction:column;gap:1px;padding:8px;background:#111827;border-radius:8px;border:1px solid #334155}
.stat b{font-size:9px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.5px}
.stat span{font-size:12px;font-weight:600;word-break:break-all}
.statusLine{margin-top:12px;font-size:12px;padding:10px;border-radius:8px;background:#1e1b4b;color:#c7d2fe;display:none;border:1px solid #3730a3}
.check{display:flex;align-items:center;gap:10px;cursor:pointer;padding:6px 0;user-select:none;font-size:13px}
.check input{width:18px;height:18px;margin:0;border-radius:5px}
.payloadBox{margin:0;max-height:160px;overflow:auto;white-space:pre-wrap;background:#0f172a;border:1px solid #334155;border-radius:8px;color:#bfdbfe;padding:10px;font:11px/1.4 ui-monospace,monospace}
.copyBtn{position:absolute;top:6px;right:6px;width:auto;padding:2px 8px;font-size:10px;background:#334155;border-color:#475569;min-height:24px}
footer{margin-top:24px;padding:16px;text-align:center;border-top:1px solid #334155;color:#64748b;font-size:11px}

@media (max-width: 960px) {
  .wrap { grid-template-columns: 1fr; }
  aside { order: 2; }
  main { order: 1; }
}

@media (max-width: 640px) {
  .wrap { padding: 12px; }
  .panel { padding: 12px; }
  .settingsGrid { grid-template-columns: 1fr 1fr !important; gap: 10px !important; }
  .grid { grid-template-columns: 1fr 1fr !important; gap: 8px !important; }
  .captureHead { flex-direction: column; align-items: flex-start; gap: 8px; }
  .captureHead h1 { font-size: 18px !important; }
  .captureHead button { width: 100%; }
  .stat span { font-size: 11px; }
}
</style>
</head>
<body>
<div class="wrap">
  <main>
    <section class="panel">
      <div class="captureHead">
        <div>
          <h1 style="margin:0;font-size:22px">Screen Capture</h1>
          <div class="muted">Live ESP32-CAM output</div>
        </div>
        <button id="capture">Take Snapshot</button>
      </div>
      <div class="imageBox">
        <span id="placeholder" class="muted">No image captured</span>
        <img id="photo" alt="Captured frame">
        <div id="captureStatus" class="watermark">Ready</div>
      </div>
    </section>
    <section class="panel">
      <div class="panelHead">
        <h2 style="margin:0;font-size:18px">Camera Settings</h2>
        <button id="resetCamera" class="secondary smallBtn">Defaults</button>
      </div>
      <div class="settingsStack">
        <div class="settingsBlock">
          <div class="sectionTitle">Capture Configuration</div>
          <div class="settingsGrid" style="display:grid;grid-template-columns:repeat(3, 1fr);gap:12px">
            <div class="field">
              <label>Resolution</label>
              <select id="resolution">
                <option>UXGA (1600x1200)</option>
                <option>SXGA (1280x1024)</option>
                <option>XGA (1024x768)</option>
                <option>SVGA (800x600)</option>
                <option>VGA (640x480)</option>
                <option>CIF (400x296)</option>
                <option>QVGA (320x240)</option>
                <option>HQVGA (240x176)</option>
              </select>
            </div>
            <div class="field"><label class="rangeLabel"><span>Quality</span><span class="value" id="qualityVal">10</span></label><input id="quality" type="range" min="10" max="63" value="10"></div>
            <div class="field"><label>Flash</label><select id="flash"><option value="false">Off</option><option value="true">On</option></select></div>
          </div>
        </div>
        <div class="settingsBlock">
          <div class="sectionTitle">Image Tuning</div>
          <div class="settingsGrid" style="display:grid;grid-template-columns:repeat(auto-fit, minmax(160px, 1fr));gap:12px">
            <div class="field"><label class="rangeLabel"><span>Brightness</span><span class="value" id="brightnessVal">0</span></label><input id="brightness" type="range" min="-2" max="2" value="0"></div>
            <div class="field"><label class="rangeLabel"><span>Contrast</span><span class="value" id="contrastVal">0</span></label><input id="contrast" type="range" min="-2" max="2" value="0"></div>
            <div class="field"><label class="rangeLabel"><span>Saturation</span><span class="value" id="saturationVal">0</span></label><input id="saturation" type="range" min="-2" max="2" value="0"></div>
            <div class="field"><label class="rangeLabel"><span>Exposure</span><span class="value" id="exposureVal">300</span></label><input id="exposure" type="range" min="0" max="1200" step="10" value="300"></div>
            <div class="field"><label class="rangeLabel"><span>Gain</span><span class="value" id="gainVal">0</span></label><input id="gain" type="range" min="0" max="30" value="0"></div>
          </div>
        </div>
        <div class="settingsBlock">
          <div class="sectionTitle">Advanced Processing</div>
          <div class="settingsGrid" style="display:grid;grid-template-columns:repeat(auto-fit, minmax(180px, 1fr));gap:16px;align-items:start">
            <div class="field" style="margin:0"><label>White Balance</label><select id="wbMode"><option value="0">Auto</option><option value="1">Sunny</option><option value="2">Cloudy</option><option value="3">Office</option><option value="4">Home</option></select></div>
            <div class="field" style="margin:0"><label>Special Effect</label><select id="specialEffect"><option value="0">None</option><option value="1">Negative</option><option value="2">Grayscale</option><option value="3">Red tint</option><option value="4">Green tint</option><option value="5">Blue tint</option><option value="6">Sepia</option></select></div>
            <div style="display:flex;flex-direction:column;gap:4px">
              <label class="check"><input id="hmirror" type="checkbox"><span>Horizontal Mirror</span></label>
              <label class="check"><input id="vflip" type="checkbox"><span>Vertical Flip</span></label>
            </div>
          </div>
        </div>
        <div class="settingsBlock">
          <div class="sectionTitle">API Payload Preview</div>
          <div style="position:relative">
            <pre id="payloadText" class="payloadBox"></pre>
            <button id="copyPayload" class="secondary copyBtn">Copy</button>
          </div>
        </div>
      </div>
    </section>
  </main>
  <aside>
    <section class="panel">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
        <h2 style="margin:0;font-size:16px">Network Status</h2>
        <button id="refreshStatus" class="secondary smallBtn" style="min-width:60px">Refresh</button>
      </div>
      <div class="grid">
        <div class="stat"><b>SSID</b><span id="wifiSsid">-</span></div>
        <div class="stat"><b>IP</b><span id="wifiIp">-</span></div>
        <div class="stat"><b>Signal</b><span id="wifiSignal">-</span></div>
        <div class="stat"><b>Mode</b><span id="wifiMode">-</span></div>
      </div>
      <div class="stat" style="margin-top:10px"><b>MAC</b><span id="wifiMac">-</span></div>
      <div class="stat" style="margin-top:10px"><b>Link Details</b><span id="wifiProtocol">-</span></div>
      <div class="stat" style="margin-top:10px"><b>Bandwidth Mode</b><span id="wifiBandwidth">-</span></div>
    </section>
    <section class="panel" style="margin-top:16px">
      <h2 style="margin:0 0 14px;font-size:16px">WiFi Configuration</h2>
      <div class="field"><label>SSID</label><input id="wifiInputSsid" placeholder="New SSID"></div>
      <div class="field"><label>Password</label><input id="wifiInputPassword" type="password" placeholder="New Password"></div>
      <div class="field"><label>Performance</label><select id="wifiInputBandwidth"><option value="0">Max Range (802.11b)</option><option value="1">Balanced (HT20)</option><option value="2">Max Speed (HT40)</option></select></div>
      <button id="saveWifi">Update & Reconnect</button>
      <button id="togglePassword" class="secondary" style="margin-top:8px">Show Password</button>
      <div id="wifiResult" class="statusLine"></div>
    </section>
    <section class="panel" style="margin-top:16px">
      <h2 style="margin:0 0 14px;font-size:16px">Hardware Information</h2>
      <div class="grid">
        <div class="stat"><b>Sensor</b><span id="camReady">-</span></div>
        <div class="stat"><b>Resolution</b><span id="camResolution">-</span></div>
        <div class="stat"><b>PSRAM</b><span id="camPsram">-</span></div>
        <div class="stat"><b>Buffer</b><span id="camFb">-</span></div>
      </div>
      <div class="stat" style="margin-top:10px"><b>Activity</b><span id="camCaptures">-</span></div>
    </section>
  </aside>
</div>
<footer>
  Build: <span id="buildNum">-</span> &bull; <span id="buildTime">-</span>
</footer>
<script>
const $=id=>document.getElementById(id);
function setText(id,value){const el=$(id);if(el)el.textContent=value??'-'}
function bandwidthValue(label){if((label||'').includes('HT40'))return '2';if((label||'').includes('HT20'))return '1';return '0'}
const cameraDefaults={resolution:'UXGA',flash:'false',wbMode:'0',quality:10,brightness:0,contrast:0,saturation:0,exposure:300,gain:0,specialEffect:'0',hmirror:false,vflip:false};
const rangeFields=['quality','brightness','contrast','saturation','exposure','gain'];
function syncRangeLabel(id){const el=$(id+'Val');if(el)el.textContent=$(id).value}
function applyCameraDefaults(){
  $('resolution').value=cameraDefaults.resolution; $('flash').value=cameraDefaults.flash; $('wbMode').value=cameraDefaults.wbMode; $('specialEffect').value=cameraDefaults.specialEffect;
  rangeFields.forEach(id=>{$(id).value=cameraDefaults[id];syncRangeLabel(id)});
  $('hmirror').checked=cameraDefaults.hmirror; $('vflip').checked=cameraDefaults.vflip;
  updatePayloadPreview();
}
function cameraPayload(){
  return {
    resolution:$('resolution').value,
    quality:parseInt($('quality').value,10),
    flash:$('flash').value==='true',
    brightness:parseInt($('brightness').value,10),
    contrast:parseInt($('contrast').value,10),
    saturation:parseInt($('saturation').value,10),
    exposure:parseInt($('exposure').value,10),
    gain:parseInt($('gain').value,10),
    special_effect:parseInt($('specialEffect').value,10),
    wb_mode:parseInt($('wbMode').value,10),
    hmirror:$('hmirror').checked,
    vflip:$('vflip').checked
  };
}
function updatePayloadPreview(){ $('payloadText').textContent=JSON.stringify(cameraPayload(),null,2) }
let firstLoad=true;
async function refreshStatus(){
  try{
    const r=await fetch('/status');
    const d=await r.json();
    setText('wifiSsid',d.wifi.ssid); setText('wifiIp',d.wifi.ip); setText('wifiMode',d.wifi.mode);
    setText('wifiSignal',`${d.wifi.rssi} dBm (${d.wifi.signal_percentage}%)`);
    setText('wifiMac',d.wifi.mac);
    setText('wifiProtocol',d.wifi.protocol); setText('wifiBandwidth',d.wifi.bandwidth);
    setText('camReady',d.camera.ready?'Active':'Offline'); setText('camResolution',d.camera.resolution);
    setText('camPsram',d.camera.psram_available?'Detected':'No'); setText('camFb',d.camera.frame_buffers_in_psram?'PSRAM':'Internal');
    setText('camCaptures',`${d.camera.total_captures} captured / ${d.camera.failed_captures} failed`);
    setText('buildNum',d.build.number); setText('buildTime',d.build.timestamp);
    $('wifiInputSsid').placeholder=d.wifi.ssid||'New SSID';
    $('wifiInputBandwidth').value=bandwidthValue(d.wifi.bandwidth);
    if(firstLoad && d.camera.ready){
      if(d.camera.resolution) $('resolution').value=d.camera.resolution;
      if(d.camera.quality!==undefined) $('quality').value=d.camera.quality;
      if(d.camera.brightness!==undefined) $('brightness').value=d.camera.brightness;
      if(d.camera.contrast!==undefined) $('contrast').value=d.camera.contrast;
      if(d.camera.saturation!==undefined) $('saturation').value=d.camera.saturation;
      if(d.camera.exposure!==undefined) $('exposure').value=d.camera.exposure;
      if(d.camera.gain!==undefined) $('gain').value=d.camera.gain;
      if(d.camera.special_effect!==undefined) $('specialEffect').value=d.camera.special_effect.toString();
      if(d.camera.wb_mode!==undefined) $('wbMode').value=d.camera.wb_mode.toString();
      if(d.camera.hmirror!==undefined) $('hmirror').checked=d.camera.hmirror;
      if(d.camera.vflip!==undefined) $('vflip').checked=d.camera.vflip;
      rangeFields.forEach(syncRangeLabel);
      updatePayloadPreview();
      firstLoad=false;
    }
  }catch(e){console.error(e)}
}
async function capture(){
  const btn=$('capture');
  btn.disabled=true;
  $('captureStatus').textContent='Capturing...';
  const payload=cameraPayload();
  updatePayloadPreview();
  try{
    const r=await fetch('/snapshot',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    if(!r.ok)throw new Error('Capture failed');
    const blob=await r.blob();
    const url=URL.createObjectURL(blob);
    $('photo').src=url; $('photo').style.display='block'; $('placeholder').style.display='none';
    $('captureStatus').textContent='Captured';
    setTimeout(refreshStatus,100);
  }catch(e){$('captureStatus').textContent='Error'; $('captureStatus').classList.add('error')}
  finally{btn.disabled=false}
}
async function saveWifi(){
  const payload={bandwidth:parseInt($('wifiInputBandwidth').value,10)};
  const ssid=$('wifiInputSsid').value.trim();
  const pass=$('wifiInputPassword').value;
  if(ssid)payload.ssid=ssid;
  if(pass)payload.password=pass;
  const res=$('wifiResult'); res.style.display='block'; res.textContent='Saving...';
  try{
    const r=await fetch('/wifi',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const d=await r.json();
    res.textContent=d.message||'Success';
    if(d.reconnect_requested)setTimeout(()=>window.location.reload(),5000);
  }catch(e){res.textContent='Sent. Reconnecting...'}
}
$('capture').addEventListener('click',capture);
$('saveWifi').addEventListener('click',saveWifi);
$('refreshStatus').addEventListener('click',refreshStatus);
$('resetCamera').addEventListener('click',applyCameraDefaults);
$('copyPayload').addEventListener('click',()=>{
  navigator.clipboard.writeText($('payloadText').textContent);
  const oldText=$('copyPayload').textContent;
  $('copyPayload').textContent='Copied';
  setTimeout(()=>$('copyPayload').textContent=oldText,2000);
});
rangeFields.forEach(id=>$(id).addEventListener('input',()=>{syncRangeLabel(id);updatePayloadPreview()}));
['resolution','flash','wbMode','specialEffect','hmirror','vflip'].forEach(id=>$(id).addEventListener('change',updatePayloadPreview));
$('togglePassword').addEventListener('click',()=>{$('wifiInputPassword').type=$('wifiInputPassword').type==='password'?'text':'password'});
rangeFields.forEach(syncRangeLabel);
updatePayloadPreview();
refreshStatus();
setInterval(refreshStatus,30000);
</script>
</body>
</html>
"""

with open(file_path, 'r') as f:
    content = f.read()

start_index = content.find(start_marker)
end_index = content.find(end_marker, start_index)

if start_index != -1 and end_index != -1:
    end_index += len(end_marker)
    new_block = '  ' + start_marker + new_html + end_marker
    
    before_content = content[:start_index]
    after_content = content[end_index:]
    
    new_content = before_content.rstrip() + '\n' + new_block + '\n' + after_content.lstrip()

    with open(file_path, 'w') as f:
        f.write(new_content)
    print("Successfully updated webserver.cpp with corrected UI HTML.")
else:
    print(f"Error: Could not find the markers in {file_path}")
    sys.exit(1)
