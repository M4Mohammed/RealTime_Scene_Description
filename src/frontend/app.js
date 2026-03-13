document.addEventListener('DOMContentLoaded', () => {
    // API Configuration
    const API_BASE_URL = window.location.origin;

    // Construct WebSocket URL robustly
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const WS_URL = `${wsProtocol}//${window.location.host}/ws/livestream`;

    // DOM Elements - Navigation
    const tabs = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    // DOM Elements - Image Upload
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const imagePreview = document.getElementById('image-preview');
    const previewContainer = document.getElementById('preview-container');
    const removeImageBtn = document.getElementById('remove-image-btn');
    const analyzeBtn = document.getElementById('analyze-btn');

    // DOM Elements - Camera
    const video = document.getElementById('camera-stream');
    const canvas = document.getElementById('camera-canvas');
    const startCameraBtn = document.getElementById('start-camera-btn');
    const stopCameraBtn = document.getElementById('stop-camera-btn');
    const fpsCounter = document.getElementById('fps-counter');

    // DOM Elements - Video Upload
    const videoDropZone = document.getElementById('video-drop-zone');
    const videoInput = document.getElementById('video-input');
    const videoPreviewContainer = document.getElementById('video-preview-container');
    const videoFileName = document.getElementById('video-file-name');
    const videoFileSize = document.getElementById('video-file-size');
    const removeVideoBtn = document.getElementById('remove-video-btn');
    const analyzeVideoBtn = document.getElementById('analyze-video-btn');

    // DOM Elements - Results & States
    const loadingIndicator = document.getElementById('loading-indicator');
    const resultsContent = document.getElementById('results-content');
    const emptyState = document.getElementById('empty-state');

    // DOM Elements - Specific Results Data
    const statusBanner = document.getElementById('status-banner');
    const classificationResult = document.getElementById('classification-result');
    const dangerReason = document.getElementById('danger-reason');
    const captionText = document.getElementById('caption-text');
    const latencyVal = document.getElementById('latency-val');
    const statusIcon = document.getElementById('status-icon');
    const captionHeaderTitle = document.getElementById('caption-header-title');
    const videoActionsContainer = document.getElementById('video-actions-container');
    const downloadReportBtn = document.getElementById('download-report-btn');

    // DOM Elements - Video Player
    const slideshowContainer = document.getElementById('slideshow-container');
    const resultVideo = document.getElementById('result-video');
    const loadingText = document.getElementById('loading-text');

    // DOM Elements - Toasts
    const toastContainer = document.getElementById('toast-container');

    // DOM Elements - TTS
    const ttsToggle = document.getElementById('tts-toggle');
    const ttsWave = document.getElementById('tts-wave');

    // DOM Elements - Perception UI
    const urgencyBar = document.getElementById('urgency-bar');
    const dangerOverlay = document.getElementById('danger-overlay');
    const cameraPlaceholder = document.getElementById('camera-placeholder');

    // State Variables
    let selectedImageFile = null;
    let selectedVideoFile = null;
    let cameraStream = null;
    let ws = null;
    let streamInterval = null;
    let frameCount = 0;
    let lastFpsTime = Date.now();
    const FRAME_RATE_MS = 1000; // 1 fps

    // TTS Context State Tracking
    let isSpeaking = false;
    let lastSpokenCaption = "";
    let lastSpokenTime = 0;
    const TTS_DEBOUNCE_MS = 8000; // Wait 8 seconds before repeating the exact same safe caption

    // SVG Icons
    const ICONS = {
        safe: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" /></svg>`,
        danger: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3Z" /></svg>`,
        error: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3Z" /></svg>`,
        info: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="m11.25 11.25.041-.02a.75.75 0 0 1 1.063.852l-.708 2.836a.75.75 0 0 0 1.063.853l.041-.021M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9-3.75h.008v.008H12V8.25Z" /></svg>`
    };

    // ==========================================
    // Friendly Toast Notifications
    // ==========================================
    function showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;

        const icon = type === 'error' ? ICONS.error : ICONS.info;

        toast.innerHTML = `
            <div class="toast-icon">${icon}</div>
            <div class="toast-message">${message}</div>
        `;

        toastContainer.appendChild(toast);

        // Remove toast after duration
        setTimeout(() => {
            toast.classList.add('fade-out');
            setTimeout(() => toast.remove(), 300); // Wait for fade-out animation
        }, 4000);
    }

    // ==========================================
    // Perception Features: Tone System & Semantic Dedup
    // ==========================================
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();

    function playTone(type) {
        if (!ttsToggle || !ttsToggle.checked) return;
        if (audioCtx.state === 'suspended') audioCtx.resume();

        const osc = audioCtx.createOscillator();
        const gainNode = audioCtx.createGain();
        osc.connect(gainNode);
        gainNode.connect(audioCtx.destination);

        if (type === 'critical') {
            // Sawtooth warning (880 -> 660 -> 880)
            osc.type = 'sawtooth';
            osc.frequency.setValueAtTime(880, audioCtx.currentTime);
            osc.frequency.setValueAtTime(660, audioCtx.currentTime + 0.1);
            osc.frequency.setValueAtTime(880, audioCtx.currentTime + 0.2);
            gainNode.gain.setValueAtTime(0.1, audioCtx.currentTime);
            osc.start();
            osc.stop(audioCtx.currentTime + 0.3);
        } else if (type === 'high') {
            // High warning
            osc.type = 'sine';
            osc.frequency.setValueAtTime(880, audioCtx.currentTime);
            gainNode.gain.setValueAtTime(0.1, audioCtx.currentTime);
            osc.start();
            osc.stop(audioCtx.currentTime + 0.15);
        } else if (type === 'medium') {
            osc.type = 'sine';
            osc.frequency.setValueAtTime(440, audioCtx.currentTime);
            gainNode.gain.setValueAtTime(0.05, audioCtx.currentTime);
            osc.start();
            osc.stop(audioCtx.currentTime + 0.1);
        }
    }

    function calculateSemanticOverlap(text1, text2) {
        if (!text1 || !text2) return 0;

        // Remove punctuation and lowercase
        const clean1 = text1.toLowerCase().replace(/[^\w\s]/g, '').split(/\s+/);
        const clean2 = text2.toLowerCase().replace(/[^\w\s]/g, '').split(/\s+/);

        // Remove common stop words for better semantic comparison
        const stopWords = new Set(['a', 'an', 'the', 'is', 'are', 'in', 'on', 'at', 'with', 'of', 'and']);
        const words1 = new Set(clean1.filter(w => !stopWords.has(w) && w.length > 0));
        const words2 = new Set(clean2.filter(w => !stopWords.has(w) && w.length > 0));

        if (words1.size === 0 && words2.size === 0) return 100;
        if (words1.size === 0 || words2.size === 0) return 0;

        let intersectionCount = 0;
        for (let word of words1) {
            if (words2.has(word)) intersectionCount++;
        }

        // Percentage based on the smaller set to ensure subsets trigger dedup
        const minLength = Math.min(words1.size, words2.size);
        return (intersectionCount / minLength) * 100;
    }

    // ==========================================
    // Smart Text-to-Speech (TTS)
    // ==========================================
    function speakText(text, urgencyLevel = 'safe') {
        if (!ttsToggle || !ttsToggle.checked) return;
        if (!('speechSynthesis' in window)) return;

        // Stop currently speaking audio immediately if danger pops up or resolving new caption
        window.speechSynthesis.cancel();

        // Play tone before speech to prime the user's attention
        playTone(urgencyLevel);

        isSpeaking = true;
        if (ttsWave) ttsWave.classList.add('speaking');

        const msg = new SpeechSynthesisUtterance();
        msg.text = text;
        msg.volume = 1.0;

        // Adjust Voice parameters based on urgency
        if (urgencyLevel === 'critical') {
            msg.rate = 1.15; // Faster
            msg.pitch = 1.3; // Higher pitch
            msg.text = `Critical Warning: ${text}`;
        } else if (urgencyLevel === 'high') {
            msg.rate = 1.05;
            msg.pitch = 1.1;
            msg.text = `Warning: ${text}`;
        } else {
            msg.rate = 1.0;
            msg.pitch = 1.0;
        }

        msg.onend = () => { isSpeaking = false; if (ttsWave) ttsWave.classList.remove('speaking'); };
        msg.onerror = () => { isSpeaking = false; if (ttsWave) ttsWave.classList.remove('speaking'); };

        // Add tiny delay to allow tone to play first, then speak
        setTimeout(() => {
            window.speechSynthesis.speak(msg);
        }, 300);

        lastSpokenCaption = text;
        lastSpokenTime = Date.now();
    }

    // ==========================================
    // Tab Switching Logic
    // ==========================================
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            tabContents.forEach(c => {
                c.classList.add('hidden');
                c.classList.remove('active');
            });

            tab.classList.add('active');
            const targetId = tab.getAttribute('data-target');
            document.getElementById(targetId).classList.remove('hidden');
            document.getElementById(targetId).classList.add('active');

            resetResults();

            if (targetId !== 'camera-tab' && cameraStream) {
                stopCamera();
            }
        });
    });

    // ==========================================
    // Image Upload Logic
    // ==========================================
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => dropZone.classList.add('dragover'), false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => dropZone.classList.remove('dragover'), false);
    });

    dropZone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length) handleFileSelect(files[0]);
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length) handleFileSelect(e.target.files[0]);
    });

    function handleFileSelect(file) {
        if (!file.type.startsWith('image/')) {
            showToast('Please select a valid image file (JPEG, PNG, etc).', 'error');
            return;
        }

        selectedImageFile = file;

        const reader = new FileReader();
        reader.onload = (e) => {
            imagePreview.src = e.target.result;
            previewContainer.classList.remove('preview-hidden');
            dropZone.classList.add('hidden');
            analyzeBtn.disabled = false;
        };
        reader.readAsDataURL(file);

        resetResults();
    }

    removeImageBtn.addEventListener('click', () => {
        selectedImageFile = null;
        fileInput.value = ''; // Clear input
        imagePreview.src = '';
        previewContainer.classList.add('preview-hidden');
        dropZone.classList.remove('hidden');
        resetResults();
    });

    analyzeBtn.addEventListener('click', async () => {
        if (!selectedImageFile) return;

        showLoading();
        analyzeBtn.disabled = true;

        const formData = new FormData();
        formData.append('file', selectedImageFile);

        try {
            const response = await fetch(`${API_BASE_URL}/api/analyze/image`, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) throw new Error(`Server responded with ${response.status}`);

            const data = await response.json();
            displayResults(data);
        } catch (error) {
            console.error('Error analyzing image:', error);
            showToast('Failed to analyze the image. Ensure the backend server is running.', 'error');
            resetResults();
            analyzeBtn.disabled = false;
        }
    });

    // ==========================================
    // Video Upload & Analysis Logic
    // ==========================================
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        videoDropZone.addEventListener(eventName, preventDefaults, false);
    });

    ['dragenter', 'dragover'].forEach(eventName => {
        videoDropZone.addEventListener(eventName, () => videoDropZone.classList.add('dragover'), false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        videoDropZone.addEventListener(eventName, () => videoDropZone.classList.remove('dragover'), false);
    });

    videoDropZone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length) handleVideoSelect(files[0]);
    });

    videoInput.addEventListener('change', (e) => {
        if (e.target.files.length) handleVideoSelect(e.target.files[0]);
    });

    function handleVideoSelect(file) {
        if (!file.type.startsWith('video/')) {
            showToast('Please select a valid video file (MP4, WebM, etc).', 'error');
            return;
        }

        selectedVideoFile = file;

        videoFileName.textContent = file.name;
        videoFileSize.textContent = (file.size / (1024 * 1024)).toFixed(2) + ' MB';

        videoPreviewContainer.classList.remove('preview-hidden');
        videoDropZone.classList.add('hidden');
        analyzeVideoBtn.disabled = false;

        resetResults();
    }

    removeVideoBtn.addEventListener('click', () => {
        selectedVideoFile = null;
        videoInput.value = '';
        videoPreviewContainer.classList.add('preview-hidden');
        videoDropZone.classList.remove('hidden');
        resetResults();
    });

    analyzeVideoBtn.addEventListener('click', async () => {
        if (!selectedVideoFile) return;

        showLoading("Extracting keyframes and analyzing video. This may take a minute...");
        analyzeVideoBtn.disabled = true;

        const formData = new FormData();
        formData.append('file', selectedVideoFile);

        try {
            const response = await fetch(`${API_BASE_URL}/api/analyze/video`, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) throw new Error(`Server responded with ${response.status}`);

            const data = await response.json();

            if (data.video_base64) {
                // Set the video player source to the synthesized MP4
                resultVideo.src = `data:video/mp4;base64,${data.video_base64}`;
                slideshowContainer.classList.remove('hidden');

                // Display summary results
                displayResults({
                    caption: data.summary || `Video Analysis Complete. Processed ${data.unique_keyframes} unique keyframes.`,
                    classification: "INFO",
                    danger_reason: "Review the generated summary video above.",
                    latency_ms: null,
                    is_video: true,
                    full_report: data
                });
            } else {
                showToast("No video generated or processing failed.", "error");
                resetResults();
            }
        } catch (error) {
            console.error('Error analyzing video:', error);
            showToast('Failed to analyze the video. Ensure the backend supports video.', 'error');
            resetResults();
        } finally {
            analyzeVideoBtn.disabled = false;
        }
    });

    // ==========================================
    // Live Camera Logic (WebSockets)
    // ==========================================
    startCameraBtn.addEventListener('click', async () => {
        try {
            cameraStream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: "environment", width: { ideal: 640 }, height: { ideal: 480 } },
                audio: false
            });
            video.srcObject = cameraStream;

            startCameraBtn.classList.add('hidden');
            stopCameraBtn.classList.remove('hidden');
            if (cameraPlaceholder) cameraPlaceholder.classList.add('hidden');
            resetResults();

            connectWebSocket();
        } catch (err) {
            console.error("Error accessing camera: ", err);
            showToast("Camera access denied or unavailable. Please check permissions.", "error");
        }
    });

    stopCameraBtn.addEventListener('click', stopCamera);

    function stopCamera() {
        if (cameraStream) {
            cameraStream.getTracks().forEach(track => track.stop());
            cameraStream = null;
        }
        video.srcObject = null;

        if (ws) ws.close();
        if (streamInterval) clearInterval(streamInterval);

        // Stop any ongoing speech
        if ('speechSynthesis' in window) {
            window.speechSynthesis.cancel();
        }

        startCameraBtn.classList.remove('hidden');
        stopCameraBtn.classList.add('hidden');
        if (cameraPlaceholder) cameraPlaceholder.classList.remove('hidden');
        fpsCounter.textContent = '0 FPS';
    }

    function connectWebSocket() {
        ws = new WebSocket(WS_URL);

        ws.onopen = () => {
            console.log('WebSocket Connected');
            streamInterval = setInterval(sendFrame, FRAME_RATE_MS);
            showToast('Live camera analysis started.');
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.error) {
                    console.error("WS Server Error:", data.error);
                    return;
                }
                displayResults(data);
                updateFPS();

                // --- Smart Debouncing & Semantic Dedup TTS Logic ---
                if (data.caption && !data.caption.startsWith("Error")) {
                    const isDanger = (data.classification && data.classification.toUpperCase() === 'DANGEROUS');
                    const reasonStr = (data.danger_reason || "").toLowerCase();
                    const now = Date.now();
                    const timeSinceLastSpeech = now - lastSpokenTime;

                    // Determine Severity
                    let severity = 'safe';
                    if (isDanger) {
                        if (reasonStr.includes('fast') || reasonStr.includes('weapon') || reasonStr.includes('fire')) {
                            severity = 'critical';
                        } else {
                            severity = 'high';
                        }
                    } else if (data.caption.includes('moving') || data.caption.includes('approaching')) {
                        severity = 'medium'; // Provide a soft blip for motion
                    }

                    // Semantic Dedup: Check overlap rather than exact string match
                    const overlapPercent = calculateSemanticOverlap(data.caption, lastSpokenCaption);
                    const isSemanticallySimilar = (overlapPercent > 55);

                    // Always speak immediately if danger is detected
                    if (isDanger) {
                        // We don't debounce Dangers. If it's dangerous, yell immediately.
                        // But if it's the highly similar danger rapidly flickering, only repeat every 4 seconds.
                        if (!isSemanticallySimilar || timeSinceLastSpeech > 4000) {
                            speakText(`${data.danger_reason}. ${data.caption}`, severity);
                        } else {
                            console.log(`⚡ Cached Danger: ${overlapPercent.toFixed(1)}% overlap.`);
                        }
                    }
                    // If safe, only speak if it's a NEW scene semantically, or if the long timeout has passed
                    else {
                        if (!isSemanticallySimilar || timeSinceLastSpeech > TTS_DEBOUNCE_MS) {
                            speakText(data.caption, severity);
                        } else {
                            console.log(`⚡ Cached Safe: ${overlapPercent.toFixed(1)}% overlap.`);
                        }
                    }
                }
                // ------------------------------------

            } catch (e) {
                console.error("Failed to parse WS message", e);
            }
        };

        ws.onerror = (error) => {
            console.error("WebSocket Error:", error);
            showToast('Connection error. Is the backend running?', 'error');
            stopCamera();
        }

        ws.onclose = () => {
            console.log('WebSocket Disconnected');
            if (streamInterval) clearInterval(streamInterval);
        };
    }

    function sendFrame() {
        if (!ws || ws.readyState !== WebSocket.OPEN || !cameraStream) return;

        const ctx = canvas.getContext('2d');
        canvas.width = video.videoWidth || 640;
        canvas.height = video.videoHeight || 480;
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

        // Compress heavily to ensure real-time performance over WS
        const frameData = canvas.toDataURL('image/jpeg', 0.5);

        ws.send(JSON.stringify({ frame: frameData }));
    }

    function updateFPS() {
        frameCount++;
        const now = Date.now();
        if (now - lastFpsTime >= 1000) {
            fpsCounter.textContent = `${frameCount} FPS`;
            frameCount = 0;
            lastFpsTime = now;
        }
    }

    // ==========================================
    // UI Helpers & Slideshow
    // ==========================================
    function showLoading(msg = 'Analyzing scene...') {
        loadingText.textContent = msg;
        emptyState.classList.add('hidden');
        resultsContent.classList.add('hidden');
        slideshowContainer.classList.add('hidden');
        loadingIndicator.classList.remove('hidden');
        if (resultVideo) resultVideo.pause();
    }

    function resetResults() {
        emptyState.classList.remove('hidden');
        resultsContent.classList.add('hidden');
        slideshowContainer.classList.add('hidden');
        loadingIndicator.classList.add('hidden');
        statusBanner.className = 'status-banner';
        statusIcon.innerHTML = ICONS.info;
        classificationResult.textContent = 'N/A';
        dangerReason.textContent = 'Awaiting analysis...';
        captionText.textContent = 'No caption available.';
        latencyVal.textContent = '0 ms';
        if (captionHeaderTitle) captionHeaderTitle.textContent = 'Generated Caption';
        if (videoActionsContainer) videoActionsContainer.classList.add('hidden');
        if (resultVideo) resultVideo.pause();

        // Reset UI perception features
        if (urgencyBar) urgencyBar.className = 'urgency-bar low';
        if (dangerOverlay) dangerOverlay.classList.remove('active');
        if (ttsWave) ttsWave.classList.remove('speaking');
    }

    function displayResults(data) {
        loadingIndicator.classList.add('hidden');
        emptyState.classList.add('hidden');
        resultsContent.classList.remove('hidden');

        // Apply slide-up animation to the caption
        if (captionText.textContent !== data.caption) {
            captionText.classList.add('caption-fade-out');
            setTimeout(() => {
                captionText.textContent = data.caption || 'No caption returned.';
                captionText.classList.remove('caption-fade-out');
                captionText.classList.remove('caption-slide');
                void captionText.offsetWidth; // Trigger reflow to restart animation
                captionText.classList.add('caption-slide');
            }, 200); // Wait for fade-out
        } else {
            captionText.textContent = data.caption || 'No caption returned.';
        }

        const isSafe = data.classification && data.classification.toUpperCase() === 'SAFE';
        classificationResult.textContent = (data.classification || 'UNKNOWN').toUpperCase();

        if (isSafe) {
            statusBanner.className = 'status-banner safe';
            dangerReason.textContent = "Scene appears clear of common hazards.";
            statusIcon.innerHTML = ICONS.safe;
            if (urgencyBar) urgencyBar.className = 'urgency-bar low';
            if (dangerOverlay) dangerOverlay.classList.remove('active');
        } else {
            statusBanner.className = 'status-banner dangerous';
            dangerReason.textContent = data.danger_reason || "Potential hazard detected!";
            statusIcon.innerHTML = ICONS.danger;

            // Perception UI triggers based on theoretical danger severity
            const reasonLower = (data.danger_reason || "").toLowerCase();
            if (reasonLower.includes('fast') || reasonLower.includes('weapon') || reasonLower.includes('fire')) {
                if (urgencyBar) urgencyBar.className = 'urgency-bar critical';
            } else {
                if (urgencyBar) urgencyBar.className = 'urgency-bar high';
            }
            if (dangerOverlay) dangerOverlay.classList.add('active');
        }

        if (data.latency_ms) {
            latencyVal.textContent = `${data.latency_ms.toFixed(0)} ms`;
        }

        if (data.is_video) {
            if (captionHeaderTitle) captionHeaderTitle.textContent = "Video Summary";
            if (videoActionsContainer) videoActionsContainer.classList.remove('hidden');

            // Set up download button
            if (downloadReportBtn) {
                downloadReportBtn.onclick = () => {
                    const reportData = {
                        summary: data.full_report.summary,
                        total_frames: data.full_report.total_frames,
                        unique_keyframes: data.full_report.unique_keyframes,
                        frame_captions: data.full_report.frame_captions
                    };
                    const blob = new Blob([JSON.stringify(reportData, null, 2)], { type: "application/json" });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = "video_analysis_report.json";
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    URL.revokeObjectURL(url);
                };
            }
        } else {
            if (captionHeaderTitle) captionHeaderTitle.textContent = "Generated Caption";
            if (videoActionsContainer) videoActionsContainer.classList.add('hidden');
            if (downloadReportBtn) downloadReportBtn.onclick = null;
        }
    }

    // (Slideshow logic removed because we now stream a real MP4 back from the server)

});
