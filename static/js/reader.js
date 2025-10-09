document.addEventListener('DOMContentLoaded', () => {
    // --- LocalStorage Keys ---
    const FIT_MODE_KEY = 'pdfReaderFitMode';
    const SCALE_KEY = 'pdfReaderScale';
    const VIEW_MODE_KEY = 'pdfReaderViewMode';
    const BRIGHTNESS_KEY = 'pdfReaderBrightness';
    const CONTRAST_KEY = 'pdfReaderContrast';
    const SATURATION_KEY = 'pdfReaderSaturation';
    const INVERT_COLORS_KEY = 'pdfReaderInvertColors';
    const PAGE_INDICATOR_VISIBLE_KEY = 'pdfReaderPageIndicatorVisible';

    // --- Default Settings ---
    const DEFAULT_BRIGHTNESS = 100;
    const DEFAULT_CONTRAST = 100;
    const DEFAULT_SATURATION = 100;
    const DEFAULT_INVERT_COLORS = false;

    // --- Load settings from LocalStorage ---
    const savedFitMode = localStorage.getItem(FIT_MODE_KEY);
    const savedScale = parseFloat(localStorage.getItem(SCALE_KEY));
    const savedViewMode = localStorage.getItem(VIEW_MODE_KEY);
    let isPageIndicatorVisible = localStorage.getItem(PAGE_INDICATOR_VISIBLE_KEY) !== 'false'; // Default to true

    // --- DOM Elements ---
    const fileId = document.body.dataset.fileId;
    const pdfUrl = document.body.dataset.pdfUrl;
    const initialPage = parseInt(document.body.dataset.initialPage, 10);
    const viewer = document.getElementById('pdf-viewer');
    const container = document.getElementById('reader-container');
    const pageNumSpan = document.getElementById('page-num');
    const pageCountSpan = document.getElementById('page-count');
    const pageIndicator = document.getElementById('page-indicator');
    
    // UI Elements
    const settingsPanel = document.getElementById('settings-panel');
    const floatingControls = document.getElementById('floating-controls');
    const settingsBtn = document.getElementById('settings-btn');

    // Settings Panel Buttons
    const fitWidthBtn = document.getElementById('fit-to-width');
    const fitHeightBtn = document.getElementById('fit-to-height');
    const viewOnePageBtn = document.getElementById('view-one-page');
    const viewTwoPageLtrBtn = document.getElementById('view-two-page-ltr');
    const viewTwoPageRtlBtn = document.getElementById('view-two-page-rtl');
    const togglePageIndicator = document.getElementById('toggle-page-indicator');

    // Color settings
    const brightnessSlider = document.getElementById('brightness-slider');
    const contrastSlider = document.getElementById('contrast-slider');
    const saturationSlider = document.getElementById('saturation-slider');
    const resetColorSettingsBtn = document.getElementById('reset-color-settings');
    const invertColorsToggle = document.getElementById('invert-colors-toggle');

    // --- State Variables ---
    let pdfDoc = null;
    let pageNum = initialPage;
    let pageRendering = false;
    let pageNumPending = null;
    let fitMode = savedFitMode || 'width';
    let scale = !isNaN(savedScale) ? savedScale : 1.5;
    let viewMode = savedViewMode || 'one'; // 'one', 'ltr', 'rtl'

    // --- Load Color Settings ---
    let currentBrightness = parseInt(localStorage.getItem(BRIGHTNESS_KEY) || DEFAULT_BRIGHTNESS, 10);
    let currentContrast = parseInt(localStorage.getItem(CONTRAST_KEY) || DEFAULT_CONTRAST, 10);
    let currentSaturation = parseInt(localStorage.getItem(SATURATION_KEY) || DEFAULT_SATURATION, 10);
    let isInverted = (localStorage.getItem(INVERT_COLORS_KEY) === 'true');

    // --- Initial UI Setup ---
    updateFitModeUI();
    updateViewModeUI();
    applyColorFilters();
    updatePageIndicatorState();

    // --- UI Update Functions ---
    function updateFitModeUI() {
        fitWidthBtn.classList.toggle('active', fitMode === 'width');
        fitHeightBtn.classList.toggle('active', fitMode === 'height');
    }

    function updateViewModeUI() {
        viewOnePageBtn.classList.toggle('active', viewMode === 'one');
        viewTwoPageLtrBtn.classList.toggle('active', viewMode === 'ltr');
        viewTwoPageRtlBtn.classList.toggle('active', viewMode === 'rtl');
    }

    function updatePageIndicatorState() {
        pageIndicator.classList.toggle('hidden', !isPageIndicatorVisible);
        togglePageIndicator.checked = isPageIndicatorVisible;
    }

    function applyColorFilters() {
        let filterString = `brightness(${currentBrightness}%) contrast(${currentContrast}%) saturate(${currentSaturation}%)`;
        if (isInverted) {
            filterString += ' invert(100%)';
        }
        viewer.style.filter = filterString;

        brightnessSlider.value = currentBrightness;
        contrastSlider.value = currentContrast;
        saturationSlider.value = currentSaturation;
        invertColorsToggle.checked = isInverted;

        localStorage.setItem(BRIGHTNESS_KEY, currentBrightness);
        localStorage.setItem(CONTRAST_KEY, currentContrast);
        localStorage.setItem(SATURATION_KEY, currentSaturation);
        localStorage.setItem(INVERT_COLORS_KEY, isInverted);
    }

    function resetColorFilters() {
        currentBrightness = DEFAULT_BRIGHTNESS;
        currentContrast = DEFAULT_CONTRAST;
        currentSaturation = DEFAULT_SATURATION;
        isInverted = DEFAULT_INVERT_COLORS;
        applyColorFilters();
    }

    // --- Core Rendering Functions ---
    function renderPage(num, canvas) {
        pageRendering = true;
        return pdfDoc.getPage(num).then(page => {
            let currentScale = scale;
            if (fitMode !== 'custom') {
                const unscaledViewport = page.getViewport({ scale: 1 });
                const containerWidth = container.clientWidth - 20;
                const containerHeight = container.clientHeight - 20;
                if (fitMode === 'width') {
                    currentScale = containerWidth / unscaledViewport.width;
                } else if (fitMode === 'height') {
                    currentScale = containerHeight / unscaledViewport.height;
                }
            }
            const viewport = page.getViewport({ scale: currentScale });
            canvas.height = viewport.height;
            canvas.width = viewport.width;
            const renderContext = { canvasContext: canvas.getContext('2d'), viewport: viewport };
            return page.render(renderContext).promise.then(() => {
                pageRendering = false;
                if (pageNumPending !== null) {
                    renderQueue(pageNumPending);
                    pageNumPending = null;
                }
            });
        });
    }

    function renderQueue(num) {
        if (pageRendering) {
            pageNumPending = num;
        } else {
            if (viewMode === 'one') {
                renderOnePage(num);
            } else { // 'ltr' or 'rtl'
                renderTwoPages(num, viewMode);
            }
        }
    }

    function renderTwoPages(num, direction) {
        viewer.innerHTML = '';
        const canvas1 = document.createElement('canvas');
        const canvas2 = document.createElement('canvas');

        if (direction === 'rtl') {
            viewer.appendChild(canvas2);
            viewer.appendChild(canvas1);
        } else { // 'ltr'
            viewer.appendChild(canvas1);
            viewer.appendChild(canvas2);
        }

        renderPage(num, canvas1);
        if (num + 1 <= pdfDoc.numPages) { renderPage(num + 1, canvas2); }
        pageNum = num;
        updatePageNumUI();
    }

    function renderOnePage(num) {
        viewer.innerHTML = '';
        const canvas = document.createElement('canvas');
        viewer.appendChild(canvas);
        renderPage(num, canvas);
        pageNum = num;
        updatePageNumUI();
    }

    // --- UI & State Update Functions ---
    function updatePageNumUI() {
        let pageString = pageNum;
        if (viewMode !== 'one' && pageNum + 1 <= pdfDoc.numPages) {
            pageString = (viewMode === 'ltr') ? `${pageNum}-${pageNum + 1}` : `${pageNum + 1}-${pageNum}`;
        }
        pageNumSpan.textContent = pageString;
    }

    const updateStatus = debounce(() => {
        fetch('/api/status/update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ file_id: fileId, current_page: pageNum })
        });
    }, 1000);

    function onPrevPage() {
        if (pageNum <= 1) return;
        const decrement = viewMode !== 'one' ? 2 : 1;
        pageNum -= decrement;
        renderQueue(pageNum);
        updateStatus();
    }

    function onNextPage() {
        const increment = viewMode !== 'one' ? 2 : 1;
        if (pageNum + increment > pdfDoc.numPages) {
            checkForNextVolume();
            return;
        }
        pageNum += increment;
        renderQueue(pageNum);
        updateStatus();
    }

    function changeScale(mod) {
        fitMode = 'custom';
        scale = Math.max(0.2, Math.min(5, scale + mod));
        localStorage.setItem(FIT_MODE_KEY, 'custom');
        localStorage.setItem(SCALE_KEY, scale);
        updateFitModeUI();
        renderQueue(pageNum);
    }

    function setViewMode(newMode) {
        if (viewMode === newMode) return;
        viewMode = newMode;
        localStorage.setItem(VIEW_MODE_KEY, viewMode);
        updateViewModeUI();

        if (viewMode !== 'one' && pageNum % 2 === 0 && pageNum > 1) {
            pageNum--;
        }
        renderQueue(pageNum);
    }

    async function checkForNextVolume() {
        const nextVolumePopup = document.getElementById('next-volume-popup');
        const nextVolumeMessage = document.getElementById('next-volume-message');
        const goToNextActionButton = document.getElementById('go-to-next-action');

        try {
            const response = await fetch(`/api/next_volume/${fileId}`);
            const data = await response.json();

            if (data.next_file_id) {
                nextVolumeMessage.textContent = '마지막 페이지입니다. 다음 권으로 이동하시겠습니까?';
                goToNextActionButton.onclick = () => {
                    window.location.href = `/reader/${data.next_file_id}`;
                };
            } else {
                nextVolumeMessage.textContent = '마지막 페이지입니다. 목록으로 돌아가시겠습니까?';
                goToNextActionButton.onclick = () => {
                    window.location.href = '/';
                };
            }
            nextVolumePopup.classList.remove('hidden');
        } catch (error) {
            console.error('Error checking for next volume:', error);
            window.location.href = '/';
        }
    }

    // --- Event Listeners ---
    // Zoom
    document.getElementById('zoom-in').addEventListener('click', () => changeScale(0.2));
    document.getElementById('zoom-out').addEventListener('click', () => changeScale(-0.2));

    // Settings Toggle (Mobile vs Desktop)
    settingsBtn.addEventListener('click', () => {
        const isMobile = window.innerWidth <= 480;
        if (isMobile) {
            floatingControls.classList.toggle('fabs-expanded');
        } else {
            const isHidden = settingsPanel.classList.toggle('hidden');
            floatingControls.classList.toggle('shifted-for-panel', !isHidden);
        }
    });

    // Page Indicator Toggle
    togglePageIndicator.addEventListener('change', (e) => {
        isPageIndicatorVisible = e.target.checked;
        localStorage.setItem(PAGE_INDICATOR_VISIBLE_KEY, isPageIndicatorVisible);
        updatePageIndicatorState();
    });

    // Fit Modes
    fitWidthBtn.addEventListener('click', () => {
        fitMode = 'width';
        localStorage.setItem(FIT_MODE_KEY, 'width');
        updateFitModeUI();
        renderQueue(pageNum);
    });
    fitHeightBtn.addEventListener('click', () => {
        fitMode = 'height';
        localStorage.setItem(FIT_MODE_KEY, 'height');
        updateFitModeUI();
        renderQueue(pageNum);
    });

    // View Modes
    viewOnePageBtn.addEventListener('click', () => setViewMode('one'));
    viewTwoPageLtrBtn.addEventListener('click', () => setViewMode('ltr'));
    viewTwoPageRtlBtn.addEventListener('click', () => setViewMode('rtl'));

    // Color Settings
    brightnessSlider.addEventListener('input', (e) => {
        currentBrightness = parseInt(e.target.value, 10);
        applyColorFilters();
    });
    contrastSlider.addEventListener('input', (e) => {
        currentContrast = parseInt(e.target.value, 10);
        applyColorFilters();
    });
    saturationSlider.addEventListener('input', (e) => {
        currentSaturation = parseInt(e.target.value, 10);
        applyColorFilters();
    });
    resetColorSettingsBtn.addEventListener('click', resetColorFilters);
    invertColorsToggle.addEventListener('change', (e) => {
        isInverted = e.target.checked;
        applyColorFilters();
    });

    // Close settings panel when clicking outside
    document.addEventListener('click', (e) => {
        // Check if the settings panel is open
        if (!settingsPanel.classList.contains('hidden')) {
            const isClickInsidePanel = settingsPanel.contains(e.target);
            const isClickOnSettingsBtn = settingsBtn.contains(e.target);

            if (!isClickInsidePanel && !isClickOnSettingsBtn) {
                settingsPanel.classList.add('hidden');
                floatingControls.classList.remove('shifted-for-panel');
            }
        }
    });

    // Window Resize
    window.addEventListener('resize', debounce(() => {
        if (fitMode !== 'custom') {
            renderQueue(pageNum);
        }
    }, 250));

    // Keyboard Navigation
    document.addEventListener('keydown', (e) => {
        if (e.target.tagName === 'INPUT') return;
        switch (e.key) {
            case 'ArrowLeft': onPrevPage(); e.preventDefault(); break;
            case 'ArrowRight': onNextPage(); e.preventDefault(); break;
        }
    });

    // Swipe Navigation
    let startX = 0, startY = 0;
    const swipeThreshold = 50;
    viewer.addEventListener('touchstart', (e) => {
        startX = e.touches[0].clientX;
        startY = e.touches[0].clientY;
    });
    viewer.addEventListener('touchend', (e) => {
        const endX = e.changedTouches[0].clientX;
        const endY = e.changedTouches[0].clientY;
        const diffX = startX - endX;
        const diffY = startY - endY;

        if (Math.abs(diffX) > Math.abs(diffY) && Math.abs(diffX) > swipeThreshold) {
            if (diffX > 0) { onNextPage(); } else { onPrevPage(); }
        }
        startX = 0; startY = 0;
    });

    // --- Initial Load ---
    const loaderOverlay = document.getElementById('loader-overlay');
    pdfjsLib.getDocument(pdfUrl).promise.then(doc => {
        pdfDoc = doc;
        pageCountSpan.textContent = pdfDoc.numPages;
        renderQueue(pageNum);
    }).finally(() => {
        setTimeout(() => { 
            loaderOverlay.classList.add('hidden');
        }, 200);
    });

    function debounce(func, delay) {
        let timeout;
        return function(...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), delay);
        };
    }
});