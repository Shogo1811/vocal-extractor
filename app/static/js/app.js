/**
 * Vocal Extractor Application
 */

// API endpoints
const API = {
    upload: '/api/upload',
    youtube: '/api/youtube',
    status: (jobId) => `/api/status/${jobId}`,
    download: (jobId) => `/api/download/${jobId}`,
    preview: (jobId) => `/api/preview/${jobId}`,
};

// State
let currentJobId = null;
let statusInterval = null;

// DOM Elements
const elements = {
    // Tabs
    tabBtns: document.querySelectorAll('.tab-btn'),
    uploadTab: document.getElementById('upload-tab'),
    youtubeTab: document.getElementById('youtube-tab'),

    // Upload
    dropZone: document.getElementById('drop-zone'),
    fileInput: document.getElementById('file-input'),

    // YouTube
    youtubeUrl: document.getElementById('youtube-url'),
    youtubeSubmit: document.getElementById('youtube-submit'),

    // Processing
    processingSection: document.getElementById('processing-section'),
    processingTitle: document.getElementById('processing-title'),
    progressFill: document.getElementById('progress-fill'),
    progressText: document.getElementById('progress-text'),
    statusMessage: document.getElementById('status-message'),

    // Result
    resultSection: document.getElementById('result-section'),
    audioPreview: document.getElementById('audio-preview'),
    downloadBtn: document.getElementById('download-btn'),
    newExtractBtn: document.getElementById('new-extract-btn'),

    // Error
    errorSection: document.getElementById('error-section'),
    errorMessage: document.getElementById('error-message'),
    retryBtn: document.getElementById('retry-btn'),
};

// Initialize
document.addEventListener('DOMContentLoaded', init);

function init() {
    setupTabNavigation();
    setupFileUpload();
    setupYouTube();
    setupResultActions();
}

// Tab Navigation
function setupTabNavigation() {
    elements.tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabName = btn.dataset.tab;
            switchTab(tabName);
        });
    });
}

function switchTab(tabName) {
    // Update buttons
    elements.tabBtns.forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabName);
    });

    // Update content
    elements.uploadTab.classList.toggle('active', tabName === 'upload');
    elements.youtubeTab.classList.toggle('active', tabName === 'youtube');
}

// File Upload
function setupFileUpload() {
    const dropZone = elements.dropZone;
    const fileInput = elements.fileInput;

    // Drag and drop events
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropZone.classList.add('dragover');
        });
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragover');
        });
    });

    dropZone.addEventListener('drop', (e) => {
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFileUpload(files[0]);
        }
    });

    // File input change
    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            handleFileUpload(fileInput.files[0]);
        }
    });
}

async function handleFileUpload(file) {
    // Validate file
    const validFormats = ['mp3', 'wav', 'm4a', 'flac'];
    const extension = file.name.split('.').pop().toLowerCase();

    if (!validFormats.includes(extension)) {
        showError(`対応していない形式です。対応形式: ${validFormats.join(', ')}`);
        return;
    }

    const maxSize = 50 * 1024 * 1024; // 50MB
    if (file.size > maxSize) {
        showError('ファイルサイズが50MBを超えています');
        return;
    }

    // Upload file
    showProcessing('ファイルをアップロード中...');

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch(API.upload, {
            method: 'POST',
            body: formData,
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'アップロードに失敗しました');
        }

        currentJobId = data.job_id;
        startStatusPolling();

    } catch (error) {
        showError(error.message);
    }
}

// YouTube
function setupYouTube() {
    elements.youtubeSubmit.addEventListener('click', handleYouTube);
    elements.youtubeUrl.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            handleYouTube();
        }
    });
}

async function handleYouTube() {
    const url = elements.youtubeUrl.value.trim();

    if (!url) {
        showError('URLを入力してください');
        return;
    }

    // Basic YouTube URL validation
    const youtubeRegex = /^(https?:\/\/)?(www\.)?(youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/shorts\/)[\w-]+/;
    if (!youtubeRegex.test(url)) {
        showError('有効なYouTube URLを入力してください');
        return;
    }

    showProcessing('YouTube動画を処理中...');

    try {
        const response = await fetch(API.youtube, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ url }),
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || '処理を開始できませんでした');
        }

        currentJobId = data.job_id;
        startStatusPolling();

    } catch (error) {
        showError(error.message);
    }
}

// Status Polling
function startStatusPolling() {
    if (statusInterval) {
        clearInterval(statusInterval);
    }

    statusInterval = setInterval(checkStatus, 1000);
    checkStatus(); // Initial check
}

async function checkStatus() {
    if (!currentJobId) return;

    try {
        const response = await fetch(API.status(currentJobId));
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'ステータスの取得に失敗しました');
        }

        updateProgress(data.progress, data.message);

        if (data.status === 'completed') {
            stopStatusPolling();
            showResult();
        } else if (data.status === 'failed') {
            stopStatusPolling();
            showError(data.error || '処理に失敗しました');
        }

    } catch (error) {
        console.error('Status check error:', error);
    }
}

function stopStatusPolling() {
    if (statusInterval) {
        clearInterval(statusInterval);
        statusInterval = null;
    }
}

// UI Updates
function showProcessing(message) {
    hideAllSections();
    elements.processingSection.classList.remove('hidden');
    elements.processingTitle.textContent = '処理中...';
    elements.statusMessage.textContent = message;
    updateProgress(0, message);
}

function updateProgress(progress, message) {
    const percentage = Math.round(progress);
    elements.progressFill.style.width = `${percentage}%`;
    elements.progressText.textContent = `${percentage}%`;
    if (message) {
        elements.statusMessage.textContent = message;
    }
}

function showResult() {
    hideAllSections();
    elements.resultSection.classList.remove('hidden');

    // Set audio preview source
    elements.audioPreview.src = API.preview(currentJobId);
    elements.audioPreview.load();
}

function showError(message) {
    hideAllSections();
    elements.errorSection.classList.remove('hidden');
    elements.errorMessage.textContent = message;
}

function hideAllSections() {
    elements.processingSection.classList.add('hidden');
    elements.resultSection.classList.add('hidden');
    elements.errorSection.classList.add('hidden');
}

function resetUI() {
    hideAllSections();
    currentJobId = null;
    elements.fileInput.value = '';
    elements.youtubeUrl.value = '';
    elements.audioPreview.src = '';
    updateProgress(0, '');
}

// Result Actions
function setupResultActions() {
    elements.downloadBtn.addEventListener('click', () => {
        if (currentJobId) {
            window.location.href = API.download(currentJobId);
        }
    });

    elements.newExtractBtn.addEventListener('click', resetUI);
    elements.retryBtn.addEventListener('click', resetUI);
}
