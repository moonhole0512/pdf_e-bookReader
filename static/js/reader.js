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
    const SHARPEN_KEY = 'pdfReaderSharpenMode';

    // --- Default Settings ---
    const DEFAULT_BRIGHTNESS = 100;
    const DEFAULT_CONTRAST = 100;
    const DEFAULT_SATURATION = 100;
    const DEFAULT_INVERT_COLORS = false;
    const DEFAULT_SHARPEN = 'off'; // ponytail: 'off', 'mild', 'strong'

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
    const settingsModalOverlay = document.getElementById('settings-modal-overlay');
    const settingsPanel = document.getElementById('settings-panel');
    const closeSettingsBtn = document.getElementById('close-settings-btn');
    const floatingControls = document.getElementById('floating-controls');
    const settingsBtn = document.getElementById('settings-btn');

    // Settings Panel Buttons
    const fitWidthBtn = document.getElementById('fit-to-width');
    const fitHeightBtn = document.getElementById('fit-to-height');
    const viewOnePageBtn = document.getElementById('view-one-page');
    const viewTwoPageLtrBtn = document.getElementById('view-two-page-ltr');
    const viewTwoPageRtlBtn = document.getElementById('view-two-page-rtl');
    const togglePageIndicator = document.getElementById('toggle-page-indicator');

    // Sharpen settings (ponytail: Native GPU filter controls)
    const sharpenOffBtn = document.getElementById('sharpen-off');
    const sharpenMildBtn = document.getElementById('sharpen-mild');
    const sharpenStrongBtn = document.getElementById('sharpen-strong');

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
    let lastRenderedScale = scale;
    let viewMode = savedViewMode || 'one'; // 'one', 'ltr', 'rtl'

    // --- Load Color & Sharpen Settings ---
    let currentSharpen = localStorage.getItem(SHARPEN_KEY) || DEFAULT_SHARPEN;
    let currentBrightness = parseInt(localStorage.getItem(BRIGHTNESS_KEY) || DEFAULT_BRIGHTNESS, 10);
    let currentContrast = parseInt(localStorage.getItem(CONTRAST_KEY) || DEFAULT_CONTRAST, 10);
    let currentSaturation = parseInt(localStorage.getItem(SATURATION_KEY) || DEFAULT_SATURATION, 10);
    let isInverted = (localStorage.getItem(INVERT_COLORS_KEY) === 'true');

    // --- Initial UI Setup ---
    updateFitModeUI();
    updateViewModeUI();
    updateSharpenUI();
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

    function updateSharpenUI() {
        if (sharpenOffBtn) sharpenOffBtn.classList.toggle('active', currentSharpen === 'off');
        if (sharpenMildBtn) sharpenMildBtn.classList.toggle('active', currentSharpen === 'mild');
        if (sharpenStrongBtn) sharpenStrongBtn.classList.toggle('active', currentSharpen === 'strong');
    }

    function applyColorFilters() {
        // ponytail: Combine GPU-accelerated SVG sharpen filter with native CSS color filters
        let sharpenPrefix = '';
        if (currentSharpen === 'mild') {
            sharpenPrefix = 'url(#sharpen-filter-mild) ';
        } else if (currentSharpen === 'strong') {
            sharpenPrefix = 'url(#sharpen-filter-strong) ';
        }

        let filterString = `${sharpenPrefix}brightness(${currentBrightness}%) contrast(${currentContrast}%) saturate(${currentSaturation}%)`;
        if (isInverted) {
            filterString += ' invert(100%)';
        }
        viewer.style.filter = filterString;

        updateSharpenUI();
        brightnessSlider.value = currentBrightness;
        contrastSlider.value = currentContrast;
        saturationSlider.value = currentSaturation;
        invertColorsToggle.checked = isInverted;

        localStorage.setItem(SHARPEN_KEY, currentSharpen);
        localStorage.setItem(BRIGHTNESS_KEY, currentBrightness);
        localStorage.setItem(CONTRAST_KEY, currentContrast);
        localStorage.setItem(SATURATION_KEY, currentSaturation);
        localStorage.setItem(INVERT_COLORS_KEY, isInverted);
    }

    function resetColorFilters() {
        currentSharpen = DEFAULT_SHARPEN;
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
                const availableWidth = Math.max(100, container.clientWidth - 20);
                const availableHeight = Math.max(100, container.clientHeight - 20);
                if (fitMode === 'width') {
                    const targetWidth = (viewMode !== 'one') ? (availableWidth / 2) : availableWidth;
                    currentScale = targetWidth / unscaledViewport.width;
                } else if (fitMode === 'height') {
                    currentScale = availableHeight / unscaledViewport.height;
                }
            }
            lastRenderedScale = currentScale;
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

        const promises = [renderPage(num, canvas1)];
        if (num + 1 <= pdfDoc.numPages) {
            promises.push(renderPage(num + 1, canvas2));
        }

        Promise.all(promises).then(() => {
            container.scrollTop = 0;
            container.scrollLeft = 0;
        });

        pageNum = num;
        updatePageNumUI();
    }

    function renderOnePage(num) {
        viewer.innerHTML = '';
        const canvas = document.createElement('canvas');
        viewer.appendChild(canvas);
        renderPage(num, canvas).then(() => {
            container.scrollTop = 0;
            container.scrollLeft = 0;
        });
        pageNum = num;
        updatePageNumUI();
    }

    // --- UI & State Update Functions ---
    function updateScrubberUI() {
        if (!pdfDoc || pdfDoc.numPages <= 0) return;
        const scrubberProgress = document.getElementById('scrubber-progress');
        const scrubberThumb = document.getElementById('scrubber-thumb');
        const pct = Math.min(100, Math.max(0, (pageNum / pdfDoc.numPages) * 100));
        if (scrubberProgress) scrubberProgress.style.width = `${pct}%`;
        if (scrubberThumb) scrubberThumb.style.left = `${pct}%`;
    }

    function updatePageNumUI() {
        let pageString = pageNum;
        if (viewMode !== 'one' && pageNum + 1 <= pdfDoc.numPages) {
            pageString = (viewMode === 'ltr') ? `${pageNum}-${pageNum + 1}` : `${pageNum + 1}-${pageNum}`;
        }
        pageNumSpan.textContent = pageString;
        updateScrubberUI();
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
        // ponytail: Always zoom relative to the currently visible screen scale (even in fit-to-width/height mode)
        const baseScale = (fitMode !== 'custom' && lastRenderedScale > 0) ? lastRenderedScale : scale;
        scale = Math.max(0.2, Math.min(5, Math.round((baseScale + mod) * 100) / 100));
        lastRenderedScale = scale;
        fitMode = 'custom';
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
                const volTxt = data.next_volume_number ? `제${data.next_volume_number}권` : '다음 권';
                nextVolumeMessage.textContent = `시리즈의 다음 권(${volTxt})이 준비되어 있습니다. 지금 바로 이어서 읽으시겠습니까?`;
                goToNextActionButton.textContent = `▶ ${volTxt} 이어서 읽기`;
                goToNextActionButton.style.display = 'inline-flex';
                goToNextActionButton.onclick = () => {
                    window.location.href = `/reader/${data.next_file_id}`;
                };
            } else {
                nextVolumeMessage.textContent = '이 책의 모든 권을 완독하셨거나 단행본의 마지막 페이지입니다. 수고하셨습니다! 👏';
                goToNextActionButton.style.display = 'none';
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

    // Settings modal open/close functions (ponytail: Center glassmorphic modal with click-outside-to-close)
    function openSettings() {
        if (settingsModalOverlay) {
            settingsModalOverlay.classList.remove('hidden');
        } else if (settingsPanel) {
            settingsPanel.classList.remove('hidden');
        }
    }

    function closeSettings() {
        if (settingsModalOverlay) {
            settingsModalOverlay.classList.add('hidden');
        } else if (settingsPanel) {
            settingsPanel.classList.add('hidden');
        }
    }

    function toggleSettings() {
        const isCurrentlyHidden = settingsModalOverlay ? settingsModalOverlay.classList.contains('hidden') : settingsPanel.classList.contains('hidden');
        if (isCurrentlyHidden) {
            openSettings();
        } else {
            closeSettings();
        }
    }

    settingsBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleSettings();
    });

    if (closeSettingsBtn) {
        closeSettingsBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            closeSettings();
        });
    }

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

    // Sharpen Settings (ponytail: 1-click native sharpen toggle)
    const setSharpenMode = (mode) => {
        currentSharpen = mode;
        applyColorFilters();
    };
    if (sharpenOffBtn) sharpenOffBtn.addEventListener('click', () => setSharpenMode('off'));
    if (sharpenMildBtn) sharpenMildBtn.addEventListener('click', () => setSharpenMode('mild'));
    if (sharpenStrongBtn) sharpenStrongBtn.addEventListener('click', () => setSharpenMode('strong'));

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

    // Close modal when clicking directly on the dark overlay backdrop (outside the modal card)
    if (settingsModalOverlay) {
        settingsModalOverlay.addEventListener('click', (e) => {
            if (e.target === settingsModalOverlay) {
                closeSettings();
            }
        });
    }

    // Close popups when clicking outside
    document.addEventListener('click', (e) => {
        // Fallback close settings modal if click is outside modal card and outside settingsBtn
        const isSettingsOpen = settingsModalOverlay ? !settingsModalOverlay.classList.contains('hidden') : !settingsPanel.classList.contains('hidden');
        if (isSettingsOpen && !settingsPanel.contains(e.target) && !settingsBtn.contains(e.target)) {
            closeSettings();
        }
    });

    // --- Click & Tap Navigation Zones (Left 25%, Center 50%, Right 25%) ---
    const zonePrev = document.getElementById('zone-prev');
    const zoneCenter = document.getElementById('zone-center');
    const zoneNext = document.getElementById('zone-next');

    let isControlsVisible = true;
    function toggleReaderControls() {
        isControlsVisible = !isControlsVisible;
        floatingControls.classList.toggle('reader-controls-hidden', !isControlsVisible);
        pageIndicator.classList.toggle('reader-controls-hidden', !isControlsVisible);
        const scrubber = document.getElementById('reader-scrubber-container');
        if (scrubber) scrubber.classList.toggle('reader-controls-hidden', !isControlsVisible);
    }

    if (zonePrev) {
        zonePrev.addEventListener('click', (e) => {
            e.stopPropagation();
            if (viewMode === 'rtl') onNextPage(); else onPrevPage();
        });
    }
    if (zoneNext) {
        zoneNext.addEventListener('click', (e) => {
            e.stopPropagation();
            if (viewMode === 'rtl') onPrevPage(); else onNextPage();
        });
    }
    if (zoneCenter) {
        zoneCenter.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleReaderControls();
        });
    }

    // Forward mouse wheel events over touch zones to the scrollable container
    const touchZonesWrapper = document.getElementById('reader-touch-zones');
    if (touchZonesWrapper) {
        touchZonesWrapper.addEventListener('wheel', (e) => {
            container.scrollTop += e.deltaY;
            container.scrollLeft += e.deltaX;
        }, { passive: true });
    }

    // --- Scrubber Bar Interaction ---
    const scrubberTrack = document.getElementById('scrubber-track');
    const scrubberTooltip = document.getElementById('scrubber-tooltip');

    if (scrubberTrack) {
        function updateTooltip(clientX, targetPage) {
            if (!scrubberTooltip || !pdfDoc || pdfDoc.numPages <= 0) return;
            const clampedX = Math.max(60, Math.min(window.innerWidth - 60, clientX));
            scrubberTooltip.style.left = `${clampedX}px`;
            scrubberTooltip.textContent = `p. ${targetPage} / ${pdfDoc.numPages}`;
            scrubberTooltip.classList.remove('hidden');
        }

        function hideTooltip() {
            if (scrubberTooltip) {
                scrubberTooltip.classList.add('hidden');
            }
        }

        const handleScrub = (e) => {
            if (!pdfDoc || pdfDoc.numPages <= 0) return;
            const rect = scrubberTrack.getBoundingClientRect();
            const clientX = (e.touches && e.touches.length > 0) ? e.touches[0].clientX : e.clientX;
            const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
            let targetPage = Math.max(1, Math.min(pdfDoc.numPages, Math.round(ratio * pdfDoc.numPages)));
            if (viewMode !== 'one' && targetPage % 2 === 0 && targetPage > 1) targetPage--;

            updateTooltip(clientX, targetPage);

            if (targetPage !== pageNum) {
                pageNum = targetPage;
                renderQueue(pageNum);
                updateStatus();
            }
        };

        let isScrubbing = false;

        scrubberTrack.addEventListener('mousedown', (e) => {
            isScrubbing = true;
            handleScrub(e);
        });

        window.addEventListener('mousemove', (e) => {
            if (isScrubbing) {
                handleScrub(e);
            }
        });

        window.addEventListener('mouseup', () => {
            if (isScrubbing) {
                isScrubbing = false;
                hideTooltip();
            }
        });

        scrubberTrack.addEventListener('mousemove', (e) => {
            if (!isScrubbing && pdfDoc && pdfDoc.numPages > 0) {
                const rect = scrubberTrack.getBoundingClientRect();
                const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
                const hoverPage = Math.max(1, Math.min(pdfDoc.numPages, Math.round(ratio * pdfDoc.numPages)));
                updateTooltip(e.clientX, hoverPage);
            }
        });

        scrubberTrack.addEventListener('mouseleave', () => {
            if (!isScrubbing) {
                hideTooltip();
            }
        });

        // Mobile touch scrubbing
        scrubberTrack.addEventListener('touchstart', (e) => {
            isScrubbing = true;
            handleScrub(e);
        }, { passive: true });

        scrubberTrack.addEventListener('touchmove', (e) => {
            if (isScrubbing) {
                handleScrub(e);
            }
        }, { passive: true });

        window.addEventListener('touchend', () => {
            if (isScrubbing) {
                isScrubbing = false;
                hideTooltip();
            }
        });

        window.addEventListener('touchcancel', () => {
            if (isScrubbing) {
                isScrubbing = false;
                hideTooltip();
            }
        });
    }


    // Window Resize
    window.addEventListener('resize', debounce(() => {
        if (fitMode !== 'custom') {
            renderQueue(pageNum);
        }
    }, 250));

    // Enhanced Keyboard Navigation
    document.addEventListener('keydown', (e) => {
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
        switch (e.key) {
            case 'ArrowLeft':
            case 'PageUp':
                if (viewMode === 'rtl') onNextPage(); else onPrevPage();
                e.preventDefault();
                break;
            case 'ArrowRight':
            case 'PageDown':
                if (viewMode === 'rtl') onPrevPage(); else onNextPage();
                e.preventDefault();
                break;
            case ' ': // Space bar
                if (e.shiftKey) {
                    if (viewMode === 'rtl') onNextPage(); else onPrevPage();
                } else {
                    if (viewMode === 'rtl') onPrevPage(); else onNextPage();
                }
                e.preventDefault();
                break;
            case '+':
            case '=':
                changeScale(0.2);
                e.preventDefault();
                break;
            case '-':
            case '_':
                changeScale(-0.2);
                e.preventDefault();
                break;
            case 's':
            case 'S':
                settingsBtn.click();
                e.preventDefault();
                break;
            case 'Escape':
                if ((settingsModalOverlay && !settingsModalOverlay.classList.contains('hidden')) || (settingsPanel && !settingsPanel.classList.contains('hidden'))) {
                    closeSettings();
                } else {
                    window.location.href = '/';
                }
                e.preventDefault();
                break;
        }
    });

    // --- Mobile Touch Gestures: Smooth Scroll Preservation + Tap Navigation + Swipe ---
    let touchStartTime = 0;
    let touchStartX = 0;
    let touchStartY = 0;
    let isTouchScrolling = false;

    document.addEventListener('touchstart', (e) => {
        if (e.target.closest('#settings-panel, #floating-controls, #reader-scrubber-container, button, input, a')) {
            touchStartX = 0;
            touchStartY = 0;
            return;
        }
        touchStartTime = Date.now();
        touchStartX = e.touches[0].clientX;
        touchStartY = e.touches[0].clientY;
        isTouchScrolling = false;
    }, { passive: true });

    document.addEventListener('touchmove', (e) => {
        if (touchStartX === 0) return;
        const diffX = Math.abs(e.touches[0].clientX - touchStartX);
        const diffY = Math.abs(e.touches[0].clientY - touchStartY);
        if (diffY > 8 || diffX > 8) {
            isTouchScrolling = true;
        }
    }, { passive: true });

    document.addEventListener('touchend', (e) => {
        if (touchStartX === 0) return;

        const endX = e.changedTouches[0].clientX;
        const endY = e.changedTouches[0].clientY;
        const diffX = endX - touchStartX;
        const diffY = endY - touchStartY;
        const touchDuration = Date.now() - touchStartTime;

        // 1. Horizontal Swipe: Swipe left/right turns page
        if (Math.abs(diffX) >= 45 && Math.abs(diffX) > Math.abs(diffY) * 1.5) {
            if (diffX < 0) {
                if (viewMode === 'rtl') onPrevPage(); else onNextPage();
            } else {
                if (viewMode === 'rtl') onNextPage(); else onPrevPage();
            }
            touchStartX = 0;
            touchStartY = 0;
            return;
        }

        // 2. Pure Tap (Not a drag/scroll, short duration, minimal displacement)
        // This ensures scrolling never triggers accidental page flips or menu toggling!
        if (!isTouchScrolling && Math.abs(diffX) < 12 && Math.abs(diffY) < 12 && touchDuration < 350) {
            const screenWidth = window.innerWidth;
            const leftBoundary = screenWidth * 0.25;
            const rightBoundary = screenWidth * 0.75;

            if (endX <= leftBoundary) {
                if (viewMode === 'rtl') onNextPage(); else onPrevPage();
            } else if (endX >= rightBoundary) {
                if (viewMode === 'rtl') onPrevPage(); else onNextPage();
            } else {
                toggleReaderControls();
            }
        }

        touchStartX = 0;
        touchStartY = 0;
        isTouchScrolling = false;
    });

    // --- Initial Load ---
    const loaderOverlay = document.getElementById('loader-overlay');
    pdfjsLib.getDocument(pdfUrl).promise.then(doc => {
        pdfDoc = doc;
        pageCountSpan.textContent = pdfDoc.numPages;
        renderQueue(pageNum);
        updateScrubberUI();
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