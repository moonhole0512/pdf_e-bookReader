
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

    // --- Functions ---

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

        // Clear previous results and show loading
        resultsDiv.innerHTML = '<div class="loader"></div><p style="text-align: center;">책 정보 자동 검색 중...</p>';
        registerBtn.disabled = true;
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
        selectedCoverUrl = data.thumbnail;
        
        let imagesHtml = '';
        if (data.thumbnail) {
            imagesHtml = `<img src="${data.thumbnail}" alt="Book Cover" id="cover-preview-img" class="cover-preview selected">`;
        } else {
            const title = data.title || document.getElementById('result-title').textContent;
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
                const url = e.target.value;
                const previewImg = document.getElementById('cover-preview-img');
                if (url) {
                    previewImg.src = url;
                    previewImg.style.display = 'block';
                    selectedCoverUrl = url;
                    if (noCoverMessage) noCoverMessage.style.display = 'none';
                    document.getElementById('cover-search-results').innerHTML = '';
                } else {
                    previewImg.style.display = 'none';
                    if (noCoverMessage) noCoverMessage.style.display = 'block';
                }
            });
        }

        registerBtn.disabled = false;
    };

    const displayMultipleResults = (results) => {
        resultsDiv.classList.add('has-multiple-results');
        resultsDiv.innerHTML = '<p>여러 결과가 검색되었습니다. 등록할 책을 선택해주세요.</p>';
        const selectionGrid = document.createElement('div');
        selectionGrid.className = 'book-grid';

        results.forEach(book => {
            const bookCard = document.createElement('div');
            bookCard.className = 'book-card-small';
            bookCard.dataset.title = book.title;
            bookCard.dataset.author = book.author;
            bookCard.dataset.coverUrl = book.thumbnail || '';
            bookCard.dataset.isbn13 = book.isbn_13 || '';
            bookCard.dataset.isbn10 = book.isbn_10 || '';

            const placeholder = `https://placehold.co/150x225/2a2a2a/ffffff?text=No IMG`;
            const cover = book.thumbnail || placeholder;

            bookCard.innerHTML = `
                <img src="${cover}" alt="${book.title}">
                <div class="book-info-small">
                    <p title="${book.title}">${book.title}</p>
                    <span title="${book.author || ''}">${book.author || '저자 미상'}</span>
                </div>
            `;
            selectionGrid.appendChild(bookCard);
        });

        resultsDiv.appendChild(selectionGrid);

        selectionGrid.addEventListener('click', (e) => {
            const selectedCard = e.target.closest('.book-card-small');
            if (!selectedCard) return;

            // Remove previous selection
            document.querySelectorAll('.book-card-small.selected').forEach(card => {
                card.classList.remove('selected');
            });

            // Add new selection
            selectedCard.classList.add('selected');

            // Populate preview with the selected candidate
            const selectedBook = {
                title: selectedCard.dataset.title,
                author: selectedCard.dataset.author,
                thumbnail: selectedCard.dataset.coverUrl,
                isbn_13: selectedCard.dataset.isbn13,
                isbn_10: selectedCard.dataset.isbn10
            };

            selectedCoverUrl = selectedBook.thumbnail;
            registerBtn.disabled = !selectedCoverUrl;
        });
    };

    const closeIsbnModal = () => {
        isbnModal.classList.add('hidden');
        resultsDiv.innerHTML = '';
        resultsDiv.classList.remove('has-multiple-results');
        isbnInput.value = '';
        registerBtn.disabled = true;
        selectedCoverUrl = null;
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
            const isCompleted = (vol.total_pages > 0 && vol.current_page >= vol.total_pages * 0.95);
            const isReading = (vol.current_page > 0 && !isCompleted);
            const isNextToRead = (vol.id === nextToReadVolId);

            if (isCompleted) volCard.classList.add('vol-completed');
            if (isNextToRead) volCard.classList.add('vol-next-focus');

            let badgeHtml = '';
            if (isCompleted) {
                badgeHtml = '<div class="completed-badge">완독 ✓</div>';
            } else if (isNextToRead) {
                badgeHtml = '<div class="next-to-read-badge">다음 읽을 차례 ✨</div>';
            } else if (isReading) {
                badgeHtml = '<div class="reading-badge">읽는 중</div>';
            }

            volCard.innerHTML = `
                <a href="/reader/${vol.id}">
                    <div class="vol-thumb-wrapper">
                        <img src="${cover}" alt="${vol.title || 'No Title'}">
                        ${badgeHtml}
                    </div>
                    <div class="book-info">
                        <h3>제 ${vol.volume_number}권</h3>
                        <p>${vol.title || '제목 없음'}</p>
                    </div>
                </a>
                ${vol.total_pages > 0 ? `
                <div class="progress-bar-container">
                    <div class="progress-bar" style="width: ${((vol.current_page || 0) / vol.total_pages) * 100}%;"></div>
                </div>
                <span class="progress-text">${vol.current_page || 0} / ${vol.total_pages}</span>
                ` : ''}
                <button class="isbn-btn" data-file-id="${vol.id}" data-book-title="${vol.title || '제목 없음'}" data-volume-number="${vol.volume_number}">정보 수정</button>
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

        resultsDiv.innerHTML = '<div class="loader"></div><p style="text-align: center;">책 정보 검색 중...</p>';
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
        const title = document.getElementById('result-title').textContent;
        const author = document.getElementById('result-author').textContent;

        if (!selectedCoverUrl) {
            alert('표지 이미지가 선택되지 않았습니다.');
            return;
        }

        try {
            const response = await fetch('/api/file/update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    file_id: fileId,
                    title: title,
                    author: author,
                    cover_url: selectedCoverUrl
                })
            });

            if (!response.ok) throw new Error('Update failed');
            
            const data = await response.json();

            // Update card on main page (for last_read_file)
            const cardToUpdate = document.querySelector(`.isbn-btn[data-file-id='${fileId}']`);
            if (cardToUpdate) {
                const parentCard = cardToUpdate.closest('.book-card');
                if(parentCard) {
                    parentCard.querySelector('img').src = data.file.cover_url;
                    parentCard.querySelector('h3').textContent = data.file.title;
                    parentCard.querySelector('.book-info p').textContent = data.file.author;
                }
            }

            closeIsbnModal();

        } catch (error) {
            alert('책 정보 업데이트에 실패했습니다.');
        }
    };

    // --- Event Listeners ---

    // Main click handler for cards and buttons
    document.body.addEventListener('click', (e) => {
        // For opening ISBN modal
        if (e.target.matches('.isbn-btn')) {
            openIsbnModal(e);
            return;
        }

        // For opening Volume Select modal
        const card = e.target.closest('.book-card[data-is-group="true"]');
        if (card) {
            const volumeCount = parseInt(card.dataset.volumeCount, 10);
            if (volumeCount === 1) {
                window.location.href = card.dataset.singleUrl;
            } else {
                openVolumeModal(card);
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
    closeVolumeModalBtn.addEventListener('click', closeVolumeModal);
    volumeModal.addEventListener('click', (e) => {
        if (e.target === volumeModal) closeVolumeModal();
    });

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
                    const page = url.searchParams.get('page');
                    const searchQuery = url.searchParams.get('search_query') || '';

                    try {
                        const response = await fetch(`/api/books?page=${page}&search_query=${encodeURIComponent(searchQuery)}`);
                        const html = await response.text();
                        allBooksSectionContent.innerHTML = html;
                        history.pushState({ page: page, search_query: searchQuery }, '', url.href);
                    } catch (error) {
                        console.error('Error fetching pagination content:', error);
                    }
                }
            });

            // Handle browser back/forward buttons
            window.addEventListener('popstate', async (e) => {
                if (e.state && e.state.page) {
                    const page = e.state.page;
                    const searchQuery = e.state.search_query || '';
                    try {
                        const response = await fetch(`/api/books?page=${page}&search_query=${encodeURIComponent(searchQuery)}`);
                        const html = await response.text();
                        allBooksSectionContent.innerHTML = html;
                    } catch (error) {
                        console.error('Error fetching pagination content on popstate:', error);
                    }
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
    }
});
