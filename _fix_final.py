p = r'C:\Projects\AI-Code-Guardian\frontend\index.html'

with open(p, 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Center se purana Terminal aur AI Assistant hatao, naya bada Terminal (Chat ke sath) lagao
old_terminal_and_ai = """        <!-- Terminal log -->
        <div class="mt-4 rounded-xl border border-[#163349] bg-[#061019] overflow-hidden shrink-0">
          <div class="flex items-center justify-between px-3 py-2 border-b border-[#163349]">
            <span class="text-[14px] text-txt-dim font-mono">Terminal Log</span>
            <span class="text-[11px] text-txt-dim font-mono">&times;</span>
          </div>
          <div id="terminalBody" class="h-[105px] overflow-y-auto thin-scroll px-3 py-2">
            <div class="font-mono text-[14px] leading-6 text-[#7A8FA6]">Ready. Upload a .zip or Folder to begin.</div>
          </div>
        </div>
      </div>

      <!-- Card 3: AI Assistant -->
      <div class="glow-border rounded-2xl bg-[#0B1826] p-5 shrink-0">
        <div class="flex items-center gap-3 mb-4">
          <div class="w-9 h-9 rounded-full border border-[#19E6D0]/50 flex items-center justify-center shrink-0">
            <svg viewBox="0 0 24 24" fill="none" stroke="#19E6D0" stroke-width="1.8" class="w-5 h-5 pulse-glow">
              <path d="M3 12h3l2-5 4 10 2-5h4"/>
            </svg>
          </div>
          <div>
            <div class="text-[14.5px] font-semibold text-white">AI Assistant</div>
            <div class="text-[14px] text-txt-dim">
              Ask anything about your scan results, fixes or code quality.
            </div>
          </div>
        </div>
        <div class="rounded-xl border border-[#163349] bg-[#08121C] px-4 py-3 fade-in">
          <div class="flex items-start gap-3">
            <div class="w-7 h-7 rounded-full bg-[#19E6D0]/10 border border-[#19E6D0]/40 flex items-center justify-center shrink-0">
              <svg viewBox="0 0 24 24" fill="none" stroke="#19E6D0" stroke-width="2" class="w-4 h-4">
                <circle cx="12" cy="12" r="9"/>
              </svg>
            </div>
            <div class="text-[12.5px] leading-6 text-[#D6E6F0]">
              <span class="text-[#19E6D0] font-semibold">AI:</span> Upload a project and click <b>Start Scan</b>.<br/>
              I'll explain every issue in plain language once the scan finishes.
            </div>
          </div>
        </div>
      </div>
    </section>"""

new_terminal = """        <!-- Terminal log (Expanded) -->
        <div class="mt-4 rounded-xl border border-[#163349] bg-[#061019] overflow-hidden flex-1 flex flex-col min-h-[250px]">
          <div class="flex items-center justify-between px-3 py-2 border-b border-[#163349]">
            <span class="text-[14px] text-txt-dim font-mono">Terminal Log</span>
            <span class="text-[11px] text-txt-dim font-mono">&times;</span>
          </div>
          <div id="terminalBody" class="flex-1 overflow-y-auto thin-scroll px-3 py-2">
            <div class="font-mono text-[14px] leading-6 text-[#7A8FA6]">Ready. Upload a .zip or Folder to begin.</div>
          </div>
          <!-- Chat Input Box -->
          <div class="flex items-center gap-2 px-3 py-2 border-t border-[#163349] bg-[#08121C] shrink-0">
            <input id="chatInput" type="text" placeholder="Ask a question about the scan results..." class="flex-1 bg-transparent outline-none text-[12.5px] text-white placeholder-[#516679] w-full"/>
            <button class="text-[#7A8FA6] hover:text-[#19E6D0] shrink-0" type="button">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" class="w-4 h-4">
                <path d="M21.4 11.6l-8.5 8.5a5 5 0 0 1-7-7l8.5-8.5a3.3 3.3 0 0 1 4.7 4.7l-8.5 8.5a1.7 1.7 0 0 1-2.4-2.4l7.8-7.8"/>
              </svg>
            </button>
            <button id="chatSendBtn" class="w-7 h-7 rounded-md bg-[#1EF0A0] flex items-center justify-center hover:brightness-110 shrink-0" type="button">
              <svg viewBox="0 0 24 24" fill="none" stroke="#08121C" stroke-width="2.4" class="w-3.5 h-3.5">
                <path d="M5 12h14M13 5l7 7-7 7"/>
              </svg>
            </button>
          </div>
        </div>
      </div>
    </section>"""

html = html.replace(old_terminal_and_ai, new_terminal)

# 2. Right side se purana View All aur Chat hatao, naya Center View All aur AI Assistant lagao
old_right = """        <div class="text-right mt-3 shrink-0">
          <a href="#" id="viewAllBtn" class="text-[14px] text-[#19E6D0] hover:underline">View All Results &rarr;</a>
        </div>

        <div class="mt-3 flex items-center gap-2 px-3 py-2 rounded-lg border border-[#163349] bg-[#08121C] shrink-0">
          <input id="chatInput" type="text" placeholder="Ask a question about the scan results..."
                 class="flex-1 bg-transparent outline-none text-[12.5px] text-white placeholder-[#516679] w-full"/>
          <button class="text-[#7A8FA6] hover:text-[#19E6D0] shrink-0" type="button">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" class="w-4 h-4">
              <path d="M21.4 11.6l-8.5 8.5a5 5 0 0 1-7-7l8.5-8.5a3.3 3.3 0 0 1 4.7 4.7l-8.5 8.5a1.7 1.7 0 0 1-2.4-2.4l7.8-7.8"/>
            </svg>
          </button>
          <button id="chatSendBtn" class="w-7 h-7 rounded-md bg-[#1EF0A0] flex items-center justify-center hover:brightness-110 shrink-0" type="button">
            <svg viewBox="0 0 24 24" fill="none" stroke="#08121C" stroke-width="2.4" class="w-3.5 h-3.5">
              <path d="M5 12h14M13 5l7 7-7 7"/>
            </svg>
          </button>
        </div>"""

new_right = """        <div class="text-center mt-3 shrink-0">
          <a href="#" id="viewAllBtn" class="text-[14px] text-[#19E6D0] hover:underline">View All Results &rarr;</a>
        </div>

        <!-- AI Assistant (Moved here) -->
        <div class="mt-3 rounded-xl border border-[#163349] bg-[#08121C] px-4 py-3 fade-in shrink-0">
          <div class="flex items-center gap-3 mb-2">
            <div class="w-7 h-7 rounded-full bg-[#19E6D0]/10 border border-[#19E6D0]/40 flex items-center justify-center shrink-0">
              <svg viewBox="0 0 24 24" fill="none" stroke="#19E6D0" stroke-width="2" class="w-4 h-4">
                <circle cx="12" cy="12" r="9"/>
              </svg>
            </div>
            <div class="text-[13px] font-semibold text-white">AI Assistant</div>
          </div>
          <div class="text-[12px] leading-5 text-[#D6E6F0]">
            <span class="text-[#19E6D0] font-semibold">AI:</span> Upload a project and click <b>Start Scan</b>. I'll explain every issue in plain language once the scan finishes.
          </div>
        </div>"""

html = html.replace(old_right, new_right)

with open(p, 'w', encoding='utf-8') as f:
    f.write(html)