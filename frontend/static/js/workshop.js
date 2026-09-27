/**
 * GSCMS Workshop Management — JavaScript Engine
 * Apple España Vitrine Aesthetics & Micro-interactions
 */

document.addEventListener('DOMContentLoaded', () => {
    initQuickSearch();
    initDraftProtection();
    initComparisonSlider();
    initKarigarActions();
    initAnimatedDeleteButtons();
    initAtelierTaskTracking();
    initClientFolders();
    initDigitalCalculator();
});

/* --- 1. QUICK SEARCH MODAL (CMD/CTRL + K) --- */
function initQuickSearch() {
    const modal = document.getElementById('searchModalBackdrop');
    const searchInput = document.getElementById('globalSearchInput');
    const resultsContainer = document.getElementById('searchResultsList');
    const openButtons = document.querySelectorAll('.open-search-trigger');

    if (!modal || !searchInput) return;

    function openModal() {
        modal.classList.add('active');
        searchInput.value = '';
        if (resultsContainer) resultsContainer.innerHTML = '<div style="padding:16px; color:#86868b; text-align:center;">Type customer name, mobile, Job ID (e.g. J-2026), or Order ID...</div>';
        setTimeout(() => searchInput.focus(), 50);
    }

    function closeModal() {
        modal.classList.remove('active');
    }

    openButtons.forEach(btn => btn.addEventListener('click', (e) => {
        e.preventDefault();
        openModal();
    }));

    modal.addEventListener('click', (e) => {
        if (e.target === modal) closeModal();
    });

    document.addEventListener('keydown', (e) => {
        if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
            e.preventDefault();
            if (modal.classList.contains('active')) closeModal();
            else openModal();
        }
        if (e.key === 'Escape' && modal.classList.contains('active')) {
            closeModal();
        }
    });

    // Debounced Live Search
    let debounceTimer;
    searchInput.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        const query = searchInput.value.trim();
        if (query.length < 2) {
            resultsContainer.innerHTML = '<div style="padding:16px; color:#86868b; text-align:center;">Type at least 2 characters to search...</div>';
            return;
        }

        debounceTimer = setTimeout(() => {
            fetch(`/api/quick-search/?q=${encodeURIComponent(query)}`)
                .then(res => res.json())
                .then(data => {
                    renderSearchResults(data, resultsContainer);
                })
                .catch(err => {
                    console.error('Search error:', err);
                    resultsContainer.innerHTML = '<div style="padding:16px; color:#ff3b30; text-align:center;">Error fetching search results.</div>';
                });
        }, 250);
    });
}

function renderSearchResults(data, container) {
    if (!data.results || data.results.length === 0) {
        container.innerHTML = '<div style="padding:24px; color:#86868b; text-align:center;">No matching jobs, orders, or customers found.</div>';
        return;
    }

    let html = '';
    data.results.forEach(item => {
        let badgeClass = 'badge-ash';
        if (item.type === 'JOB') badgeClass = 'badge-blue';
        else if (item.type === 'CUSTOMER') badgeClass = 'badge-green';
        else badgeClass = 'badge-purple';

        html += `
            <a href="${item.url}" class="search-result-item">
                <div>
                    <div style="display:flex; align-items:center; gap:8px; margin-bottom:4px;">
                        <span class="badge-chip ${badgeClass}">${item.type}</span>
                        <strong style="font-size:15px; color:#1d1d1f;">${item.title}</strong>
                    </div>
                    <div style="font-size:13px; color:#707070;">${item.subtitle}</div>
                </div>
                <div style="font-size:12px; color:#86868b; text-align:right;">
                    <div>${item.meta || ''}</div>
                    <span style="color:#0066cc; font-weight:500;">View &rarr;</span>
                </div>
            </a>
        `;
    });
    container.innerHTML = html;
}

/* --- 2. OFFLINE / FORM DRAFT PROTECTION --- */
function initDraftProtection() {
    const draftForms = document.querySelectorAll('form[data-auto-draft]');
    draftForms.forEach(form => {
        const formKey = 'draft_' + (form.getAttribute('id') || window.location.pathname);
        
        // Restore from storage if empty
        const saved = localStorage.getItem(formKey);
        if (saved) {
            try {
                const formData = JSON.parse(saved);
                Object.keys(formData).forEach(name => {
                    const el = form.elements[name];
                    if (el && !el.value && el.type !== 'file' && el.type !== 'password') {
                        el.value = formData[name];
                    }
                });
            } catch (e) {
                console.error('Failed to restore draft', e);
            }
        }

        // Save drafts on input
        form.addEventListener('input', () => {
            const data = {};
            Array.from(form.elements).forEach(el => {
                if (el.name && el.type !== 'file' && el.type !== 'password') {
                    data[el.name] = el.value;
                }
            });
            localStorage.setItem(formKey, JSON.stringify(data));
        });

        // Clear draft on submit
        form.addEventListener('submit', () => {
            localStorage.removeItem(formKey);
        });
    });
}

/* --- 3. REFERENCE VS FINAL SLIDER & LIGHTBOX --- */
function initComparisonSlider() {
    const compareContainers = document.querySelectorAll('.comparison-container');
    compareContainers.forEach(container => {
        const imgs = container.querySelectorAll('img');
        imgs.forEach(img => {
            img.addEventListener('click', () => {
                openLightbox(img.src, img.alt);
            });
        });
    });
}

function openLightbox(src, caption) {
    let lb = document.getElementById('vitrineLightbox');
    if (!lb) {
        lb = document.createElement('div');
        lb.id = 'vitrineLightbox';
        lb.style.cssText = 'position:fixed; inset:0; background:rgba(0,0,0,0.85); backdrop-filter:blur(15px); z-index:3000; display:flex; flex-direction:column; align-items:center; justify-content:center; cursor:zoom-out;';
        lb.innerHTML = '<img id="lbImg" style="max-width:85vw; max-height:80vh; border-radius:20px; object-fit:contain; box-shadow:0 25px 60px rgba(0,0,0,0.5);"><div id="lbCaption" style="color:white; margin-top:16px; font-size:15px; font-weight:500;"></div>';
        document.body.appendChild(lb);
        lb.addEventListener('click', () => lb.style.display = 'none');
    }
    document.getElementById('lbImg').src = src;
    document.getElementById('lbCaption').textContent = caption || '';
    lb.style.display = 'flex';
}

/* --- 4. KARIGAR STAGE ACTIONS VIA AJAX --- */
function initKarigarActions() {
    const actionButtons = document.querySelectorAll('[data-stage-action]');
    actionButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const action = btn.getAttribute('data-stage-action');
            const jobId = btn.getAttribute('data-job-id');
            const confirmMsg = btn.getAttribute('data-confirm');

            if (confirmMsg && !confirm(confirmMsg)) return;

            const csrfToken = getCookie('csrftoken');
            fetch(`/api/jobs/${jobId}/stage-action/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ action: action })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    showToast(data.message || 'Stage updated successfully.', 'success');
                    setTimeout(() => window.location.reload(), 600);
                } else {
                    showToast(data.error || 'Failed to update stage.', 'error');
                }
            })
            .catch(err => {
                console.error(err);
                showToast('Network error while updating stage.', 'error');
            });
        });
    });
}

/* Toast Notifications */
function showToast(message, type = 'info') {
    let container = document.getElementById('toastContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toastContainer';
        container.style.cssText = 'position:fixed; bottom:24px; right:24px; z-index:9999; display:flex; flex-direction:column; gap:10px;';
        document.body.appendChild(container);
    }
    const toast = document.createElement('div');
    const bg = type === 'success' ? '#1c7430' : (type === 'error' ? '#ff3b30' : '#1d1d1f');
    toast.style.cssText = `background:${bg}; color:white; padding:12px 24px; border-radius:980px; font-size:14px; font-weight:500; box-shadow:0 8px 24px rgba(0,0,0,0.15); transition:opacity 0.3s ease; opacity:0;`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.style.opacity = '1', 50);
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

/* ==========================================================================
   USER COMPONENT 1: ANIMATED EXPANDABLE DELETE BUTTON ENGINE
   Matches User's Motion/React DeleteButton Component:
   - Expands to 128px
   - Lid rotates -35deg
   - Cancel closes with settle bounce
   - Confirm shows draw checkmark and moves to Recycle Bin
   ========================================================================== */
function initAnimatedDeleteButtons() {
    document.querySelectorAll('.del-widget').forEach(widget => {
        const trigger = widget.querySelector('.del-trigger');
        const confirmBtn = widget.querySelector('.del-circle-confirm');
        const cancelBtn = widget.querySelector('.del-circle-cancel');

        if (!trigger || widget.dataset.initialized) return;
        widget.dataset.initialized = "true";

        function openWidget() {
            // Close other open delete buttons
            document.querySelectorAll('.del-widget.open').forEach(w => {
                if (w !== widget) closeWidget(w, false);
            });
            widget.classList.add('open');
            widget.setAttribute('data-state', 'open');
        }

        function closeWidget(targetWidget = widget, animateSettle = true) {
            targetWidget.classList.remove('open');
            targetWidget.setAttribute('data-state', 'closed');
            if (animateSettle) {
                targetWidget.classList.add('del-settle');
                setTimeout(() => targetWidget.classList.remove('del-settle'), 450);
            }
        }

        trigger.addEventListener('click', (e) => {
            e.stopPropagation();
            if (widget.classList.contains('open')) {
                closeWidget(widget, true);
            } else {
                openWidget();
            }
        });

        if (cancelBtn) {
            cancelBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                closeWidget(widget, true);
            });
        }

        if (confirmBtn) {
            confirmBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                const itemType = widget.dataset.itemType;
                const pk = widget.dataset.pk;
                const nextUrl = widget.dataset.next || window.location.pathname;

                // Animate to deleted state
                widget.setAttribute('data-status', 'deleted');
                widget.classList.remove('open');

                // Perform soft delete
                const csrfToken = getCookie('csrftoken');
                const formData = new FormData();
                formData.append('csrfmiddlewaretoken', csrfToken);
                formData.append('next', nextUrl);

                setTimeout(() => {
                    fetch(`/delete/${itemType}/${pk}/`, {
                        method: 'POST',
                        body: formData,
                        headers: {
                            'X-CSRFToken': csrfToken
                        }
                    })
                    .then(res => {
                        showToast(`Moved to Recycle Bin.`, 'success');
                        setTimeout(() => {
                            // If row is inside table or card, animate fade out, or reload
                            const row = widget.closest('tr') || widget.closest('.customer-card') || widget.closest('.job-item-card');
                            if (row) {
                                row.style.transition = 'all 0.4s ease';
                                row.style.opacity = '0';
                                row.style.transform = 'translateX(20px)';
                                setTimeout(() => window.location.reload(), 450);
                            } else {
                                window.location.reload();
                            }
                        }, 400);
                    })
                    .catch(() => {
                        showToast('Error moving item to Recycle Bin.', 'error');
                        widget.setAttribute('data-status', 'idle');
                    });
                }, 500);
            });
        }
    });

    // Close on click outside or Escape
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.del-widget')) {
            document.querySelectorAll('.del-widget.open').forEach(w => closeWidget(w, false));
        }
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            document.querySelectorAll('.del-widget.open').forEach(w => closeWidget(w, true));
        }
    });
}

/* ==========================================================================
   USER COMPONENT 2: ATELIER WORK TRACKING TASK LIST ENGINE
   Matches User's TaskList & TaskItem:
   - Dashed circle pops and fills with white tick
   - Strikethrough strikes through label
   - Micro-nudge flick animation
   - Updates backend workshop stage in real time
   ========================================================================== */
function initAtelierTaskTracking() {
    document.querySelectorAll('.atelier-task-item').forEach(item => {
        if (item.dataset.trackingInitialized) return;
        item.dataset.trackingInitialized = "true";

        item.addEventListener('click', (e) => {
            e.preventDefault();
            const jobId = item.dataset.jobId;
            const stageAction = item.dataset.stageAction;
            const isChecked = item.getAttribute('data-state') === 'checked';

            // Don't uncheck if already settled without confirmation
            if (isChecked) {
                showToast('This workshop step is already completed.', 'info');
                return;
            }

            // Animate Check State
            item.setAttribute('data-state', 'checked');
            item.classList.add('task-nudge');
            setTimeout(() => item.classList.remove('task-nudge'), 350);

            // Send stage update to backend
            const csrfToken = getCookie('csrftoken');
            fetch(`/api/jobs/${jobId}/stage-action/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ action: stageAction })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    showToast(data.message || 'Stage updated successfully.', 'success');
                    setTimeout(() => window.location.reload(), 700);
                } else {
                    showToast(data.error || 'Failed to update stage.', 'error');
                    item.setAttribute('data-state', 'unchecked');
                }
            })
            .catch(err => {
                console.error(err);
                showToast('Network error while updating stage.', 'error');
                item.setAttribute('data-state', 'unchecked');
            });
        });
    });
}

/* ==========================================================================
   USER COMPONENT 3: 3D CLIENT DOCUMENT FOLDERS ("Client Docs")
   Matches User's FolderComponent:
   - 3 interior cards fan out on hover and click
   - Translucent front flap tilts with 3D perspective
   ========================================================================== */
function initClientFolders() {
    // Support both .folder-interactive-box and legacy .folder-scene
    const boxes = document.querySelectorAll('.folder-interactive-box, .folder-scene');
    boxes.forEach(box => {
        if (box.dataset.folderInitialized) return;
        box.dataset.folderInitialized = "true";

        // Mouse leave: resets open and hover state (matching onMouseLeave in React component)
        box.addEventListener('mouseleave', () => {
            box.classList.remove('is-open');
            box.classList.remove('open');
        });

        // Click: toggles open/close or follows card actions
        box.addEventListener('click', (e) => {
            const card = e.target.closest('[data-doc-action]');
            if (card) {
                const action = card.dataset.docAction;
                const url = card.dataset.docUrl;
                if (url) {
                    e.stopPropagation();
                    if (action === 'bill') {
                        window.open(url, '_blank');
                    } else {
                        window.location.href = url;
                    }
                    return;
                }
            }
            // Toggle open state
            box.classList.toggle('is-open');
            box.classList.toggle('open');
        });
    });

    // Theme Switcher Buttons (if present on docs page)
    document.querySelectorAll('[data-set-folder-theme]').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const targetTheme = btn.dataset.setFolderTheme;
            document.querySelectorAll('.client-folder-wrapper').forEach(wrapper => {
                wrapper.classList.remove('theme-black', 'theme-white', 'theme-blue');
                wrapper.classList.add(`theme-${targetTheme}`);
            });
            document.querySelectorAll('[data-set-folder-theme]').forEach(b => {
                b.classList.remove('active');
                b.style.borderColor = 'var(--pearl-border)';
                b.style.background = 'var(--pearl-card)';
            });
            btn.classList.add('active');
            btn.style.borderColor = 'var(--gold-primary)';
            btn.style.background = 'rgba(212,175,55,0.12)';
            try { localStorage.setItem('gscms_folder_theme', targetTheme); } catch (_) {}
        });
    });

    // Restore saved folder theme if any
    try {
        const savedTheme = localStorage.getItem('gscms_folder_theme');
        if (savedTheme) {
            const btn = document.querySelector(`[data-set-folder-theme="${savedTheme}"]`);
            if (btn) btn.click();
        }
    } catch (_) {}
}

/* ==========================================================================
   USER COMPONENT 4: FAST & SMOOTH DIGITAL CALCULATOR
   Standard calculator with immediate responsiveness and keyboard support
   ========================================================================== */
let calcCurrentVal = '0';
let calcPrevVal = '';
let calcOperation = null;
let calcResetScreen = false;

function initDigitalCalculator() {
    const screenCurrent = document.getElementById('calcScreenCurrent');
    const screenPrev = document.getElementById('calcScreenPrev');
    const screenWords = document.getElementById('calcScreenWords');
    const calculatorDock = document.getElementById('dashboardCalculatorDock');
    const calculatorToggle = calculatorDock && calculatorDock.querySelector('summary');
    if (!screenCurrent) return;

    function numberToIndianWords(n) {
        if (n === null || n === undefined || n === '') return 'Zero';
        const num = parseFloat(n);
        if (isNaN(num)) return '';
        if (num === 0) return 'Zero';

        const isNeg = num < 0;
        const absNum = Math.abs(num);

        const parts = String(absNum).split('.');
        let intVal = parseInt(parts[0], 10);
        const decVal = parts[1];

        const ones = ['', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine',
                      'Ten', 'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen', 'Sixteen', 'Seventeen', 'Eighteen', 'Nineteen'];
        const tens = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety'];

        function twoDigits(val) {
            val = parseInt(val, 10);
            if (val < 20) return ones[val];
            const t = tens[Math.floor(val / 10)];
            const o = ones[val % 10];
            return o ? `${t} ${o}` : t;
        }

        function threeDigits(val) {
            val = parseInt(val, 10);
            const h = Math.floor(val / 100);
            const rem = val % 100;
            let res = '';
            if (h > 0) res += ones[h] + ' Hundred';
            if (rem > 0) res += (res ? ' ' : '') + twoDigits(rem);
            return res;
        }

        function section(val) {
            if (val >= 100) return threeDigits(val);
            return twoDigits(val);
        }

        let wordsArr = [];
        if (intVal > 0) {
            const crore = Math.floor(intVal / 10000000);
            intVal %= 10000000;

            const lakh = Math.floor(intVal / 100000);
            intVal %= 100000;

            const thousand = Math.floor(intVal / 1000);
            intVal %= 1000;

            const hundred = intVal;

            if (crore > 0) wordsArr.push(section(crore) + (crore > 1 ? ' Crores' : ' Crore'));
            if (lakh > 0) wordsArr.push(section(lakh) + (lakh > 1 ? ' Lakhs' : ' Lakh'));
            if (thousand > 0) wordsArr.push(section(thousand) + ' Thousand');
            if (hundred > 0) wordsArr.push(threeDigits(hundred));
        }

        let finalWords = wordsArr.filter(Boolean).join(' ');
        if (!finalWords) finalWords = 'Zero';

        if (decVal && parseInt(decVal, 10) > 0) {
            const decWords = decVal.split('').map(d => ones[parseInt(d, 10)] || 'Zero').join(' ');
            finalWords += ' point ' + decWords;
        }

        return (isNeg ? 'Minus ' : '') + finalWords;
    }

    function updateDisplay() {
        screenCurrent.textContent = calcCurrentVal;
        screenPrev.textContent = calcPrevVal;
        if (screenWords) {
            screenWords.textContent = numberToIndianWords(calcCurrentVal);
        }
    }

    function appendNumber(number) {
        if (calcCurrentVal === '0' || calcResetScreen) {
            calcCurrentVal = number;
            calcResetScreen = false;
        } else {
            if (calcCurrentVal.length < 12) {
                calcCurrentVal += number;
            }
        }
        updateDisplay();
    }

    function appendDecimal() {
        if (calcResetScreen) {
            calcCurrentVal = '0.';
            calcResetScreen = false;
            updateDisplay();
            return;
        }
        if (!calcCurrentVal.includes('.')) {
            calcCurrentVal += '.';
            updateDisplay();
        }
    }

    function clearAll() {
        calcCurrentVal = '0';
        calcPrevVal = '';
        calcOperation = null;
        calcResetScreen = false;
        updateDisplay();
    }

    function toggleSign() {
        if (calcCurrentVal === '0') return;
        calcCurrentVal = calcCurrentVal.startsWith('-') ? calcCurrentVal.slice(1) : '-' + calcCurrentVal;
        updateDisplay();
    }

    function percentage() {
        const val = parseFloat(calcCurrentVal);
        if (isNaN(val)) return;
        calcCurrentVal = String(val / 100);
        updateDisplay();
    }

    function setOperation(op) {
        if (calcOperation !== null) calculate();
        calcPrevVal = `${calcCurrentVal} ${op}`;
        calcOperation = op;
        calcResetScreen = true;
        updateDisplay();
    }

    function calculate() {
        if (calcOperation === null || calcResetScreen) return;
        const prev = parseFloat(calcPrevVal);
        const current = parseFloat(calcCurrentVal);
        if (isNaN(prev) || isNaN(current)) return;

        let result = 0;
        switch (calcOperation) {
            case '+': result = prev + current; break;
            case '−':
            case '-': result = prev - current; break;
            case '×':
            case '*': result = prev * current; break;
            case '÷':
            case '/':
                if (current === 0) {
                    showToast('Cannot divide by zero', 'error');
                    clearAll();
                    return;
                }
                result = prev / current;
                break;
            default: return;
        }

        calcCurrentVal = String(Math.round(result * 100000) / 100000);
        calcPrevVal = '';
        calcOperation = null;
        calcResetScreen = true;
        updateDisplay();
    }

    function backspace() {
        if (calcResetScreen) return;
        if (calcCurrentVal.length > 1) {
            calcCurrentVal = calcCurrentVal.slice(0, -1);
            if (calcCurrentVal === '-') calcCurrentVal = '0';
        } else {
            calcCurrentVal = '0';
        }
        updateDisplay();
    }

    function highlightButton(selector) {
        const btn = document.querySelector(selector);
        if (btn) {
            btn.classList.add('calc-btn-active-key');
            setTimeout(() => btn.classList.remove('calc-btn-active-key'), 120);
        }
    }

    // Attach button clicks
    document.querySelectorAll('.calc-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const action = btn.dataset.action;
            const val = btn.dataset.val;

            if (val !== undefined) {
                appendNumber(val);
            } else if (action === 'decimal') {
                appendDecimal();
            } else if (action === 'clear') {
                clearAll();
            } else if (action === 'toggle-sign') {
                toggleSign();
            } else if (action === 'percent') {
                percentage();
            } else if (action === 'add') {
                setOperation('+');
            } else if (action === 'subtract') {
                setOperation('−');
            } else if (action === 'multiply') {
                setOperation('×');
            } else if (action === 'divide') {
                setOperation('÷');
            } else if (action === 'calculate') {
                calculate();
            }
        });
    });

    if (calculatorDock) {
        calculatorDock.addEventListener('toggle', function () {
            calculatorToggle.setAttribute('aria-label', calculatorDock.open ? 'Close calculator' : 'Open calculator');
        });
        document.addEventListener('click', function (event) {
            if (calculatorDock.open && !calculatorDock.contains(event.target)) calculatorDock.open = false;
        });
        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape' && calculatorDock.open) {
                calculatorDock.open = false;
                calculatorToggle.focus();
            }
        });
    }
    updateDisplay();

    // Keyboard support: Numbers 0-9, Numpad, Operators, Enter, Backspace, Escape
    document.addEventListener('keydown', (e) => {
        // If typing in input, textarea, or contentEditable element, ignore calculator keyboard
        const activeTag = document.activeElement ? document.activeElement.tagName.toLowerCase() : '';
        if (activeTag === 'input' || activeTag === 'textarea' || (document.activeElement && document.activeElement.isContentEditable)) {
            return;
        }

        const key = e.key;

        // Numbers 0-9 (standard row and numpad)
        if (/^[0-9]$/.test(key)) {
            e.preventDefault();
            appendNumber(key);
            highlightButton(`.calc-btn[data-val="${key}"]`);
            return;
        }

        // Decimal point
        if (key === '.' || key === ',') {
            e.preventDefault();
            appendDecimal();
            highlightButton('.calc-btn[data-action="decimal"]');
            return;
        }

        // Operators
        if (key === '+') {
            e.preventDefault();
            setOperation('+');
            highlightButton('.calc-btn[data-action="add"]');
            return;
        }
        if (key === '-' || key === '−') {
            e.preventDefault();
            setOperation('−');
            highlightButton('.calc-btn[data-action="subtract"]');
            return;
        }
        if (key === '*' || key === 'x' || key === 'X') {
            e.preventDefault();
            setOperation('×');
            highlightButton('.calc-btn[data-action="multiply"]');
            return;
        }
        if (key === '/') {
            e.preventDefault();
            setOperation('÷');
            highlightButton('.calc-btn[data-action="divide"]');
            return;
        }

        // Calculate / Equals
        if (key === 'Enter' || key === '=') {
            e.preventDefault();
            calculate();
            highlightButton('.calc-btn[data-action="calculate"]');
            return;
        }

        // Backspace
        if (key === 'Backspace') {
            e.preventDefault();
            backspace();
            return;
        }

        // Clear All
        if (key === 'Escape' || key.toLowerCase() === 'c' || key === 'Delete') {
            e.preventDefault();
            clearAll();
            highlightButton('.calc-btn[data-action="clear"]');
            return;
        }

        // Percentage
        if (key === '%') {
            e.preventDefault();
            percentage();
            highlightButton('.calc-btn[data-action="percent"]');
            return;
        }
    });

    updateDisplay();
}
