
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
        
        const btn = e.target;
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
        isbnInput.style.display = 'none'; // Hide manual ISBN input initially
        searchBtn.style.display = 'none'; // Hide manual search button initially

        try {
            const response = await fetch(`/api/book/lookup_by_title_volume?title=${encodeURIComponent(bookTitle)}&volume=${encodeURIComponent(volumeNumber || '')}`);
            const data = await response.json();

            if (response.ok) {
                // Single result found, populate automatically
                selectedCoverUrl = data.thumbnail;
                
                let imagesHtml = '';
                if (data.thumbnail) {
                    imagesHtml = `<img src="${data.thumbnail}" alt="Book Cover" id="cover-preview-img" class="cover-preview selected">`;
                } else {
                    imagesHtml = `
                        <p>표지 이미지를 찾을 수 없습니다.</p>
                        <div id="manual-cover-input-group">
                            <input type="text" id="manual-cover-url" placeholder="이미지 URL을 직접 붙여넣으세요">
                            <img src="" alt="미리보기" id="cover-preview-img" class="cover-preview" style="display:none; margin-top: 10px;">
                        </div>
                    `;
                }

                resultsDiv.innerHTML = `
                    <div id="result-info">
                        <p><strong>제목:</strong> <span id="result-title">${data.title || 'N/A'}</span></p>
                        <p><strong>저자:</strong> <span id="result-author">${data.author || 'N/A'}</span></p>
                        <p><strong>ISBN:</strong> <span id="result-isbn">${data.isbn_13 || 'N/A'}</span></p>
                    </div>
                    <div id="result-images">${imagesHtml}</div>
                `;

                if (!data.thumbnail) {
                    document.getElementById('manual-cover-url').addEventListener('input', (e) => {
                        const url = e.target.value;
                        const previewImg = document.getElementById('cover-preview-img');
                        if (url) {
                            previewImg.src = url;
                            previewImg.style.display = 'block';
                            selectedCoverUrl = url;
                        } else {
                            previewImg.style.display = 'none';
                        }
                    });
                }

                registerBtn.disabled = false;

            } else {
                // No unique result, fall back to manual ISBN input
                resultsDiv.innerHTML = `<p class="error">${data.error || '책 정보를 자동으로 찾을 수 없습니다. 수동으로 ISBN을 입력해주세요.'}</p>`;
                isbnInput.style.display = 'block';
                searchBtn.style.display = 'block';
            }

        } catch (error) {
            console.error('Error during automatic book lookup:', error);
            resultsDiv.innerHTML = `<p class="error">자동 검색 중 네트워크 오류가 발생했습니다. 수동으로 ISBN을 입력해주세요.</p>`;
            isbnInput.style.display = 'block';
            searchBtn.style.display = 'block';
        }
    };

    const closeIsbnModal = () => {
        isbnModal.classList.add('hidden');
        resultsDiv.innerHTML = '';
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

        volumes.forEach(vol => {
            const volCard = document.createElement('div');
            volCard.className = 'book-card';

            const placeholder = `https://placehold.co/300x450/2a2a2a/ffffff?text=${encodeURIComponent(vol.title || 'No Title')}`;
            const cover = vol.cover_url || placeholder;

            volCard.innerHTML = `
                <a href="/reader/${vol.id}">
                    <img src="${cover}" alt="${vol.title || 'No Title'}">
                    <div class="book-info">
                        <h3>제 ${vol.volume_number}권</h3>
                        <p>${vol.title || '제목 없음'}</p>
                    </div>
                </a>
                <button class="isbn-btn" data-file-id="${vol.id}" data-book-title="${vol.title || '제목 없음'}" data-volume-number="${vol.volume_number}">ISBN</button>
            `;
            volumeList.appendChild(volCard);
        });

        volumeModal.classList.remove('hidden');
    };

    const closeVolumeModal = () => {
        volumeModal.classList.add('hidden');
    };

    const searchIsbn = async () => {
        const isbn = isbnInput.value.trim();
        if (!isbn) return;

        resultsDiv.innerHTML = '<div class="loader"></div><p style="text-align: center;">책 정보 검색 중...</p>';
        registerBtn.disabled = true;

        try {
            const response = await fetch(`/api/book/lookup?isbn=${isbn}`);
            const data = await response.json();

            if (!response.ok) {
                resultsDiv.innerHTML = `<p class="error">오류: ${data.error}</p>`;
                return;
            }

            selectedCoverUrl = data.thumbnail;
            
            let imagesHtml = '';
            if (data.thumbnail) {
                imagesHtml = `<img src="${data.thumbnail}" alt="Book Cover" id="cover-preview-img" class="cover-preview selected">`;
            } else {
                imagesHtml = `
                    <p>표지 이미지를 찾을 수 없습니다.</p>
                    <div id="manual-cover-input-group">
                        <input type="text" id="manual-cover-url" placeholder="이미지 URL을 직접 붙여넣으세요">
                        <img src="" alt="미리보기" id="cover-preview-img" class="cover-preview" style="display:none; margin-top: 10px;">
                    </div>
                `;
            }

            resultsDiv.innerHTML = `
                <div id="result-info">
                    <p><strong>제목:</strong> <span id="result-title">${data.title || 'N/A'}</span></p>
                    <p><strong>저자:</strong> <span id="result-author">${data.author || 'N/A'}</span></p>
                </div>
                <div id="result-images">${imagesHtml}</div>
            `;

            if (!data.thumbnail) {
                document.getElementById('manual-cover-url').addEventListener('input', (e) => {
                    const url = e.target.value;
                    const previewImg = document.getElementById('cover-preview-img');
                    if (url) {
                        previewImg.src = url;
                        previewImg.style.display = 'block';
                        selectedCoverUrl = url;
                    } else {
                        previewImg.style.display = 'none';
                    }
                });
            }

            registerBtn.disabled = false;

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
});
