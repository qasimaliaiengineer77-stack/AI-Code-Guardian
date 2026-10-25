$ErrorActionPreference = 'Stop'

$projectRoot = (Get-Location).Path
$path = Join-Path $projectRoot 'frontend\index.html'
if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
    throw "STOP: Run this script from the AI-Code-Guardian project root. Expected: $path"
}

$text = [System.IO.File]::ReadAllText($path)
$pattern = "(?s)        const btn = document\.getElementById\('startScanBtn'\);.*?(?=\r?\n    \}\);)"
$rx = [regex]::new($pattern)
$matches = $rx.Matches($text)
if ($matches.Count -ne 1) {
    throw "STOP: Expected exactly one original placeholder click handler; found $($matches.Count). No file was changed."
}

$backup = Join-Path (Split-Path -Parent $path) 'index.html.before_picker_scan_fix.backup'
if (Test-Path -LiteralPath $backup) {
    throw "STOP: Backup already exists at $backup. No file was changed; rename/inspect that backup before retrying."
}

$new = @'
        // ZIP/folder selection, upload, and scan workflow.
        const zipInput = document.getElementById('zipInput');
        const folderInput = document.getElementById('folderInput');
        const chooseZipBtn = document.getElementById('chooseZipBtn');
        const chooseFolderBtn = document.getElementById('chooseFolderBtn');
        const startScanBtn = document.getElementById('startScanBtn');
        const uploadStatus = document.getElementById('uploadStatus');
        const dropZone = document.getElementById('dropZone');
        let currentScanId = null;
        let uploadBusy = false;
        let scanBusy = false;
        const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;
        const MAX_FOLDER_FILES = 500;
        const checkSvg = '<svg viewBox="0 0 24 24" fill="none" stroke="#000" stroke-width="4" class="w-3 h-3"><path d="M5 12l5 5L20 7"/></svg>';

        const setUploadStatus = (message, isError = false) => {
            if (!uploadStatus) return;
            uploadStatus.textContent = message;
            uploadStatus.style.color = isError ? '#FF4D5A' : '#7A8FA6';
        };

        const readResponseJson = async (response) => {
            try { return await response.json(); }
            catch (_) { return {}; }
        };

        const getErrorMessage = (body, fallback) => {
            if (body && typeof body.detail === 'string') return body.detail;
            if (body && body.detail) return JSON.stringify(body.detail);
            if (body && typeof body.error === 'string') return body.error;
            return fallback;
        };

        const setPickerButtonsDisabled = (disabled) => {
            if (chooseZipBtn) chooseZipBtn.disabled = disabled;
            if (chooseFolderBtn) chooseFolderBtn.disabled = disabled;
        };

        const uploadForm = async (url, form, description) => {
            if (uploadBusy) return;
            uploadBusy = true;
            currentScanId = null;
            setPickerButtonsDisabled(true);
            setUploadStatus('Uploading ' + description + '...');
            logLine('[BOOT] Uploading ' + description + '...');
            try {
                const response = await fetch(url, { method: 'POST', body: form });
                const body = await readResponseJson(response);
                if (!response.ok) {
                    throw new Error(getErrorMessage(body, 'Upload failed (HTTP ' + response.status + ').'));
                }
                if (!body.scan_id) throw new Error('Upload response did not include a scan ID.');
                currentScanId = body.scan_id;
                const count = Number.isFinite(Number(body.file_count)) ? Number(body.file_count) : '?';
                setUploadStatus('Upload ready: ' + count + ' file(s). Click INITIATE SCAN.');
                logLine('[/] Upload complete: ' + count + ' file(s) received.');
            } catch (error) {
                currentScanId = null;
                setUploadStatus(error.message || 'Upload failed.', true);
                logLine('[!] Upload failed: ' + (error.message || error));
            } finally {
                uploadBusy = false;
                setPickerButtonsDisabled(false);
            }
        };

        const uploadZipFile = (file) => {
            if (!file) return;
            if (!file.name.toLowerCase().endsWith('.zip')) {
                setUploadStatus('Please choose a .zip file.', true);
                return;
            }
            if (file.size > MAX_UPLOAD_BYTES) {
                setUploadStatus('ZIP exceeds the 50 MB upload limit.', true);
                return;
            }
            const form = new FormData();
            form.append('file', file, file.name);
            void uploadForm('/api/input/upload/zip', form, file.name);
        };

        const uploadFolderFiles = (fileList) => {
            const files = Array.from(fileList || []);
            if (!files.length) {
                setUploadStatus('No files selected. Choose a folder and try again.', true);
                return;
            }
            if (files.length > MAX_FOLDER_FILES) {
                setUploadStatus('Folder contains ' + files.length + ' files; maximum is ' + MAX_FOLDER_FILES + '.', true);
                return;
            }
            const totalBytes = files.reduce((sum, file) => sum + file.size, 0);
            if (totalBytes > MAX_UPLOAD_BYTES) {
                setUploadStatus('Folder contents exceed the 50 MB upload limit.', true);
                return;
            }
            const form = new FormData();
            for (const file of files) {
                form.append('files', file, file.name);
                form.append('paths', file.webkitRelativePath || file.name);
            }
            void uploadForm('/api/input/upload/folder', form, 'folder (' + files.length + ' files)');
        };

        if (chooseZipBtn && zipInput) {
            chooseZipBtn.type = 'button';
            chooseZipBtn.addEventListener('click', () => zipInput.click());
            zipInput.addEventListener('change', () => {
                if (zipInput.files && zipInput.files.length) uploadZipFile(zipInput.files[0]);
                zipInput.value = '';
            });
        }

        if (chooseFolderBtn && folderInput) {
            chooseFolderBtn.type = 'button';
            chooseFolderBtn.addEventListener('click', () => folderInput.click());
            folderInput.addEventListener('change', () => {
                if (folderInput.files && folderInput.files.length) uploadFolderFiles(folderInput.files);
                folderInput.value = '';
            });
        }

        // The scan-option labels are custom spans, not native checkboxes, so wire them explicitly.
        const optionControls = [
            ['lblOptSecurity', 'optSecurity'],
            ['lblOptQuality', 'optQuality'],
            ['lblOptDependencies', 'optDependencies']
        ];
        for (const [labelId, boxId] of optionControls) {
            const label = document.getElementById(labelId);
            const box = document.getElementById(boxId);
            if (!label || !box) continue;
            box.dataset.enabled = box.querySelector('svg') ? 'true' : 'false';
            label.addEventListener('click', (event) => {
                event.preventDefault();
                const enabled = box.dataset.enabled !== 'true';
                box.dataset.enabled = enabled ? 'true' : 'false';
                box.innerHTML = enabled ? checkSvg : '';
                box.style.backgroundColor = enabled ? '#19E6D0' : 'transparent';
            });
        }

        if (dropZone) {
            dropZone.style.cursor = 'pointer';
            dropZone.setAttribute('role', 'button');
            dropZone.setAttribute('tabindex', '0');
            dropZone.setAttribute('aria-label', 'Choose a ZIP file or drop upload files here');
            dropZone.addEventListener('click', () => { if (zipInput) zipInput.click(); });
            dropZone.addEventListener('keydown', (event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    if (zipInput) zipInput.click();
                }
            });
            dropZone.addEventListener('dragover', (event) => {
                event.preventDefault();
                dropZone.style.borderColor = '#19E6D0';
            });
            dropZone.addEventListener('dragleave', () => {
                dropZone.style.borderColor = '';
            });
            dropZone.addEventListener('drop', (event) => {
                event.preventDefault();
                dropZone.style.borderColor = '';
                const files = Array.from((event.dataTransfer && event.dataTransfer.files) || []);
                if (files.length === 1 && files[0].name.toLowerCase().endsWith('.zip')) {
                    uploadZipFile(files[0]);
                } else if (files.length) {
                    uploadFolderFiles(files);
                } else {
                    setUploadStatus('Browser did not provide folder files; click FOLDER to select a folder.', true);
                }
            });
        }

        const optionEnabled = (id) => {
            const box = document.getElementById(id);
            return !!box && box.dataset.enabled === 'true';
        };

        const showScanResult = (body) => {
            const data = (body && body.result && typeof body.result === 'object') ? body.result : (body || {});
            let issues = Array.isArray(data.issues) ? data.issues.slice() :
                (Array.isArray(data.findings) ? data.findings.slice() : []);
            if (!issues.length) {
                const nestedIssues = [];
                const scanners = data.scanners && typeof data.scanners === 'object' ? data.scanners : {};
                for (const [scannerName, scannerResult] of Object.entries(scanners)) {
                    if (scannerResult && Array.isArray(scannerResult.issues)) {
                        for (const issue of scannerResult.issues) {
                            nestedIssues.push({ ...issue, scanner: issue.scanner || scannerName });
                        }
                    }
                }
                if (nestedIssues.length) issues = nestedIssues;
            }
            window.renderResults({ ...data, issues });
            return issues.length;
        };

        if (startScanBtn) {
            startScanBtn.type = 'button';
            startScanBtn.addEventListener('click', async () => {
                if (scanBusy) return;
                if (!currentScanId) {
                    setUploadStatus('Choose a ZIP or folder first, then initiate the scan.', true);
                    logLine('[!] No upload target. Choose .ZIP or FOLDER first.');
                    return;
                }
                const security = optionEnabled('optSecurity');
                const quality = optionEnabled('optQuality');
                const dependencies = optionEnabled('optDependencies');
                if (!security && !quality && !dependencies) {
                    setUploadStatus('Enable at least one scan category.', true);
                    logLine('[!] Enable Security, Code Quality, or Dependencies.');
                    return;
                }
                scanBusy = true;
                startScanBtn.disabled = true;
                startScanBtn.style.opacity = '0.6';
                document.getElementById('terminalBody').innerHTML = '';
                document.getElementById('issueList').innerHTML = '<div class="text-[#7A8FA6] text-center py-4">Scanning...</div>';
                logLine('[BOOT] Initializing scan...');
                setUploadStatus('Scan running. This can take a few minutes.');
                try {
                    const params = new URLSearchParams({
                        security: String(security),
                        quality: String(quality),
                        dependencies: String(dependencies)
                    });
                    const runResponse = await fetch('/api/scans/' + encodeURIComponent(currentScanId) + '/run?' + params.toString(), { method: 'POST' });
                    const runBody = await readResponseJson(runResponse);
                    if (!runResponse.ok) throw new Error(getErrorMessage(runBody, 'Could not start scan (HTTP ' + runResponse.status + ').'));
                    logLine('[BOOT] Scan started: ' + currentScanId);
                    const deadline = Date.now() + 10 * 60 * 1000;
                    while (Date.now() < deadline) {
                        await new Promise(resolve => setTimeout(resolve, 1500));
                        const statusResponse = await fetch('/api/scans/' + encodeURIComponent(currentScanId));
                        const statusBody = await readResponseJson(statusResponse);
                        if (!statusResponse.ok) throw new Error(getErrorMessage(statusBody, 'Status check failed (HTTP ' + statusResponse.status + ').'));
                        if (statusBody.status === 'done') {
                            const issueCount = showScanResult(statusBody);
                            logLine('[/] Scan complete. ' + issueCount + ' finding(s) displayed.');
                            setUploadStatus('Scan complete: ' + issueCount + ' finding(s). Choose another ZIP or folder to scan again.');
                            return;
                        }
                        if (statusBody.status === 'error') {
                            throw new Error(statusBody.error || statusBody.detail || 'The scan failed.');
                        }
                    }
                    throw new Error('Scan is still running after 10 minutes. Check Past Results before retrying.');
                } catch (error) {
                    document.getElementById('issueList').innerHTML = '<div class="text-[#FF4D5A] text-center py-4">Scan failed. See terminal log.</div>';
                    setUploadStatus(error.message || 'Scan failed.', true);
                    logLine('[!] ' + (error.message || error));
                } finally {
                    scanBusy = false;
                    startScanBtn.disabled = false;
                    startScanBtn.style.opacity = '';
                }
            });
        }
'@

# Match the replacement block's line endings to the existing HTML.
$lineEnding = if ($text.Contains("`r`n")) { "`r`n" } else { "`n" }
$new = [regex]::Replace($new, "`r`n|`n|`r", [System.Text.RegularExpressions.MatchEvaluator]{ param($m) $lineEnding })
$match = $matches[0]
$updated = $text.Substring(0, $match.Index) + $new + $text.Substring($match.Index + $match.Length)

$required = @(
    "chooseZipBtn.addEventListener('click'",
    "chooseFolderBtn.addEventListener('click'",
    "'/api/input/upload/zip'",
    "'/api/input/upload/folder'",
    "'/api/scans/'",
    "startScanBtn.addEventListener('click'"
)
foreach ($token in $required) {
    if (-not $updated.Contains($token)) {
        throw "STOP: Pre-write check failed for '$token'. Original file unchanged."
    }
}

$originalBytes = [System.IO.File]::ReadAllBytes($path)
$hasUtf8Bom = $originalBytes.Length -ge 3 -and $originalBytes[0] -eq 0xEF -and $originalBytes[1] -eq 0xBB -and $originalBytes[2] -eq 0xBF
$utf8 = [System.Text.UTF8Encoding]::new($hasUtf8Bom)
Copy-Item -LiteralPath $path -Destination $backup
try {
    [System.IO.File]::WriteAllText($path, $updated, $utf8)
    $check = [System.IO.File]::ReadAllText($path)
    foreach ($token in $required) {
        if (-not $check.Contains($token)) { throw "Post-write check failed for '$token'." }
    }
} catch {
    Copy-Item -LiteralPath $backup -Destination $path -Force
    throw "Patch verification failed; original index.html restored from backup '$backup'. Details: $($_.Exception.Message)"
}

Write-Output 'FIX APPLIED: ZIP picker, folder picker, upload endpoints, scan-option toggles, scan polling, and result rendering wired.'
Write-Output "Backup: $backup"
Write-Output 'Post-write structural checks: PASS'
