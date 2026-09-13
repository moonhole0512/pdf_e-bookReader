
document.addEventListener('DOMContentLoaded', () => {
    // --- ISBN Modal Elements ---
    const isbnModal = document.getElementById('isbn-modal');
    const closeIsbnModalBtn = document.getElementById('modal-close-btn');
    const isbnModalTitle = document.getElementById('modal-title');
    const fileIdInput = document.getElementById('modal-book-id');
    const searchBtn = document.getElementById('isbn-search-btn');
    const registerBtn = document.getElementById('isbn-register-btn');
    const isbnInput = document.getElementById('isbn-input');
    const resultsDiv = document.getElementById('isbn-results');
    
    // --- Volume Select Modal Elements ---
    const volumeModal = document.getElementById('volume-select-modal');
    const volumeModalTitle = document.getElementById('volume-modal-title');
    const volumeList = document.getElementById('volume-list');
    const closeVolumeModalBtn = document.getElementById('volume-modal-close-btn');

    let selectedCoverUrl = null;
    let selectedBookData = null; // Includes metadata used for library category filtering.

    // --- Functions ---

    const renderSearchLoading = (targetTitle, volumeNumber = null) => {
        const volText = volumeNumber ? `<span class="search-target-vol-badge">제${volumeNumber}권</span>` : '';
        return `
            <div class="isbn-search-loading-card">
                <div class="search-pulse-visual">
                    <div class="search-pulse-ring"></div>
                    <div class="search-pulse-ring pulse-delay"></div>
                    <div class="search-pulse-core">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <circle cx="11" cy="11" r="8"></circle>
                            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                        </svg>
                    </div>
                </div>
                <div class="search-loading-content">
                    <h4 class="search-loading-title">도서 정보 검색 중</h4>
                    <div class="search-target-pill">
                        <span class="target-title-text" title="${targetTitle}">${targetTitle}</span>
                        ${volText}
                    </div>
                    <p class="search-step-desc">알라딘 · Google Books · Amazon 서지 데이터베이스에서<br>고화질 원본 표지와 작가·도서 정보를 정밀 조회하고 있습니다.</p>
                </div>
            </div>
        `;
    };

    const openIsbnModal = async (e) => {
        e.preventDefault();
        e.stopPropagation();
        
        const btn = e.target.closest('.isbn-btn'); // Use closest for robustness
        if (!btn) return; // Should not happen if called from event listener

        const fileId = btn.dataset.fileId;
        const bookTitle = btn.dataset.bookTitle;
        const volumeNumber = btn.dataset.volumeNumber; // Get volume number

        fileIdInput.value = fileId;
        isbnModalTitle.textContent = `'${bookTitle}' 정보 업데이트`;
        isbnModal.classList.remove('hidden');

        // Close volume selection modal if it is open
        if (!volumeModal.classList.contains('hidden')) {
            closeVolumeModal();
        }

        // Clear previous results and show rich informative loading state
        resultsDiv.innerHTML = renderSearchLoading(bookTitle, volumeNumber);
        registerBtn.disabled = true;
        registerBtn.textContent = '등록';
        selectedCoverUrl = null;
        selectedBookData = null;
        isbnInput.value = ''; // Clear manual ISBN input

        try {
            const response = await fetch(`/api/book/lookup_by_title_volume?title=${encodeURIComponent(bookTitle)}&volume=${encodeURIComponent(volumeNumber || '')}`);
            const data = await response.json();

            if (response.ok) {
                if (Array.isArray(data)) {
                    // Multiple results, let user choose
                    displayMultipleResults(data);
                } else {
                    // Single result found, populate automatically
                    displaySingleResult(data);
                }
            } else {
                // No unique result, fall back to manual ISBN input
                resultsDiv.innerHTML = `<p class="error">${data.error || '책 정보를 자동으로 찾을 수 없습니다. 수동으로 ISBN을 입력해주세요.'}</p>`;
            }

        } catch (error) {
            console.error('Error during automatic book lookup:', error);
            resultsDiv.innerHTML = `<p class="error">자동 검색 중 네트워크 오류가 발생했습니다. 수동으로 ISBN을 입력해주세요.</p>`;
        }
    };

    const displaySingleResult = (data) => {
        resultsDiv.classList.remove('has-multiple-results');
        selectedCoverUrl = data.thumbnail || null;
        selectedBookData = {
            title: data.title || '',
            author: data.author || '',
            cover_url: data.thumbnail || '',
            isbn_13: data.isbn_13 || '',
            isbn_10: data.isbn_10 || '',
            source_category: data.source_category || '',
            category: data.category || '',
            metadata_source: data.source || '',
            product_url: data.product_url || ''
        };
        
        let imagesHtml = '';
        if (data.thumbnail) {
            imagesHtml = `<img src="${data.thumbnail}" alt="Book Cover" id="cover-preview-img" class="cover-preview selected">`;
        } else {
            const title = data.title || '도서';
            let query = title;
            if (data.volume_number && !title.includes(String(data.volume_number))) {
                query += ` ${data.volume_number}`;
            }
            query += ' 표지';
            const googleImagesUrl = `https://www.google.com/search?tbm=isch&q=${encodeURIComponent(query)}`;

            imagesHtml = `
                <div id="manual-cover-input-group">
                    <input type="text" id="manual-cover-url" placeholder="이미지 URL을 직접 붙여넣으세요">
                    <a href="${googleImagesUrl}" target="_blank" rel="noopener noreferrer" id="cover-search-btn">표지 검색</a>
                </div>
                <p id="no-cover-message">표지 이미지를 찾을 수 없습니다.</p>
                <div id="cover-search-results" class="book-grid"></div>
                <img src="" alt="미리보기" id="cover-preview-img" class="cover-preview" style="display:none; margin-top: 10px;">
            `;
        }

        resultsDiv.innerHTML = `
            <div id="result-info">
                <p><strong>제목:</strong> <span id="result-title">${data.title || 'N/A'}</span></p>
                <p><strong>저자:</strong> <span id="result-author">${data.author || 'N/A'}</span></p>
                <p><strong>ISBN:</strong> <span id="result-isbn">${data.isbn_13 || data.isbn_10 || 'N/A'}</span></p>
            </div>
            <div id="result-images">${imagesHtml}</div>
        `;

        if (!data.thumbnail) {
            const noCoverMessage = document.getElementById('no-cover-message');
            document.getElementById('manual-cover-url').addEventListener('input', (e) => {
                const url = e.target.value.trim();
                const previewImg = document.getElementById('cover-preview-img');
                if (url) {
                    previewImg.src = url;
                    previewImg.style.display = 'block';
                    selectedCoverUrl = url;
                    if (selectedBookData) selectedBookData.cover_url = url;
                    if (noCoverMessage) noCoverMessage.style.display = 'none';
                    document.getElementById('cover-search-results').innerHTML = '';
                    registerBtn.disabled = false;
                } else {
                    previewImg.style.display = 'none';
                    if (noCoverMessage) noCoverMessage.style.display = 'block';
                    registerBtn.disabled = true;
                }
            });
        }

        registerBtn.disabled = !selectedCoverUrl;
        registerBtn.textContent = '등록';
    };

    const displayMultipleResults = (results) => {
        resultsDiv.classList.add('has-multiple-results');
        resultsDiv.innerHTML = '<p style="margin-bottom: 12px; font-weight: 500; color: #a1a1aa;">여러 결과가 검색되었습니다. 등록할 책을 선택해주세요:</p>';
        const selectionGrid = document.createElement('div');
        selectionGrid.className = 'book-grid';

        results.forEach((book, idx) => {
            const bookCard = document.createElement('div');
            bookCard.className = 'book-card-small';
            bookCard.dataset.title = book.title;
            bookCard.dataset.author = book.author;
            bookCard.dataset.coverUrl = book.thumbnail || '';
            bookCard.dataset.isbn13 = book.isbn_13 || '';
            bookCard.dataset.isbn10 = book.isbn_10 || '';
            bookCard.dataset.sourceCategory = book.source_category || '';
            bookCard.dataset.category = book.category || '';
            bookCard.dataset.metadataSource = book.source || '';
            bookCard.dataset.productUrl = book.product_url || '';

            const placeholder = `https://placehold.co/150x225/2a2a2a/ffffff?text=No IMG`;
            const cover = book.thumbnail || placeholder;

            bookCard.innerHTML = `
                <img src="${cover}" alt="${book.title}">
                <div class="book-info-small">
                    <p title="${book.title}">${book.title}</p>
                    <span title="${book.author || ''}">${book.author || '저자 미상'}</span>
                    ${book.isbn_13 ? `<small class="isbn-tag" style="display:block; font-size: 10px; color: #8e8e93; margin-top:2px;">${book.isbn_13}</small>` : ''}
                </div>
            `;
            selectionGrid.appendChild(bookCard);
        });

        resultsDiv.appendChild(selectionGrid);

        // Placeholder for live selection confirmation box
        const summaryBox = document.createElement('div');
        summaryBox.id = 'selected-book-summary';
        resultsDiv.appendChild(summaryBox);

        selectionGrid.addEventListener('click', (e) => {
            const selectedCard = e.target.closest('.book-card-small');
            if (!selectedCard) return;

            // Remove previous selection
            document.querySelectorAll('.book-card-small.selected').forEach(card => {
                card.classList.remove('selected');
            });

            // Add new selection
            selectedCard.classList.add('selected');

            // Populate selectedBookData with the chosen candidate
            selectedBookData = {
                title: selectedCard.dataset.title || '',
                author: selectedCard.dataset.author || '',
                cover_url: selectedCard.dataset.coverUrl || '',
                isbn_13: selectedCard.dataset.isbn13 || '',
                isbn_10: selectedCard.dataset.isbn10 || '',
                source_category: selectedCard.dataset.sourceCategory || '',
                category: selectedCard.dataset.category || '',
                metadata_source: selectedCard.dataset.metadataSource || '',
                product_url: selectedCard.dataset.productUrl || ''
            };

            selectedCoverUrl = selectedBookData.cover_url;

            // Update live summary box
            summaryBox.className = 'selected-summary-box';
            summaryBox.innerHTML = `
                <div class="summary-check-icon">✓ 선택됨</div>
                <div class="summary-details">
                    <p><strong>제목:</strong> ${selectedBookData.title}</p>
                    <p><strong>저자:</strong> ${selectedBookData.author || '저자 미상'}</p>
                    ${selectedBookData.isbn_13 ? `<p><strong>ISBN:</strong> ${selectedBookData.isbn_13}</p>` : ''}
                </div>
            `;

            registerBtn.disabled = !selectedCoverUrl;
            registerBtn.textContent = '등록';
        });

        // Auto-select the first candidate (highest scored) if available
        const firstCard = selectionGrid.querySelector('.book-card-small');
        if (firstCard) {
            firstCard.click();
        }
    };

    const closeIsbnModal = () => {
        isbnModal.classList.add('hidden');
        resultsDiv.innerHTML = '';
        resultsDiv.classList.remove('has-multiple-results');
        isbnInput.value = '';
        registerBtn.disabled = true;
        registerBtn.textContent = '등록';
        selectedCoverUrl = null;
        selectedBookData = null;
        isbnInput.style.display = 'block'; // Ensure manual input is visible next time
        searchBtn.style.display = 'block'; // Ensure manual search button is visible next time
    };

    const openVolumeModal = (card) => {
        const volumes = JSON.parse(card.dataset.volumes);
        const seriesTitle = card.dataset.seriesTitle;
        
        volumeModalTitle.textContent = seriesTitle;
        volumeList.innerHTML = ''; // Clear previous list

        // Find which volume is the next one to read
        // It is either the first unread volume after completed ones, or the currently reading volume
        let nextToReadVolId = null;
        const readingVol = volumes.find(v => v.current_page > 0 && !(v.total_pages > 0 && v.current_page >= v.total_pages * 0.95));
        if (readingVol) {
            nextToReadVolId = readingVol.id;
        } else {
            const firstUnread = volumes.find(v => (v.current_page || 0) === 0);
            if (firstUnread) {
                nextToReadVolId = firstUnread.id;
            }
        }

        volumes.forEach(vol => {
            const volCard = document.createElement('div');
            volCard.className = 'book-card vol-item-card';

            const placeholder = `https://placehold.co/300x450/2a2a2a/ffffff?text=No IMG`;
            const cover = vol.cover_url || placeholder;
            const hasPages = (vol.total_pages && vol.total_pages > 0);
            const curPage = vol.current_page || 0;
            const totalPages = vol.total_pages || 0;
            const isCompleted = (hasPages && curPage >= totalPages * 0.95);
            const isReading = (curPage > 0 && !isCompleted);
            const isNextToRead = (vol.id === nextToReadVolId);

            if (isCompleted) volCard.classList.add('vol-completed');
            if (isNextToRead) volCard.classList.add('vol-next-focus');

            let badgeHtml = '';
            if (isCompleted) {
                badgeHtml = '<div class="completed-badge">완독 ✓</div>';
            } else if (isNextToRead) {
                badgeHtml = '<div class="next-to-read-badge">다음 차례</div>';
            } else if (isReading) {
                badgeHtml = '<div class="reading-badge">읽는 중</div>';
            }

            // Standardized progress & status text across ALL volumes (even unread ones)
            const pct = hasPages ? Math.min(100, Math.round((curPage / totalPages) * 100)) : 0;
            let progressLabel = '';
            if (hasPages) {
                if (isCompleted) {
                    progressLabel = `완독 (${totalPages}p)`;
                } else if (curPage > 0) {
                    progressLabel = `${curPage} / ${totalPages}p (${pct}%)`;
                } else {
                    progressLabel = `미독 (총 ${totalPages}p)`;
                }
            } else {
                progressLabel = '미독 (읽기 시작)';
            }

            volCard.innerHTML = `
                <a href="/reader/${vol.id}" class="vol-card-main-link">
                    <div class="vol-thumb-wrapper book-cover-container">
                        <img src="${cover}" alt="${vol.title || 'No Title'}">
                        <div class="book-spine-crease"></div>
                        ${badgeHtml}
                    </div>
                    <div class="book-info vol-book-info">
                        <h3>제 ${vol.volume_number}권</h3>
                        <p title="${vol.title || '제목 없음'}">${vol.title || '제목 없음'}</p>
                    </div>
                </a>
                <div class="vol-card-footer">
                    <div class="vol-progress-slot">
                        <div class="progress-bar-container">
                            <div class="progress-bar" style="width: ${pct}%;"></div>
                        </div>
                        <span class="progress-text">${progressLabel}</span>
                    </div>
                    <div class="vol-action-row">
                        <button type="button" class="isbn-btn vol-isbn-btn" data-file-id="${vol.id}" data-book-title="${vol.title || '제목 없음'}" data-volume-number="${vol.volume_number}" title="도서 메타데이터 및 표지 수정">ISBN</button>
                    </div>
                </div>
            `;
            volumeList.appendChild(volCard);
        });

        volumeModal.classList.remove('hidden');
    };

    const closeVolumeModal = () => {
        volumeModal.classList.add('hidden');
    };

    const searchIsbn = async () => {
        const query = isbnInput.value.trim();
        if (!query) return;

        resultsDiv.innerHTML = renderSearchLoading(query, null);
        registerBtn.disabled = true;

        try {
            const isIsbn = /^[\d-]+[xX]?$/.test(query.replace(/\s+/g, '')) && query.replace(/[-\s]/g, '').length >= 9;
            const endpoint = isIsbn
                ? `/api/book/lookup?isbn=${encodeURIComponent(query)}`
                : `/api/book/lookup_by_title_volume?title=${encodeURIComponent(query)}`;

            const response = await fetch(endpoint);
            const data = await response.json();

            if (!response.ok) {
                resultsDiv.innerHTML = `<p class="error">오류: ${data.error || '도서 정보를 찾을 수 없습니다.'}</p>`;
                return;
            }

            if (Array.isArray(data)) {
                displayMultipleResults(data);
            } else {
                displaySingleResult(data);
            }

        } catch (error) {
            resultsDiv.innerHTML = `<p class="error">네트워크 오류가 발생했습니다.</p>`;
        }
    };

    const registerInfo = async () => {
        const fileId = fileIdInput.value;
        if (!fileId) {
            alert('대상 도서 파일을 식별할 수 없습니다.');
            return;
        }

        // Determine title, author, and cover safely from selectedBookData or DOM
        let title = '';
        let author = '';
        let coverUrl = selectedCoverUrl;

        if (selectedBookData) {
            title = selectedBookData.title || '';
            author = selectedBookData.author || '';
            coverUrl = selectedBookData.cover_url || coverUrl;
        } else {
            const titleEl = document.getElementById('result-title');
            const authorEl = document.getElementById('result-author');
            if (titleEl) title = titleEl.textContent;
            if (authorEl) author = authorEl.textContent;
        }

        if (!coverUrl) {
            alert('표지 이미지가 선택되지 않았습니다.');
            return;
        }

        registerBtn.disabled = true;
        registerBtn.textContent = '등록 중...';

        try {
            const response = await fetch('/api/file/update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    file_id: fileId,
                    title: title,
                    author: author,
                    cover_url: coverUrl,
                    isbn_13: selectedBookData?.isbn_13 || '',
                    source_category: selectedBookData?.source_category || '',
                    category: selectedBookData?.category || '',
                    metadata_source: selectedBookData?.metadata_source || '',
                    product_url: selectedBookData?.product_url || ''
                })
            });

            if (!response.ok) throw new Error('Update failed');
            
            const data = await response.json();

            showToast('도서 정보가 성공적으로 등록되었습니다!');
            closeIsbnModal();

            // Refresh library view after short delay so updated cover and title appear
            setTimeout(() => {
                location.reload();
            }, 500);

        } catch (error) {
            console.error('Error registering book info:', error);
            alert('책 정보 업데이트에 실패했습니다.');
            registerBtn.disabled = false;
            registerBtn.textContent = '등록';
        }
    };

    // --- Event Listeners ---

    // Main click handler for cards and buttons
    document.body.addEventListener('click', (e) => {
        // For opening ISBN modal
        if (e.target.matches('.isbn-btn') || e.target.closest('.isbn-btn')) {
            openIsbnModal(e);
            return;
        }

        // For opening Volume Select modal when clicking series view button or volume badge
        const seriesBtn = e.target.closest('.series-view-btn');
        if (seriesBtn) {
            e.stopPropagation();
            openVolumeModal(seriesBtn);
            return;
        }

        const volumeBadge = e.target.closest('.volume-badge');
        if (volumeBadge) {
            const card = volumeBadge.closest('.book-card[data-is-group="true"]');
            if (card && parseInt(card.dataset.volumeCount, 10) > 1) {
                e.stopPropagation();
                openVolumeModal(card);
                return;
            }
        }

        // Clicking the Reading Lounge Hero card: navigate directly to reader
        const loungeCard = e.target.closest('.reading-lounge-card');
        if (loungeCard && !e.target.closest('a') && !e.target.closest('button')) {
            if (loungeCard.dataset.url) {
                window.location.href = loungeCard.dataset.url;
                return;
            }
        }

        // Clicking any book card: navigate directly to last read position (or 1st volume)
        const card = e.target.closest('.book-card[data-is-group="true"]');
        if (card) {
            const targetUrl = card.dataset.targetUrl || card.dataset.singleUrl;
            if (targetUrl) {
                window.location.href = targetUrl;
            } else {
                openVolumeModal(card);
            }
        }
    });

    // Suppress parent card tooltip when hovering over ISBN button to prevent tooltip collision
    document.body.addEventListener('mouseover', (e) => {
        const isbnBtn = e.target.closest('.isbn-btn');
        if (isbnBtn) {
            const parentCard = isbnBtn.closest('.book-card');
            if (parentCard && parentCard.hasAttribute('title')) {
                parentCard.dataset.savedTitle = parentCard.getAttribute('title');
                parentCard.removeAttribute('title');
            }
        }
    });

    document.body.addEventListener('mouseout', (e) => {
        const isbnBtn = e.target.closest('.isbn-btn');
        if (isbnBtn) {
            const parentCard = isbnBtn.closest('.book-card');
            if (parentCard && parentCard.dataset.savedTitle) {
                parentCard.setAttribute('title', parentCard.dataset.savedTitle);
                delete parentCard.dataset.savedTitle;
            }
        }
    });

    // Listeners for ISBN modal
    closeIsbnModalBtn.addEventListener('click', closeIsbnModal);
    isbnModal.addEventListener('click', (e) => {
        if (e.target === isbnModal) closeIsbnModal();
    });
    searchBtn.addEventListener('click', searchIsbn);
    registerBtn.addEventListener('click', registerInfo);

    // Listeners for Volume Select modal
    if (closeVolumeModalBtn) closeVolumeModalBtn.addEventListener('click', closeVolumeModal);
    const volumeModalCloseIcon = document.getElementById('volume-modal-close-icon');
    if (volumeModalCloseIcon) volumeModalCloseIcon.addEventListener('click', closeVolumeModal);
    if (volumeModal) {
        volumeModal.addEventListener('click', (e) => {
            if (e.target === volumeModal) closeVolumeModal();
        });
    }

    // --- Scan Button Logic ---
    const scanPdfBtn = document.getElementById('scan-pdf-btn');
    const scanSettingsBtn = document.getElementById('scan-settings-btn');
    const scanSettingsModal = document.getElementById('scan-settings-modal');
    const scanSettingsCloseBtn = document.getElementById('scan-settings-close-btn');
    const scanSettingsSaveBtn = document.getElementById('scan-settings-save-btn');
    const scanBatchSizeInput = document.getElementById('scan-batch-size');
    const toast = document.getElementById('toast-notification');

    // Load saved batch size or use default
    scanBatchSizeInput.value = localStorage.getItem('scanBatchSize') || 30;

    function showToast(message, isError = false) {
        toast.textContent = message;
        toast.style.backgroundColor = isError ? '#dc3545' : '#28a745';
        toast.classList.add('show');
        setTimeout(() => {
            toast.classList.remove('show');
            if (!isError) {
                setTimeout(() => {
                    location.reload();
                }, 500); // Wait for fade out animation
            }
        }, 2500);
    }

    if (scanSettingsBtn) {
        scanSettingsBtn.addEventListener('click', () => {
            scanSettingsModal.classList.remove('hidden');
        });

        scanSettingsCloseBtn.addEventListener('click', () => {
            scanSettingsModal.classList.add('hidden');
        });

        scanSettingsSaveBtn.addEventListener('click', () => {
            const batchSize = scanBatchSizeInput.value;
            localStorage.setItem('scanBatchSize', batchSize);
            scanSettingsModal.classList.add('hidden');
            showToast(`스캔 단위가 ${batchSize}로 저장되었습니다.`);
        });

        scanSettingsModal.addEventListener('click', (e) => {
            if (e.target === scanSettingsModal) {
                scanSettingsModal.classList.add('hidden');
            }
        });
    }

    if (scanPdfBtn) {
        let scanPollInterval = null;

        const pollScanStatus = () => {
            scanPollInterval = setInterval(async () => {
                try {
                    const res = await fetch('/api/admin/scan/status');
                    if (!res.ok) return;
                    const status = await res.json();

                    if (status.state === 'running') {
                        scanPdfBtn.textContent = `스캔 중 (${status.total_scanned}개)`;
                    } else if (status.state === 'completed') {
                        clearInterval(scanPollInterval);
                        scanPollInterval = null;
                        showToast(status.message || '스캔 완료!');
                        scanPdfBtn.textContent = 'PDF 스캔';
                        scanPdfBtn.disabled = false;
                        scanSettingsBtn.disabled = false;
                        // Reload bookshelf to display newly added books
                        setTimeout(() => location.reload(), 1200);
                    } else if (status.state === 'error') {
                        clearInterval(scanPollInterval);
                        scanPollInterval = null;
                        showToast(status.message || '스캔 실패', true);
                        scanPdfBtn.textContent = 'PDF 스캔';
                        scanPdfBtn.disabled = false;
                        scanSettingsBtn.disabled = false;
                    }
                } catch (e) {
                    console.error('Error polling scan status:', e);
                }
            }, 1000);
        };

        scanPdfBtn.addEventListener('click', async function(event) {
            event.preventDefault();
            
            scanPdfBtn.textContent = '스캔 시작...';
            scanPdfBtn.disabled = true;
            scanSettingsBtn.disabled = true;

            const batchSize = localStorage.getItem('scanBatchSize') || 30;

            try {
                const response = await fetch(`/admin/scan?batch_size=${batchSize}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                
                const data = await response.json();

                if (response.ok || response.status === 409) {
                    showToast(data.message || '스캔이 시작되었습니다.');
                    pollScanStatus();
                } else {
                    showToast('스캔 요청 실패: ' + (data.error || response.statusText), true);
                    scanPdfBtn.textContent = 'PDF 스캔';
                    scanPdfBtn.disabled = false;
                    scanSettingsBtn.disabled = false;
                }
            } catch (error) {
                console.error('Error starting PDF scan:', error);
                showToast('스캔 요청 중 오류가 발생했습니다.', true);
                scanPdfBtn.textContent = 'PDF 스캔';
                scanPdfBtn.disabled = false;
                scanSettingsBtn.disabled = false;
            }
        });
    }

    // --- Auto Metadata Enrichment Logic ---
    const autoEnrichBtn = document.getElementById('auto-enrich-btn');
    if (autoEnrichBtn) {
        let enrichPollInterval = null;

        const pollEnrichStatus = () => {
            enrichPollInterval = setInterval(async () => {
                try {
                    const res = await fetch('/api/admin/enrich/status');
                    if (!res.ok) return;
                    const status = await res.json();

                    if (status.state === 'running') {
                        const total = status.total_books || 0;
                        const processed = status.processed_books || 0;
                        autoEnrichBtn.textContent = total > 0 ? `취득 중 (${processed}/${total})` : '취득 중...';
                    } else if (status.state === 'completed') {
                        clearInterval(enrichPollInterval);
                        enrichPollInterval = null;
                        showToast(status.message || '도서 정보 자동 완성 완료!');
                        autoEnrichBtn.textContent = '정보 자동 검색';
                        autoEnrichBtn.disabled = false;
                        setTimeout(() => location.reload(), 1200);
                    } else if (status.state === 'error') {
                        clearInterval(enrichPollInterval);
                        enrichPollInterval = null;
                        showToast(status.message || '도서 정보 검색 오류', true);
                        autoEnrichBtn.textContent = '정보 자동 검색';
                        autoEnrichBtn.disabled = false;
                    }
                } catch (e) {
                    console.error('Error polling enrichment status:', e);
                }
            }, 1000);
        };

        autoEnrichBtn.addEventListener('click', async function(e) {
            e.preventDefault();
            autoEnrichBtn.textContent = '검색 시작...';
            autoEnrichBtn.disabled = true;

            try {
                const response = await fetch('/api/admin/enrich', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ force_all: false })
                });

                const data = await response.json();
                if (response.ok || response.status === 409) {
                    showToast(data.message || '온라인 도서 정보 검색을 시작합니다.');
                    pollEnrichStatus();
                } else {
                    showToast('요청 실패: ' + (data.error || response.statusText), true);
                    autoEnrichBtn.textContent = '정보 자동 검색';
                    autoEnrichBtn.disabled = false;
                }
            } catch (err) {
                console.error('Error starting auto enrichment:', err);
                showToast('네트워크 오류가 발생했습니다.', true);
                autoEnrichBtn.textContent = '정보 자동 검색';
                autoEnrichBtn.disabled = false;
            }
        });
    }

    // --- Autocomplete Logic ---
    const searchInput = document.querySelector('input[name="search_query"]');
    const autocompleteResults = document.getElementById('autocomplete-results');
    let activeIndex = -1;

    if (searchInput && autocompleteResults) {
        searchInput.addEventListener('input', async () => {
            const query = searchInput.value;
            activeIndex = -1; // Reset index on new input
            if (query.length < 1) {
                autocompleteResults.innerHTML = '';
                return;
            }

            try {
                const response = await fetch(`/api/books/autocomplete?q=${encodeURIComponent(query)}`);
                const titles = await response.json();

                autocompleteResults.innerHTML = '';
                if (titles.length > 0) {
                    titles.forEach(title => {
                        const item = document.createElement('div');
                        item.className = 'autocomplete-item';
                        item.textContent = title;
                        item.addEventListener('click', () => {
                            searchInput.value = title;
                            autocompleteResults.innerHTML = '';
                        });
                        autocompleteResults.appendChild(item);
                    });
                }
            } catch (error) {
                console.error('Autocomplete error:', error);
            }
        });

        searchInput.addEventListener('keydown', (e) => {
            const items = autocompleteResults.querySelectorAll('.autocomplete-item');
            if (items.length === 0) return;

            switch (e.key) {
                case 'ArrowDown':
                    e.preventDefault();
                    activeIndex = (activeIndex + 1) % items.length;
                    updateHighlight(items);
                    break;
                case 'ArrowUp':
                    e.preventDefault();
                    activeIndex = (activeIndex - 1 + items.length) % items.length;
                    updateHighlight(items);
                    break;
                case 'Enter':
                    if (activeIndex > -1) {
                        e.preventDefault();
                        searchInput.value = items[activeIndex].textContent;
                        autocompleteResults.innerHTML = '';
                    }
                    break;
                case 'Escape':
                    autocompleteResults.innerHTML = '';
                    break;
            }
        });

        function updateHighlight(items) {
            items.forEach((item, index) => {
                if (index === activeIndex) {
                    item.classList.add('highlighted');
                    item.scrollIntoView({ block: 'nearest' });
                } else {
                    item.classList.remove('highlighted');
                }
            });
        }

        // Hide autocomplete when clicking outside
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.search-form')) {
                autocompleteResults.innerHTML = '';
            }
        });

        // --- AJAX Pagination Logic ---
        const allBooksSectionContent = document.getElementById('all-books-section-content');

        if (allBooksSectionContent) {
            document.addEventListener('click', async (e) => {
                const pageLink = e.target.closest('.pagination-container .page-link');
                if (pageLink && !pageLink.closest('.page-item.disabled')) {
                    e.preventDefault();
                    const url = new URL(pageLink.href);
                    const page = url.searchParams.get('page') || '1';
                    const searchQuery = url.searchParams.get('search_query') || '';

                    try {
                        const response = await fetch(`/api/books?page=${page}&search_query=${encodeURIComponent(searchQuery)}`, {
                            headers: { 'X-Requested-With': 'XMLHttpRequest' }
                        });
                        const html = await response.text();
                        allBooksSectionContent.innerHTML = html;

                        // Maintain a clean, human-friendly URL (e.g. /?page=2) that reloads correctly
                        const displayUrl = new URL(window.location.origin);
                        displayUrl.pathname = '/';
                        if (parseInt(page, 10) > 1) {
                            displayUrl.searchParams.set('page', page);
                        }
                        if (searchQuery) {
                            displayUrl.searchParams.set('search_query', searchQuery);
                        }

                        history.pushState({ page: page, search_query: searchQuery }, '', displayUrl.toString());

                        // Smooth scroll to the bookshelf section
                        const shelfSection = document.getElementById('all-books-section') || allBooksSectionContent;
                        if (shelfSection) {
                            shelfSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
                        }
                    } catch (error) {
                        console.error('Error fetching pagination content:', error);
                    }
                }
            });

            // Handle browser back/forward buttons
            window.addEventListener('popstate', async (e) => {
                const page = (e.state && e.state.page) ? e.state.page : (new URL(window.location.href).searchParams.get('page') || '1');
                const searchQuery = (e.state && e.state.search_query !== undefined) ? e.state.search_query : (new URL(window.location.href).searchParams.get('search_query') || '');

                try {
                    const response = await fetch(`/api/books?page=${page}&search_query=${encodeURIComponent(searchQuery)}`, {
                        headers: { 'X-Requested-With': 'XMLHttpRequest' }
                    });
                    const html = await response.text();
                    allBooksSectionContent.innerHTML = html;
                } catch (error) {
                    console.error('Error fetching pagination content on popstate:', error);
                }
            });
        }

        // --- App Settings Modal ---
        const appSettingsBtn = document.getElementById('app-settings-btn');
        const appSettingsModal = document.getElementById('app-settings-modal');
        const settingsModalCloseBtn = document.getElementById('settings-modal-close-btn');
        const settingsModalCloseX = document.getElementById('settings-modal-close-x');

        if (appSettingsBtn && appSettingsModal) {
            appSettingsBtn.addEventListener('click', () => {
                appSettingsModal.classList.remove('hidden');
            });

            const closeSettingsModal = () => {
                appSettingsModal.classList.add('hidden');
            };

            if (settingsModalCloseBtn) settingsModalCloseBtn.addEventListener('click', closeSettingsModal);
            if (settingsModalCloseX) settingsModalCloseX.addEventListener('click', closeSettingsModal);

            appSettingsModal.addEventListener('click', (e) => {
                if (e.target === appSettingsModal) closeSettingsModal();
            });
        }

        // --- Desktop Keyboard Shortcuts (/ for search, ESC for closing modals) ---
        document.addEventListener('keydown', (e) => {
            if (e.key === '/' && !['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) {
                e.preventDefault();
                const searchInput = document.querySelector('.search-form input[name="search_query"]');
                if (searchInput) {
                    searchInput.focus();
                    searchInput.select();
                }
            } else if (e.key === 'Escape') {
                document.querySelectorAll('.modal-overlay').forEach(modal => {
                    modal.classList.add('hidden');
                });
            }
        });

        // --- Unread Shuffle Recommendation Logic ---
        const shufflePickBtn = document.getElementById('shuffle-pick-btn');
        const shuffleAgainBtn = document.getElementById('shuffle-again-btn');
        const shuffleCloseBtn = document.getElementById('shuffle-close-btn');
        const shuffleModal = document.getElementById('shuffle-recommend-modal');
        const shuffleModalCloseX = document.getElementById('shuffle-modal-close-x');
        const shuffleCover = document.getElementById('shuffle-cover');
        const shuffleTitle = document.getElementById('shuffle-title');
        const shuffleAuthor = document.getElementById('shuffle-author');
        const shuffleVolCount = document.getElementById('shuffle-volume-count');
        const shuffleReadBtn = document.getElementById('shuffle-read-now-btn');

        const pickRandomUnreadBook = () => {
            const allCards = Array.from(document.querySelectorAll('.book-card[data-is-group="true"]'));
            if (allCards.length === 0) return;

            let eligibleCards = allCards.filter(c => c.dataset.status === 'unread');
            if (eligibleCards.length === 0) eligibleCards = allCards;

            const randomCard = eligibleCards[Math.floor(Math.random() * eligibleCards.length)];
            const title = randomCard.querySelector('h3')?.textContent || '제목 없음';
            const author = randomCard.querySelector('p')?.textContent || '저자 미상';
            const img = randomCard.querySelector('img')?.src || '';
            const volCount = randomCard.dataset.volumeCount || '1';
            let targetUrl = randomCard.dataset.singleUrl;

            if (!targetUrl && randomCard.dataset.volumes) {
                try {
                    const vols = JSON.parse(randomCard.dataset.volumes);
                    if (vols.length > 0) targetUrl = `/reader/${vols[0].id}`;
                } catch (e) {}
            }

            if (shuffleTitle) shuffleTitle.textContent = title;
            if (shuffleAuthor) shuffleAuthor.textContent = author;
            if (shuffleCover) shuffleCover.src = img;
            if (shuffleVolCount) shuffleVolCount.textContent = `전 ${volCount}권`;
            if (shuffleReadBtn) shuffleReadBtn.href = targetUrl || '#';

            if (shuffleModal) shuffleModal.classList.remove('hidden');
        };

        if (shufflePickBtn) shufflePickBtn.addEventListener('click', pickRandomUnreadBook);
        if (shuffleAgainBtn) shuffleAgainBtn.addEventListener('click', pickRandomUnreadBook);
        if (shuffleCloseBtn && shuffleModal) {
            shuffleCloseBtn.addEventListener('click', () => {
                shuffleModal.classList.add('hidden');
            });
        }
        if (shuffleModalCloseX && shuffleModal) {
            shuffleModalCloseX.addEventListener('click', () => {
                shuffleModal.classList.add('hidden');
            });
        }
        if (shuffleModal) {
            shuffleModal.addEventListener('click', (e) => {
                if (e.target === shuffleModal) shuffleModal.classList.add('hidden');
            });
        }

        // --- Bookshelf Filter Chips (All / Reading / Unread / Completed) ---
        const filterChips = document.querySelectorAll('.shelf-filter-chips .filter-chip');
        if (filterChips.length > 0) {
            filterChips.forEach(chip => {
                chip.addEventListener('click', () => {
                    const filter = chip.dataset.filter;
                    filterChips.forEach(c => c.classList.toggle('active', c === chip));

                    const bookCards = document.querySelectorAll('.all-books-shelf .book-card');
                    bookCards.forEach(card => {
                        if (filter === 'all') {
                            card.style.display = '';
                        } else if (filter === 'reading') {
                            card.style.display = (card.dataset.status === 'reading') ? '' : 'none';
                        } else if (filter === 'unread') {
                            card.style.display = (card.dataset.status === 'unread') ? '' : 'none';
                        } else if (filter === 'completed') {
                            card.style.display = (card.dataset.status === 'completed') ? '' : 'none';
                        }
                    });
                });
            });
        }

        // --- Bookshelf Sorting (Title, Recent, Volumes, Unread) ---
        const sortSelect = document.getElementById('shelf-sort-select');
        if (sortSelect) {
            sortSelect.addEventListener('change', () => {
                const sortBy = sortSelect.value;
                const gridContainer = document.querySelector('.all-books-shelf .book-grid');
                if (!gridContainer) return;
                const cards = Array.from(gridContainer.querySelectorAll('.book-card'));

                cards.sort((a, b) => {
                    if (sortBy === 'title') {
                        const titleA = a.dataset.seriesTitle || '';
                        const titleB = b.dataset.seriesTitle || '';
                        return titleA.localeCompare(titleB, 'ko');
                    } else if (sortBy === 'recent') {
                        const timeA = parseFloat(a.dataset.lastRead || 0);
                        const timeB = parseFloat(b.dataset.lastRead || 0);
                        return timeB - timeA;
                    } else if (sortBy === 'volumes') {
                        const volA = parseInt(a.dataset.volumeCount || 1, 10);
                        const volB = parseInt(b.dataset.volumeCount || 1, 10);
                        return volB - volA;
                    } else if (sortBy === 'unread') {
                        const statusOrder = { 'unread': 1, 'reading': 2, 'completed': 3 };
                        const orderA = statusOrder[a.dataset.status] || 2;
                        const orderB = statusOrder[b.dataset.status] || 2;
                        return orderA - orderB;
                    }
                    return 0;
                });

                cards.forEach(card => gridContainer.appendChild(card));
            });
        }

        // --- View Mode Toggle (Grid vs List) ---
        const gridBtn = document.getElementById('view-mode-grid-btn');
        const listBtn = document.getElementById('view-mode-list-btn');
        const allBooksGrid = document.querySelector('.all-books-shelf .book-grid');
        const VIEW_MODE_KEY = 'eBookLibraryViewMode';

        function setLibraryViewMode(mode) {
            if (!allBooksGrid) return;
            if (mode === 'list') {
                allBooksGrid.classList.add('book-list-view');
                if (listBtn) listBtn.classList.add('active');
                if (gridBtn) gridBtn.classList.remove('active');
            } else {
                allBooksGrid.classList.remove('book-list-view');
                if (gridBtn) gridBtn.classList.add('active');
                if (listBtn) listBtn.classList.remove('active');
            }
            localStorage.setItem(VIEW_MODE_KEY, mode);
        }

        if (gridBtn) gridBtn.addEventListener('click', () => setLibraryViewMode('grid'));
        if (listBtn) listBtn.addEventListener('click', () => setLibraryViewMode('list'));

        const savedViewMode = localStorage.getItem(VIEW_MODE_KEY);
        if (savedViewMode === 'list') {
            setLibraryViewMode('list');
        }

        // --- Hybrid Page Management (Client-Side PDF Manipulation & Batch Commit) ---
        const pendingEditsBtn = document.getElementById('pending-edits-btn');
        const pendingEditsLabel = document.getElementById('pending-edits-label');
        const pendingEditsModal = document.getElementById('pending-edits-modal');
        const pendingEditsCloseIcon = document.getElementById('pending-edits-close-icon');
        const pendingEditsCloseBtn = document.getElementById('pending-edits-close-btn');
        const pendingEditsList = document.getElementById('pending-edits-list');
        const commitAllEditsBtn = document.getElementById('commit-all-edits-btn');
        const commitProgressContainer = document.getElementById('commit-progress-container');
        const commitProgressBar = document.getElementById('commit-progress-bar');
        const commitProgressStatus = document.getElementById('commit-progress-status');

        let currentPendingEdits = [];

        async function loadPendingEditsBadge() {
            try {
                const resp = await fetch('/api/page/pending_edits');
                if (resp.ok) {
                    const data = await resp.json();
                    currentPendingEdits = data.edits || [];
                    const count = data.total_count || 0;
                    if (pendingEditsBtn && pendingEditsLabel) {
                        if (count > 0) {
                            pendingEditsLabel.textContent = `편집 대기 ${count}건`;
                            pendingEditsBtn.classList.remove('hidden');
                        } else {
                            pendingEditsBtn.classList.add('hidden');
                        }
                    }
                }
            } catch (e) {
                console.warn('Failed to load pending page edits:', e);
            }
        }

        function renderPendingEditsModal() {
            if (!pendingEditsList) return;
            pendingEditsList.innerHTML = '';

            if (currentPendingEdits.length === 0) {
                pendingEditsList.innerHTML = '<p style="color: #8e95a5; text-align: center; padding: 20px;">대기 중인 편집 건이 없습니다.</p>';
                if (commitAllEditsBtn) commitAllEditsBtn.disabled = true;
                return;
            }

            if (commitAllEditsBtn) commitAllEditsBtn.disabled = false;

            currentPendingEdits.forEach(edit => {
                const item = document.createElement('div');
                item.className = 'pending-edit-item';
                
                const isReplace = edit.action === 'replace';
                const actionText = isReplace ? '이미지 교체' : '페이지 삭제';
                const badgeClass = isReplace ? 'badge-replace' : 'badge-delete';

                item.innerHTML = `
                    <div class="pending-edit-item-left">
                        <span class="pending-edit-action-badge ${badgeClass}">${actionText}</span>
                        <div class="pending-edit-meta">
                            <span class="pending-edit-title">${escapeHtml(edit.book_title || '도서')} (제${edit.volume_number || 1}권)</span>
                            <span class="pending-edit-page">대상: 원본 ${edit.page_num}페이지</span>
                        </div>
                    </div>
                    <button type="button" class="pending-edit-cancel-btn" data-edit-id="${edit.id}">취소</button>
                `;

                const cancelBtn = item.querySelector('.pending-edit-cancel-btn');
                cancelBtn.addEventListener('click', async () => {
                    cancelBtn.disabled = true;
                    cancelBtn.textContent = '취소 중...';
                    try {
                        const resp = await fetch(`/api/page/edit/${edit.id}/cancel`, { method: 'POST' });
                        if (resp.ok) {
                            showToast('편집이 취소되었습니다.');
                            await loadPendingEditsBadge();
                            renderPendingEditsModal();
                        }
                    } catch (err) {
                        console.error(err);
                        showToast('취소 처리에 실패했습니다.');
                    }
                });

                pendingEditsList.appendChild(item);
            });
        }

        if (pendingEditsBtn) {
            pendingEditsBtn.addEventListener('click', () => {
                renderPendingEditsModal();
                if (pendingEditsModal) pendingEditsModal.classList.remove('hidden');
            });
        }

        const closePendingModal = () => {
            if (pendingEditsModal) pendingEditsModal.classList.add('hidden');
        };

        if (pendingEditsCloseIcon) pendingEditsCloseIcon.addEventListener('click', closePendingModal);
        if (pendingEditsCloseBtn) pendingEditsCloseBtn.addEventListener('click', closePendingModal);
        if (pendingEditsModal) {
            pendingEditsModal.addEventListener('click', (e) => {
                if (e.target === pendingEditsModal) closePendingModal();
            });
        }

        // Client-Side PDF Batch Commit via pdf-lib
        if (commitAllEditsBtn) {
            commitAllEditsBtn.addEventListener('click', async () => {
                if (currentPendingEdits.length === 0) return;
                if (typeof PDFLib === 'undefined') {
                    showToast('PDF 처리 라이브러리를 로드하는 중입니다. 잠시 후 다시 시도해 주세요.');
                    return;
                }

                if (!confirm(`총 ${currentPendingEdits.length}건의 편집을 현재 기기(브라우저)에서 원본 PDF로 영구 병합하시겠습니까?\n(NAS 메모리 부하 없이 안전하게 수행됩니다)`)) {
                    return;
                }

                commitAllEditsBtn.disabled = true;
                if (commitProgressContainer) commitProgressContainer.classList.remove('hidden');
                if (commitProgressBar) commitProgressBar.style.width = '5%';
                if (commitProgressStatus) commitProgressStatus.textContent = '편집 작업을 도서별로 분석 중...';

                const editsByFile = {};
                currentPendingEdits.forEach(e => {
                    if (!editsByFile[e.file_id]) editsByFile[e.file_id] = [];
                    editsByFile[e.file_id].push(e);
                });

                const fileIds = Object.keys(editsByFile);
                let processedFiles = 0;

                try {
                    for (const fileIdStr of fileIds) {
                        const fid = parseInt(fileIdStr, 10);
                        const fileEdits = editsByFile[fid];
                        const bookName = fileEdits[0].book_title || `도서 #${fid}`;

                        if (commitProgressStatus) {
                            commitProgressStatus.textContent = `[${processedFiles + 1}/${fileIds.length}] '${bookName}' PDF 다운로드 중...`;
                        }
                        if (commitProgressBar) {
                            const pct = Math.floor((processedFiles / fileIds.length) * 80) + 10;
                            commitProgressBar.style.width = `${pct}%`;
                        }

                        const pdfResp = await fetch(`/reader/${fid}`);
                        if (!pdfResp.ok) throw new Error(`PDF 접근 실패 (ID: ${fid})`);
                        const htmlText = await pdfResp.text();
                        
                        const match = htmlText.match(/pdfUrl\s*=\s*['"]([^'"]+)['"]/);
                        if (!match) throw new Error('PDF 다운로드 주소를 찾을 수 없습니다.');
                        const pdfFetchUrl = match[1];

                        const pdfDataResp = await fetch(pdfFetchUrl);
                        if (!pdfDataResp.ok) throw new Error('PDF 바이너리 다운로드 실패');
                        const origPdfBytes = await pdfDataResp.arrayBuffer();

                        if (commitProgressStatus) {
                            commitProgressStatus.textContent = `[${processedFiles + 1}/${fileIds.length}] '${bookName}' 브라우저(PC)에서 페이지 재구성 중...`;
                        }

                        const pdfDoc = await PDFLib.PDFDocument.load(origPdfBytes);

                        const deleteEdits = fileEdits.filter(e => e.action === 'delete').sort((a, b) => b.page_num - a.page_num);
                        const replaceEdits = fileEdits.filter(e => e.action === 'replace');

                        for (const rep of replaceEdits) {
                            const pageIndex = rep.page_num - 1;
                            if (pageIndex >= 0 && pageIndex < pdfDoc.getPageCount()) {
                                const imgResp = await fetch(`/api/page/override_image/${rep.id}`);
                                if (imgResp.ok) {
                                    const imgBlob = await imgResp.blob();
                                    const imgBytes = await imgBlob.arrayBuffer();
                                    const isPng = imgBlob.type === 'image/png';
                                    const embeddedImage = isPng ? await pdfDoc.embedPng(imgBytes) : await pdfDoc.embedJpg(imgBytes);

                                    const newPage = pdfDoc.insertPage(pageIndex, [embeddedImage.width, embeddedImage.height]);
                                    newPage.drawImage(embeddedImage, {
                                        x: 0,
                                        y: 0,
                                        width: embeddedImage.width,
                                        height: embeddedImage.height
                                    });
                                    pdfDoc.removePage(pageIndex + 1);
                                }
                            }
                        }

                        for (const del of deleteEdits) {
                            const pageIndex = del.page_num - 1;
                            if (pageIndex >= 0 && pageIndex < pdfDoc.getPageCount()) {
                                pdfDoc.removePage(pageIndex);
                            }
                        }

                        if (commitProgressStatus) {
                            commitProgressStatus.textContent = `[${processedFiles + 1}/${fileIds.length}] '${bookName}' 최종 PDF 저장 및 NAS 전송 중...`;
                        }
                        const modifiedPdfBytes = await pdfDoc.save();

                        const formData = new FormData();
                        formData.append('file_id', fid);
                        formData.append('pdf', new Blob([modifiedPdfBytes], { type: 'application/pdf' }), 'merged.pdf');

                        const uploadResp = await fetch('/api/file/replace_pdf', {
                            method: 'POST',
                            body: formData
                        });
                        const uploadResult = await uploadResp.json();
                        if (!uploadResult.success) {
                            throw new Error(uploadResult.message || 'PDF 저장 실패');
                        }

                        processedFiles++;
                    }

                    if (commitProgressBar) commitProgressBar.style.width = '100%';
                    if (commitProgressStatus) commitProgressStatus.textContent = '모든 도서의 영구 병합이 완료되었습니다! ✓';
                    showToast('모든 도서의 영구 저장이 완료되었습니다! ✓');

                    setTimeout(async () => {
                        closePendingModal();
                        await loadPendingEditsBadge();
                        window.location.reload();
                    }, 1200);

                } catch (error) {
                    console.error('Commit edits failed:', error);
                    alert(`영구 병합 중 오류가 발생했습니다: ${error.message}`);
                    commitAllEditsBtn.disabled = false;
                    if (commitProgressContainer) commitProgressContainer.classList.add('hidden');
                }
            });
        }

        // Check pending edits on page load
        loadPendingEditsBadge();
    }
});
