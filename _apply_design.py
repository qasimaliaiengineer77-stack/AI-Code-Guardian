import re
p = r'C:\Projects\AI-Code-Guardian\frontend\index.html'
with open(p, encoding='utf-8') as f:
    lines = f.read().split('\n')

# lines[0:130] = CSS/head (unchanged)
# lines[130:554] = body (replace)
# lines[554:] = JS + close (unchanged)

NEW_BODY = r'''<body class="min-h-screen">
<div class="bg-grid"></div>
<div class="bg-vignette"></div>
<div class="relative z-10 min-w-[1366px] max-w-[1600px] mx-auto w-full flex flex-col min-h-screen">
  <header class="flex items-center justify-between px-6 py-3 border-b border-[#163349]">
    <div class="flex items-center gap-3">
      <svg viewBox="0 0 60 60" class="w-9 h-9"><polygon points="30,3 55,16 55,44 30,57 5,44 5,16" fill="rgba(25,230,208,0.08)" stroke="#19E6D0" stroke-width="1.6"/><text x="30" y="36" text-anchor="middle" font-family="Inter" font-weight="800" font-size="14" fill="#19E6D0">AI</text></svg>
      <div class="leading-tight"><div class="text-[15px] font-bold text-white tracking-wide">CODE GUARDIAN <span class="text-[#19E6D0]">// AI</span></div><div class="text-[10.5px] text-txt-dim font-mono mt-0.5">FIND FIXES | FIX CODE | BUILD SAFER SOFTWARE</div></div>
    </div>
    <div class="flex items-center gap-3 text-[10.5px] font-mono">
      <div class="flex items-center gap-2 px-3 py-1.5 rounded-full border border-[#1EF0A0]/50 bg-[#1EF0A0]/5"><span class="w-1.5 h-1.5 rounded-full bg-[#1EF0A0] pulse-glow"></span><span class="text-[#1EF0A0]">NEURAL CORE: ONLINE</span></div>
      <div class="px-3 py-1.5 rounded-full border border-[#19E6D0]/40 text-[#19E6D0]">USER: GUEST_A1</div>
      <div class="px-3 py-1.5 rounded-full border border-[#7A8FA6]/40 text-[#9AB0C2]">BUILD: UNLOCKED</div>
    </div>
  </header>
  <main class="flex gap-4 px-4 pt-4 pb-6 flex-1">
    <aside class="w-[190px] shrink-0 flex flex-col gap-1.5">
      <div class="text-[10px] text-txt-dim font-mono mb-1 px-1">// NAVIGATION</div>
      <div class="side-item glow-border-active rounded-lg px-3 py-2 flex items-center gap-2.5 bg-[#0E1E2E]"><span class="text-[10.5px] font-mono text-[#19E6D0] font-bold">01</span><span class="text-[11.5px] font-bold text-white tracking-wide">DASHBOARD</span></div>
      <div class="side-item rounded-lg px-3 py-2 flex items-center gap-2.5"><span class="text-[10.5px] font-mono text-[#7A8FA6] font-bold">02</span><span class="text-[11.5px] font-semibold text-[#9AB0C2]">GITHUB LINK</span></div>
      <div class="side-item rounded-lg px-3 py-2 flex items-center gap-2.5"><span class="text-[10.5px] font-mono text-[#7A8FA6] font-bold">03</span><span class="text-[11.5px] font-semibold text-[#9AB0C2]">UPLOAD FILES</span></div>
      <div class="side-item rounded-lg px-3 py-2 flex items-center gap-2.5"><span class="text-[10.5px] font-mono text-[#7A8FA6] font-bold">04</span><span class="text-[11.5px] font-semibold text-[#9AB0C2]">PAST RESULTS</span></div>
      <div class="side-item rounded-lg px-3 py-2 flex items-center gap-2.5" onclick="openSettings()" style="cursor:pointer"><span class="text-[10.5px] font-mono text-[#7A8FA6] font-bold">05</span><span class="text-[11.5px] font-semibold text-[#9AB0C2]">SETTINGS</span></div>
      <div class="flex-1"></div>
      <div class="glow-border rounded-lg p-3 bg-[#0E1E2E]"><div class="text-[10px] text-txt-dim font-mono mb-2">// SYSTEM SENSE</div><div class="flex items-center gap-2 mb-1"><svg viewBox="0 0 60 60" class="w-5 h-5"><polygon points="30,3 55,16 55,44 30,57 5,44 5,16" fill="rgba(25,230,208,0.1)" stroke="#19E6D0" stroke-width="2"/><text x="30" y="36" text-anchor="middle" font-family="Inter" font-weight="800" font-size="13" fill="#19E6D0">AI</text></svg><div class="text-[11px] font-bold text-white leading-tight">SECURE CODE<br/>BETTER TOMORROW</div></div><p class="text-[10px] text-txt-dim leading-snug">AI-powered analysis for safer projects.</p><div class="text-[10px] text-txt-dim font-mono pt-2">v1.0.0</div></div>
    </aside>
    <section class="flex-1 min-w-0 flex flex-col gap-3">
      <div class="glow-border rounded-xl bg-[#0B1826] p-4">
        <div class="text-[10.5px] font-mono text-[#19E6D0] mb-3">// TARGET SOURCE</div>
        <div class="grid grid-cols-3 gap-3">
          <div class="col-span-2 flex flex-col gap-2">
            <div class="flex gap-2">
              <div class="flex-1 flex items-center gap-2 px-3 py-2 rounded-lg border border-[#163349] bg-[#08121C]"><svg viewBox="0 0 24 24" fill="none" stroke="#19E6D0" stroke-width="1.6" class="w-4 h-4 shrink-0"><path d="M9 19c-4 1.5-4-2.5-6-3m12 5v-3.5c0-1 .1-1.4-.5-2 2.8-.3 5.5-1.4 5.5-6a4.6 4.6 0 0 0-1.3-3.2 4.3 4.3 0 0 0-.1-3.2s-1-.3-3.3 1.3a11 11 0 0 0-6 0C7.9 1.8 6.9 2.1 6.9 2.1a4.3 4.3 0 0 0-.1 3.2A4.6 4.6 0 0 0 5.5 8.5c0 4.6 2.7 5.7 5.5 6-.6.6-.6 1.2-.5 2V21"/></svg><input id="githubUrl" type="text" placeholder="https://github.com/username/your-repo" class="w-full bg-transparent outline-none text-[12px] text-white placeholder-[#516679]"/></div>
              <button id="githubScanBtn" class="px-3 py-2 rounded-lg border border-[#19E6D0]/60 text-[#19E6D0] text-[11.5px] font-semibold hover:bg-[#19E6D0]/10 transition whitespace-nowrap">SCAN REPO</button>
            </div>
            <div id="dropZone" class="rounded-lg border-2 border-dashed border-[#19E6D0]/30 bg-[#19E6D0]/[0.02] px-3 py-3 flex items-center justify-center gap-2 transition-colors"><svg viewBox="0 0 24 24" fill="none" stroke="#19E6D0" stroke-width="1.6" class="w-5 h-5"><path d="M17 16h1a4 4 0 0 0 0-8h-1.3A7 7 0 0 0 3 10a4.5 4.5 0 0 0 1.5 8.8H9"/><path d="M12 12v9M9 15l3-3 3 3"/></svg><span class="text-[11.5px] text-[#9AB0C2]">DROP .ZIP / FOLDER TO TARGET</span><button id="chooseZipBtn" class="px-2.5 py-1 rounded border border-[#19E6D0]/50 text-[#19E6D0] text-[11px] font-medium hover:bg-[#19E6D0]/10">.ZIP</button><button id="chooseFolderBtn" class="px-2.5 py-1 rounded border border-[#1EF0A0]/50 text-[#1EF0A0] text-[11px] font-medium hover:bg-[#1EF0A0]/10">FOLDER</button></div>
            <input id="zipInput" type="file" accept=".zip" hidden />
            <input id="folderInput" type="file" webkitdirectory directory multiple style="display:none" />
            <p id="uploadStatus" class="text-[10.5px] text-txt-dim text-center">Supported: .zip | folder (max 500 files, 50MB)</p>
          </div>
          <div class="flex flex-col gap-1.5">
            <label id="lblOptSecurity" class="flex items-center gap-2 cursor-pointer select-none"><span id="optSecurity" class="opt-box w-3.5 h-3.5 rounded border-2 border-[#19E6D0] flex items-center justify-center bg-[#19E6D0] shrink-0"><svg viewBox="0 0 24 24" fill="none" stroke="#08121C" stroke-width="3" class="w-2.5 h-2.5"><path d="M5 12l5 5L20 7"/></svg></span><span class="text-[10.5px] text-[#D6E6F0]">SECURITY SCAN</span></label>
            <label id="lblOptQuality" class="flex items-center gap-2 cursor-pointer select-none"><span id="optQuality" class="opt-box w-3.5 h-3.5 rounded border-2 border-[#19E6D0] flex items-center justify-center bg-[#19E6D0] shrink-0"><svg viewBox="0 0 24 24" fill="none" stroke="#08121C" stroke-width="3" class="w-2.5 h-2.5"><path d="M5 12l5 5L20 7"/></svg></span><span class="text-[10.5px] text-[#D6E6F0]">CODE QUALITY</span></label>
            <label id="lblOptDependencies" class="flex items-center gap-2 cursor-pointer select-none"><span id="optDependencies" class="opt-box w-3.5 h-3.5 rounded border-2 border-[#19E6D0] flex items-center justify-center bg-[#19E6D0] shrink-0"><svg viewBox="0 0 24 24" fill="none" stroke="#08121C" stroke-width="3" class="w-2.5 h-2.5"><path d="M5 12l5 5L20 7"/></svg></span><span class="text-[10.5px] text-[#D6E6F0]">DEPENDENCIES</span></label>
            <label id="lblOptDetailed" class="flex items-center gap-2 cursor-pointer select-none"><span id="optDetailed" class="opt-box w-3.5 h-3.5 rounded border-2 border-[#19E6D0] flex items-center justify-center bg-[#19E6D0] shrink-0"><svg viewBox="0 0 24 24" fill="none" stroke="#08121C" stroke-width="3" class="w-2.5 h-2.5"><path d="M5 12l5 5L20 7"/></svg></span><span class="text-[10.5px] text-[#D6E6F0]">DETAILED</span></label>
            <button id="startScanBtn" class="mt-2 w-full py-2 rounded-lg bg-gradient-to-r from-[#1EF0A0] to-[#19E6D0] text-[#08121C] font-bold text-[12px] flex items-center justify-center gap-1.5 hover:brightness-110 transition shadow-[0_0_20px_rgba(30,240,160,0.35)] disabled:opacity-50 disabled:cursor-not-allowed"><svg viewBox="0 0 24 24" fill="currentColor" class="w-3.5 h-3.5"><path d="M8 5v14l11-7z"/></svg>INITIATE SCAN</button>
          </div>
        </div>
      </div>
      <div class="grid grid-cols-3 gap-3">
        <div class="glow-border rounded-xl bg-[#0B1826] p-3"><div class="text-[10px] font-mono text-txt-dim">// RISK SCORE</div><div class="mt-1 flex items-baseline gap-1"><div class="text-[32px] font-bold text-[#1EF0A0] leading-none">92</div><div class="text-[14px] text-txt-dim">/100</div></div><div class="text-[10px] text-[#1EF0A0] font-mono mt-1">NEURAL SCORE</div></div>
        <div class="glow-border rounded-xl bg-[#0B1826] p-3"><div class="text-[10px] font-mono text-txt-dim mb-2">// THREAT LEVELS</div><div class="space-y-1">
          <div class="flex items-center gap-1.5 text-[9.5px] font-mono"><span class="w-[42px] text-[#FF4D5A]">CRITICAL</span><div class="flex-1 h-1.5 bg-[#0A1826] rounded"><div class="h-full w-[20%] bg-[#FF4D5A] rounded"></div></div><span class="text-[#FF4D5A] w-3 text-right">0</span></div>
          <div class="flex items-center gap-1.5 text-[9.5px] font-mono"><span class="w-[42px] text-[#FF4D5A]">HIGH</span><div class="flex-1 h-1.5 bg-[#0A1826] rounded"><div class="h-full w-[40%] bg-[#FF4D5A] rounded"></div></div><span id="cntHigh" class="text-white w-3 text-right font-bold">0</span></div>
          <div class="flex items-center gap-1.5 text-[9.5px] font-mono"><span class="w-[42px] text-[#F5C518]">MEDIUM</span><div class="flex-1 h-1.5 bg-[#0A1826] rounded"><div class="h-full w-[30%] bg-[#F5C518] rounded"></div></div><span id="cntMedLow" class="text-white w-3 text-right font-bold">0</span></div>
          <div class="flex items-center gap-1.5 text-[9.5px] font-mono"><span class="w-[42px] text-[#7A8FA6]">LOW</span><div class="flex-1 h-1.5 bg-[#0A1826] rounded"><div class="h-full w-[15%] bg-[#7A8FA6] rounded"></div></div><span class="text-[#7A8FA6] w-3 text-right">0</span></div>
        </div></div>
        <div class="glow-border rounded-xl bg-[#0B1826] p-3"><div class="text-[10px] font-mono text-txt-dim mb-2">// SCAN STATUS</div><div class="space-y-1.5 text-[11px]">
          <div class="flex justify-between"><span class="text-txt-dim font-mono">FILES</span><span id="statFiles" class="text-white font-semibold">—</span></div>
          <div class="flex justify-between"><span class="text-txt-dim font-mono">ISSUES</span><span id="statIssues" class="text-white font-semibold">—</span></div>
          <div class="flex justify-between"><span class="text-txt-dim font-mono">TIME</span><span id="statTime" class="text-white font-semibold">00:00:00</span></div>
        </div><div class="mt-2 relative h-1.5 rounded-full bg-[#0A1826] overflow-hidden"><div id="progressFill" class="progress-fill h-full rounded-full" style="width:0%"></div></div><div id="progressPct" class="text-right text-[10.5px] text-[#19E6D0] font-semibold mt-1">0%</div></div>
      </div>
      <div class="grid grid-cols-[2fr_1fr] gap-3 flex-1 min-h-0">
        <div class="glow-border rounded-xl bg-[#061019] p-3 flex flex-col min-h-0"><div class="flex items-center justify-between mb-2"><span class="text-[11px] font-mono text-[#19E6D0]">// TERMINAL — AI ASSISTANT REPORT</span><span id="scanTitle" class="text-[10px] font-mono text-txt-dim">IDLE</span></div><div id="terminalBody" class="flex-1 overflow-y-auto thin-scroll px-1 py-1"><div class="font-mono text-[11px] leading-5 text-[#7A8FA6]">Ready. Upload a .zip or Folder to begin.</div></div><div class="mt-2 flex items-center gap-2 px-2 py-1.5 rounded border border-[#163349] bg-[#08121C]"><span class="text-[#19E6D0] font-mono text-[11px]">&gt;</span><input id="chatInput" type="text" placeholder="Ask AI about a finding..." class="flex-1 bg-transparent outline-none text-[11px] text-white placeholder-[#516679]"/><button id="chatSendBtn" class="px-2 py-0.5 rounded bg-[#1EF0A0] text-[#08121C] font-bold text-[10.5px] hover:brightness-110" type="button">SEND</button></div></div>
        <div class="glow-border rounded-xl bg-[#0B1826] p-3 flex flex-col min-h-0"><div class="flex items-center justify-between mb-2"><span class="text-[11px] font-mono text-[#19E6D0]">// THREAT LOG</span><a href="#" id="viewAllBtn" class="text-[10.5px] text-[#19E6D0] hover:underline">VIEW ALL</a></div><div class="flex items-center gap-2 mb-2 text-[10px] font-mono"><span id="gateBadge" class="hidden"></span></div><div id="aiBanner" class="hidden rounded px-2 py-1 mb-2 text-[11px] leading-snug"></div><div id="issueList" class="space-y-1.5 overflow-y-auto thin-scroll pr-1 flex-1"><div class="text-[10.5px] text-txt-dim text-center py-4">No results yet.</div></div></div>
      </div>
    </section>
  </main>
  <footer class="px-5 py-2 border-t border-[#163349] text-[10px] font-mono text-txt-dim flex justify-between"><span>LIVE CORE FEED | DASH: 0% | NET: 0.00GB | SECURE COMMS</span><span>ENCRYPTED // PULSE 1.0</span></footer>
</div>
<div id="viewAllModal" class="fixed inset-0 bg-black/80 z-50 hidden flex-col items-center justify-center p-4"><div class="bg-[#0B101E] border border-[#19E6D0]/30 rounded-lg w-full max-w-4xl max-h-[85vh] flex flex-col shadow-2xl"><div class="flex justify-between items-center p-4 border-b border-[#19E6D0]/20"><h2 class="text-white font-bold text-lg">All Scan Results <span id="viewAllCount" class="text-[#19E6D0]"></span></h2><button id="closeViewAllBtn" class="text-gray-400 hover:text-white text-2xl leading-none">&times;</button></div><div id="viewAllList" class="p-4 overflow-y-auto flex flex-col gap-3 thin-scroll"></div></div></div>
<div id="settingsModal" class="fixed inset-0 bg-black/70 hidden z-50 flex items-center justify-center"><div class="bg-[#08121C] border border-[#19E6D0]/30 rounded-xl p-6 w-[400px]"><h2 class="text-white text-lg font-bold mb-4">Settings</h2><div class="mb-4"><label class="text-[#D6E6F0] text-sm block mb-1">Retention Days (1 or 2)</label><input type="number" id="setRetention" min="1" max="2" class="w-full bg-[#0F1E2E] border border-[#19E6D0]/30 rounded p-2 text-white"></div><div class="mb-4"><label class="text-[#D6E6F0] text-sm block mb-1">Language</label><select id="setLanguage" class="w-full bg-[#0F1E2E] border border-[#19E6D0]/30 rounded p-2 text-white"><option value="en">English</option><option value="roman_urdu">Roman Urdu</option></select></div><div class="mb-4 flex items-center gap-2"><input type="checkbox" id="setAI" class="w-4 h-4"><label class="text-[#D6E6F0] text-sm">Enable AI Explanation</label></div><div class="flex justify-end gap-2 mt-6"><button id="btnCancelSettings" class="px-4 py-2 text-txt-dim hover:text-white">Cancel</button><button id="btnSaveSettings" class="px-4 py-2 bg-[#19E6D0] text-[#08121C] rounded font-bold">Save</button></div></div></div>
'''

new_lines = lines[:130] + NEW_BODY.split('\n') + lines[554:]

with open(p, 'w', encoding='utf-8') as f:
    f.write('\n'.join(new_lines))

print(f"Done. Old: {len(lines)} lines, New: {len(new_lines)} lines")