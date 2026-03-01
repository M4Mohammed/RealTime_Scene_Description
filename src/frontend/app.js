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

    // DOM Elements - Slideshow Player (Video Analysis)
    const slideshowContainer = document.getElementById('slideshow-container');
    const slideshowFrame = document.getElementById('slideshow-frame');
    const btnSlideshowPrev = document.getElementById('slideshow-prev');
    const btnSlideshowNext = document.getElementById('slideshow-next');
    const btnSlideshowPlayPause = document.getElementById('slideshow-play-pause');
    const slideshowProgress = document.getElementById('slideshow-progress');
    const loadingText = document.getElementById('loading-text');

    // DOM Elements - Toasts
    const toastContainer = document.getElementById('toast-container');

    // State Variables
    let selectedImageFile = null;
    let selectedVideoFile = null;
    let cameraStream = null;
    let ws = null;
    let streamInterval = null;
    let frameCount = 0;
    let lastFpsTime = Date.now();
    const FRAME_RATE_MS = 1000; // 1 fps

    // Slideshow State Variables
    let videoResults = [];
    let currentSlideIndex = 0;
    let isPlayingSlideshow = false;
    let slideshowInterval = null;
    const SLIDESHOW_DELAY = 2500; // 2.5 seconds per frame

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
    // Tab Switching Logic
    // ==========================================
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            tabContents.forEach(c => c.classList.add('hidden'));

            tab.classList.add('active');
            const targetId = tab.getAttribute('data-target');
            document.getElementById(targetId).classList.remove('hidden');

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

            if (data.frames && data.frames.length > 0) {
                videoResults = data.frames;
                initSlideshow();
            } else {
                showToast("No distinct frames found or video processing failed.", "error");
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

        startCameraBtn.classList.remove('hidden');
        stopCameraBtn.classList.add('hidden');
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
        stopSlideshow();
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
        stopSlideshow();
        videoResults = [];
    }

    function displayResults(data) {
        loadingIndicator.classList.add('hidden');
        emptyState.classList.add('hidden');
        resultsContent.classList.remove('hidden');

        captionText.textContent = data.caption || 'No caption returned.';

        const isSafe = data.classification && data.classification.toUpperCase() === 'SAFE';
        classificationResult.textContent = (data.classification || 'UNKNOWN').toUpperCase();

        if (isSafe) {
            statusBanner.className = 'status-banner safe';
            dangerReason.textContent = "Scene appears clear of common hazards.";
            statusIcon.innerHTML = ICONS.safe;
        } else {
            statusBanner.className = 'status-banner dangerous';
            dangerReason.textContent = data.danger_reason || "Potential hazard detected!";
            statusIcon.innerHTML = ICONS.danger;
        }

        if (data.latency_ms) {
            latencyVal.textContent = `${data.latency_ms.toFixed(0)} ms`;
        }
    }

    // --- Slideshow Logic ---
    function initSlideshow() {
        if (videoResults.length === 0) return;

        currentSlideIndex = 0;
        slideshowContainer.classList.remove('hidden');
        loadingIndicator.classList.add('hidden');

        updateSlideshowUI();
        startSlideshow();
    }

    function updateSlideshowUI() {
        const frameData = videoResults[currentSlideIndex];

        if (frameData.image_base64) {
            slideshowFrame.src = 'data:image/jpeg;base64,' + frameData.image_base64;
        }

        slideshowProgress.textContent = `${currentSlideIndex + 1} / ${videoResults.length}`;

        displayResults({
            caption: frameData.caption,
            classification: frameData.classification,
            danger_reason: frameData.danger_reason,
            latency_ms: frameData.latency_ms
        });
    }

    function nextSlide() {
        currentSlideIndex = (currentSlideIndex + 1) % videoResults.length;
        updateSlideshowUI();
    }

    function prevSlide() {
        currentSlideIndex = (currentSlideIndex - 1 + videoResults.length) % videoResults.length;
        updateSlideshowUI();
    }

    function startSlideshow() {
        isPlayingSlideshow = true;
        btnSlideshowPlayPause.textContent = "Pause";
        if (slideshowInterval) clearInterval(slideshowInterval);
        slideshowInterval = setInterval(nextSlide, SLIDESHOW_DELAY);
    }

    function stopSlideshow() {
        isPlayingSlideshow = false;
        btnSlideshowPlayPause.textContent = "Play";
        if (slideshowInterval) clearInterval(slideshowInterval);
    }

    btnSlideshowNext.addEventListener('click', () => {
        stopSlideshow();
        nextSlide();
    });

    btnSlideshowPrev.addEventListener('click', () => {
        stopSlideshow();
        prevSlide();
    });

    btnSlideshowPlayPause.addEventListener('click', () => {
        if (isPlayingSlideshow) {
            stopSlideshow();
        } else {
            startSlideshow();
        }
    });

});
