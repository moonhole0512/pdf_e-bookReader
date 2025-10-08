document.addEventListener('DOMContentLoaded', () => {
    // --- LocalStorage Keys ---
    const FIT_MODE_KEY = 'pdfReaderFitMode';
    const SCALE_KEY = 'pdfReaderScale';
    const VIEW_MODE_KEY = 'pdfReaderViewMode'; // Changed from TWO_PAGE_MODE_KEY

    // --- Load settings from LocalStorage ---
    const savedFitMode = localStorage.getItem(FIT_MODE_KEY);
    const savedScale = parseFloat(localStorage.getItem(SCALE_KEY));
    const savedViewMode = localStorage.getItem(VIEW_MODE_KEY);

    // --- DOM Elements ---
    const body = document.body;
    const fileId = body.dataset.fileId;
    const pdfUrl = body.dataset.pdfUrl;
    const initialPage = parseInt(body.dataset.initialPage, 10);
    const viewer = document.getElementById('pdf-viewer');
    const container = document.getElementById('reader-container');
    const pageNumSpan = document.getElementById('page-num');
    const pageCountSpan = document.getElementById('page-count');
    const viewModeButton = document.getElementById('toggle-view');
    const readerControls = document.querySelector('.reader-controls');
    const toggleColorSettingsBtn = document.getElementById('toggle-color-settings');
    const colorSettingsPanel = document.getElementById('color-settings-panel');
    const brightnessSlider = document.getElementById('brightness-slider');
    const contrastSlider = document.getElementById('contrast-slider');
    const saturationSlider = document.getElementById('saturation-slider');
    const resetColorSettingsBtn = document.getElementById('reset-color-settings');
    const invertColorsToggle = document.getElementById('invert-colors-toggle');

    // --- LocalStorage Keys for Color Settings ---
    const BRIGHTNESS_KEY = 'pdfReaderBrightness';
    const CONTRAST_KEY = 'pdfReaderContrast';
    const SATURATION_KEY = 'pdfReaderSaturation';
    const INVERT_COLORS_KEY = 'pdfReaderInvertColors';

    // --- Default Color Settings ---
    const DEFAULT_BRIGHTNESS = 100;
    const DEFAULT_CONTRAST = 100;
    const DEFAULT_SATURATION = 100;
    const DEFAULT_INVERT_COLORS = false;

    // --- Load Color Settings from LocalStorage ---
    let currentBrightness = parseInt(localStorage.getItem(BRIGHTNESS_KEY) || DEFAULT_BRIGHTNESS, 10);
    let currentContrast = parseInt(localStorage.getItem(CONTRAST_KEY) || DEFAULT_CONTRAST, 10);
    let currentSaturation = parseInt(localStorage.getItem(SATURATION_KEY) || DEFAULT_SATURATION, 10);
    let isInverted = (localStorage.getItem(INVERT_COLORS_KEY) === 'true');

    // --- State Variables ---
    let pdfDoc = null;
    let pageNum = initialPage;
    let pageRendering = false;
    let pageNumPending = null;
    let fitMode = savedFitMode || 'width';
    let scale = !isNaN(savedScale) ? savedScale : 1.5;
    let viewMode = savedViewMode || 'one'; // 'one', 'ltr' (Left-to-Right), 'rtl' (Right-to-Left)
    let controlsHideTimeout;

    updateFitModeUI(); // Call on initial load
    applyColorFilters(); // Apply saved color filters on initial load

    // --- UI Update Functions ---
    function updateFitModeUI() {
        const fitWidthBtn = document.getElementById('fit-to-width');
        const fitHeightBtn = document.getElementById('fit-to-height');

        fitWidthBtn.classList.remove('active-fit-mode');
        fitHeightBtn.classList.remove('active-fit-mode');

        if (fitMode === 'width') {
            fitWidthBtn.classList.add('active-fit-mode');
        } else if (fitMode === 'height') {
            fitHeightBtn.classList.add('active-fit-mode');
        }
    }

    function applyColorFilters() {
        let filterString = `brightness(${currentBrightness}%) contrast(${currentContrast}%) saturate(${currentSaturation}%)`;
        if (isInverted) {
            filterString += ' invert(100%)';
        }
        viewer.style.filter = filterString;

        // Update slider UI
        brightnessSlider.value = currentBrightness;
        contrastSlider.value = currentContrast;
        saturationSlider.value = currentSaturation;
        invertColorsToggle.checked = isInverted;

        // Save to localStorage
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
            viewer.appendChild(canvas2); // Page N+1 first
            viewer.appendChild(canvas1); // Page N second
        } else { // 'ltr'
            viewer.appendChild(canvas1); // Page N first
            viewer.appendChild(canvas2); // Page N+1 second
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

    function updateViewModeButton() {
        if (viewMode === 'one') viewModeButton.textContent = '1';
        else if (viewMode === 'ltr') viewModeButton.textContent = '1/2';
        else viewModeButton.textContent = '2/1';
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
        updateFitModeUI(); // Update UI after fitMode changes
        renderQueue(pageNum);
    }

    function toggleViewMode() {
        if (viewMode === 'one') viewMode = 'ltr';
        else if (viewMode === 'ltr') viewMode = 'rtl';
        else viewMode = 'one';
        
        localStorage.setItem(VIEW_MODE_KEY, viewMode);
        updateViewModeButton();

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
            // Fallback: if error, just go back to library
            window.location.href = '/';
        }
    }

    // --- Event Listeners ---
    document.getElementById('prev-page').addEventListener('click', onPrevPage);
    document.getElementById('next-page').addEventListener('click', onNextPage);
    document.getElementById('zoom-in').addEventListener('click', () => changeScale(0.2));
    document.getElementById('zoom-out').addEventListener('click', () => changeScale(-0.2));
    viewModeButton.addEventListener('click', toggleViewMode);
    document.getElementById('fit-to-width').addEventListener('click', () => {
        fitMode = 'width';
        localStorage.setItem(FIT_MODE_KEY, 'width');
        updateFitModeUI(); // Update UI after fitMode changes
        renderQueue(pageNum);
    });
    document.getElementById('fit-to-height').addEventListener('click', () => {
        fitMode = 'height';
        localStorage.setItem(FIT_MODE_KEY, 'height');
        updateFitModeUI(); // Update UI after fitMode changes
        renderQueue(pageNum);
    });

    // --- Color Settings Event Listeners ---
    toggleColorSettingsBtn.addEventListener('click', () => {
        colorSettingsPanel.classList.toggle('hidden');
        if (!colorSettingsPanel.classList.contains('hidden')) { // If panel is now visible
            clearTimeout(controlsHideTimeout);
            readerControls.classList.add('visible');
        }
    });

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

    window.addEventListener('resize', debounce(() => {
        if (fitMode !== 'custom') {
            renderQueue(pageNum);
        }
    }, 250));

    // --- Mouse movement for controls visibility ---
    document.body.addEventListener('mousemove', (e) => {
        clearTimeout(controlsHideTimeout);
        if (e.clientY < 100) { // If mouse is in the top 100px of the screen
            readerControls.classList.add('visible');
        } else {
            if (colorSettingsPanel.classList.contains('hidden')) { // Only hide if color settings panel is hidden
                controlsHideTimeout = setTimeout(() => {
                    readerControls.classList.remove('visible');
                }, 1000); // Hide after 1 second of inactivity
            }
        }
    });

    // --- Touch for controls visibility (for mobile/tablet) ---
    document.body.addEventListener('touchstart', (e) => {
        if (e.touches[0].clientY < 100) { // Only show if touch is in the top 100px of the screen
            clearTimeout(controlsHideTimeout);
            readerControls.classList.add('visible');
            if (colorSettingsPanel.classList.contains('hidden')) { // Only set hide timeout if color settings panel is hidden
                controlsHideTimeout = setTimeout(() => {
                    readerControls.classList.remove('visible');
                }, 3000); // Hide after 3 seconds of inactivity
            }
        }
    });

    // --- Close color settings panel when clicking outside ---
    document.body.addEventListener('click', (e) => {
        const isClickInsidePanel = colorSettingsPanel.contains(e.target);
        const isClickOnToggleButton = toggleColorSettingsBtn.contains(e.target);

        if (!colorSettingsPanel.classList.contains('hidden') && !isClickInsidePanel && !isClickOnToggleButton) {
            colorSettingsPanel.classList.add('hidden');
        }
    });

    // --- Keyboard Navigation ---
    document.addEventListener('keydown', (e) => {
        const scrollAmount = 100; // Amount to scroll by
        switch (e.key) {
            case 'ArrowUp':
                if (container.scrollTop === 0) {
                    onPrevPage();
                } else {
                    container.scrollBy(0, -scrollAmount);
                }
                e.preventDefault(); // Prevent default browser scroll
                break;
            case 'ArrowDown':
                if (container.scrollTop + container.clientHeight >= container.scrollHeight) {
                    onNextPage();
                } else {
                    container.scrollBy(0, scrollAmount);
                }
                e.preventDefault(); // Prevent default browser scroll
                break;
            case 'ArrowLeft':
                onPrevPage();
                e.preventDefault();
                break;
            case 'ArrowRight':
                onNextPage();
                e.preventDefault();
                break;
        }
    });

    // --- Initial Load ---
    const loaderOverlay = document.getElementById('loader-overlay');

    pdfjsLib.getDocument(pdfUrl).promise.then(doc => {
        pdfDoc = doc;
        pageCountSpan.textContent = pdfDoc.numPages;
        updateViewModeButton(); // Set initial button text
        
        // Render the first page, then hide the loader.
        renderQueue(pageNum);

        // The rendering itself is async, so we can't hide the loader immediately.
        // A simple approach is to hide it after a short delay, assuming rendering has started.
        // A better way would be to use the promise from renderPage.
        // Let's modify renderPage to return its promise.
    }).finally(() => {
        // A simple way to hide the loader. This hides it after the PDF is loaded,
        // but maybe before the first page is fully rendered. It's a good compromise.
        setTimeout(() => { // Use a small timeout to ensure a smoother transition
            loaderOverlay.classList.add('hidden');
        }, 200);
    });

    // --- Swipe Navigation ---
    let startX = 0;
    let startY = 0;
    const swipeThreshold = 50; // Minimum pixels to be considered a swipe

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
            // Horizontal swipe
            if (diffX > 0) {
                // Swiped left, go to next page
                onNextPage();
            } else {
                // Swiped right, go to previous page
                onPrevPage();
            }
        }
        // Reset start coordinates
        startX = 0;
        startY = 0;
    });

    function debounce(func, delay) {
        let timeout;
        return function(...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), delay);
        };
    }
});