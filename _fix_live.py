import os

orig = r'C:\Projects\AI-Code-Guardian\frontend\index.backup_20261023_design.html'
out = r'C:\Projects\AI-Code-Guardian\frontend\index.html'

with open(orig, 'r', encoding='utf-8') as f:
    lines = f.readlines()

head = lines[:129]
js_block = lines[554:]

body = """<body class="bg-[#03070A] text-[#E2E8F0] font-mono text-[12px] min-h-screen selection:bg-[#19E6D0] selection:text-black">
  <div class="fixed inset-0 pointer-events-none" style="background-image: linear-gradient(rgba(25,230,208,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(25,230,208,0.03) 1px, transparent 1px); background-size: 30px 30px;"></div>
  <div class="fixed inset-0 pointer-events-none bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-[#0A1A2A]/40 via-[#03070A] to-[#03070A]"></div>

  <div class="relative z-10 w-full h-screen max-w-[1400px] mx-auto flex flex-col p-4">
    
    <header class="flex items-center justify-between pb-3 border-b border-[#153245] mb-4 shrink-0">
      <div class="flex items-center gap-3">
        <svg viewBox="0 0 60 60" class="w-8 h-8"><polygon points="30,3 55,16 55,44 30,57 5,44 5,16" fill="none" stroke="#19E6D0" stroke-width="1.5"/><text x="30" y="36" text-anchor="middle" font-family="sans-serif" font-weight="bold" font-size="16" fill="#19E6D0">AI</text></svg>
        <div class="leading-tight">
          <div class="text-[15px] font-bold text-white tracking-widest">CODE GUARDIAN <span class="text-[#19E6D0]">// AI</span></div>
          <div class="text-[9px] text-[#7A8FA6] tracking-widest mt-0.5">FIND FIXES | FIX CODE | BUILD SAFER SOFTWARE</div>
        </div>
      </div>
      <div class="flex items-center gap-2 text-[9.5px]">
        <div class="flex items-center gap-1.5 px-3 py-1.5 rounded border border-[#1EF0A0]/40 bg-[#1EF0A0]/5"><span class="w-1.5 h-1.5 rounded-full bg-[#1EF0A0] shadow-[0_0_8px_#1EF0A0]"></span><span class="text-[#1EF0A0] tracking-widest">NEURAL CORE: ONLINE</span></div>
        <div class="px-3 py-1.5 rounded border border-[#19E6D0]/40 text-[#19E6D0] tracking-widest">USER: QASIM_ALI</div>
        <div class="px-3 py-1.5 rounded border border-[#7A8FA6]/40 text-[#7A8FA6] tracking-widest">BUILD: DEVELOPER</div>
      </div>
    </header>

    <main class="flex gap-4 flex-1 min-h-0">
      
      <aside class="w-[180px] shrink-0 flex flex-col gap-1.5">
        <div class="text-[9px] text-[#7A8FA6] mb-1 px-1 tracking-widest">// NAVIGATION</div>
        
        <div class="side-item rounded border border-[#19E6D0]/50 bg-[#0A1725] px-3 py-2.5 flex items-center gap-3 shadow-[0_0_10px_rgba(25,230,208,0.1)]">
          <span class="text-[10px] text-[#19E6D0] font-bold">01</span>
          <span class="text-[11px] font-bold text-white tracking-widest">DASHBOARD</span>
        </div>
        <div class="side-item rounded border border-transparent px-3 py-2.5 flex items-center gap-3 hover:bg-white/5 transition">
          <span class="text-[10px] text-[#7A8FA6] font-bold">02</span>
          <span class="text-[11px] font-semibold text-[#7A8FA6] tracking-widest">GITHUB LINK</span>
        </div>
        <div class="side-item rounded border border-transparent px-3 py-2.5 flex items-center gap-3 hover:bg-white/5 transition">
          <span class="text-[10px] text-[#7A8FA6] font-bold">03</span>
          <span class="text-[11px] font-semibold text-[#7A8FA6] tracking-widest">UPLOAD FILES</span>
        </div>
        <div class="side-item rounded border border-transparent px-3 py-2.5 flex items-center gap-3 hover:bg-white/5 transition">
          <span class="text-[10px] text-[#7A8FA6] font-bold">04</span>
          <span class="text-[11px] font-semibold text-[#7A8FA6] tracking-widest">PAST RESULTS</span>
        </div>
        <div class="side-item rounded border border-transparent px-3 py-2.5 flex items-center gap-3 hover:bg-white/5 transition cursor-pointer" onclick="openSettings()">
          <span class="text-[10px] text-[#7A8FA6] font-bold">05</span>
          <span class="text-[11px] font-semibold text-[#7A8FA6] tracking-widest">SETTINGS</span>
        </div>
        
        <div class="flex-1"></div>
        
        <div class="rounded border border-[#153245] p-3 bg-[#060D14]">
          <div class="flex items-center gap-2 mb-1.5">
            <svg viewBox="0 0 24 24" fill="none" stroke="#19E6D0" stroke-width="2" class="w-4 h-4"><path d="M12 2l8 3v6c0 5-3.5 9.5-8 11-4.5-1.5-8-6-8-11V5l8-3z"/></svg>
            <div class="text-[9.5px] font-bold text-white tracking-widest">SECURE CODE</div>
          </div>
          <p class="text-[8.5px] text-[#7A8FA6] leading-tight mb-1">Better tomorrow. AI-powered analysis for safer software.</p>
          <div class="text-[8.5px] text-[#19E6D0]">v1.0.0</div>
        </div>
      </aside>

      <section class="flex-1 flex flex-col gap-4 min-w-0">
        
        <div class="rounded border border-[#153245] bg-[#060D14] p-3">
          <div class="text-[10px] text-[#19E6D0] mb-3 tracking-widest">// TARGET SOURCE</div>
          <div class="flex gap-4">
            <div class="flex-1 flex flex-col gap-2">
              <div class="flex gap-2">
                <div class="flex-1 flex items-center gap-2 px-2 py-1.5 border border-[#153245] bg-[#03070A]">
                  <svg viewBox="0 0 24 24" fill="none" stroke="#7A8FA6" stroke-width="1.5" class="w-3.5 h-3.5"><path d="M9 19c-4 1.5-4-2.5-6-3m12 5v-3.5c0-1 .1-1.4-.5-2 2.8-.3 5.5-1.4 5.5-6a4.6 4.6 0 0 0-1.3-3.2 4.3 4.3 0 0 0-.1-3.2s-1-.3-3.3 1.3a11 11 0 0 0-6 0C7.9 1.8 6.9 2.1 6.9 2.1a4.3 4.3 0 0 0-.1 3.2A4.6 4.6 0 0 0 5.5 8.5c0 4.6 2.7 5.7 5.5 6-.6.6-.6 1.2-.5 2V21"/></svg>
                  <input id="githubUrl" type="text" placeholder="https://github.com/username/your-repo" class="w-full bg-transparent outline-none text-[11px] text-white placeholder-[#4A6B7D]"/>
                </div>
                <button id="githubScanBtn" class="px-3 py-1.5 border border-[#19E6D0]/50 text-[#19E6D0] text-[10.5px] font-bold hover:bg-[#19E6D0]/10 transition whitespace-nowrap">SCAN REPO</button>
              </div>
              <div class="flex gap-2 items-stretch">
                <div id="dropZone" class="flex-1 border border-dashed border-[#19E6D0]/30 bg-[#19E6D0]/[0.02] px-3 py-2 flex items-center justify-center gap-2 transition">
                  <svg viewBox="0 0 24 24" fill="none" stroke="#19E6D0" stroke-width="1.5" class="w-4 h-4"><path d="M17 16h1a4 4 0 0 0 0-8h-1.3A7 7 0 0 0 3 10a4.5 4.5 0 0 0 1.5 8.8H9"/><path d="M12 12v9M9 15l3-3 3 3"/></svg>
                  <span class="text-[10.5px] text-[#7A8FA6] tracking-widest">DROP .ZIP / FOLDER TO TARGET</span>
                </div>
                <button id="chooseZipBtn" class="px-4 py-1.5 border border-[#153245] text-[#7A8FA6] text-[10.5px] font-bold hover:text-white transition">.ZIP</button>
                <button id="chooseFolderBtn" class="px-4 py-1.5 border border-[#153245] text-[#7A8FA6] text-[10.5px] font-bold hover:text-white transition">FOLDER</button>
              </div>
              <input id="zipInput" type="file" accept=".zip" hidden /><input id="folderInput" type="file" webkitdirectory directory multiple style="display:none" />
              <p id="uploadStatus" class="text-[9px] text-[#7A8FA6] text-center mt-1">Supported: .zip | folder (max 500 files, 50MB)</p>
            </div>

            <div class="w-[170px] shrink-0 flex flex-col justify-between">
              <div class="flex flex-col gap-2">
                <label id="lblOptSecurity" class="flex items-center gap-2 cursor-pointer select-none"><span id="optSecurity" class="opt-box w-3.5 h-3.5 border border-[#19E6D0] flex items-center justify-center bg-[#19E6D0]"><svg viewBox="0 0 24 24" fill="none" stroke="#000" stroke-width="4" class="w-2.5 h-2.5"><path d="M5 12l5 5L20 7"/></svg></span><span class="text-[10px] text-white tracking-widest">SECURITY SCAN</span></label>
                <label id="lblOptQuality" class="flex items-center gap-2 cursor-pointer select-none"><span id="optQuality" class="opt-box w-3.5 h-3.5 border border-[#19E6D0] flex items-center justify-center bg-[#19E6D0]"><svg viewBox="0 0 24 24" fill="none" stroke="#000" stroke-width="4" class="w-2.5 h-2.5"><path d="M5 12l5 5L20 7"/></svg></span><span class="text-[10px] text-white tracking-widest">CODE QUALITY</span></label>
                <label id="lblOptDependencies" class="flex items-center gap-2 cursor-pointer select-none"><span id="optDependencies" class="opt-box w-3.5 h-3.5 border border-[#19E6D0] flex items-center justify-center bg-[#19E6D0]"><svg viewBox="0 0 24 24" fill="none" stroke="#000" stroke-width="4" class="w-2.5 h-2.5"><path d="M5 12l5 5L20 7"/></svg></span><span class="text-[10px] text-white tracking-widest">DEPENDENCIES</span></label>
                <label id="lblOptDetailed" class="hidden"><span id="optDetailed"></span></label>
              </div>
              <button id="startScanBtn" class="mt-2 w-full py-2 bg-[#19E6D0] text-black font-bold text-[11px] flex items-center justify-center gap-1 hover:brightness-110 transition tracking-widest"><svg viewBox="0 0 24 24" fill="currentColor" class="w-3 h-3"><path d="M8 5v14l11-7z"/></svg>INITIATE SCAN</button>
            </div>
          </div>
        </div>

        <div class="grid grid-cols-3 gap-4">
          <div class="rounded border border-[#153245] bg-[#060D14] p-3 relative overflow-hidden flex flex-col justify-between h-[100px]">
            <svg viewBox="0 0 100 100" class="absolute left-2 top-1/2 -translate-y-1/2 w-[85px] h-[85px]">
              <defs><linearGradient id="radarGrad" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="#1EF0A0" stop-opacity="0.8"/><stop offset="100%" stop-color="#1EF0A0" stop-opacity="0"/></linearGradient></defs>
              <circle cx="50" cy="50" r="45" fill="none" stroke="#19E6D0" stroke-width="1" opacity="0.3" stroke-dasharray="4 2"/>
              <circle cx="50" cy="50" r="30" fill="none" stroke="#19E6D0" stroke-width="1" opacity="0.5"/>
              <circle cx="50" cy="50" r="15" fill="none" stroke="#19E6D0" stroke-width="1" opacity="0.7"/>
              <path d="M50 50 L50 5 A45 45 0 0 1 95 50 Z" fill="url(#radarGrad)"/>
              <circle cx="50" cy="50" r="2.5" fill="#1EF0A0" />
            </svg>
            <div class="relative z-10 text-[9px] text-[#7A8FA6] tracking-widest text-right">// SEC_SCORE</div>
            <div class="relative z-10 flex items-center justify-end h-full pr-4"><div class="flex items-baseline gap-1"><div id="riskScore" class="text-[32px] font-bold text-[#1EF0A0] leading-none">—</div><div class="text-[11px] text-[#7A8FA6] mb-1">/100</div></div></div>
            <div class="relative z-10 text-[8px] text-[#1EF0A0] text-center tracking-widest mt-1">SYSTEM SECURE</div>
          </div>

          <div class="rounded border border-[#153245] bg-[#060D14] p-3 flex flex-col justify-between h-[100px]">
            <div class="text-[9px] text-[#7A8FA6] mb-1 tracking-widest">// THREAT_LEVELS</div>
            <div class="flex flex-col gap-1.5 justify-center flex-1">
              <div class="flex items-center justify-between"><span class="text-[8.5px] text-[#FF4D5A] w-12 tracking-widest">HIGH</span><div class="flex-1 h-1.5 bg-[#1A0A10] mx-2"><div id="barHigh" class="h-full w-[0%] bg-[#FF4D5A] transition-all"></div></div><span id="cntHigh" class="text-[9px] text-white font-bold">0</span></div>
              <div class="flex items-center justify-between"><span class="text-[8.5px] text-[#F5C518] w-12 tracking-widest">MEDIUM</span><div class="flex-1 h-1.5 bg-[#1A160A] mx-2"><div id="barMed" class="h-full w-[0%] bg-[#F5C518] transition-all"></div></div><span id="cntMedLow" class="text-[9px] text-white font-bold">0</span></div>
              <div class="flex items-center justify-between"><span class="text-[8.5px] text-[#0084FF] w-12 tracking-widest">LOW</span><div class="flex-1 h-1.5 bg-[#0A111E] mx-2"><div id="barLow" class="h-full w-[0%] bg-[#0084FF] transition-all"></div></div><span class="text-[9px] text-white font-bold">0</span></div>
            </div>
          </div>

          <div class="rounded border border-[#153245] bg-[#060D14] p-3 flex flex-col justify-between h-[100px]">
            <div class="text-[9px] text-[#7A8FA6] mb-1 tracking-widest">// SCAN_STATS</div>
            <div class="flex justify-between items-start flex-1">
              <div class="flex flex-col gap-1">
                <div class="flex justify-between w-[90px]"><span class="text-[9px] text-[#7A8FA6] tracking-widest">FILES</span><span id="statFiles" class="text-[10px] text-white font-bold">—</span></div>
                <div class="flex justify-between w-[90px]"><span class="text-[9px] text-[#7A8FA6] tracking-widest">TIME</span><span id="statTime" class="text-[10px] text-white font-bold">00:00:00</span></div>
                <div class="flex justify-between w-[90px]"><span class="text-[9px] text-[#7A8FA6] tracking-widest">ISSUES</span><span id="statIssues" class="text-[10px] text-white font-bold">—</span></div>
              </div>
              <div id="progressPct" class="text-[28px] font-bold text-[#1EF0A0] leading-none">0%</div>
            </div>
            <div class="w-full h-1 bg-[#03070A] mt-1"><div id="progressFill" class="h-full w-[0%] bg-[#1EF0A0] transition-all"></div></div>
          </div>
        </div>

        <div class="grid grid-cols-[1.8fr_1fr] gap-4 flex-1 min-h-0">
          
          <div class="rounded border border-[#153245] bg-[#03070A] p-3 flex flex-col min-h-0">
            <div class="flex items-center justify-between mb-2 border-b border-[#153245] pb-1.5">
              <span class="text-[10px] text-[#19E6D0] tracking-widest">// TERMINAL — AI ASSISTANT REPORT</span>
              <div class="flex items-center gap-3"><span class="text-[9px] text-[#7A8FA6] cursor-pointer hover:text-white">[ EXPAND ]</span><span id="scanTitle" class="text-[9px] text-[#7A8FA6]">IDLE</span></div>
            </div>
            <div id="terminalBody" class="flex-1 overflow-y-auto px-1 py-1 text-[11px] leading-[1.6]">
              <div class="text-[#7A8FA6]">[BOOT] Neural core ready. Waiting for target...</div>
            </div>
            <div class="mt-2 flex items-center gap-2 px-3 py-1.5 border border-[#153245] bg-[#060D14]"><span class="text-[#19E6D0]">&gt;</span><input id="chatInput" type="text" placeholder="ask neural core about a finding..." class="flex-1 bg-transparent outline-none text-[10px] text-white placeholder-[#4A6B7D]"/><button id="chatSendBtn" class="px-3 py-1 bg-[#19E6D0] text-black font-bold text-[9px] tracking-widest hover:brightness-110" type="button">SEND</button></div>
          </div>

          <div class="rounded border border-[#153245] bg-[#060D14] p-3 flex flex-col min-h-0">
            <div class="flex items-center justify-between mb-2 border-b border-[#153245] pb-1.5"><span class="text-[10px] text-[#19E6D0] tracking-widest">// THREAT_LOG</span><a href="#" id="viewAllBtn" class="text-[9px] text-[#19E6D0] hover:underline">VIEW_ALL</a></div>
            <div class="flex items-center gap-2 mb-1"><span id="gateBadge" class="hidden"></span></div><div id="aiBanner" class="hidden rounded px-2 py-1 mb-1 text-[9px]"></div>
            
            <div id="issueList" class="space-y-2 overflow-y-auto flex-1 pr-1">
              <div class="text-[10px] text-[#7A8FA6] text-center py-4">No results yet.</div>
            </div>
          </div>

        </div>
      </section>
    </main>

    <footer class="flex justify-between items-center pt-2 mt-2 border-t border-[#153245] text-[8px] text-[#4A6B7D] tracking-widest shrink-0">
      <div class="flex gap-4"><span>LIVE_CORE_FEED</span><span>DASH: 0%</span><span>NET: 0.00GB</span><span>SECURE_COMMS</span></div>
      <span>ENCRYPTED // PULSE 1.0</span>
    </footer>
  </div>

  <div id="viewAllModal" class="fixed inset-0 bg-black/80 z-50 hidden flex-col items-center justify-center p-4"><div class="bg-[#0B101E] border border-[#19E6D0]/30 rounded-lg w-full max-w-4xl max-h-[85vh] flex flex-col shadow-2xl"><div class="flex justify-between items-center p-4 border-b border-[#19E6D0]/20"><h2 class="text-white font-bold text-lg">All Scan Results <span id="viewAllCount" class="text-[#19E6D0]"></span></h2><button id="closeViewAllBtn" class="text-gray-400 hover:text-white text-2xl leading-none">&times;</button></div><div id="viewAllList" class="p-4 overflow-y-auto flex flex-col gap-3"></div></div></div>
  <div id="settingsModal" class="fixed inset-0 bg-black/70 hidden z-50 flex items-center justify-center"><div class="bg-[#08121C] border border-[#19E6D0]/30 rounded-xl p-6 w-[400px]"><h2 class="text-white text-lg font-bold mb-4">Settings</h2><div class="mb-4"><label class="text-[#D6E6F0] text-sm block mb-1">Retention Days (1 or 2)</label><input type="number" id="setRetention" min="1" max="2" class="w-full bg-[#0F1E2E] border border-[#19E6D0]/30 rounded p-2 text-white"></div><div class="mb-4"><label class="text-[#D6E6F0] text-sm block mb-1">Language</label><select id="setLanguage" class="w-full bg-[#0F1E2E] border border-[#19E6D0]/30 rounded p-2 text-white"><option value="en">English</option><option value="roman_urdu">Roman Urdu</option></select></div><div class="mb-4 flex items-center gap-2"><input type="checkbox" id="setAI" class="w-4 h-4"><label class="text-[#D6E6F0] text-sm">Enable AI Explanation</label></div><div class="flex justify-end gap-2 mt-6"><button id="btnCancelSettings" class="px-4 py-2 text-txt-dim hover:text-white">Cancel</button><button id="btnSaveSettings" class="px-4 py-2 bg-[#19E6D0] text-[#08121C] rounded font-bold">Save</button></div></div></div>

  <script>
    document.addEventListener('DOMContentLoaded', () => {
        // Override renderResults to populate new UI dynamically
        window.renderResults = function(data) {
            const issues = data.issues || [];
            let high = 0, med = 0, low = 0;
            issues.forEach(i => {
                if (i.severity === 'HIGH') high++;
                else if (i.severity === 'MEDIUM') med++;
                else low++;
            });

            document.getElementById('cntHigh').innerText = high;
            document.getElementById('cntMedLow').innerText = med;
            document.getElementById('statIssues').innerText = issues.length;

            const total = issues.length || 1;
            document.getElementById('barHigh').style.width = Math.min(100, (high/total)*100) + '%';
            document.getElementById('barMed').style.width = Math.min(100, (med/total)*100) + '%';
            document.getElementById('barLow').style.width = Math.min(100, (low/total)*100) + '%';

            let riskScore = 100 - (high*10) - (med*5) - (low*2);
            if(riskScore < 0) riskScore = 0;
            document.getElementById('riskScore').innerText = riskScore;

            const list = document.getElementById('issueList');
            list.innerHTML = '';
            if (issues.length === 0) {
                list.innerHTML = '<div class="text-[#7A8FA6] text-center py-4">No issues found. Clean!</div>';
                return;
            }

            issues.forEach((issue, index) => {
                let color = issue.severity === 'HIGH' ? '#FF4D5A' : (issue.severity === 'MEDIUM' ? '#F5C518' : '#0084FF');
                let bg = issue.severity === 'HIGH' ? 'bg-[#FF4D5A]/10' : (issue.severity === 'MEDIUM' ? 'bg-[#F5C518]/10' : 'bg-[#0084FF]/10');
                
                list.innerHTML += `
                <div class="border border-[#153245] border-l-2 border-l-[${color}] bg-[#0A1018] p-2 flex flex-col mb-2">
                    <div class="flex justify-between items-start mb-1">
                        <span class="text-[8px] text-[${color}] border border-[${color}]/30 px-1 ${bg}">${issue.severity}</span>
                        <span class="text-[9.5px] text-white">${issue.type || issue.rule_id || 'Issue'}</span>
                    </div>
                    <div class="text-[8px] text-[#7A8FA6] mb-1.5">${issue.file} :: line ${issue.line}</div>
                    <div class="flex gap-1.5">
                        <button class="px-2 py-0.5 bg-transparent border border-[#19E6D0]/40 text-[#19E6D0] text-[8px] hover:bg-[#19E6D0]/10" onclick="explainIssue(${index})">AI EXPLAIN</button>
                        <button class="px-2 py-0.5 bg-transparent border border-[#7A8FA6]/40 text-[#7A8FA6] text-[8px] hover:bg-white/5" onclick="ignoreIssue(${index})">IGNORE</button>
                    </div>
                </div>`;
            });
        };

        // Override logLine
        window.logLine = function(text, color) {
            const term = document.getElementById('terminalBody');
            const div = document.createElement('div');
            div.className = 'text-[11px] leading-[1.6] mt-1';
            if (text.includes('[!]')) div.className += ' text-[#FF4D5A]';
            else if (text.includes('[/]')) div.className += ' text-[#1EF0A0]';
            else if (text.includes('root@')) div.className += ' text-white';
            else div.className += ' text-[#7A8FA6]';
            div.innerText = text;
            term.appendChild(div);
            term.scrollTop = term.scrollHeight;
        };
        
        // Intercept scan start
        const btn = document.getElementById('startScanBtn');
        if(btn) {
            btn.addEventListener('click', () => {
                document.getElementById('terminalBody').innerHTML = '';
                logLine('[BOOT] Initializing scan...');
                document.getElementById('issueList').innerHTML = '<div class="text-[#7A8FA6] text-center py-4">Scanning...</div>';
            });
        }
    });
  </script>
</body>
</html>
"""

with open(out, 'w', encoding='utf-8') as f:
    f.writelines(head)
    f.write(body)