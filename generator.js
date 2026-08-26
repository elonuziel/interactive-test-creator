document.addEventListener('DOMContentLoaded', () => {
    const STORAGE = {
        theme: 'theme'
    };

    const EMBEDDED_KEY = {
        encryptedKeyB64: 'Hv6PPzBzdBiwexOLNv2KF4vTQZCo0clZUyZNkw0zSWH/+pWkySSOJEZnv585nIoFtl/3ovyRf5vaaBE1GB2NOJKRHvyN',
        ivB64: '/5FGe5eK7voMUlB/',
        saltB64: '0FgJhVvq66HJ3YTs6XHn3Q=='
    };

    const GEMINI_CONFIG = {
        apiVersions: ['v1', 'v1beta'],
        preferredModels: ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash'],
        maxQuotaRetries: 5,
        initialRetryDelayMs: 5000,
        maxRetryDelayMs: 60000,
        interPageDelayMs: 8000,
        ocrChunkSize: 20
    };

    const state = {
        questions: [],
        templateCache: null,
        geminiModelCandidates: null,
        proofPageImages: [],
        proofMode: true,
        pdfArrayBuffer: null,
        pdfPagesState: []
    };

    const elements = {
        pdfFile: document.getElementById('pdf-file'),
        pdfTypeNote: document.getElementById('pdf-type-note'),
        jsonFile: document.getElementById('json-file'),
        csvFile: document.getElementById('csv-file'),
        formNumber: document.getElementById('form-number'),
        mergeAnswersBtn: document.getElementById('merge-answers-btn'),
        autoAttachDiagramsBtn: document.getElementById('auto-attach-diagrams-btn'),
        stripQuestionHeadersBtnPreview: document.getElementById('strip-question-headers-btn-preview'),
        ocrEngine: document.getElementById('ocr-engine'),
        llmPolicy: document.getElementById('llm-policy'),
        apiKey: document.getElementById('api-key'),
        passcode: document.getElementById('passcode'),
        credentialPopup: document.getElementById('credential-popup'),
        credentialApiKey: document.getElementById('credential-api-key'),
        credentialPasscode: document.getElementById('credential-passcode'),
        credentialSubmit: document.getElementById('credential-submit'),
        credentialCancel: document.getElementById('credential-cancel'),
        htmlFile: document.getElementById('html-file'),
        scannedActionsBox: document.getElementById('scanned-actions-box'),
        digitalActionsBox: document.getElementById('digital-actions-box'),
        runDigitalLocalBtn: document.getElementById('run-digital-local-btn'),
        digitalPromptExpandable: document.getElementById('digital-prompt-expandable'),
        copyDigitalPromptBtn: document.getElementById('copy-digital-prompt-btn'),
        digitalLlmPromptBox: document.getElementById('digital-llm-prompt-box'),
        toggleProcessingSettingsBtn: document.getElementById('toggle-processing-settings-btn'),
        processingSettingsContainer: document.getElementById('processing-settings-container'),
        copyPromptBtn: document.getElementById('copy-prompt-btn'),
        llmPromptBox: document.getElementById('llm-prompt-box'),
        pdfSidebarCard: document.getElementById('pdf-sidebar-card'),
        toggleSidebarCollapseBtn: document.getElementById('toggle-sidebar-collapse-btn'),
        builderLayout: document.getElementById('builder-layout'),
        pageCountBadge: document.getElementById('page-count-badge'),
        presetStdBtn: document.getElementById('preset-std-btn'),
        presetEvenOddBtn: document.getElementById('preset-even-odd-btn') || document.getElementById('preset-blank-btn'),
        presetBlankBtn: document.getElementById('preset-blank-btn'),
        presetSelectAllBtn: document.getElementById('preset-select-all-btn'),
        presetDeselectAllBtn: document.getElementById('preset-deselect-all-btn'),
        downloadCleanPdf: document.getElementById('download-clean-pdf'),
        pageThumbnailsContainer: document.getElementById('page-thumbnails-container'),
        runParse: document.getElementById('run-parse'),
        downloadQuiz: document.getElementById('download-quiz'),
        takeQuiz: document.getElementById('take-quiz'),
        confirmDownloadBtn: document.getElementById('confirm-download-btn'),
        compressSettingsCancel: document.getElementById('compress-settings-cancel'),
        compressSettingsPopup: document.getElementById('compress-settings-popup'),
        compressExportImages: document.getElementById('compress-export-images'),
        compressQualitySlider: document.getElementById('compress-quality-slider'),
        compressQualityVal: document.getElementById('compress-quality-val'),
        compressSliderWrap: document.getElementById('compress-slider-wrap'),
        status: document.getElementById('status'),
        preview: document.getElementById('preview'),
        proofModeToggle: document.getElementById('proof-mode-toggle'),
        useCleanPdfForApi: document.getElementById('use-clean-pdf-for-api'),
        enableLlmVerification: document.getElementById('enable-llm-verification'),
        verificationWarningBox: document.getElementById('verification-warning-box'),
        verificationBadge: document.getElementById('verification-badge'),
        themeToggle: document.getElementById('theme-toggle'),
        themeIcon: document.getElementById('theme-icon')
    };

    let theme = localStorage.getItem(STORAGE.theme) || 'light';

    function setTheme(nextTheme) {
        theme = nextTheme;
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem(STORAGE.theme, theme);
        if (theme === 'dark') {
            elements.themeIcon.innerHTML = '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"></path>';
        } else {
            elements.themeIcon.innerHTML = '<circle cx="12" cy="12" r="4"></circle><path d="M12 2v2"></path><path d="M12 20v2"></path><path d="m4.93 4.93 1.41 1.41"></path><path d="m17.66 17.66 1.41 1.41"></path><path d="M2 12h2"></path><path d="M20 12h2"></path><path d="m6.34 17.66-1.41 1.41"></path><path d="m19.07 4.93-1.41 1.41"></path>';
        }
    }

    setTheme(theme);
    elements.themeToggle.addEventListener('click', () => setTheme(theme === 'light' ? 'dark' : 'light'));
    if (elements.proofModeToggle) {
        state.proofMode = !!elements.proofModeToggle.checked;
        elements.proofModeToggle.addEventListener('change', () => {
            state.proofMode = !!elements.proofModeToggle.checked;
            renderPreview();
        });
    }
    function updateVerificationUI() {
        if (!elements.enableLlmVerification) return;
        const isChecked = elements.enableLlmVerification.checked;
        if (elements.verificationWarningBox) {
            elements.verificationWarningBox.classList.toggle('hidden', !isChecked);
        }
        if (elements.verificationBadge) {
            if (isChecked) {
                elements.verificationBadge.textContent = '🔍 2 קריאות API';
                elements.verificationBadge.style.background = 'rgba(217, 119, 6, 0.15)';
                elements.verificationBadge.style.color = '#d97706';
                elements.verificationBadge.style.borderColor = 'rgba(217, 119, 6, 0.35)';
            } else {
                elements.verificationBadge.textContent = '⚡ קריאה 1 (מהיר)';
                elements.verificationBadge.style.background = 'rgba(16, 185, 129, 0.12)';
                elements.verificationBadge.style.color = '#059669';
                elements.verificationBadge.style.borderColor = 'rgba(16, 185, 129, 0.3)';
            }
        }
    }

    if (elements.enableLlmVerification) {
        updateVerificationUI();
        elements.enableLlmVerification.addEventListener('change', updateVerificationUI);
    }

    function showToast(message, type = 'success', duration = 4000) {
        const container = document.getElementById('toast-container');
        if (!container) return;

        const toast = document.createElement('div');
        toast.className = `toast ${type}`;

        const iconMap = {
            success: '✅',
            error: '⚠️',
            info: '💡'
        };

        const iconSpan = document.createElement('span');
        iconSpan.textContent = iconMap[type] || 'ℹ️';

        const textSpan = document.createElement('span');
        textSpan.textContent = message;

        toast.append(iconSpan, textSpan);
        container.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(10px)';
            toast.style.transition = 'all 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }

    // ── Image Lightbox ──
    // Shows an image in a fullscreen overlay. If pageNum is provided and
    // PDF bytes are available, re-renders the page at high resolution
    // (scale 2.5) and swaps the image in once ready.
    async function showImageZoom(src, pageNum = null) {
        let overlay = document.getElementById('gen-zoom-overlay');
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.id = 'gen-zoom-overlay';
            overlay.style.cssText = [
                'position:fixed;inset:0;z-index:99999',
                'background:rgba(0,0,0,0.88)',
                'display:flex;flex-direction:column;align-items:center;justify-content:center;gap:12px',
                'cursor:zoom-out;padding:24px;box-sizing:border-box'
            ].join(';');

            const spinner = document.createElement('div');
            spinner.id = 'gen-zoom-spinner';
            spinner.style.cssText = [
                'width:40px;height:40px',
                'border:4px solid rgba(255,255,255,0.2)',
                'border-top-color:#fff',
                'border-radius:50%',
                'animation:gen-spin 0.7s linear infinite',
                'display:none'
            ].join(';');
            if (!document.getElementById('gen-spin-style')) {
                const s = document.createElement('style');
                s.id = 'gen-spin-style';
                s.textContent = '@keyframes gen-spin{to{transform:rotate(360deg)}}';
                document.head.appendChild(s);
            }

            const zoomImg = document.createElement('img');
            zoomImg.id = 'gen-zoom-img';
            zoomImg.style.cssText = [
                'max-width:100%;max-height:88vh',
                'border-radius:10px',
                'box-shadow:0 8px 40px rgba(0,0,0,0.7)',
                'object-fit:contain'
            ].join(';');

            overlay.appendChild(spinner);
            overlay.appendChild(zoomImg);

            overlay.addEventListener('click', (e) => {
                if (e.target === overlay || e.target === zoomImg) {
                    overlay.style.display = 'none';
                    document.body.style.overflow = '';
                }
            });
            document.body.appendChild(overlay);
            // Single persistent Escape handler — registered once on the overlay element
            overlay._keyHandler = (e) => {
                if (e.key === 'Escape' && overlay.style.display !== 'none') {
                    overlay.style.display = 'none';
                    document.body.style.overflow = '';
                }
            };
            document.addEventListener('keydown', overlay._keyHandler);
        }

        const zoomImg = document.getElementById('gen-zoom-img');
        const spinner = document.getElementById('gen-zoom-spinner');

        // Show placeholder (low-res thumbnail) immediately
        zoomImg.src = src;
        zoomImg.style.opacity = '1';
        overlay.style.display = 'flex';
        document.body.style.overflow = 'hidden';

        // If we have the PDF and a page number, render hi-res in the background
        if (pageNum && state.pdfBytes && state.pdfBytes.length > 0) {
            const pdfjs = window.pdfjsLib || window['pdfjs-dist/build/pdf'] || window.pdfjs;
            if (pdfjs?.getDocument) {
                spinner.style.display = 'block';
                zoomImg.style.opacity = '0.4';
                try {
                    const pdfDoc = await pdfjs.getDocument({ data: new Uint8Array(state.pdfBytes) }).promise;
                    const page = await pdfDoc.getPage(pageNum);
                    const hiResSrc = 'data:image/png;base64,' + await renderPageImageData(page);
                    // Only update if overlay is still open
                    if (overlay.style.display !== 'none') {
                        zoomImg.src = hiResSrc;
                        zoomImg.style.opacity = '1';
                    }
                } catch (err) {
                    console.warn('Hi-res zoom render failed:', err);
                } finally {
                    spinner.style.display = 'none';
                    zoomImg.style.opacity = '1';
                }
            }
        }
    }

    function setStatus(message, isError = false, triggerToast = false) {
        elements.status.textContent = message;
        elements.status.classList.toggle('muted', !isError);
        elements.status.style.color = isError ? 'var(--danger)' : 'var(--text-primary)';
        if (triggerToast || isError) {
            showToast(message, isError ? 'error' : 'success');
        }
    }

    function disableOutputActions(disabled) {
        if (elements.downloadQuiz) elements.downloadQuiz.disabled = disabled;
        if (elements.takeQuiz) elements.takeQuiz.disabled = disabled;
        if (elements.compressSettingsBtn) elements.compressSettingsBtn.disabled = disabled;
        if (elements.compressExportImages) elements.compressExportImages.disabled = disabled;
    }

    function setPdfTypeNote(message = '', tone = 'neutral') {
        if (!elements.pdfTypeNote) return;
        elements.pdfTypeNote.textContent = message;
        elements.pdfTypeNote.classList.toggle('hidden', !message);
        elements.pdfTypeNote.classList.remove('is-loading', 'is-digital', 'is-scanned', 'is-error');
        if (!message) return;
        if (tone === 'loading') elements.pdfTypeNote.classList.add('is-loading');
        else if (tone === 'digital') elements.pdfTypeNote.classList.add('is-digital');
        else if (tone === 'scanned') elements.pdfTypeNote.classList.add('is-scanned');
        else if (tone === 'error') elements.pdfTypeNote.classList.add('is-error');
    }

    function decodeBase64(base64) {
        const str = atob(base64);
        const bytes = new Uint8Array(str.length);
        for (let i = 0; i < str.length; i++) bytes[i] = str.charCodeAt(i);
        return bytes;
    }

    async function decryptSingleKey(passcode, keyObj) {
        if (!keyObj || !keyObj.encryptedKeyB64 || !keyObj.ivB64 || !keyObj.saltB64 || !passcode) {
            return '';
        }

        try {
            const encoder = new TextEncoder();
            const keyMaterial = await crypto.subtle.importKey(
                'raw',
                encoder.encode(passcode),
                'PBKDF2',
                false,
                ['deriveKey']
            );

            const aesKey = await crypto.subtle.deriveKey(
                {
                    name: 'PBKDF2',
                    salt: decodeBase64(keyObj.saltB64),
                    iterations: 100000,
                    hash: 'SHA-256'
                },
                keyMaterial,
                { name: 'AES-GCM', length: 256 },
                false,
                ['decrypt']
            );

            const decrypted = await crypto.subtle.decrypt(
                {
                    name: 'AES-GCM',
                    iv: decodeBase64(keyObj.ivB64)
                },
                aesKey,
                decodeBase64(keyObj.encryptedKeyB64)
            );

            return new TextDecoder().decode(decrypted).trim();
        } catch {
            return '';
        }
    }

    async function decryptEmbeddedApiKey(passcode) {
        const gemini = await decryptSingleKey(passcode, EMBEDDED_KEY);
        if (!gemini) return null;
        return gemini;
    }

    function requestGeminiCredentials() {
        return new Promise((resolve, reject) => {
            const popup = elements.credentialPopup;
            const apiKeyInput = elements.credentialApiKey;
            const passcodeInput = elements.credentialPasscode;
            const submitButton = elements.credentialSubmit;
            const cancelButton = elements.credentialCancel;

            if (!popup || !apiKeyInput || !passcodeInput || !submitButton || !cancelButton) {
                reject(new Error('ממשק הזנת האישורים לא נטען. רענן את העמוד ונסה שוב.'));
                return;
            }

            apiKeyInput.value = elements.apiKey.value.trim();
            passcodeInput.value = '';
            popup.classList.add('show');

            const cleanup = () => {
                popup.classList.remove('show');
                submitButton.removeEventListener('click', handleSubmit);
                cancelButton.removeEventListener('click', handleCancel);
            };

            const handleSubmit = () => {
                const apiKey = apiKeyInput.value.trim();
                const passcode = passcodeInput.value.trim();
                cleanup();
                resolve({ apiKey, passcode });
            };

            const handleCancel = () => {
                cleanup();
                reject(new Error('העיבוד הנוכחי דורש Gemini. הזן API Key או Passcode כדי להמשיך, או עבור למצב ללא LLM.'));
            };

            submitButton.addEventListener('click', handleSubmit);
            cancelButton.addEventListener('click', handleCancel);
            apiKeyInput.focus();
        });
    }

    async function resolveGeminiApiKey(allowPrompt = false) {
        const typedApiKey = elements.apiKey.value.trim();
        if (typedApiKey) {
            if (typedApiKey.toLowerCase().includes('elza')) {
                throw new Error('שרת Elza בביטול / יוצא משימוש (Phasing Out). אנא הזן מפתח AQ API תקין (AQ...) מ-Google AI Studio.');
            }
            return typedApiKey;
        }

        const currentPasscode = elements.passcode.value.trim();
        if (currentPasscode) {
            const decrypted = await decryptEmbeddedApiKey(currentPasscode);
            if (decrypted) {
                elements.apiKey.value = decrypted;
                return decrypted;
            }
            if (!allowPrompt) {
                throw new Error('ה-Passcode שגוי או שמפתח ה-API המוצפן לא הוגדר נכון בקובץ generator.js.');
            }
        }

        if (!allowPrompt) {
            return '';
        }

        const { apiKey: promptedApiKey, passcode: promptedPasscode } = await requestGeminiCredentials();
        if (promptedApiKey) {
            if (promptedApiKey.toLowerCase().includes('elza')) {
                throw new Error('שרת Elza בביטול / יוצא משימוש (Phasing Out). אנא הזן מפתח AQ API תקין (AQ...) מ-Google AI Studio.');
            }
            elements.apiKey.value = promptedApiKey;
            return promptedApiKey;
        }

        if (promptedPasscode) {
            elements.passcode.value = promptedPasscode;
            const decrypted = await decryptEmbeddedApiKey(promptedPasscode);
            if (decrypted) {
                elements.apiKey.value = decrypted;
                return decrypted;
            }
            throw new Error('ה-Passcode שגוי או שמפתח ה-API המוצפן לא הוגדר נכון בקובץ generator.js.');
        }

        throw new Error('העיבוד הנוכחי דורש Gemini. הזן API Key או Passcode כדי להמשיך, או עבור למצב ללא LLM.');
    }

    function normalizeWhitespace(value) {
        return value.replace(/\u00A0/g, ' ').replace(/\s+/g, ' ').trim();
    }

    function stripExamFooterArtifacts(value) {
        if (!value) return '';
        return value
            .replace(/\[cite:\s*\d+\]/gi, '')
            .replace(/-+\s*סוף\s+המבחן\s*-+/g, ' ');
    }

    function stripQuestionHeaderPrefix(value) {
        if (!value) return '';
        let t = value.replace(/^#+\s*/, '').trim();
        const prefixPattern = /^(?:(?:שאלה(?:\s+מספר)?\s*:?\s*:?\d+\s*:?|:?\d+\s*:?\s*(?:שאלה(?:\s+מספר)?|מספר\s+שאלה)|מספר\s+שאלה\s*:?\s*:?\d+\s*:?|\d+\s*[\.\)\(-])\s*)+:?\s*/i;
        const cleaned = t.replace(prefixPattern, '').trim();
        return cleaned || t;
    }

    function fixHebrewWordOrder(text) {
        return text
            .split('\n')
            .map((line) => {
                const trimmed = line.trim();
                if (!trimmed) return '';
                return trimmed.split(/\s+/).reverse().join(' ');
            })
            .join('\n');
    }

    function maybeFixHebrewWordOrder(text) {
        const lines = text
            .split(/\r?\n/)
            .map((line) => line.trim())
            .filter(Boolean)
            .slice(0, 200);

        if (!lines.length) {
            return text;
        }

        // If key phrases are mostly reversed (e.g. "מספר שאלה"), reorder words.
        // Keep this conservative so digital PDFs that are already logical are
        // not accidentally flipped.
        let normalSignals = 0;
        let reversedSignals = 0;

        for (const line of lines) {
            if (/שאלה\s+מספר|מבחן\s+מס/.test(line)) {
                normalSignals++;
            }
            if (/מספר\s+שאלה|מס\s+מבחן/.test(line)) {
                reversedSignals++;
            }
        }

        const strongReversedEvidence = reversedSignals >= 4 && reversedSignals >= (normalSignals + 2);
        return strongReversedEvidence ? fixHebrewWordOrder(text) : text;
    }

    function hasHebrew(text) {
        return /[\u0590-\u05FF]/.test(text || '');
    }

    function detectLineDirection(chunks) {
        let rtlScore = 0;
        let ltrScore = 0;

        for (const chunk of chunks) {
            const t = chunk.text || '';
            if (!t) continue;

            if (chunk.dir === 'rtl') rtlScore += 2;
            if (chunk.dir === 'ltr') ltrScore += 2;

            if (hasHebrew(t)) rtlScore += 1;
            if (/[A-Za-z]/.test(t)) ltrScore += 1;
            if (/\d/.test(t) && !hasHebrew(t)) ltrScore += 1;
        }

        return rtlScore > ltrScore ? 'rtl' : 'ltr';
    }

    function joinChunksByGeometry(chunks, direction) {
        if (!chunks || !chunks.length) return '';
        if (chunks.length === 1) return chunks[0].text || '';

        const charWidths = chunks
            .map((c) => {
                const t = String(c.text || '');
                const w = Number(c.w || 0);
                return (t.length > 0 && w > 0) ? (w / t.length) : 0;
            })
            .filter((v) => v > 0 && Number.isFinite(v));

        const avgCharWidth = charWidths.length
            ? (charWidths.reduce((sum, v) => sum + v, 0) / charWidths.length)
            : 6;

        const gapThreshold = Math.max(1.2, avgCharWidth * 0.45);
        let out = String(chunks[0].text || '');

        for (let i = 1; i < chunks.length; i++) {
            const prev = chunks[i - 1];
            const curr = chunks[i];
            const prevText = String(prev.text || '');
            const currText = String(curr.text || '');

            const prevW = Number(prev.w || 0);
            const currW = Number(curr.w || 0);

            let gap = gapThreshold + 1;
            if (prevW > 0 && currW > 0) {
                if (direction === 'rtl') {
                    // For RTL sorting (right -> left): gap is distance between
                    // previous chunk's left edge and current chunk's right edge.
                    gap = prev.x - (curr.x + currW);
                } else {
                    // For LTR sorting (left -> right): gap is distance between
                    // previous chunk's right edge and current chunk's left edge.
                    gap = curr.x - (prev.x + prevW);
                }
            }

            const needsSpace = gap > gapThreshold;
            out += (needsSpace ? ' ' : '') + currText;
        }

        return out.replace(/\s+/g, ' ').trim();
    }

    function buildLinesFromStreamOrder(items) {
        const lines = [];
        let current = '';

        for (const item of (items || [])) {
            const raw = item && typeof item.str === 'string' ? item.str : '';
            const text = raw.replace(/\u00A0/g, ' ').trim();
            const hasEOL = Boolean(item && item.hasEOL);

            if (text) {
                if (!current) {
                    current = text;
                } else {
                    const noLeadingSpace = /^[\)\]\}\.,:;!?%]/.test(text);
                    const noTrailingSpace = /[\(\[\{\-\/]$/.test(current);
                    current += (noLeadingSpace || noTrailingSpace ? '' : ' ') + text;
                }
            }

            if (hasEOL) {
                if (current.trim()) lines.push(current.trim());
                current = '';
            }
        }

        if (current.trim()) lines.push(current.trim());
        return lines;
    }

    function computeHebrewBreakageScore(text) {
        const tokens = String(text || '').split(/\s+/).filter(Boolean);
        if (!tokens.length) return 1;

        const hebTokens = tokens.filter((t) => /[\u0590-\u05FF]/.test(t));
        if (!hebTokens.length) return 1;

        const singleHeb = hebTokens.filter((t) => /^[\u0590-\u05FF]$/.test(t)).length;
        const tinyHeb = hebTokens.filter((t) => /^[\u0590-\u05FF]{1,2}$/.test(t)).length;

        // Lower is better.
        return (singleHeb / hebTokens.length) + ((tinyHeb / hebTokens.length) * 0.35);
    }

    function computeStructureSignal(lines) {
        const qLike = /(?:^#*\s*שאלה\s+\d+|^#*\s*שאלה\s+מספר\s*:?\d+|^\d+\s*[\)\(\.-]\s*)/;
        const aLike = /^(?:[-\*\+\u2022]\s*)?[אבגדהוזחטי]\s*[\.)]/;

        let score = 0;
        for (const line of (lines || [])) {
            const l = String(line || '').trim();
            if (!l) continue;
            if (qLike.test(l)) score += 2;
            if (aLike.test(l)) score += 1;
        }
        return score;
    }

    function chooseBestPageText(linesA, linesB) {
        const textA = (linesA || []).join('\n');
        const textB = (linesB || []).join('\n');

        if (!textA && !textB) return '';
        if (!textA) return textB;
        if (!textB) return textA;

        const breakA = computeHebrewBreakageScore(textA);
        const breakB = computeHebrewBreakageScore(textB);
        const structA = computeStructureSignal(linesA);
        const structB = computeStructureSignal(linesB);

        const qualityA = structA - (breakA * 8);
        const qualityB = structB - (breakB * 8);

        return qualityB > qualityA ? textB : textA;
    }

    function groupPdfTextItemsToLines(items) {
        const normalized = items
            .filter((item) => item.str && item.str.trim())
            .map((item) => ({
                text: item.str.trim(),
                x: item.transform[4],
                y: item.transform[5],
                dir: item.dir || '',
                w: item.width || 0
            }));

        normalized.sort((a, b) => {
            if (Math.abs(a.y - b.y) > 4) return b.y - a.y;
            return a.x - b.x;
        });

        const lines = [];
        for (const item of normalized) {
            const line = lines.find((candidate) => Math.abs(candidate.y - item.y) <= 4);
            if (!line) {
                lines.push({ y: item.y, chunks: [item] });
            } else {
                line.chunks.push(item);
            }
        }

        lines.sort((a, b) => b.y - a.y);

        return lines.map((line) => {
            const direction = detectLineDirection(line.chunks);
            const sorted = [...line.chunks].sort((a, b) => direction === 'rtl' ? b.x - a.x : a.x - b.x);
            return joinChunksByGeometry(sorted, direction);
        });
    }

    async function extractPageImage(page) {
        // Render the full page to a canvas and return it as a base64 PNG data URL.
        const viewport = page.getViewport({ scale: 1.5 });
        const canvas = document.createElement('canvas');
        canvas.width = Math.floor(viewport.width);
        canvas.height = Math.floor(viewport.height);
        const ctx = canvas.getContext('2d');
        await page.render({ canvasContext: ctx, viewport }).promise;
        return canvas.toDataURL('image/png');
    }

    async function extractPdfText(inputBuffer) {
        const pdfjs = window.pdfjsLib || window['pdfjs-dist/build/pdf'] || window.pdfjs;
        if (!pdfjs?.getDocument) {
            throw new Error('PDF.js לא נטען. רענן את העמוד ונסה שוב.');
        }

        const freshData = new Uint8Array(inputBuffer);
        const loadingTask = pdfjs.getDocument({ data: freshData });
        const pdf = await loadingTask.promise;
        const pages = [];
        const pageImages = []; // index = pageNumber-1, value = base64 data URL or null
        let nonWhitespaceChars = 0;

        for (let pageNumber = 1; pageNumber <= pdf.numPages; pageNumber++) {
            const page = await pdf.getPage(pageNumber);
            const textContent = await page.getTextContent({ normalizeWhitespace: true, disableCombineTextItems: false });
            const geoLines = groupPdfTextItemsToLines(textContent.items);
            const streamLines = buildLinesFromStreamOrder(textContent.items);
            const lineText = chooseBestPageText(geoLines, streamLines);
            pages.push(lineText);
            nonWhitespaceChars += lineText.replace(/\s/g, '').length;

            // Detect if this page has embedded images via operator list.
            // Fallback to hardcoded PDF.js OPS values if .OPS is not exported.
            try {
                const ops = await page.getOperatorList();
                const PAINT_IMAGE = (pdfjs.OPS && pdfjs.OPS.paintImageXObject) || 85;
                const PAINT_INLINE = (pdfjs.OPS && pdfjs.OPS.paintInlineImageXObject) || 86;
                const hasPaintOp = ops.fnArray.some((fn) => fn === PAINT_IMAGE || fn === PAINT_INLINE);
                pageImages.push(hasPaintOp ? await extractPageImage(page) : null);
            } catch {
                pageImages.push(null);
            }
        }

        return {
            pdf,
            pageImages,
            isScanned: nonWhitespaceChars < Math.max(pdf.numPages * 60, 120),
            text: maybeFixHebrewWordOrder(pages.join('\n')),
            rawPages: pages // preserve per-page text for image association
        };
    }

    async function detectPdfType(inputBuffer) {
        const pdfjs = window.pdfjsLib || window['pdfjs-dist/build/pdf'] || window.pdfjs;
        if (!pdfjs?.getDocument) {
            throw new Error('PDF.js לא נטען. אם העמוד נפתח ישירות מהדיסק (file://), יש להשתמש בשרת מקומי (start_test_server.bat) או לוודא חיבור לרשת.');
        }

        const freshData = new Uint8Array(inputBuffer);
        const loadingTask = pdfjs.getDocument({ data: freshData });
        const pdf = await loadingTask.promise;
        let nonWhitespaceChars = 0;

        for (let pageNumber = 1; pageNumber <= pdf.numPages; pageNumber++) {
            const page = await pdf.getPage(pageNumber);
            const textContent = await page.getTextContent();
            const pageText = textContent.items.map((item) => (item.str || '').trim()).join(' ');
            nonWhitespaceChars += pageText.replace(/\s/g, '').length;
        }

        const isScanned = nonWhitespaceChars < Math.max(pdf.numPages * 60, 120);
        return {
            isScanned,
            pdfTypeLabel: isScanned ? '📷 PDF סרוק (תמונה)' : '📄 PDF דיגיטלי (עם טקסט)',
            recommendation: isScanned
                ? 'יזדקק ל-OCR. אפשר להשתמש ב-Gemini או ב-OCR החינמי בדפדפן.'
                : 'יעובד מקומית בלחיצת כפתור ללא OCR וללא צורך ב-API Key.'
        };
    }

    async function renderPageImageData(page, scale = 2.5) {
        const viewport = page.getViewport({ scale });
        const canvas = document.createElement('canvas');
        const context = canvas.getContext('2d');
        canvas.width = Math.floor(viewport.width);
        canvas.height = Math.floor(viewport.height);
        await page.render({ canvasContext: context, viewport }).promise;
        return canvas.toDataURL('image/png').replace(/^data:image\/png;base64,/, '');
    }

    function fileToBase64(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => {
                const result = String(reader.result || '');
                const commaIdx = result.indexOf(',');
                if (commaIdx < 0) {
                    reject(new Error('לא ניתן היה לקודד את קובץ ה-PDF לבסיס64.'));
                    return;
                }
                resolve(result.slice(commaIdx + 1));
            };
            reader.onerror = () => {
                reject(new Error('קריאת קובץ ה-PDF נכשלה.'));
            };
            reader.readAsDataURL(file);
        });
    }

    async function renderAllPdfPageImages(pdf) {
        const imageDatas = [];
        const pagePreviews = [];

        for (let pageNumber = 1; pageNumber <= pdf.numPages; pageNumber++) {
            setStatus(`מכין עמוד ${pageNumber}/${pdf.numPages} לשליחה...`);
            const page = await pdf.getPage(pageNumber);
            const imageData = await renderPageImageData(page);
            imageDatas.push(imageData);
            pagePreviews.push(`data:image/png;base64,${imageData}`);
        }

        return { imageDatas, pagePreviews };
    }

    async function extractTextViaOfflineOcr(pdf) {
        if (!window.Tesseract?.createWorker) {
            throw new Error('רכיב OCR חינמי לא נטען בדפדפן. רענן את העמוד ונסה שוב, או בחר Gemini.');
        }

        setStatus('מכין OCR חינמי בדפדפן. האיכות כנראה תהיה נמוכה יותר מ-Gemini...');
        const { imageDatas, pagePreviews } = await renderAllPdfPageImages(pdf);
        const pages = [];
        const worker = await window.Tesseract.createWorker('heb');

        try {
            for (let i = 0; i < imageDatas.length; i++) {
                setStatus(`OCR חינמי מעבד עמוד ${i + 1}/${imageDatas.length}... האיכות כנראה תהיה נמוכה יותר מ-Gemini.`);
                const { data } = await worker.recognize(`data:image/png;base64,${imageDatas[i]}`);
                pages.push(maybeFixHebrewWordOrder((data && data.text) || ''));
            }
        } finally {
            await worker.terminate();
        }

        return {
            pages,
            pagePreviews,
            text: pages.join('\n')
        };
    }

    function buildGeminiEndpoint(version, model, apiKey) {
        return `https://generativelanguage.googleapis.com/${version}/models/${model}:generateContent?key=${encodeURIComponent(apiKey)}`;
    }

    function normalizeModelName(name) {
        if (!name) return '';
        return name.startsWith('models/') ? name.slice('models/'.length) : name;
    }

    async function discoverGeminiModelCandidates(apiKey) {
        if (state.geminiModelCandidates) {
            return state.geminiModelCandidates;
        }

        const discovered = [];
        const seen = new Set();

        for (const version of GEMINI_CONFIG.apiVersions) {
            const endpoint = `https://generativelanguage.googleapis.com/${version}/models?key=${encodeURIComponent(apiKey)}`;
            try {
                const response = await fetch(endpoint);
                if (!response.ok) {
                    continue;
                }

                const payload = await response.json();
                const models = payload.models || [];
                for (const model of models) {
                    const modelName = normalizeModelName(model.name || '');
                    const supportedMethods = model.supportedGenerationMethods || [];
                    if (!modelName || !supportedMethods.includes('generateContent')) {
                        continue;
                    }

                    if (!modelName.includes('gemini') || !modelName.includes('flash')) {
                        continue;
                    }

                    const key = `${version}:${modelName}`;
                    if (seen.has(key)) {
                        continue;
                    }

                    seen.add(key);
                    discovered.push({ version, model: modelName });
                }
            } catch {
                // Fall through to static fallback list.
            }
        }

        if (!discovered.length) {
            for (const version of GEMINI_CONFIG.apiVersions) {
                for (const model of GEMINI_CONFIG.preferredModels) {
                    discovered.push({ version, model });
                }
            }
        }

        state.geminiModelCandidates = discovered;
        return discovered;
    }

    function sortGeminiModelCandidates(candidates) {
        const priority = [
            'gemini-2.5-flash',
            'gemini-2.0-flash',
            'gemini-1.5-flash',
            'gemini-2.0-flash-lite',
            'gemini-2.5-flash-lite'
        ];

        return [...candidates].sort((a, b) => {
            const idxA = priority.indexOf(a.model);
            const idxB = priority.indexOf(b.model);

            if (idxA !== -1 && idxB !== -1) return idxA - idxB;
            if (idxA !== -1) return -1;
            if (idxB !== -1) return 1;

            const isExpA = a.model.includes('3.5') || a.model.includes('3.6') || a.model.includes('experimental') || a.model.includes('preview');
            const isExpB = b.model.includes('3.5') || b.model.includes('3.6') || b.model.includes('experimental') || b.model.includes('preview');

            if (isExpA && !isExpB) return 1;
            if (!isExpA && isExpB) return -1;

            if (a.version !== b.version) return a.version === 'v1beta' ? -1 : 1;
            return a.model.localeCompare(b.model);
        });
    }

    function getGeminiErrorInfo(status, errorText) {
        const raw = String(errorText || '');
        let parsedMessage = '';

        try {
            const parsed = JSON.parse(raw);
            parsedMessage = parsed?.error?.message || '';
        } catch {
            parsedMessage = raw;
        }

        const message = String(parsedMessage || raw || '').trim();
        const normalized = message.toLowerCase();

        if (status === 401 || status === 403) {
            return {
                code: 'auth',
                retryNextModel: false,
                userMessage: 'מפתח Gemini לא תקין, חסום או חסרות הרשאות (401/403).'
            };
        }

        if (status === 429) {
            return {
                code: 'quota',
                retryNextModel: true,
                userMessage: 'חריגה ממכסה או קצב בקשות Gemini (429). מנסה מודל חלופי...'
            };
        }

        if (
            status === 404 ||
            normalized.includes('not found') ||
            normalized.includes('not supported for generatecontent') ||
            normalized.includes('is not supported for generatecontent') ||
            normalized.includes('only supports interactions api')
        ) {
            return {
                code: 'model_not_found',
                retryNextModel: true,
                userMessage: 'המודל אינו זמין עבור המפתח/גרסת API, מנסה מודל חלופי...'
            };
        }

        if (status >= 500 || status === 503) {
            return {
                code: 'server',
                retryNextModel: true,
                userMessage: 'שגיאת שרת זמנית של Gemini (500/503). מנסה מודל חלופי...'
            };
        }

        return {
            code: 'unknown',
            retryNextModel: true,
            userMessage: message || `Gemini request failed (${status}).`
        };
    }

    function delay(ms) {
        return new Promise((resolve) => setTimeout(resolve, ms));
    }

    function computeRetryDelayMs(response, retryCount) {
        const retryAfter = response.headers.get('Retry-After');
        if (retryAfter) {
            const asSeconds = Number(retryAfter);
            if (Number.isFinite(asSeconds) && asSeconds > 0) {
                return Math.min(asSeconds * 1000, GEMINI_CONFIG.maxRetryDelayMs);
            }

            const asDate = Date.parse(retryAfter);
            if (!Number.isNaN(asDate)) {
                const delta = asDate - Date.now();
                if (delta > 0) {
                    return Math.min(delta, GEMINI_CONFIG.maxRetryDelayMs);
                }
            }
        }

        const exponential = GEMINI_CONFIG.initialRetryDelayMs * (2 ** retryCount);
        const jitter = Math.floor(Math.random() * 500);
        return Math.min(exponential + jitter, GEMINI_CONFIG.maxRetryDelayMs);
    }

    async function callGeminiOcr(apiKey, imageDatas) {
        const prompt = [
            'You are an expert exam parser for Hebrew multiple-choice exams.',
            'Extract all multiple-choice questions into a clean JSON array of objects.',
            'JSON Schema per object:',
            '  - "question": string (full question text in natural Hebrew reading order)',
            '  - "options": array of strings (all answer choices, stripping option letter prefixes like "א." or "ב.")',
            '  - "correctIndex": number (0 by default)',
            '  - "sourcePage": number (1-based physical page number)',
            '',
            'Rules:',
            '1. Do NOT reverse Hebrew word or letter order.',
            '2. Ensure mixed Hebrew and English/scientific terms (e.g. "ATP", "pH", "DNA") read correctly.',
            '3. Extract all options into the options array (questions can have 4, 5, 6 or more choices).',
            '4. Output ONLY valid JSON array.'
        ].join('\n');
        const attemptErrors = [];
        const candidates = await discoverGeminiModelCandidates(apiKey);

        const parts = [{ text: prompt }];
        for (const data of imageDatas) {
            parts.push({ inlineData: { mimeType: 'image/png', data } });
        }

        const sortedCandidates = sortGeminiModelCandidates(candidates);

        for (const candidate of sortedCandidates) {
            const endpoint = buildGeminiEndpoint(candidate.version, candidate.model, apiKey);

            for (let retryCount = 0; retryCount <= GEMINI_CONFIG.maxQuotaRetries; retryCount++) {
                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        contents: [{ parts }],
                        generationConfig: {
                            temperature: 0,
                            topP: 0.1,
                            maxOutputTokens: 16384,
                            responseMimeType: "application/json"
                        }
                    })
                });

                if (response.ok) {
                    const payload = await response.json();
                    const responseParts = payload.candidates?.[0]?.content?.parts || [];
                    const text = responseParts.map((part) => part.text || '').join('\n').trim();
                    if (!text) {
                        const finishReason = payload.candidates?.[0]?.finishReason || 'UNKNOWN';
                        const promptFeedback = payload.promptFeedback?.blockReason || 'NONE';
                        throw new Error(`Gemini returned empty OCR text. Finish Reason: ${finishReason}, Prompt Blocked: ${promptFeedback}. Raw: ${JSON.stringify(payload)}`);
                    }
                    // The OCR prompt requests a JSON array (responseMimeType: "application/json"),
                    // so Gemini never emits PAGE_BOUNDARY separators. Return the full response
                    // as a single element; the caller joins all chunks before parseQuestionsFromText
                    // which handles JSON-first parsing.
                    return [text];
                }

                const errorText = await response.text();
                const errorInfo = getGeminiErrorInfo(response.status, errorText);

                if (errorInfo.code === 'quota' && retryCount < GEMINI_CONFIG.maxQuotaRetries) {
                    const delayMs = computeRetryDelayMs(response, retryCount);
                    setStatus(`Gemini החזיר 429. ממתין ${Math.ceil(delayMs / 1000)} שניות ומנסה שוב...`);
                    await delay(delayMs);
                    continue;
                }

                attemptErrors.push(`[${candidate.version}/${candidate.model}] ${response.status} ${errorInfo.userMessage}`);

                if (errorInfo.retryNextModel) {
                    break;
                }

                throw new Error(`Gemini request failed: ${errorInfo.userMessage}`);
            }
        }

        throw new Error(`Gemini request failed: לא נמצא מודל Gemini נתמך. ${attemptErrors.join(' | ')}`);
    }

    async function extractTextViaGemini(pdf, apiKey, chunkSizeOverride = null) {
        if (!apiKey) {
            throw new Error('ה-PDF נראה סרוק ואין מפתח Gemini זמין לחילוץ טקסט. הזן API key או Passcode תקין.');
        }

        const pages = [];
        const { imageDatas, pagePreviews } = await renderAllPdfPageImages(pdf);

        const CHUNK_SIZE = Math.max(1, Number(chunkSizeOverride || GEMINI_CONFIG.ocrChunkSize) || 1);
        for (let i = 0; i < imageDatas.length; i += CHUNK_SIZE) {
            const chunk = imageDatas.slice(i, i + CHUNK_SIZE);
            setStatus(`מפענח עמודים ${i + 1}-${Math.min(i + CHUNK_SIZE, imageDatas.length)} מתוך ${imageDatas.length} ב-Gemini...`);

            const chunkPagesText = await callGeminiOcr(apiKey, chunk);
            pages.push(...chunkPagesText.map((pageText) => maybeFixHebrewWordOrder(pageText || '')));

            if (i + CHUNK_SIZE < imageDatas.length && GEMINI_CONFIG.interPageDelayMs > 0) {
                await delay(GEMINI_CONFIG.interPageDelayMs);
            }
        }

        return {
            pages,
            pagePreviews,
            text: pages.join('\n')
        };
    }


    async function extractTextViaGeminiNativePdf(pdfFile, pdf, apiKey, mode = 'schema') {
        if (!apiKey) {
            throw new Error('ה-PDF נראה סרוק ואין מפתח Gemini זמין לחילוץ טקסט. הזן API key או Passcode תקין.');
        }

        setStatus('מעלה את מסמך ה-PDF ישירות ל-Gemini (Native PDF)...');

        const base64Pdf = await fileToBase64(pdfFile);
        const prompt = [
            'You are an expert exam parser for Hebrew multiple-choice exams.',
            'Extract all multiple-choice questions into a clean JSON array of objects.',
            'Rules:',
            '1. Do NOT reverse Hebrew word or letter order.',
            '2. Ensure mixed Hebrew and English/scientific terms (e.g. "ATP", "pH", "DNA") read correctly.',
            '3. Extract all options into the options array (questions can have 4, 5, 6 or more choices).',
            '4. Set "sourcePage" to 1-based physical page number.',
            '5. Set "hasVisualElement" to true if the question references a diagram, graph, chart, table, or figure.',
            '6. Output ONLY valid JSON array.'
        ].join('\n');

        const generationConfig = {
            temperature: 0,
            topP: 0.1,
            maxOutputTokens: 16384,
            responseMimeType: "application/json"
        };

        if (mode === 'schema') {
            generationConfig.responseSchema = {
                type: "ARRAY",
                items: {
                    type: "OBJECT",
                    properties: {
                        question: { type: "STRING" },
                        options: {
                            type: "ARRAY",
                            items: { type: "STRING" }
                        },
                        sourcePage: { type: "INTEGER" },
                        hasVisualElement: { type: "BOOLEAN" }
                    },
                    required: ["question", "options", "sourcePage"]
                }
            };
        }

        const attemptErrors = [];
        const candidates = await discoverGeminiModelCandidates(apiKey);
        const sortedCandidates = sortGeminiModelCandidates(candidates);
        let extractedPages = null;

        for (const candidate of sortedCandidates) {
            const endpoint = buildGeminiEndpoint(candidate.version, candidate.model, apiKey);

            for (let retryCount = 0; retryCount <= GEMINI_CONFIG.maxQuotaRetries; retryCount++) {
                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        contents: [{
                            parts: [
                                { text: prompt },
                                { inlineData: { mimeType: 'application/pdf', data: base64Pdf } }
                            ]
                        }],
                        generationConfig
                    })
                });

                if (response.ok) {
                    const payload = await response.json();
                    const responseParts = payload.candidates?.[0]?.content?.parts || [];
                    const text = responseParts.map((part) => part.text || '').join('\n').trim();

                    if (!text) {
                        const finishReason = payload.candidates?.[0]?.finishReason || 'UNKNOWN';
                        throw new Error(`Gemini returned empty OCR text. Finish Reason: ${finishReason}`);
                    }

                    extractedPages = text.split(/---PAGE_BOUNDARY---/i).map((s) => s.trim());
                    break;
                }

                const errorText = await response.text();
                const errorInfo = getGeminiErrorInfo(response.status, errorText);

                if (errorInfo.code === 'quota' && retryCount < GEMINI_CONFIG.maxQuotaRetries) {
                    const delayMs = computeRetryDelayMs(response, retryCount);
                    setStatus(`Gemini החזיר 429 ב-Native PDF (${candidate.model}). ממתין ${Math.ceil(delayMs / 1000)} שניות ומנסה שוב...`);
                    await delay(delayMs);
                    continue;
                }

                attemptErrors.push(`[${candidate.version}/${candidate.model}] ${response.status} ${errorInfo.userMessage}`);

                if (errorInfo.retryNextModel) {
                    break;
                }

                throw new Error(`Gemini Native PDF OCR failed: ${errorInfo.userMessage}`);
            }

            if (extractedPages) {
                break;
            }
        }

        if (!extractedPages) {
            throw new Error(`Gemini Native PDF OCR failed: לא נמצא מודל Gemini נתמך. ${attemptErrors.join(' | ')}`);
        }

        // Generate previews for proof mode
        const pagePreviews = [];
        for (let pageNumber = 1; pageNumber <= pdf.numPages; pageNumber++) {
            setStatus(`מכין תצוגות מקדימות לעמוד ${pageNumber}/${pdf.numPages}...`);
            const page = await pdf.getPage(pageNumber);
            const imageData = await renderPageImageData(page);
            pagePreviews.push(`data:image/png;base64,${imageData}`);
        }

        return {
            pages: extractedPages.map(p => maybeFixHebrewWordOrder(p || '')),
            pagePreviews,
            text: extractedPages.join('\n')
        };
    }


    async function verifyTestWithGemini(parsedQuestions, apiKey) {
        setStatus('מבצע הגהה ותיקון של המבחן עם Gemini...');
        const prompt = [
            'You are an expert exam proofreader.',
            'I am providing you with a JSON array of parsed exam questions extracted via OCR.',
            'Your task is to verify and fix the JSON:',
            '1. Fix any OCR typos in the Hebrew text.',
            '2. Ensure options are logically separated and not truncated.',
            '3. Maintain the exact JSON schema provided.',
            '4. Return ONLY the raw JSON array, without any markdown formatting or code blocks.',
            '',
            'JSON:',
            JSON.stringify(parsedQuestions, null, 2)
        ].join('\n');

        const candidates = await discoverGeminiModelCandidates(apiKey);
        const sortedCandidates = sortGeminiModelCandidates(candidates);

        for (const candidate of sortedCandidates) {
            const endpoint = buildGeminiEndpoint(candidate.version, candidate.model, apiKey);
            try {
                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        contents: [{ parts: [{ text: prompt }] }],
                        generationConfig: {
                            temperature: 0.1,
                            topP: 0.8,
                            maxOutputTokens: 8192
                        }
                    })
                });

                if (!response.ok) continue;

                const payload = await response.json();
                const responseParts = payload.candidates?.[0]?.content?.parts || [];
                let text = responseParts.map((part) => part.text || '').join('\n').trim();

                text = text.replace(/^```json\s*/i, '').replace(/```\s*$/i, '').trim();

                const verified = JSON.parse(text);
                if (Array.isArray(verified) && verified.length > 0 && verified[0].question) {
                    return verified;
                }
            } catch (e) {
                console.warn(`Gemini verification failed for model ${candidate.model}:`, e);
            }
        }

        return parsedQuestions;
    }

    function parseQuestionsFromMarkdown(markdownText) {
        if (!markdownText) return [];

        let cleanText = String(markdownText).trim();
        cleanText = cleanText.replace(/^```(?:markdown|md|txt)?\s*/i, '').replace(/\s*```$/i, '').trim();
        if (!cleanText) return [];

        const lines = cleanText.split(/\r?\n/);
        const headerRe = /^###\s*שאלה\s*(\d{1,3})\s*:\s*(.+?)\s*(?:\((?:עמוד|עמ'|page)\s*(\d{1,3})\))?\s*$/i;
        const optionRe = /^[-*+]\s*([אבגדהוזחטי])\.\s*(.+)$/;

        const parsed = [];
        let current = null;

        function pushCurrentIfValid() {
            if (!current) return;
            const questionText = normalizeWhitespace(String(current.question || ''));
            const options = (current.options || []).map((opt) => normalizeWhitespace(String(opt || ''))).filter(Boolean);
            if (questionText && options.length >= 2) {
                parsed.push({
                    question: questionText,
                    options,
                    correctIndex: 0,
                    sourcePage: current.sourcePage || 1
                });
            }
        }

        for (const rawLine of lines) {
            const line = String(rawLine || '').trim();
            if (!line) continue;

            const headerMatch = line.match(headerRe);
            if (headerMatch) {
                pushCurrentIfValid();
                current = {
                    question: normalizeWhitespace(headerMatch[2] || ''),
                    options: [],
                    sourcePage: Number(headerMatch[3]) || 1
                };
                continue;
            }

            if (!current) continue;

            const optionMatch = line.match(optionRe);
            if (optionMatch) {
                current.options.push(optionMatch[2] || '');
                continue;
            }

            if (current.options.length > 0) {
                const lastIdx = current.options.length - 1;
                current.options[lastIdx] = `${current.options[lastIdx]} ${line}`.trim();
            } else {
                current.question = `${current.question} ${line}`.trim();
            }
        }

        pushCurrentIfValid();
        return parsed;
    }

    function parseQuestionsFromText(text, rawPages, pageImages) {
        if (!text) return [];

        let cleanText = text.trim();
        cleanText = cleanText.replace(/^```(?:markdown|md|json|txt)?\s*/i, '').replace(/\s*```$/i, '').trim();

        if (cleanText.startsWith('[') || cleanText.startsWith('{')) {
            try {
                const parsed = JSON.parse(cleanText);
                const questionsArray = Array.isArray(parsed) ? parsed : (parsed.questions || parsed.data);
                if (Array.isArray(questionsArray) && questionsArray.length > 0) {
                    return normalizeQuestionsJson(questionsArray);
                }
            } catch (e) {
                console.warn('JSON parse attempt failed, falling back to line-by-line parser:', e);
            }
        }

        const lines = cleanText.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
        // Build linePageMap from the same processed text that lines[] comes from.
        // We apply fixHebrewWordOrder per page and count non-empty lines to match the filter(Boolean).
        const filteredLinePageMap = [];
        if (rawPages && rawPages.length) {
            rawPages.forEach((pageText, pageIdx) => {
                const processedLines = maybeFixHebrewWordOrder(pageText || '')
                    .split('\n')
                    .map(l => l.trim())
                    .filter(Boolean);
                for (let i = 0; i < processedLines.length; i++) {
                    filteredLinePageMap.push(pageIdx);
                }
            });
        }
        const qPatternTextual = /(?:^#*\s*(?:\*\*)?שאלה\s+(?:מספר\s*)?:?\s*:?\d+\s*:?|^#*\s*(?:\*\*)?:?\d+\s*:?\s*מספר\s+שאלה)/i;
        const qPatternNumeric = /(?:^\.?\s*#*\s*(?:\*\*)?\s*[\(\[]?\s*:?\d+\s*[\.\)\(\-\]]?\s+(?![אבגדהוזחטי]\s*$))/i;
        const qNumericCapture = /^\.?\s*#*\s*(?:\*\*)?\s*[\(\[]?\s*:?\s*(\d{1,3})\s*[\.\)\(\-\]]?\s+/i;
        // Matches: '- א. text', '- **א.** text', '* א. text', '(א) text', 'א. text', '1. text', 'א . text'
        const ansPatternStart = /^(?:[-\*\+\u2022]\s*)?(?:\*\*)?[\(\[]?([אבגדהוזחטיa-e1-9])\s*[\)\]\.]\s*(?:\*\*)?\s*(.*)$|^[\.]\s*([אבגדהוזחטי])\s*(.*)$/i;
        // Matches: 'text א.' or 'text .א' at end of line
        const ansPatternEnd = /^(.*)\s+([אבגדהוזחטי1-9])\s*[\.\)]$|^(.*)\s+[\.]\s*([אבגדהוזחטי])$/;
        const ansInlineGlobal = /(?:^|[\s\u2022\-\*\+\(\[])([אבגדהוזחטי])\s*[\.\)]\s*/g;
        const noisePattern = /^עמוד\s+\d+\s+מתוך\s+\d+$/;
        const footerPattern = /^-+\s*סוף\s+המבחן\s*-+$/;
        const qInlineLocator = /\s(#*\s*(?:שאלה\s+(?:מספר\s*)?:?\s*:?\d+\s*:?|[\(\[]?\s*:??\d+\s*[\)\(\.-\]]?)\s+)/i;
        const hebOptionOrder = { 'א': 1, 'ב': 2, 'ג': 3, 'ד': 4, 'ה': 5, 'ו': 6, 'ז': 7, 'ח': 8, 'ט': 9 };

        function parseInlineAnswers(lineText) {
            if (!lineText) return null;

            const matches = [];
            ansInlineGlobal.lastIndex = 0;
            let m;
            while ((m = ansInlineGlobal.exec(lineText)) !== null) {
                matches.push({
                    letter: m[1],
                    markerStart: m.index,
                    textStart: ansInlineGlobal.lastIndex
                });
            }

            if (!matches.length) return null;

            const prefix = lineText.slice(0, matches[0].markerStart).trim();
            const hasOnlyTrivialPrefix = /^[-\*\+\u2022\(\[\]\)\.:\s]*$/.test(prefix);

            // For regular lines like "- א. ..." or "א. ...", keep the standard
            // answer parser path and only use inline parsing for genuine merged
            // multi-option lines.
            if (matches.length < 2 && hasOnlyTrivialPrefix) {
                return null;
            }

            if (matches.length >= 2) {
                // Accept only plausible option letter progression (א->ב->ג->ד...).
                let prevOrder = 0;
                let jumps = 0;
                for (const mm of matches) {
                    const ord = hebOptionOrder[mm.letter] || 0;
                    if (!ord) return null;
                    if (prevOrder > 0) {
                        const delta = ord - prevOrder;
                        if (delta <= 0) return null;
                        if (delta > 2) jumps++;
                    }
                    prevOrder = ord;
                }
                if (jumps > 0) return null;
            }

            const options = [];
            for (let k = 0; k < matches.length; k++) {
                const cur = matches[k];
                const next = matches[k + 1];
                const textEnd = next ? next.markerStart : lineText.length;
                const optionText = lineText.slice(cur.textStart, textEnd).trim();
                options.push({ letter: cur.letter, text: optionText });
            }

            // One inline marker with no meaningful prefix is still a normal answer line.
            if (options.length === 1 && !prefix) {
                return null;
            }

            return { prefix, options };
        }

        function splitInlineQuestionHeader(lineText) {
            if (!lineText) return null;
            const m = lineText.match(qInlineLocator);
            if (!m || typeof m.index !== 'number') return null;
            const markerStart = m.index + 1; // skip the leading whitespace in regex
            if (markerStart <= 0 || markerStart >= lineText.length) return null;
            return {
                before: lineText.slice(0, markerStart).trim(),
                after: lineText.slice(markerStart).trim()
            };
        }

        function splitAnswerLineWithEmbeddedHeader(lineText) {
            if (!lineText) return null;
            const ansStart = lineText.match(/^(\s*(?:[-\*\+\u2022]\s*)?[אבגדהוזחטי]\s*[\.)]\s*)(.*)$/);
            if (!ansStart) return null;

            const prefix = ansStart[1] || '';
            const body = (ansStart[2] || '').trim();
            if (!body) return null;

            const headerTailRe1 = /([\?？][^\n]*[\)\(]\s*\d{1,3}\s*)$/;
            const headerTailRe2 = /((?:על\s+פי|מהו|מה\s+יהיה|איזו|ממה|מטעמי|הינך|היכן|כיצד)[^\n]*[\)\(]\s*\d{1,3}\s*)$/;
            const m = body.match(headerTailRe1) || body.match(headerTailRe2);
            if (!m) return null;

            const headerPart = (m[1] || '').trim();
            if (!headerPart || headerPart.length < 8) return null;

            const cutIdx = body.lastIndexOf(headerPart);
            if (cutIdx <= 0) return null;

            const optionPart = body.slice(0, cutIdx).trim();
            if (!optionPart) return null;

            let optionClean = optionPart;
            let headerRaw = headerPart;

            // If OCR placed part of the next question before the numeric marker,
            // move suffix from last question-mark into the header fragment.
            const qMarkIdx = optionClean.lastIndexOf('?');
            if (qMarkIdx > 0 && (optionClean.length - qMarkIdx) <= 120) {
                headerRaw = `${optionClean.slice(qMarkIdx).trim()} ${headerRaw}`.trim();
                optionClean = optionClean.slice(0, qMarkIdx).trim();
            }

            if (!optionClean) return null;

            let normalizedHeader = headerRaw;
            if (!extractNumericHeaderNumber(normalizedHeader)) {
                const rev = normalizedHeader.split(/\s+/).reverse().join(' ');
                if (extractNumericHeaderNumber(rev) || qPatternNumeric.test(rev) || qPatternTextual.test(rev)) {
                    normalizedHeader = rev;
                }
            }

            return {
                optionLine: `${prefix}${optionClean}`.trim(),
                headerLine: normalizedHeader
            };
        }

        function preprocessEmbeddedHeaders(inputLines) {
            const out = [];
            const source = [];
            for (let i = 0; i < inputLines.length; i++) {
                const line = String(inputLines[i] || '').trim();
                if (!line) continue;
                const split = splitAnswerLineWithEmbeddedHeader(line);
                if (split) {
                    if (split.optionLine) {
                        out.push(split.optionLine.trim());
                        source.push(i);
                    }
                    if (split.headerLine) {
                        out.push(split.headerLine.trim());
                        source.push(i);
                    }
                } else {
                    out.push(line);
                    source.push(i);
                }
            }
            return { lines: out, sourceIdx: source };
        }

        function normalizeEmbeddedHeaderText(headerText) {
            let t = normalizeWhitespace(String(headerText || ''));
            t = t.replace(/^[:\-–—\s]+/, '').trim();

            let m = t.match(/^(.*?)[\)\(]\s*(\d{1,3})\s*$/);
            if (m) {
                return normalizeWhitespace(`${m[2]}) ${m[1].trim()}`);
            }

            m = t.match(/^(.*?)(\d{1,3})\s*\)\s*$/);
            if (m) {
                return normalizeWhitespace(`${m[2]}) ${m[1].trim()}`);
            }

            m = t.match(/^(.*?)(\d{1,2})\s+(\d{1,2})\s*\)\s*$/);
            if (m) {
                return normalizeWhitespace(`${m[2]}${m[3]}) ${m[1].trim()}`);
            }

            return t;
        }

        function extractEmbeddedHeaderFromOptionText(optionText) {
            const t = normalizeWhitespace(String(optionText || ''));
            if (!t) return null;

            const cueWords = /(?:על\s+פי|מהו|מה\s+יהיה|איזו|ממה|מטעמי|הינך|היכן|כיצד|מהם|מה\s+החשיבות|איזה\s+מערכת)/;
            const numberMarkers = /(?:\)\s*\d{1,3}|\d{1,3}\s*\)|\d{1,2}\s+\d{1,2}\s*\))/g;

            // 1) Prefer tail-like splits from a numeric marker through the end.
            let marker;
            while ((marker = numberMarkers.exec(t)) !== null) {
                const start = marker.index;
                const before = normalizeWhitespace(t.slice(0, start));
                const after = normalizeWhitespace(t.slice(start));
                if (!before || !after || after.length < 8) continue;
                if (!/[\?？]/.test(after) && !cueWords.test(after)) continue;
                const header = normalizeEmbeddedHeaderText(after);
                if (!header) continue;
                return { before, header };
            }

            // 2) Fallback: split before cue words when they appear after a marker.
            const cueMatch = t.match(/(?:על\s+פי|מהו|מה\s+יהיה|איזו|ממה|מטעמי|הינך|היכן|כיצד|מהם|מה\s+החשיבות|איזה\s+מערכת)/);
            if (cueMatch && typeof cueMatch.index === 'number' && cueMatch.index > 4) {
                const before = normalizeWhitespace(t.slice(0, cueMatch.index));
                const after = normalizeWhitespace(t.slice(cueMatch.index));
                if (before && after && /(?:\)\s*\d{1,3}|\d{1,3}\s*\)|\d{1,2}\s+\d{1,2}\s*\))/.test(after)) {
                    const header = normalizeEmbeddedHeaderText(after);
                    if (header) return { before, header };
                }
            }

            return null;
        }

        function splitMergedQuestions(rawQs) {
            const out = [];

            for (const q of rawQs) {
                if (!q || !Array.isArray(q.answers) || q.answers.length <= 6) {
                    out.push(q);
                    continue;
                }

                let current = {
                    text: Array.isArray(q.text) ? [...q.text] : [String(q.text || '')],
                    answers: [],
                    lineIdx: q.lineIdx
                };

                for (const a of q.answers) {
                    const optionText = normalizeWhitespace(Array.isArray(a.text) ? a.text.join(' ') : String(a.text || ''));
                    const split = extractEmbeddedHeaderFromOptionText(optionText);

                    if (split) {
                        current.answers.push({ text: [split.before] });
                        out.push(current);
                        current = {
                            text: [split.header],
                            answers: [],
                            lineIdx: q.lineIdx
                        };
                    } else {
                        current.answers.push({ text: optionText ? [optionText] : [] });
                    }
                }

                if (current.text.length || current.answers.length) {
                    out.push(current);
                }
            }

            return out;
        }

        function splitCorruptedMergedOptions(rawQs) {
            const out = [];

            for (const q of rawQs) {
                if (!q || !Array.isArray(q.answers)) {
                    out.push(q);
                    continue;
                }

                const nextAnswers = [];
                for (const a of q.answers) {
                    const t = normalizeWhitespace(Array.isArray(a.text) ? a.text.join(' ') : String(a.text || ''));
                    const m = t.match(/^(.*?[\.!?])\s*\.?\s*\d+\s+(.+?)\s*[\.]\s*([אבגדהוזחטי])\s*$/);
                    if (m) {
                        const first = normalizeWhitespace(m[1]);
                        const second = normalizeWhitespace(m[2]);
                        if (first) nextAnswers.push({ text: [first] });
                        if (second) nextAnswers.push({ text: [second] });
                    } else {
                        nextAnswers.push({ text: t ? [t] : [] });
                    }
                }

                out.push({ ...q, answers: nextAnswers });
            }

            return out;
        }

        function expandInlineQuestionLines(inputLines) {
            const expanded = [];
            const sourceIdx = [];

            for (let i = 0; i < inputLines.length; i++) {
                const original = String(inputLines[i] || '').trim();
                if (!original) continue;

                const embeddedSplit = splitAnswerLineWithEmbeddedHeader(original);
                if (embeddedSplit) {
                    const first = embeddedSplit.optionLine.trim();
                    const second = embeddedSplit.headerLine.trim();
                    if (first) {
                        expanded.push(first);
                        sourceIdx.push(i);
                    }
                    if (second) {
                        expanded.push(second);
                        sourceIdx.push(i);
                    }
                    continue;
                }

                let segment = original;
                let guard = 0;

                while (segment && guard < 6) {
                    guard++;
                    const split = splitInlineQuestionHeader(segment);
                    if (!split || !split.after) {
                        expanded.push(segment.trim());
                        sourceIdx.push(i);
                        break;
                    }

                    const splitRev = split.after.split(/\s+/).reverse().join(' ');
                    const splitIsHeader = qPatternTextual.test(split.after) || qPatternNumeric.test(split.after)
                        || qPatternTextual.test(splitRev) || qPatternNumeric.test(splitRev);

                    if (!splitIsHeader) {
                        expanded.push(segment.trim());
                        sourceIdx.push(i);
                        break;
                    }

                    if (split.before) {
                        expanded.push(split.before.trim());
                        sourceIdx.push(i);
                    }

                    segment = split.after.trim();
                }
            }

            return { expanded, sourceIdx };
        }

        function extractNumericHeaderNumber(lineText) {
            if (!lineText) return null;
            const m = lineText.match(qNumericCapture);
            if (!m) return null;
            const n = Number(m[1]);
            return Number.isFinite(n) ? n : null;
        }

        function buildStrictNumericBlocks(inputLines) {
            const strictHeaderRe = /^\s*(\d{1,3})\s*[\(\)\.\-]\s*/;
            const optionStartRe = /^(?:[-\*\+\u2022]\s*)?([אבגדהוזחטי])\s*[\.)]\s*(.*)$/;

            const headers = [];
            for (let i = 0; i < inputLines.length; i++) {
                const line = String(inputLines[i] || '').trim();
                if (!line) continue;
                const m = line.match(strictHeaderRe);
                if (m) {
                    headers.push({ idx: i, num: Number(m[1]) });
                }
            }

            if (headers.length < 12) {
                return null;
            }

            let sequentialHits = 0;
            for (let i = 1; i < headers.length; i++) {
                const d = headers[i].num - headers[i - 1].num;
                if (d === 1 || d === 2) sequentialHits++;
            }
            const sequentialRatio = headers.length > 1 ? (sequentialHits / (headers.length - 1)) : 0;
            if (sequentialRatio < 0.65) {
                return null;
            }

            const out = [];
            for (let h = 0; h < headers.length; h++) {
                const start = headers[h].idx;
                const end = h + 1 < headers.length ? headers[h + 1].idx : inputLines.length;
                const block = inputLines.slice(start, end).map((l) => String(l || '').trim()).filter(Boolean);
                if (!block.length) continue;

                const qObj = { text: [block[0]], answers: [], lineIdx: start };
                for (let bi = 1; bi < block.length; bi++) {
                    const line = block[bi];
                    const m = line.match(optionStartRe);
                    if (m) {
                        const t = (m[2] || '').trim();
                        qObj.answers.push({ text: t ? [t] : [] });
                        continue;
                    }

                    if (qObj.answers.length > 0) {
                        qObj.answers[qObj.answers.length - 1].text.push(line);
                    } else {
                        qObj.text.push(line);
                    }
                }

                out.push(qObj);
            }

            return out;
        }

        function detectQuestionHeaderNumber(lineText) {
            if (!lineText) return null;
            const textual = lineText.match(/שאלה(?:\s+מספר)?\s*:?[\s:]*?(\d{1,3})/i);
            if (textual) {
                const n = Number(textual[1]);
                if (Number.isFinite(n)) return n;
            }
            return extractNumericHeaderNumber(lineText);
        }

        const preprocessed = preprocessEmbeddedHeaders(lines);
        const baseLines = preprocessed.lines;
        const baseSourceIdx = preprocessed.sourceIdx;

        const strictBlocks = buildStrictNumericBlocks(baseLines);
        const useStrictNumericMode = Array.isArray(strictBlocks) && strictBlocks.length >= 20;
        const { expanded: workingLines, sourceIdx: workingLineSourceIdx } = useStrictNumericMode
            ? { expanded: baseLines, sourceIdx: baseSourceIdx }
            : expandInlineQuestionLines(baseLines);

        const rawQuestions = [];
        const headerIndices = [];

        if (useStrictNumericMode) {
            rawQuestions.push(...strictBlocks);
        } else {

        let lastHeaderNum = null;
        for (let i = 0; i < workingLines.length; i++) {
            const line = workingLines[i];
            if (!line || noisePattern.test(line) || line.includes('קוד מבחן') || line.includes("מבחן מס") || line.includes('מבחן מס')) {
                continue;
            }
            const reversedLine = line.split(/\s+/).reverse().join(' ');
            if (footerPattern.test(line) || footerPattern.test(reversedLine)) {
                continue;
            }
            const textualHeader = qPatternTextual.test(line) || qPatternTextual.test(reversedLine);
            const directNumeric = extractNumericHeaderNumber(line);
            const reverseNumeric = extractNumericHeaderNumber(reversedLine);

            let numericCandidate = directNumeric;
            if (!Number.isFinite(numericCandidate) && Number.isFinite(reverseNumeric)) {
                numericCandidate = reverseNumeric;
            }

            let numericHeader = false;
            if (Number.isFinite(numericCandidate) && numericCandidate >= 1 && numericCandidate <= 300) {
                if (!Number.isFinite(lastHeaderNum)) {
                    numericHeader = numericCandidate <= 80;
                } else {
                    const delta = numericCandidate - lastHeaderNum;
                    numericHeader = delta === 1 || delta === 2;
                }
            }

            const isQuestionHeader = textualHeader || numericHeader;
            if (isQuestionHeader) {
                headerIndices.push(i);
                const detectedNum = detectQuestionHeaderNumber(line) || detectQuestionHeaderNumber(reversedLine);
                if (Number.isFinite(detectedNum)) {
                    lastHeaderNum = detectedNum;
                }
            }
        }

        for (let h = 0; h < headerIndices.length; h++) {
            const startIdx = headerIndices[h];
            const endIdx = h + 1 < headerIndices.length ? headerIndices[h + 1] : workingLines.length;
            const blockLines = workingLines.slice(startIdx, endIdx);
            if (!blockLines.length) continue;

            const q = {
                text: [blockLines[0]],
                answers: [],
                lineIdx: Number.isInteger(workingLineSourceIdx[startIdx]) ? workingLineSourceIdx[startIdx] : startIdx
            };

            for (let bi = 1; bi < blockLines.length; bi++) {
                let line = blockLines[bi];
                if (!line || noisePattern.test(line) || line.includes('קוד מבחן') || line.includes("מבחן מס") || line.includes('מבחן מס')) {
                    continue;
                }

                const reversedLine = line.split(/\s+/).reverse().join(' ');
                if (footerPattern.test(line) || footerPattern.test(reversedLine)) {
                    continue;
                }

                // Within block parser, still guard for accidental inline next question.
                const qSplit = splitInlineQuestionHeader(line);
                const qSplitReversed = qSplit && qSplit.after ? qSplit.after.split(/\s+/).reverse().join(' ') : '';
                const qSplitIsHeader = qSplit && qSplit.after && (
                    qPatternTextual.test(qSplit.after)
                    || qPatternTextual.test(qSplitReversed)
                    || qPatternNumeric.test(qSplit.after)
                    || qPatternNumeric.test(qSplitReversed)
                );
                if (qSplitIsHeader) {
                    if (qSplit.before) {
                        if (q.answers.length > 0) {
                            q.answers[q.answers.length - 1].text.push(qSplit.before);
                        } else {
                            q.text.push(qSplit.before);
                        }
                    }
                    break;
                }

                const inlineParsed = parseInlineAnswers(line);
                if (inlineParsed && inlineParsed.options.length) {
                    if (inlineParsed.prefix) {
                        if (q.answers.length > 0) {
                            q.answers[q.answers.length - 1].text.push(inlineParsed.prefix);
                        } else {
                            q.text.push(inlineParsed.prefix);
                        }
                    }
                    for (const opt of inlineParsed.options) {
                        q.answers.push({ text: opt.text ? [opt.text] : [] });
                    }
                    continue;
                }

                const isLineStartMatch = ansPatternStart.test(line);
                let match = line.match(ansPatternStart) || reversedLine.match(ansPatternStart);
                const isLineEndMatch = !match && ansPatternEnd.test(line);
                let endMatch = (!match) && (line.match(ansPatternEnd) || reversedLine.match(ansPatternEnd));

                if (match || endMatch) {
                    let letter, answerText;
                    if (match) {
                        letter = match[1] || match[3] || match[5];
                        answerText = (match[2] || match[4] || match[6] || '').trim();
                        if (!isLineStartMatch && answerText) {
                            answerText = answerText.split(/\s+/).reverse().join(' ');
                        }
                    } else {
                        letter = endMatch[2] || endMatch[4];
                        answerText = (endMatch[1] || endMatch[3] || '').trim();
                        if (!isLineEndMatch && answerText) {
                            answerText = answerText.split(/\s+/).reverse().join(' ');
                        }
                    }

                    if (letter) {
                        q.answers.push({ text: answerText ? [answerText] : [] });
                    }
                    continue;
                }

                if (q.answers.length > 0) {
                    q.answers[q.answers.length - 1].text.push(line);
                } else {
                    q.text.push(line);
                }
            }

            rawQuestions.push(q);
        }
        }

        const normalizedRawQuestions = splitCorruptedMergedOptions(splitMergedQuestions(rawQuestions));

        const imageKeywords = /(?:^|[\s\(\[\:\,"\'-])(?:לפניכם|לפניך|גרף|הגרף|תרשים|התרשים|תמונה|התמונה|טבלה|הטבלה|איור|האיור|מפה|המפה|דיאגרמה|הדיאגרמה|צילום|סכמה|הסכמה|שרטוט|עקומה|עקומות|מוצג|המוצג|במוצג|באיור|בגרף|בטבלה|בתרשים)(?:$|[\s\)\.\:\,\?\!\"'-])/i;

        const diagnostics = [];
        const formatted = normalizedRawQuestions
            .map((q, idx) => {
                let rawQuestionText = normalizeWhitespace(stripExamFooterArtifacts(q.text.join(' ')));
                // Clean leading Markdown heading syntax & question header prefixes (e.g. ### שאלה 1:, שאלה מספר :1)
                rawQuestionText = stripQuestionHeaderPrefix(rawQuestionText);

                const mappedPageIdx = filteredLinePageMap[q.lineIdx];
                let pageIdx = Number.isInteger(mappedPageIdx) ? mappedPageIdx : 0;
                const pageMatch = rawQuestionText.match(/\((?:עמוד|עמ'|page)\s*(\d+)\)/i);
                // Inline markers like "(עמוד 2)" are often logical-section pages, not
                // physical PDF pages. Use them only when no line-to-page mapping exists.
                if (pageMatch && !Number.isInteger(mappedPageIdx)) {
                    pageIdx = Math.max(0, parseInt(pageMatch[1], 10) - 1);
                }
                const cleanQuestionText = stripQuestionHeaderPrefix(rawQuestionText.replace(/\s*\((?:עמוד|עמ'|page)\s*\d+\)$/i, '')).trim();

                const options = q.answers
                    .map((a) => normalizeWhitespace(stripExamFooterArtifacts(a.text.join(' '))))
                    .filter(Boolean);

                const obj = { question: cleanQuestionText, options, correctIndex: 0, sourcePage: pageIdx + 1 };

                if (imageKeywords.test(cleanQuestionText)) {
                    if (pageImages && pageIdx >= 0 && pageIdx < pageImages.length && pageImages[pageIdx]) {
                        obj.image = pageImages[pageIdx];
                    }
                    obj._needsPageRender = true;
                }

                if (!cleanQuestionText || options.length < 2) {
                    diagnostics.push({
                        index: idx + 1,
                        sourcePage: pageIdx + 1,
                        lineIdx: q.lineIdx,
                        questionPreview: cleanQuestionText.slice(0, 80),
                        optionCount: options.length,
                        dropReason: !cleanQuestionText ? 'empty-question' : 'insufficient-options'
                    });
                }

                return obj;
            })
            .filter((q) => q.question && q.options.length >= 2);

        if (diagnostics.length) {
            console.warn(`[parseQuestionsFromText] Dropped ${diagnostics.length} question candidate(s).`, diagnostics);
            const sample = diagnostics
                .slice(0, 3)
                .map((d) => `#${d.index}(${d.optionCount})`)
                .join(', ');
            setStatus(`זוהו ${formatted.length} שאלות תקינות. ${diagnostics.length} מועמדות הושמטו (דוגמאות: ${sample}).`, true);
            showToast(`הושמטו ${diagnostics.length} מועמדות שאלה. דוגמאות: ${sample}`, 'error', 7000);
        }

        const suspicious = formatted
            .map((q, idx) => ({ idx: idx + 1, n: q.options.length }))
            .filter((x) => x.n > 6);
        if (suspicious.length) {
            const sample = suspicious.slice(0, 3).map((s) => `#${s.idx}(${s.n})`).join(', ');
            showToast(`זוהו שאלות עם מספר תשובות חריג (חשד למיזוג): ${sample}`, 'error', 8000);
        }

        if (!formatted.length) {
            throw new Error('לא נמצאו שאלות בפורמט הנתמך.');
        }

        return formatted;
    }

    const parseCsvRows = window.QuizCore.parseCsvRows;

    function parseXlsxToRows(arrayBuffer) {
        if (!window.XLSX) {
            throw new Error('ספריית XLSX לא נטענה. אנא רענן את העמוד.');
        }
        const workbook = window.XLSX.read(new Uint8Array(arrayBuffer), { type: 'array' });
        const sheetName = workbook.SheetNames[0];
        const sheet = workbook.Sheets[sheetName];
        // Convert to array of arrays, with raw cell values as strings
        const rows = window.XLSX.utils.sheet_to_json(sheet, { header: 1, defval: '', raw: false });
        // Filter out completely empty rows
        return rows.filter((row) => row.some((cell) => String(cell).trim() !== ''));
    }

    const extractAnswersForForm = window.QuizCore.extractAnswersForForm;

    const mergeAnswers = window.QuizCore.mergeAnswers;
    const validateQuestions = window.QuizCore.validateQuestions;

    // ── Interactive PDF Page Crop Modal Controller ───────────────────────────
    let currentCropTargetIndex = null;
    let currentCropPageNum = 1;
    let cropSelection = { x: 0, y: 0, w: 0, h: 0 };
    let isCroppingDrag = false;
    let cropStartPos = { x: 0, y: 0 };
    let baseCropImage = null;
    const CROP_RENDER_SCALE = 3.0;
    const CROP_EXPORT_RENDER_SCALE = 6.0;
    const CROP_EXPORT_MIN_WIDTH = 2400;
    const CROP_EXPORT_MAX_DIMENSION = 7000;
    const CROP_EXPORT_MIME = 'image/png';

    const cropElements = {
        modal: document.getElementById('crop-modal'),
        pageSelect: document.getElementById('crop-page-select'),
        canvas: document.getElementById('crop-canvas'),
        closeBtn: document.getElementById('crop-modal-close'),
        cancelBtn: document.getElementById('crop-cancel-btn'),
        resetBtn: document.getElementById('crop-reset-btn'),
        saveBtn: document.getElementById('crop-save-btn'),
        statusText: document.getElementById('crop-status-text')
    };

    // Keep crop modal at top-level so parent popups/hidden containers cannot
    // block its visibility when opening from question cards.
    if (cropElements.modal && cropElements.modal.parentElement !== document.body) {
        document.body.appendChild(cropElements.modal);
    }

    async function getPdfBytesForCrop() {
        if (state.pdfBytes && state.pdfBytes.length > 0) {
            return new Uint8Array(state.pdfBytes);
        }

        if (state.pdfArrayBuffer && state.pdfArrayBuffer.byteLength > 0) {
            state.pdfBytes = new Uint8Array(state.pdfArrayBuffer.slice(0));
            return new Uint8Array(state.pdfBytes);
        }

        const pdfInput = elements.pdfFile?.files?.[0];
        if (pdfInput) {
            const buffer = await pdfInput.arrayBuffer();
            state.pdfArrayBuffer = buffer.slice(0);
            state.pdfBytes = new Uint8Array(buffer);
            return new Uint8Array(state.pdfBytes);
        }

        return null;
    }

    async function resolveCropTotalPages() {
        const cachedPages = state.pdfPagesState?.length || state.proofPageImages?.length || 0;
        if (cachedPages > 0) return cachedPages;

        const pdfjs = window.pdfjsLib || window['pdfjs-dist/build/pdf'] || window.pdfjs;
        if (!pdfjs?.getDocument) return 0;

        try {
            const bytes = await getPdfBytesForCrop();
            if (!bytes || !bytes.length) return 0;
            const pdfDoc = await pdfjs.getDocument({ data: bytes }).promise;
            return pdfDoc.numPages || 0;
        } catch (err) {
            console.warn('Could not resolve PDF page count for crop modal:', err);
            return 0;
        }
    }

    async function attachFullSourcePageImage(questionIndex, pageNum) {
        if (!state.questions[questionIndex]) return;

        const pdfjs = window.pdfjsLib || window['pdfjs-dist/build/pdf'] || window.pdfjs;
        if (!pdfjs?.getDocument) {
            showToast('ספריית PDF.js לא נטענה בדפדפן.', 'error');
            return;
        }

        try {
            const bytes = await getPdfBytesForCrop();
            if (!bytes || !bytes.length) {
                showToast('לא נמצא PDF זמין. העלה קובץ PDF ונסה שוב.', 'error');
                return;
            }

            const pdfDoc = await pdfjs.getDocument({ data: bytes }).promise;
            const safePage = Math.min(Math.max(1, Number(pageNum) || 1), pdfDoc.numPages);
            const page = await pdfDoc.getPage(safePage);

            // Match automatic attachment quality path.
            const imageData = await renderPageImageData(page, 2.5);
            state.questions[questionIndex].image = `data:image/png;base64,${imageData}`;
            state.questions[questionIndex].sourcePage = safePage;
            state.questions[questionIndex].imageNoCompress = true;

            renderPreview();
            showToast(`עמוד מקור ${safePage} הוצמד לשאלה באיכות מלאה.`, 'success');
        } catch (err) {
            console.error('Failed to attach full source page image:', err);
            showToast(`שגיאה בהצמדת עמוד מקור: ${err.message || err}`, 'error');
        }
    }

    async function openCropModal(questionIndex, initialPageNum = 1) {
        currentCropTargetIndex = questionIndex;
        if (!cropElements.modal || !cropElements.canvas) return;

        cropElements.modal.style.display = 'flex';
        cropElements.modal.classList.remove('hidden');

        // Populate page select dropdown
        if (cropElements.pageSelect) {
            cropElements.pageSelect.innerHTML = '';
            const totalPages = await resolveCropTotalPages();
            if (!totalPages) {
                showToast('לא נמצא PDF זמין לחיתוך. העלה קובץ PDF בשדה "קובץ PDF" ונסה שוב.', 'error');
                closeCropModal();
                return;
            }
            for (let i = 1; i <= totalPages; i++) {
                const opt = document.createElement('option');
                opt.value = i;
                opt.textContent = `עמוד ${i}`;
                if (i === Number(initialPageNum)) opt.selected = true;
                cropElements.pageSelect.appendChild(opt);
            }
        }

        await renderCropCanvasPage(initialPageNum);
    }

    async function renderCropCanvasPage(pageNum) {
        const canvas = cropElements.canvas;
        if (!canvas) return;
        currentCropPageNum = Number(pageNum) || 1;

        cropSelection = { x: 0, y: 0, w: 0, h: 0 };
        if (cropElements.statusText) cropElements.statusText.textContent = 'סמן אזור לחיתוך בעכבר';

        const pdfjs = window.pdfjsLib || window['pdfjs-dist/build/pdf'] || window.pdfjs;
        if (pdfjs?.getDocument) {
            try {
            const bytes = await getPdfBytesForCrop();
            if (!bytes || !bytes.length) throw new Error('Missing PDF bytes for crop render');
            const pdfDoc = await pdfjs.getDocument({ data: bytes }).promise;
                const page = await pdfDoc.getPage(Number(pageNum));
                const viewport = page.getViewport({ scale: CROP_RENDER_SCALE });
                canvas.width = viewport.width;
                canvas.height = viewport.height;
                const ctx = canvas.getContext('2d');
                if (ctx) {
                    ctx.imageSmoothingEnabled = true;
                    ctx.imageSmoothingQuality = 'high';
                }
                await page.render({ canvasContext: ctx, viewport }).promise;

                baseCropImage = new Image();
                baseCropImage.src = canvas.toDataURL('image/png');
                return;
            } catch (err) {
                console.warn('PDF.js render error in crop modal:', err);
            }
        }

        // Fallback: draw proof image or thumbnail
        const pageIdx = Number(pageNum) - 1;
        const imgUrl = state.proofPageImages?.[pageIdx] || state.pdfPagesState?.[pageIdx]?.thumbnailDataUrl;
        if (imgUrl) {
            const img = new Image();
            img.onload = () => {
                canvas.width = img.naturalWidth || img.width || 800;
                canvas.height = img.naturalHeight || img.height || 1100;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                baseCropImage = img;
            };
            img.src = imgUrl;
        } else {
            const ctx = canvas.getContext('2d');
            canvas.width = 600;
            canvas.height = 400;
            ctx.fillStyle = '#1e293b';
            ctx.fillRect(0, 0, 600, 400);
            ctx.fillStyle = '#94a3b8';
            ctx.font = '16px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('לא נמצא עמוד PDF זמין לחיתוך', 300, 200);
        }
    }

    async function exportHiResCropFromPdf(pageNum, selection) {
        const pdfjs = window.pdfjsLib || window['pdfjs-dist/build/pdf'] || window.pdfjs;
        if (!pdfjs?.getDocument) return null;

        const bytes = await getPdfBytesForCrop();
        if (!bytes || !bytes.length) return null;

        const pdfDoc = await pdfjs.getDocument({ data: bytes }).promise;
        const safePage = Math.min(Math.max(1, Number(pageNum) || 1), pdfDoc.numPages);
        const page = await pdfDoc.getPage(safePage);

        const baseRatio = CROP_EXPORT_RENDER_SCALE / CROP_RENDER_SCALE;
        const minWidthRatio = CROP_EXPORT_MIN_WIDTH / Math.max(1, selection.w);
        let ratio = Math.max(baseRatio, minWidthRatio);
        let exportScale = CROP_RENDER_SCALE * ratio;
        let outW = Math.max(1, Math.round(selection.w * ratio));
        let outH = Math.max(1, Math.round(selection.h * ratio));

        const maxSide = Math.max(outW, outH);
        if (maxSide > CROP_EXPORT_MAX_DIMENSION) {
            const downscale = CROP_EXPORT_MAX_DIMENSION / maxSide;
            exportScale = Math.max(CROP_RENDER_SCALE, exportScale * downscale);
            ratio = exportScale / CROP_RENDER_SCALE;
            outW = Math.max(1, Math.round(selection.w * ratio));
            outH = Math.max(1, Math.round(selection.h * ratio));
        }

        const sx = Math.max(0, selection.x * ratio);
        const sy = Math.max(0, selection.y * ratio);

        // Render full page at target DPI, then crop. This preserves glyph
        // layout for Hebrew text better than translated render transforms.
        const viewport = page.getViewport({ scale: exportScale });
        const fullCanvas = document.createElement('canvas');
        fullCanvas.width = Math.max(1, Math.round(viewport.width));
        fullCanvas.height = Math.max(1, Math.round(viewport.height));
        const fullCtx = fullCanvas.getContext('2d');
        if (!fullCtx) return null;
        fullCtx.imageSmoothingEnabled = true;
        fullCtx.imageSmoothingQuality = 'high';

        await page.render({ canvasContext: fullCtx, viewport }).promise;

        const offscreen = document.createElement('canvas');
        offscreen.width = outW;
        offscreen.height = outH;
        const ctx = offscreen.getContext('2d');
        if (!ctx) return null;
        ctx.imageSmoothingEnabled = true;
        ctx.imageSmoothingQuality = 'high';

        ctx.drawImage(fullCanvas, sx, sy, outW, outH, 0, 0, outW, outH);

        return offscreen.toDataURL(CROP_EXPORT_MIME);
    }

    function redrawCropCanvas() {
        const canvas = cropElements.canvas;
        if (!canvas || !baseCropImage) return;
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(baseCropImage, 0, 0, canvas.width, canvas.height);

        if (cropSelection.w > 5 && cropSelection.h > 5) {
            // Draw dimmed overlay
            ctx.fillStyle = 'rgba(0, 0, 0, 0.4)';
            ctx.fillRect(0, 0, canvas.width, canvas.height);

            // Clear cropped selection area
            ctx.drawImage(
                baseCropImage,
                cropSelection.x, cropSelection.y, cropSelection.w, cropSelection.h,
                cropSelection.x, cropSelection.y, cropSelection.w, cropSelection.h
            );

            // Draw red selection border
            ctx.strokeStyle = '#ef4444';
            ctx.lineWidth = 2;
            ctx.strokeRect(cropSelection.x, cropSelection.y, cropSelection.w, cropSelection.h);
        }
    }

    // Attach Crop Canvas Mouse Drag Handlers
    cropElements.canvas?.addEventListener('mousedown', (e) => {
        const rect = cropElements.canvas.getBoundingClientRect();
        const scaleX = cropElements.canvas.width / rect.width;
        const scaleY = cropElements.canvas.height / rect.height;

        isCroppingDrag = true;
        cropStartPos = {
            x: (e.clientX - rect.left) * scaleX,
            y: (e.clientY - rect.top) * scaleY
        };
        cropSelection = { x: cropStartPos.x, y: cropStartPos.y, w: 0, h: 0 };
    });

    cropElements.canvas?.addEventListener('mousemove', (e) => {
        if (!isCroppingDrag) return;
        const rect = cropElements.canvas.getBoundingClientRect();
        const scaleX = cropElements.canvas.width / rect.width;
        const scaleY = cropElements.canvas.height / rect.height;

        const currentX = (e.clientX - rect.left) * scaleX;
        const currentY = (e.clientY - rect.top) * scaleY;

        cropSelection.x = Math.min(cropStartPos.x, currentX);
        cropSelection.y = Math.min(cropStartPos.y, currentY);
        cropSelection.w = Math.abs(currentX - cropStartPos.x);
        cropSelection.h = Math.abs(currentY - cropStartPos.y);

        redrawCropCanvas();
        if (cropElements.statusText) {
            cropElements.statusText.textContent = `אזור נבחר: ${Math.round(cropSelection.w)}x${Math.round(cropSelection.h)} px`;
        }
    });

    window.addEventListener('mouseup', () => {
        if (isCroppingDrag) {
            isCroppingDrag = false;
        }
    });

    cropElements.pageSelect?.addEventListener('change', (e) => {
        renderCropCanvasPage(e.target.value);
    });

    cropElements.resetBtn?.addEventListener('click', () => {
        cropSelection = { x: 0, y: 0, w: 0, h: 0 };
        redrawCropCanvas();
        if (cropElements.statusText) cropElements.statusText.textContent = 'סמן אזור לחיתוך בעכבר';
    });

    function closeCropModal() {
        if (cropElements.modal) {
            cropElements.modal.style.display = 'none';
            cropElements.modal.classList.add('hidden');
        }
    }

    cropElements.closeBtn?.addEventListener('click', closeCropModal);
    cropElements.cancelBtn?.addEventListener('click', closeCropModal);

    cropElements.saveBtn?.addEventListener('click', async () => {
        if (currentCropTargetIndex === null || !state.questions[currentCropTargetIndex]) return;
        const canvas = cropElements.canvas;
        if (!canvas || cropSelection.w < 10 || cropSelection.h < 10) {
            showToast('אנא סמן אזור תמונה רחב יותר לחיתוך.', 'error');
            return;
        }

        let croppedDataUrl = null;
        try {
            croppedDataUrl = await exportHiResCropFromPdf(currentCropPageNum, cropSelection);
        } catch (err) {
            console.warn('High-resolution crop export failed, falling back to canvas crop:', err);
        }

        // Fallback path if high-resolution re-render is unavailable.
        if (!croppedDataUrl) {
            const offscreen = document.createElement('canvas');
            offscreen.width = cropSelection.w;
            offscreen.height = cropSelection.h;
            const ctx = offscreen.getContext('2d');
            if (!ctx) {
                showToast('לא ניתן היה ליצור תמונת חיתוך.', 'error');
                return;
            }
            ctx.imageSmoothingEnabled = true;
            ctx.imageSmoothingQuality = 'high';
            ctx.drawImage(
                canvas,
                cropSelection.x, cropSelection.y, cropSelection.w, cropSelection.h,
                0, 0, cropSelection.w, cropSelection.h
            );
            croppedDataUrl = offscreen.toDataURL(CROP_EXPORT_MIME);
        }

        state.questions[currentCropTargetIndex].image = croppedDataUrl;
        state.questions[currentCropTargetIndex].imageNoCompress = true;
        if (cropElements.pageSelect) {
            state.questions[currentCropTargetIndex].sourcePage = parseInt(cropElements.pageSelect.value, 10);
        }

        closeCropModal();
        renderPreview();
        showToast('תמונת השאלה עודכנה ונחתכה בהצלחה!', 'success');
    });

    function renderPreview() {
        elements.preview.innerHTML = '';

        state.questions.forEach((question, index) => {
            const card = document.createElement('article');
            card.className = 'question-card';

            const questionRow = document.createElement('div');
            questionRow.className = 'row';
            questionRow.style.gridTemplateColumns = '80px 1fr 28px';

            const qLabel = document.createElement('label');
            qLabel.textContent = `שאלה ${index + 1}`;
            questionRow.appendChild(qLabel);

            // Image thumbnail & per-question crop/upload controls
            const imageControlsWrap = document.createElement('div');
            imageControlsWrap.style.cssText = 'grid-column:1/-1;margin-bottom:8px;padding:8px 10px;background:var(--input-bg);border:1px solid var(--border-color);border-radius:10px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;';

            const leftBox = document.createElement('div');
            leftBox.style.cssText = 'display:flex;align-items:center;gap:6px;';

            const pageLabel = document.createElement('label');
            pageLabel.style.cssText = 'font-size:.82rem;font-weight:600;color:var(--text-secondary);';
            pageLabel.textContent = 'עמוד מקור:';

            const pageInput = document.createElement('input');
            pageInput.type = 'number';
            pageInput.min = '1';
            pageInput.value = question.sourcePage || 1;
            pageInput.style.cssText = 'width:55px;padding:3px 6px;border-radius:6px;border:1px solid var(--border-color);font:inherit;font-size:.82rem;background:var(--card-bg);color:var(--text-primary);';
            pageInput.addEventListener('change', () => {
                const p = parseInt(pageInput.value, 10);
                if (p && p >= 1) {
                    state.questions[index].sourcePage = p;
                    const card = pageInput.closest('.question-card');
                    if (card) {
                        const summary = card.querySelector('details summary');
                        if (summary) summary.textContent = `מצב הגהה: עמוד מקור ${p}`;
                        const sourceImg = card.querySelector('details img');
                        const sourcePageIndex = p - 1;
                        const newSrc = state.proofPageImages[sourcePageIndex] || state.pdfPagesState[sourcePageIndex]?.thumbnailDataUrl;
                        if (sourceImg && newSrc) {
                            sourceImg.src = newSrc;
                            sourceImg.alt = `עמוד מקור ${p}`;
                        }
                    }
                }
            });
            leftBox.append(pageLabel, pageInput);

            const rightBox = document.createElement('div');
            rightBox.style.cssText = 'display:flex;gap:6px;flex-wrap:wrap;align-items:center;';

            const cropBtn = document.createElement('button');
            cropBtn.type = 'button';
            cropBtn.className = 'secondary-btn sm-btn';
            cropBtn.textContent = question.image ? '🖼️ החלף לעמוד מקור מלא' : '🖼️ הוסף עמוד מקור מלא';
            cropBtn.style.cssText = 'font-size:.8rem;padding:4px 10px;';
            cropBtn.addEventListener('click', async () => {
                cropBtn.disabled = true;
                const prevText = cropBtn.textContent;
                cropBtn.textContent = 'מוסיף עמוד...';
                await attachFullSourcePageImage(index, question.sourcePage || 1);
                cropBtn.disabled = false;
                cropBtn.textContent = prevText;
            });

            const fileInput = document.createElement('input');
            fileInput.type = 'file';
            fileInput.accept = 'image/*';
            fileInput.style.display = 'none';
            fileInput.addEventListener('change', (e) => {
                const f = e.target.files?.[0];
                if (f) {
                    const reader = new FileReader();
                    reader.onload = (ev) => {
                        state.questions[index].image = ev.target.result;
                        delete state.questions[index].imageNoCompress;
                        renderPreview();
                    };
                    reader.readAsDataURL(f);
                }
            });

            const uploadBtn = document.createElement('button');
            uploadBtn.type = 'button';
            uploadBtn.className = 'secondary-btn sm-btn';
            uploadBtn.textContent = '📁 העלה תמונה מקובץ';
            uploadBtn.style.cssText = 'font-size:.8rem;padding:4px 10px;';
            uploadBtn.addEventListener('click', () => fileInput.click());

            rightBox.append(cropBtn, uploadBtn, fileInput);

            if (question.image) {
                const removeBtn = document.createElement('button');
                removeBtn.type = 'button';
                removeBtn.className = 'secondary-btn sm-btn';
                removeBtn.textContent = '✕ הסר תמונה';
                removeBtn.style.cssText = 'font-size:.8rem;padding:4px 8px;color:var(--danger);';
                removeBtn.addEventListener('click', () => {
                    delete state.questions[index].image;
                    renderPreview();
                });
                rightBox.appendChild(removeBtn);
            }

            imageControlsWrap.append(leftBox, rightBox);

            if (question.image) {
                const imgWrap = document.createElement('div');
                imgWrap.style.cssText = 'grid-column:1/-1;display:flex;align-items:center;gap:8px;margin-bottom:6px;';
                const thumb = document.createElement('img');
                thumb.src = question.image;
                thumb.style.cssText = 'max-height:140px;max-width:100%;border-radius:8px;border:1px solid var(--border-color);cursor:zoom-in;';
                thumb.title = 'לחץ להצגה בגודל מלא';
                thumb.addEventListener('click', () => showImageZoom(question.image));
                imgWrap.appendChild(thumb);
                card.appendChild(imgWrap);
            }

            card.appendChild(imageControlsWrap);

            const questionTextarea = document.createElement('textarea');
            questionTextarea.value = question.question;
            questionTextarea.addEventListener('input', () => {
                state.questions[index].question = questionTextarea.value;
            });
            questionRow.appendChild(questionTextarea);

            const deleteQBtn = document.createElement('button');
            deleteQBtn.type = 'button';
            deleteQBtn.textContent = '✕';
            deleteQBtn.title = 'מחק שאלה';
            deleteQBtn.style.cssText = 'width:28px;height:28px;border-radius:50%;border:1px solid var(--border-color);background:var(--input-bg);color:var(--danger);cursor:pointer;font-size:.85rem;display:flex;align-items:center;justify-content:center;padding:0;flex-shrink:0;';
            deleteQBtn.addEventListener('click', () => {
                state.questions.splice(index, 1);
                renderPreview();
            });
            questionRow.appendChild(deleteQBtn);

            card.appendChild(questionRow);

            if (state.proofMode && question.sourcePage) {
                const sourcePageIndex = Number(question.sourcePage) - 1;
                const sourcePageImage = state.proofPageImages[sourcePageIndex] || state.pdfPagesState[sourcePageIndex]?.thumbnailDataUrl;
                if (sourcePageImage) {
                    const proofWrap = document.createElement('details');
                    proofWrap.style.cssText = 'grid-column:1/-1;border:1px solid var(--border-color);border-radius:10px;background:var(--card-bg);padding:8px;';
                    proofWrap.open = false;

                    const summary = document.createElement('summary');
                    summary.textContent = `מצב הגהה: עמוד מקור ${question.sourcePage}`;
                    summary.style.cssText = 'cursor:pointer;font-weight:600;margin-bottom:8px;';
                    proofWrap.appendChild(summary);

                    const sourceImg = document.createElement('img');
                    sourceImg.src = sourcePageImage;
                    sourceImg.alt = `עמוד מקור ${question.sourcePage}`;
                    sourceImg.style.cssText = 'max-width:100%;border-radius:8px;border:1px solid var(--border-color);cursor:zoom-in;';
                    sourceImg.addEventListener('click', () => showImageZoom(sourcePageImage, Number(question.sourcePage)));
                    proofWrap.appendChild(sourceImg);

                    card.appendChild(proofWrap);
                }
            }

            question.options.forEach((option, optIndex) => {
                const optionRow = document.createElement('div');
                optionRow.className = 'option-row';

                const radio = document.createElement('input');
                radio.type = 'radio';
                radio.name = `correct-${index}`;
                radio.checked = question.correctIndex === optIndex;
                radio.title = 'סמן תשובה נכונה';
                radio.addEventListener('change', () => {
                    state.questions[index].correctIndex = optIndex;
                });

                const optionInput = document.createElement('input');
                optionInput.type = 'text';
                optionInput.value = option;
                optionInput.addEventListener('input', () => {
                    state.questions[index].options[optIndex] = optionInput.value;
                });

                const delBtn = document.createElement('button');
                delBtn.type = 'button';
                delBtn.textContent = '✕';
                delBtn.title = 'הסר תשובה';
                delBtn.style.cssText = 'width:26px;height:26px;border-radius:50%;border:1px solid var(--border-color);background:var(--input-bg);color:var(--danger);cursor:pointer;font-size:.85rem;display:flex;align-items:center;justify-content:center;padding:0;flex-shrink:0;';
                delBtn.addEventListener('click', () => {
                    if (state.questions[index].options.length <= 2) {
                        alert('שאלה חייבת להכיל לפחות 2 תשובות.');
                        return;
                    }
                    state.questions[index].options.splice(optIndex, 1);
                    if (state.questions[index].correctIndex >= state.questions[index].options.length) {
                        state.questions[index].correctIndex = Math.max(0, state.questions[index].options.length - 1);
                    }
                    renderPreview();
                });

                optionRow.append(radio, optionInput, delBtn);
                card.appendChild(optionRow);
            });

            const addBtn = document.createElement('button');
            addBtn.type = 'button';
            addBtn.textContent = '+ הוסף תשובה';
            addBtn.style.cssText = 'margin-top:4px;padding:6px 14px;border-radius:8px;border:1px dashed var(--border-color);background:var(--input-bg);color:var(--text-secondary);cursor:pointer;font:inherit;font-size:.85rem;width:100%;';
            addBtn.addEventListener('click', () => {
                state.questions[index].options.push('');
                renderPreview();
            });
            card.appendChild(addBtn);

            elements.preview.appendChild(card);
        });

        const addQBtn = document.createElement('button');
        addQBtn.type = 'button';
        addQBtn.textContent = '+ הוסף שאלה';
        addQBtn.style.cssText = 'margin-top:12px;padding:10px 16px;border-radius:10px;border:2px dashed var(--border-color);background:var(--card-bg);color:var(--text-secondary);cursor:pointer;font:inherit;font-size:.95rem;width:100%;';
        addQBtn.addEventListener('click', () => {
            state.questions.push({
                question: '',
                options: ['', '', '', ''],
                correctIndex: 0
            });
            renderPreview();
        });
        elements.preview.appendChild(addQBtn);
    }

    async function getTemplateSources() {
        if (state.templateCache) {
            return state.templateCache;
        }

        try {
            const [indexHtml, styleCss, quizCoreJs, appJs] = await Promise.all([
                fetch('quiz_player.html').then((response) => {
                    if (!response.ok) throw new Error(`HTTP ${response.status}`);
                    return response.text();
                }),
                fetch('style.css').then((response) => {
                    if (!response.ok) throw new Error(`HTTP ${response.status}`);
                    return response.text();
                }),
                fetch('quiz-core.js').then((response) => {
                    if (!response.ok) throw new Error(`HTTP ${response.status}`);
                    return response.text();
                }),
                fetch('app.js').then((response) => {
                    if (!response.ok) throw new Error(`HTTP ${response.status}`);
                    return response.text();
                })
            ]);

            state.templateCache = { indexHtml, styleCss, quizCoreJs, appJs };
            return state.templateCache;
        } catch (err) {
            if (window.location.protocol === 'file:') {
                throw new Error('לא ניתן ליצור קובץ מבחן בעת הרצה ישירה מקובץ מקומי (file://). דפדפנים חוסמים טעינת תבניות מסיבות אבטחה. הפעל שרת מקומי (כגון Live Server או npx serve) ונסה שוב.');
            }
            throw new Error(`טעינת תבניות המבחן נכשלה (${err.message}). ודא שהקבצים quiz_player.html, style.css, quiz-core.js, app.js קיימים בתיקייה.`);
        }
    }

    async function compressImageBase64(dataUrl, quality = 0.75) {
        if (!dataUrl || typeof dataUrl !== 'string' || !dataUrl.startsWith('data:image/')) {
            return dataUrl;
        }
        return new Promise((resolve) => {
            const img = new Image();
            img.onload = () => {
                const canvas = document.createElement('canvas');
                canvas.width = img.naturalWidth || img.width;
                canvas.height = img.naturalHeight || img.height;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0);
                const compressed = canvas.toDataURL('image/webp', quality);
                resolve(compressed.length < dataUrl.length ? compressed : dataUrl);
            };
            img.onerror = () => resolve(dataUrl);
            img.src = dataUrl;
        });
    }

    async function createStandaloneQuizHtml() {
        const validationErrors = validateQuestions(state.questions);
        if (validationErrors.length) {
            throw new Error(`לא ניתן לייצא: ${validationErrors.slice(0, 5).join(' ')}`);
        }

        const shouldCompress = elements.compressExportImages ? elements.compressExportImages.checked : false;
        const qualityVal = Number(elements.compressQualitySlider?.value) || 75;
        const quality = Math.min(Math.max(qualityVal, 10), 90) / 100;

        const cleanedQuestions = await Promise.all(state.questions.map(async (q) => {
            let img = q.image;
            if (shouldCompress && img) {
                const skipCompression = q.imageNoCompress === true;
                if (!skipCompression) {
                img = await compressImageBase64(img, quality);
                }
            }
            return {
                question: normalizeWhitespace(q.question),
                options: q.options.map((opt) => normalizeWhitespace(opt)),
                correctIndex: q.correctIndex,
                ...(q.shuffleOptions ? { shuffleOptions: true } : {}),
                ...(img ? { image: img } : {}) // embed base64 image directly
            };
        }));

        const { indexHtml, styleCss, quizCoreJs, appJs } = await getTemplateSources();
        const styledHtml = window.QuizExport.injectStylesheet(indexHtml, styleCss);
        const onlineBuilderUrl = 'https://elonuziel.github.io/interactive-test-creator/';
        const standaloneNavHtml = window.QuizExport.setBuilderLink(styledHtml, onlineBuilderUrl);
        const dataHtml = window.QuizExport.injectInlineQuestions(standaloneNavHtml, cleanedQuestions);
        const withCore = window.QuizExport.injectScript(dataHtml, 'quiz-core.js', quizCoreJs);
        return window.QuizExport.injectScript(withCore, 'app.js', appJs);
    }

    async function runParse() {
        disableOutputActions(true);
        elements.preview.innerHTML = '';
        state.proofPageImages = [];
        state.pdfBytes = null; // will be set below after reading the file
        let apiKey = '';

        const pdf = elements.pdfFile.files?.[0];
        const csv = elements.csvFile.files?.[0];
        const formNumber = elements.formNumber.value.trim();
        const ocrEngine = (elements.ocrEngine?.value || 'gemini_chunked').trim();
        const llmPolicy = (elements.llmPolicy?.value || 'auto').trim();

        if (!pdf) {
            throw new Error('יש לבחור קובץ PDF לפענוח.');
        }

        setStatus('קורא קובצי מקור...');

        let pdfFileToParse = pdf;
        let pdfBufferForParse = (await pdf.arrayBuffer()).slice(0);
        // Store raw bytes so hi-res lightbox zoom works regardless of whether the
        // sidebar was previously loaded (state.pdfBytes may still be null).
        if (!state.pdfBytes || state.pdfBytes.length === 0) {
            state.pdfBytes = new Uint8Array(pdfBufferForParse.slice(0));
        }

        const useCleanPdf = elements.useCleanPdfForApi ? elements.useCleanPdfForApi.checked : true;
        if (useCleanPdf) {
            try {
                const cleanBuffer = await getCleanPdfBuffer();
                if (cleanBuffer) {
                    pdfBufferForParse = cleanBuffer.slice(0);
                    pdfFileToParse = new File([cleanBuffer], `cleaned_${pdf.name}`, { type: 'application/pdf' });
                    const keptCount = state.pdfPagesState.filter(p => p.keep).length;
                    setStatus(`משתמש ב-PDF נקי (${keptCount} עמודים נבחרו בסרגל) לעיבוד...`);
                }
            } catch (e) {
                console.warn('Could not build clean PDF for parse:', e);
            }
        }

        let answerRows = null;
        if (csv) {
            const fileName = csv.name.toLowerCase();
            if (fileName.endsWith('.xlsx') || fileName.endsWith('.xls')) {
                const xlsxBuffer = await csv.arrayBuffer();
                answerRows = parseXlsxToRows(xlsxBuffer);
            } else {
                const csvText = await csv.text();
                answerRows = parseCsvRows(csvText.replace(/^\uFEFF/, ''));
            }
            if (!formNumber) {
                throw new Error('אם הועלה קובץ תשובות, יש להזין מספר שאלון.');
            }
        }

        setStatus('טוען ומנתח את מבנה קובץ ה-PDF...');
        const extracted = await extractPdfText(pdfBufferForParse);

        let examText = extracted.text;
        let sourcePages = extracted.rawPages;
        const useLlmExtraction = llmPolicy === 'force_llm' || (llmPolicy === 'auto' && extracted.isScanned && ocrEngine !== 'offline_local');
        const useOfflineOcr = extracted.isScanned && (llmPolicy === 'force_no_llm' || ocrEngine === 'offline_local');

        if (!extracted.isScanned && llmPolicy !== 'force_llm') {
            setStatus('זוהה PDF דיגיטלי. מחלץ שאלות מקומית מתוך טקסט ה-PDF ללא LLM.');
        }

        if (useOfflineOcr) {
            setStatus('מפעיל OCR מקומי בדפדפן (ללא API Key)...');
            const offlineExtraction = await extractTextViaOfflineOcr(extracted.pdf);
            examText = offlineExtraction.text;
            sourcePages = offlineExtraction.pages;
            state.proofPageImages = offlineExtraction.pagePreviews || [];
        } else if (useLlmExtraction) {
            apiKey = await resolveGeminiApiKey(true);
            if (ocrEngine.startsWith('gemini_native')) {
                const mode = ocrEngine === 'gemini_native_markdown' ? 'markdown' : 'schema';
                setStatus(`שולח את מסמך ה-PDF המלא ל-Gemini API (Native PDF - ${mode === 'schema' ? 'Enforced Schema' : 'Clean Markdown'})...`);
                const nativeExtraction = await extractTextViaGeminiNativePdf(pdfFileToParse, extracted.pdf, apiKey, mode);
                examText = nativeExtraction.text;
                sourcePages = nativeExtraction.pages;
                const previews = await renderAllPdfPageImages(extracted.pdf);
                state.proofPageImages = previews.pagePreviews || [];
            } else {
                setStatus('שולח עמודי תמונה ל-Gemini API (מצב Page Chunking)...');
                const geminiExtraction = await extractTextViaGemini(extracted.pdf, apiKey);
                examText = geminiExtraction.text;
                sourcePages = geminiExtraction.pages;
                state.proofPageImages = geminiExtraction.pagePreviews || [];
            }
        } else if (extracted.isScanned) {
            setStatus('זוהה PDF סרוק במצב מקומי בלבד (ללא LLM). התוצאה עלולה להיות חלקית.');
        }

        let parsedQuestions;
        try {
            parsedQuestions = parseQuestionsFromText(examText, sourcePages, extracted.pageImages);
        } catch (error) {
            if (useLlmExtraction) {
                setStatus('פורמט תשובת ה-LLM לא תאם מודל צפוי, מנסה ניתוח מקומי מהטקסט הדיגיטלי...');
                parsedQuestions = parseQuestionsFromText(extracted.text, extracted.rawPages, extracted.pageImages);
            } else {
                throw error;
            }
        }

        if (useLlmExtraction && ocrEngine === 'gemini_chunked' && parsedQuestions.length < 10) {
            setStatus('זוהה מספר נמוך של שאלות. מנסה פענוח פרטני עמוד-עמוד...');
            const fallbackExtraction = await extractTextViaGemini(extracted.pdf, apiKey, 1);
            const fallbackQuestions = parseQuestionsFromText(
                fallbackExtraction.text,
                fallbackExtraction.pages,
                extracted.pageImages
            );

            if (fallbackQuestions.length > parsedQuestions.length) {
                parsedQuestions = fallbackQuestions;
                examText = fallbackExtraction.text;
                sourcePages = fallbackExtraction.pages;
                state.proofPageImages = fallbackExtraction.pagePreviews || [];
            }
        }

        for (const q of parsedQuestions) {
            if (q._needsPageRender && !q.image && extracted.pdf && q.sourcePage) {
                try {
                    const page = await extracted.pdf.getPage(q.sourcePage);
                    // Use same 2.5 scale as renderPageImageData for consistent quality.
                    const imageData = await renderPageImageData(page, 2.5);
                    q.image = `data:image/png;base64,${imageData}`;
                } catch { /* skip if render fails */ }
            }
            delete q._needsPageRender;
        }

        // Default correct answer to index 0 ('א') and shuffle options until explicit merge
        state.questions = parsedQuestions.map(q => ({
            ...q,
            correctIndex: (typeof q.correctIndex === 'number' && q.correctIndex >= 0) ? q.correctIndex : 0,
            shuffleOptions: true
        }));

        // Additional AI Verification step (if explicitly enabled by user toggle)
        const enableVerification = elements.enableLlmVerification ? elements.enableLlmVerification.checked : false;
        if (enableVerification) {
            if (!apiKey) {
                apiKey = await resolveGeminiApiKey(true);
            }
            if (apiKey) {
                setStatus('מבצע סבב הגהה ותיקון נוסף מול Gemini API (Verification Pass)...');
                state.questions = await verifyTestWithGemini(state.questions, apiKey);
            }
        }

        const validationErrors = validateQuestions(state.questions);
        if (validationErrors.length) {
            throw new Error(`נמצאו שאלות לא תקינות: ${validationErrors.slice(0, 5).join(' ')}`);
        }

        renderPreview();
        disableOutputActions(false);
        setStatus(`הסתיים בהצלחה: ${state.questions.length} שאלות נטענו לעריכה.`);
    }

    elements.runParse.addEventListener('click', async () => {
        try {
            await runParse();
        } catch (error) {
            setStatus(error.message || 'אירעה שגיאה לא צפויה.', true);
        }
    });

    elements.downloadQuiz.addEventListener('click', () => {
        if (!state.questions || state.questions.length === 0) {
            showToast('אין שאלות זמינות ליצירת מבחן.', 'info');
            return;
        }
        if (elements.compressSettingsPopup) {
            elements.compressSettingsPopup.classList.add('show');
        }
    });

    elements.confirmDownloadBtn?.addEventListener('click', async () => {
        if (elements.compressSettingsPopup) {
            elements.compressSettingsPopup.classList.remove('show');
        }
        try {
            setStatus('מכין קובץ HTML להורדה...');
            const html = await createStandaloneQuizHtml();
            const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const anchor = document.createElement('a');
            anchor.href = url;
            anchor.download = 'interactive_quiz.html';
            anchor.click();
            URL.revokeObjectURL(url);
            setStatus('הקובץ נוצר וההורדה התחילה.');
        } catch (error) {
            setStatus(error.message || 'נכשלה יצירת קובץ HTML.', true);
        }
    });

    elements.takeQuiz.addEventListener('click', async () => {
        // Open synchronously from the user click so the new tab retains
        // its opener relationship, enabling the quiz player's back link.
        const previewWindow = window.open('', '_blank');
        if (!previewWindow) {
            setStatus('הדפדפן חסם את פתיחת לשונית המבחן. אפשר חלונות קופצים ונסה שוב.', true);
            return;
        }

        try {
            // Write a minimal loading page immediately so the tab shows a spinner
            // instead of blank while createStandaloneQuizHtml() runs (can be slow
            // for large quizzes with image compression).
            previewWindow.document.write('<!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8"><title>מכין מבחן...</title><style>body{display:flex;align-items:center;justify-content:center;height:100vh;margin:0;font-family:Rubik,system-ui,sans-serif;background:#f8fafc;color:#0f172a;direction:rtl}@keyframes bspin{to{transform:rotate(360deg)}}.sp{width:40px;height:40px;border:4px solid #e2e8f0;border-top-color:#3b82f6;border-radius:50%;animation:bspin .7s linear infinite;margin-bottom:16px}.wr{text-align:center}p{font-size:1.1rem;margin:0}</style></head><body><div class="wr"><div class="sp"></div><p>מכין מבחן...</p></div></body></html>');
            previewWindow.document.title = 'מכין מבחן...';
            setStatus('פותח תצוגת מבחן...');
            const html = await createStandaloneQuizHtml();
            previewWindow.document.open();
            previewWindow.document.write(html);
            previewWindow.document.close();
            setStatus('המבחן נפתח בלשונית חדשה.');
        } catch (error) {
            try {
                previewWindow.close();
            } catch {
                // Ignore browsers that refuse to close the temporary tab.
            }
            setStatus(error.message || 'לא ניתן היה לפתוח את המבחן.', true);
        }
    });

    // ── Normalization for questions.json ────────────────────────────────────────
    function normalizeQuestionsJson(data) {
        if (!Array.isArray(data) || data.length === 0) {
            throw new Error('קובץ ה-JSON הינו ריק או אינו במבנה מערך.');
        }

        return data.map((item, index) => {
            if (typeof item !== 'object' || item === null) {
                throw new Error(`שאלה מס' ${index + 1} אינה אובייקט תקין.`);
            }

            const rawQuestion = item.question || item.title || item.text || '';
            const cleanQuestion = stripQuestionHeaderPrefix(normalizeWhitespace(rawQuestion));
            let options = item.options || item.answers || item.choices || [];
            if (!Array.isArray(options)) options = [];

            options = options.map(opt => (typeof opt === 'object' && opt !== null && opt.text) ? opt.text : String(opt || ''));

            let correctIndex = item.correctIndex !== undefined ? Number(item.correctIndex) : (item.correctAnswerIndex !== undefined ? Number(item.correctAnswerIndex) : undefined);
            let shuffleOptions = item.shuffleOptions || false;

            if (correctIndex === undefined || isNaN(correctIndex) || correctIndex < 0 || correctIndex >= options.length) {
                if (typeof item.correctAnswer === 'number' && item.correctAnswer >= 1 && item.correctAnswer <= options.length) {
                    correctIndex = item.correctAnswer - 1;
                } else {
                    correctIndex = 0;
                    shuffleOptions = true;
                }
            }

            return {
                id: item.id || (index + 1),
                question: cleanQuestion,
                options: options,
                correctIndex: correctIndex,
                image: item.image || item.pageImage || null,
                sourcePage: item.sourcePage || item.page || (index + 1),
                shuffleOptions: shuffleOptions
            };
        });
    }

    function normalizeQuestionsFromAnyJson(rawData) {
        const toQuestionsArray = (input) => {
            if (!input) return null;
            if (Array.isArray(input) && input.length > 0) return input;
            if (typeof input !== 'object') return null;

            const directArray = [input.questions, input.data, input.items, input.quiz, input.test]
                .find((v) => Array.isArray(v) && v.length > 0);
            if (directArray) return directArray;

            const objectValues = Object.values(input || {});
            const nestedArray = objectValues.find((v) => Array.isArray(v) && v.length > 0);
            if (nestedArray) return nestedArray;

            const numericKeys = Object.keys(input).filter((k) => /^\d+$/.test(k));
            if (numericKeys.length > 0) {
                const sortedNumericKeys = numericKeys.sort((a, b) => Number(a) - Number(b));
                const values = sortedNumericKeys.map((k) => input[k]);

                if (values.every((v) => typeof v === 'number' && Number.isFinite(v))) {
                    return sortedNumericKeys.map((k) => {
                        const ansNum = Number(input[k]);
                        const safeIndex = Math.max(0, Math.min(3, ansNum - 1));
                        return {
                            question: `שאלה ${k}`,
                            options: ['א', 'ב', 'ג', 'ד'],
                            correctIndex: safeIndex
                        };
                    });
                }

                if (values.every((v) => v && typeof v === 'object')) {
                    return values;
                }
            }

            return null;
        };

        const asArray = toQuestionsArray(rawData);
        if (!asArray || !asArray.length) {
            throw new Error('JSON לא זוהה כמבנה שאלות נתמך.');
        }

        const normalized = normalizeQuestionsJson(asArray);
        const validationErrors = validateQuestions(normalized);
        if (validationErrors.length) {
            throw new Error(`מבנה השאלות אינו תקין: ${validationErrors.slice(0, 5).join(' ')}`);
        }
        return normalized;
    }

    // ── PDF Page Sidebar & Thumbnail Generator ─────────────────────────────────
    async function loadPdfSidebar(pdfBytesInput) {
        const pdfjs = window.pdfjsLib || window['pdfjs-dist/build/pdf'] || window.pdfjs;
        if (pdfBytesInput) {
            state.pdfBytes = new Uint8Array(pdfBytesInput);
        }
        state.pdfPagesState = [];
        if (elements.pageThumbnailsContainer) elements.pageThumbnailsContainer.innerHTML = '';

        if (!state.pdfBytes || state.pdfBytes.length === 0 || !pdfjs?.getDocument) return;

        try {
            const freshCopy = new Uint8Array(state.pdfBytes);
            const loadingTask = pdfjs.getDocument({ data: freshCopy });
            const pdfDoc = await loadingTask.promise;
            const numPages = pdfDoc.numPages;

            if (elements.pdfSidebarCard) elements.pdfSidebarCard.classList.remove('hidden');
            if (elements.builderLayout) elements.builderLayout.classList.remove('no-sidebar');

            for (let i = 1; i <= numPages; i++) {
                const page = await pdfDoc.getPage(i);
                const textContent = await page.getTextContent();
                const pageText = textContent.items.map(item => item.str).join(' ').trim();
                const isBlank = pageText.length < 30;

                const viewport = page.getViewport({ scale: 0.25 });
                const canvas = document.createElement('canvas');
                const context = canvas.getContext('2d');
                canvas.height = viewport.height;
                canvas.width = viewport.width;

                await page.render({ canvasContext: context, viewport: viewport }).promise;
                const thumbnailDataUrl = canvas.toDataURL('image/jpeg', 0.7);

                state.pdfPagesState.push({
                    pageNum: i,
                    keep: true,
                    text: pageText,
                    isBlank: isBlank,
                    thumbnailDataUrl: thumbnailDataUrl
                });
            }

            renderSidebarThumbnails();
            if (elements.downloadCleanPdf) elements.downloadCleanPdf.disabled = false;
        } catch (err) {
            console.error('Error rendering PDF sidebar thumbnails:', err);
        }
    }

    function renderSidebarThumbnails() {
        if (!elements.pageThumbnailsContainer) return;
        elements.pageThumbnailsContainer.innerHTML = '';
        const total = state.pdfPagesState.length;
        const kept = state.pdfPagesState.filter(p => p.keep).length;

        if (elements.pageCountBadge) {
            elements.pageCountBadge.textContent = `${kept} מתוך ${total} עמודים נבחרו`;
        }

        state.pdfPagesState.forEach((pageState) => {
            const item = document.createElement('div');
            item.className = `thumbnail-item ${pageState.keep ? '' : 'disabled-page'}`;

            const img = document.createElement('img');
            img.src = pageState.thumbnailDataUrl;
            img.alt = `עמוד ${pageState.pageNum}`;

            const label = document.createElement('label');
            label.className = 'thumbnail-label';

            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.checked = pageState.keep;
            checkbox.addEventListener('change', (e) => {
                pageState.keep = e.target.checked;
                item.classList.toggle('disabled-page', !pageState.keep);
                renderSidebarThumbnailsBadgeOnly();
            });

            label.appendChild(checkbox);
            label.appendChild(document.createTextNode(`עמוד ${pageState.pageNum}`));

            item.appendChild(img);
            item.appendChild(label);

            item.addEventListener('click', (e) => {
                if (e.target !== checkbox) {
                    checkbox.checked = !checkbox.checked;
                    pageState.keep = checkbox.checked;
                    item.classList.toggle('disabled-page', !pageState.keep);
                    renderSidebarThumbnailsBadgeOnly();
                }
            });

            elements.pageThumbnailsContainer.appendChild(item);
        });
    }

    function renderSidebarThumbnailsBadgeOnly() {
        const total = state.pdfPagesState.length;
        const kept = state.pdfPagesState.filter(p => p.keep).length;
        if (elements.pageCountBadge) {
            elements.pageCountBadge.textContent = `${kept} מתוך ${total} עמודים נבחרו`;
        }
    }

    function applyStandardFilter() {
        if (!state.pdfPagesState || !state.pdfPagesState.length) return;
        state.evenOddMode = null;
        const btn = elements.presetEvenOddBtn || elements.presetBlankBtn;
        if (btn) btn.textContent = '📄 עמודים זוגיים';
        state.pdfPagesState.forEach(p => {
            if (p.pageNum <= 4) p.keep = false;
            else if (p.pageNum >= 6 && p.pageNum % 2 === 0) p.keep = false;
            else p.keep = true;
        });
        renderSidebarThumbnails();
    }

    function toggleEvenOddFilter() {
        if (!state.pdfPagesState || !state.pdfPagesState.length) return;

        if (!state.evenOddMode || state.evenOddMode === 'odd') {
            // Select EVEN pages (2, 4, 6, ...)
            state.evenOddMode = 'even';
            state.pdfPagesState.forEach(p => {
                p.keep = (p.pageNum % 2 === 0);
            });
            const btn = elements.presetEvenOddBtn || elements.presetBlankBtn;
            if (btn) btn.textContent = '📄 עמודים אי-זוגיים';
            showToast('נבחרו עמודים זוגיים (2, 4, 6...)', 'info', 2000);
        } else {
            // Select ODD pages (1, 3, 5, ...)
            state.evenOddMode = 'odd';
            state.pdfPagesState.forEach(p => {
                p.keep = (p.pageNum % 2 !== 0);
            });
            const btn = elements.presetEvenOddBtn || elements.presetBlankBtn;
            if (btn) btn.textContent = '📄 עמודים זוגיים';
            showToast('נבחרו עמודים אי-זוגיים (1, 3, 5...)', 'info', 2000);
        }

        renderSidebarThumbnails();
    }

    function selectAllPages(keepState) {
        if (!state.pdfPagesState || !state.pdfPagesState.length) return;
        state.evenOddMode = null;
        const btn = elements.presetEvenOddBtn || elements.presetBlankBtn;
        if (btn) btn.textContent = '📄 עמודים זוגיים';
        state.pdfPagesState.forEach(p => {
            p.keep = keepState;
        });
        renderSidebarThumbnails();
    }

    async function getCleanPdfBuffer() {
        if (!state.pdfPagesState || !state.pdfPagesState.length) return null;
        const totalPages = state.pdfPagesState.length;
        const keptIndices = state.pdfPagesState
            .filter(p => p.keep)
            .map(p => p.pageNum - 1);

        if (keptIndices.length === 0 || keptIndices.length === totalPages) {
            return null;
        }
        if (!window.PDFLib) return null;

        let bytes = state.pdfBytes;
        if (!bytes || bytes.length === 0 || bytes.buffer.byteLength === 0) {
            const file = elements.pdfFile?.files?.[0];
            if (!file) return null;
            const buffer = await file.arrayBuffer();
            state.pdfBytes = new Uint8Array(buffer);
            bytes = state.pdfBytes;
        }

        const freshCopy = new Uint8Array(bytes.buffer.slice(0));
        const srcDoc = await window.PDFLib.PDFDocument.load(freshCopy);
        const newDoc = await window.PDFLib.PDFDocument.create();
        const copiedPages = await newDoc.copyPages(srcDoc, keptIndices);
        copiedPages.forEach(page => newDoc.addPage(page));
        const cleanPdfBytes = await newDoc.save();
        return cleanPdfBytes.buffer;
    }

    async function downloadCleanPdf() {
        if (!window.PDFLib) {
            alert('ספריית PDFLib אינה זמינה בדפדפן. יש לוודא חיבור לאינטרנט או לרענן את העמוד.');
            return;
        }

        try {
            setStatus('מכין קובץ PDF נקי להורדה...');

            let bytes = state.pdfBytes;
            // Fallback: If state.pdfBytes is missing or detached (0 byteLength), re-read directly from the file input
            if (!bytes || bytes.length === 0 || bytes.buffer.byteLength === 0) {
                const file = elements.pdfFile?.files?.[0];
                if (!file) {
                    alert('אנא בחר קובץ PDF ראשית.');
                    return;
                }
                const buffer = await file.arrayBuffer();
                state.pdfBytes = new Uint8Array(buffer);
                bytes = state.pdfBytes;
            }

            const freshCopy = new Uint8Array(bytes.buffer.slice(0));
            const srcDoc = await window.PDFLib.PDFDocument.load(freshCopy);
            const newDoc = await window.PDFLib.PDFDocument.create();

            let keptIndices = [];
            if (state.pdfPagesState && state.pdfPagesState.length > 0) {
                keptIndices = state.pdfPagesState
                    .filter(p => p.keep)
                    .map(p => p.pageNum - 1);
            }

            // Fallback: If no pages are checked or state.pdfPagesState not yet populated, keep all pages
            if (keptIndices.length === 0) {
                const totalPages = srcDoc.getPageCount();
                for (let i = 0; i < totalPages; i++) {
                    keptIndices.push(i);
                }
            }

            const copiedPages = await newDoc.copyPages(srcDoc, keptIndices);
            copiedPages.forEach(page => newDoc.addPage(page));

            const pdfDataUri = await newDoc.saveAsBase64({ dataUri: true });

            const anchor = document.createElement('a');
            anchor.href = pdfDataUri;
            anchor.download = 'cleaned_test.pdf';
            document.body.appendChild(anchor);
            anchor.click();
            document.body.removeChild(anchor);

            setStatus(`PDF נקי נוצר בהצלחה עם ${keptIndices.length} עמודים וההורדה התחילה.`);
        } catch (err) {
            console.error('Failed to export clean PDF:', err);
            alert(`שגיאה ביצירת PDF נקי: ${err.message || err}`);
            setStatus(err.message || 'שגיאה ביצירת PDF נקי.', true);
        }
    }

    const DEFAULT_LLM_PROMPT = `Please extract all multiple-choice questions from this exam PDF document as a clean Markdown file (questions.md) for an interactive Hebrew quiz system.

===========================================================================
REQUIRED MARKDOWN FORMAT (questions.md):
===========================================================================
### שאלה 1: [נוסח השאלה המלא בעברית] (עמוד 1)
- א. [אפשרות 1]
- ב. [אפשרות 2]
- ג. [אפשרות 3]
- ד. [אפשרות 4]

### שאלה 2: [נוסח השאלה השנייה בעברית] (עמוד 2)
- א. [אפשרות 1]
- ב. [אפשרות 2]
- ג. [אפשרות 3]
- ד. [אפשרות 4]

===========================================================================
STRICT EXTRACTION & FORMATTING RULES:
===========================================================================
1. QUESTION HEADERS: Include full question text on the header line starting with \`### שאלה X: [נוסח השאלה בעברית]\` and ending with the 1-based PDF page number in parentheses \`(עמוד X)\`, e.g. \`(עמוד 1)\`.
2. OPTIONS FORMATTING: Each option MUST start on a new line with standard bullet format: \`- א.\`, \`- ב.\`, \`- ג.\`, \`- ד.\`, \`- ה.\`. Extract ALL options for each question (questions may have 4, 5, 6 or more choices).
3. IMAGE-BASED OPTIONS (IMPORTANT): If an option is visual (diagram/graph/table/image) and not fully textual, use a short placeholder option text such as "ראה דיאגרמה א", "ראה גרף ב", "ראה טבלה ג".
4. MIXED OPTIONS: If an option has text plus visual content, keep the text and append a short note like "(ראה גרף בעמוד זה)".
5. HEBREW ACCURACY & ACRONYMS: Extract text in natural Hebrew reading order. Do NOT reverse words, letters, or numbers. Preserve all scientific terms, equations, and acronyms (e.g. "ATP", "DNA", "pH", "GSI", "DVM", "CO2") exactly as written.
6. PRESERVE DIAGRAM & TABLE KEYWORDS: Preserve words referencing figures or diagrams (e.g. "לפניכם", "באיור", "בגרף", "בטבלה", "בתרשים") as they appear in the original text.
7. NO CITATION TAGS OR CONVERSATIONAL CHATTER: Do NOT include web citations like \`[cite: X]\`. Do NOT write intro or outro commentary outside the code box.
8. DELIVERABLE FORMAT: Provide your entire response strictly inside a single, copyable Markdown code block (wrapped in \`\`\`markdown ... \`\`\`) OR as a downloadable \`questions.md\` file.`;

    if (elements.llmPromptBox) {
        elements.llmPromptBox.value = DEFAULT_LLM_PROMPT;
    }
    if (elements.digitalLlmPromptBox) {
        elements.digitalLlmPromptBox.value = DEFAULT_LLM_PROMPT;
    }

    // Preset buttons & Clean PDF download listeners
    elements.presetStdBtn?.addEventListener('click', applyStandardFilter);
    elements.presetEvenOddBtn?.addEventListener('click', toggleEvenOddFilter);
    elements.presetBlankBtn?.addEventListener('click', toggleEvenOddFilter);
    elements.presetSelectAllBtn?.addEventListener('click', () => selectAllPages(true));
    elements.presetDeselectAllBtn?.addEventListener('click', () => selectAllPages(false));
    elements.downloadCleanPdf?.addEventListener('click', downloadCleanPdf);

    elements.toggleSidebarCollapseBtn?.addEventListener('click', () => {
        if (!elements.pdfSidebarCard) return;
        const isCollapsed = elements.pdfSidebarCard.classList.toggle('is-collapsed');
        elements.toggleSidebarCollapseBtn.textContent = isCollapsed ? '▶ פתח סרגל' : '◀ קפל סרגל';
        showToast(isCollapsed ? 'סרגל עמודים קופל' : 'סרגל עמודים הורחב', 'info', 2000);
    });

    async function tryMergeAnswersFromCsv(explicit = false) {
        const csv = elements.csvFile?.files?.[0];
        const formNumber = elements.formNumber?.value?.trim();

        if (explicit) {
            if (!state.questions || !state.questions.length) {
                showToast('יש להעלות קודם קובץ שאלות (JSON או Markdown)!', 'error');
                return;
            }
            if (!csv) {
                showToast('יש לבחור קובץ תשובות (CSV/XLS)!', 'error');
                return;
            }
            if (!formNumber) {
                showToast('יש להזין מספר שאלון להתאמת התשובות!', 'error');
                return;
            }
        }

        if (!csv || !formNumber || !state.questions || !state.questions.length) return;

        try {
            let answerRows = null;
            const fileName = csv.name.toLowerCase();
            if (fileName.endsWith('.xlsx') || fileName.endsWith('.xls')) {
                const xlsxBuffer = await csv.arrayBuffer();
                answerRows = parseXlsxToRows(xlsxBuffer);
            } else {
                const csvText = await csv.text();
                answerRows = parseCsvRows(csvText.replace(/^\uFEFF/, ''));
            }

            const answerMap = extractAnswersForForm(answerRows, formNumber);
            if (!answerMap || !answerMap.size) {
                if (explicit) {
                    showToast(`לא נמצאו תשובות לשאלון ${formNumber} בקובץ שנבחר.`, 'error');
                }
                return;
            }

            state.questions = mergeAnswers(state.questions, answerMap);
            renderPreview();
            setStatus(`תשובות מ-CSV/XLS מוזגו בהצלחה לשאלון ${formNumber}!`, false, true);
        } catch (e) {
            console.warn('Could not merge CSV answers automatically:', e);
            if (explicit) {
                showToast(`שגיאה במיזוג תשובות: ${e.message}`, 'error');
            }
        }
    }

    async function autoAttachDiagramPageImages() {
        if (!state.questions || !state.questions.length) {
            showToast('יש להעלות קודם קובץ שאלות (JSON או Markdown)!', 'error');
            return;
        }

        let pdfBuffer = state.pdfArrayBuffer || state.pdfBytes;
        if (!pdfBuffer || pdfBuffer.byteLength === 0) {
            const pdfInput = elements.pdfFile?.files?.[0];
            if (!pdfInput) {
                alert('אנא בחר קודם את קובץ ה-PDF של המבחן בשדה "קובץ PDF".');
                return;
            }
            try {
                pdfBuffer = await pdfInput.arrayBuffer();
                state.pdfArrayBuffer = pdfBuffer.slice(0);
            } catch (e) {
                alert('קריאת קובץ ה-PDF נכשלה. אנא בחר את הקובץ מחדש.');
                return;
            }
        }

        const pdfjs = window.pdfjsLib || window['pdfjs-dist/build/pdf'] || window.pdfjs;
        if (!pdfjs?.getDocument) {
            alert('ספריית PDF.js לא נטענה בדפדפן. רענן את העמוד ונסה שוב.');
            return;
        }

        try {
            setStatus('מנתח עמודי PDF ומחבר תמונות לשאלות עם תרשימים/טבלאות...');
            const loadingTask = pdfjs.getDocument({ data: new Uint8Array(pdfBuffer.slice(0)) });
            const pdfDoc = await loadingTask.promise;

            // Build a searchable text cache once so we can map each question to
            // the most likely physical PDF page even when sourcePage is noisy.
            const normalizeForSearch = (value) => String(value || '')
                .replace(/\((?:עמוד|עמ'|page)\s*\d+\)/gi, ' ')
                .replace(/[^\u0590-\u05FFA-Za-z0-9\s]/g, ' ')
                .replace(/\s+/g, ' ')
                .trim()
                .toLowerCase();

            const pdfPageTexts = [];
            for (let p = 1; p <= pdfDoc.numPages; p++) {
                try {
                    const page = await pdfDoc.getPage(p);
                    const textContent = await page.getTextContent();
                    const pageText = textContent.items.map((it) => (it && it.str) ? it.str : '').join(' ');
                    pdfPageTexts.push(normalizeForSearch(pageText));
                } catch {
                    pdfPageTexts.push('');
                }
            }

            const findBestPageByQuestionText = (questionText, preferredPage) => {
                if (!questionText || !pdfPageTexts.length) return preferredPage;
                const normalizedQuestion = normalizeForSearch(questionText);
                if (!normalizedQuestion) return preferredPage;

                const tokens = normalizedQuestion
                    .split(' ')
                    .filter((t) => t.length >= 3)
                    .slice(0, 24);

                if (!tokens.length) return preferredPage;

                let bestPage = preferredPage;
                let bestScore = -1;

                for (let idx = 0; idx < pdfPageTexts.length; idx++) {
                    const pageText = pdfPageTexts[idx];
                    if (!pageText) continue;

                    let score = 0;
                    for (const token of tokens) {
                        if (pageText.includes(token)) score++;
                    }

                    if (score > bestScore) {
                        bestScore = score;
                        bestPage = idx + 1;
                    }
                }

                // If we have no lexical signal at all, keep current page assignment.
                return bestScore > 0 ? bestPage : preferredPage;
            };

            const imageKeywords = /(?:^|[\s\(\[\:\,\"\'-])(?:לפניכם|לפניך|גרף|הגרף|תרשים|התרשים|תמונה|התמונה|טבלה|הטבלה|איור|האיור|מפה|המפה|דיאגרמה|הדיאגרמה|צילום|סכמה|הסכמה|שרטוט|עקומה|עקומות|מוצג|המוצג|במוצג|באיור|בגרף|בטבלה|בתרשים)(?:$|[\s\)\.\:\,\?\!\"'-])/i;
            let attachedCount = 0;

            for (let i = 0; i < state.questions.length; i++) {
                const q = state.questions[i];
                const questionText = q.question || '';
                const isDiagramQuestion = imageKeywords.test(questionText);
                const requestedPage = q.sourcePage || 1;
                const clampedRequestedPage = Math.min(Math.max(1, requestedPage), pdfDoc.numPages);
                const targetPage = findBestPageByQuestionText(questionText, clampedRequestedPage);

                const shouldAttachImage = isDiagramQuestion || q.hasVisualElement || q._needsPageRender;
                if (shouldAttachImage && pdfDoc.numPages >= 1) {
                    try {
                        const page = await pdfDoc.getPage(targetPage);
                        // Use same 2.5 scale as renderPageImageData for consistent quality.
                        const imageData = await renderPageImageData(page, 2.5);
                        q.image = `data:image/png;base64,${imageData}`;
                        attachedCount++;
                    } catch (e) {
                        console.warn(`Could not render page ${targetPage} for question ${i + 1}:`, e);
                    }
                }
            }

            renderPreview();
            if (attachedCount > 0) {
                setStatus(`חוברו בהצלחה ${attachedCount} תמונות עמוד לשאלות עם תרשימים/טבלאות!`, false, true);
            } else {
                setStatus('לא נמצאו שאלות המפנות לתרשימים/טבלאות לחיבור עמוד.', false, true);
            }
        } catch (err) {
            console.error('Error auto-attaching diagram images:', err);
            alert(`שגיאה בחיבור תמונות עמוד: ${err.message || err}`);
        }
    }

    function stripAllQuestionHeaderPrefixes() {
        if (!state.questions || state.questions.length === 0) {
            showToast('אין שאלות טעונות במערכת לניקוי.', 'info');
            return;
        }
        let count = 0;
        state.questions.forEach((q) => {
            const original = q.question;
            const cleaned = stripQuestionHeaderPrefix(original);
            if (cleaned !== original) {
                q.question = cleaned;
                count++;
            }
        });
        renderPreview();
        if (count > 0) {
            showToast(`נוקו כותרות 'שאלה מספר X' מ-${count} שאלות בהצלחה!`, 'success');
        } else {
            showToast('כל השאלות כבר נקיות מכותרות.', 'info');
        }
    }

    elements.mergeAnswersBtn?.addEventListener('click', () => tryMergeAnswersFromCsv(true));
    elements.autoAttachDiagramsBtn?.addEventListener('click', autoAttachDiagramPageImages);
    elements.stripQuestionHeadersBtnPreview?.addEventListener('click', stripAllQuestionHeaderPrefixes);

    // jsonFile Upload Listener (Supports questions.json and questions.md)
    elements.jsonFile?.addEventListener('change', async () => {
        const file = elements.jsonFile.files?.[0];
        if (!file) return;
        try {
            setStatus(`מעבד קובץ ${file.name}...`);
            const text = await file.text();
            let normalizedQuestions = [];

            const trimmed = text.trim();
            const isJson = trimmed.startsWith('{') || trimmed.startsWith('[') || trimmed.startsWith('```json');

            if (isJson) {
                // Accept any .json input by first trying strict question JSON,
                // then falling back to the same markdown/text parser flow.
                let cleanJsonText = trimmed;
                if (cleanJsonText.startsWith('```json')) {
                    cleanJsonText = cleanJsonText.replace(/^```json\s*/i, '').replace(/\s*```$/, '').trim();
                }

                let parsedAsStrictJson = false;
                try {
                    const rawData = JSON.parse(cleanJsonText);
                    normalizedQuestions = normalizeQuestionsFromAnyJson(rawData);
                    if (Array.isArray(normalizedQuestions) && normalizedQuestions.length > 0) {
                        parsedAsStrictJson = normalizedQuestions.length > 0;
                    }
                } catch (jsonErr) {
                    console.warn('JSON parse failed for uploaded question file. Trying markdown/text fallback.', jsonErr);
                }

                if (!parsedAsStrictJson) {
                    const markdownQuestions = parseQuestionsFromMarkdown(text);
                    normalizedQuestions = markdownQuestions.length > 0
                        ? markdownQuestions
                        : parseQuestionsFromText(text, [], []);
                }
            } else {
                // Prefer strict Markdown parsing for questions.md uploads.
                // Fall back to the flexible text parser for other plain-text formats.
                const markdownQuestions = parseQuestionsFromMarkdown(text);
                normalizedQuestions = markdownQuestions.length > 0
                    ? markdownQuestions
                    : parseQuestionsFromText(text, [], []);
            }

            if (!normalizedQuestions || !normalizedQuestions.length) {
                throw new Error('לא פוענחו שאלות מהקובץ שנבחר.');
            }

            const selectedCsv = elements.csvFile?.files?.[0] || null;
            const currentFormNumber = (elements.formNumber?.value || '').trim();
            const isFormZero = currentFormNumber === '0';
            const hasShuffleFlag = normalizedQuestions.some((q) => q && q.shuffleOptions === true);
            const allAnswersDefaultToAlef = normalizedQuestions.every((q) => q && Number(q.correctIndex) === 0);

            // No answer key file should behave like Form 0: keep correctIndex at א and
            // randomize option order for solving. This preserves expected behavior when
            // users upload only questions.json/questions.md from test folders.
            const shouldAutoEnableFormZeroShuffle = !selectedCsv && !hasShuffleFlag && allAnswersDefaultToAlef;
            if (isFormZero || shouldAutoEnableFormZeroShuffle) {
                normalizedQuestions = normalizedQuestions.map((q) => ({ ...q, shuffleOptions: true }));

                if (shouldAutoEnableFormZeroShuffle && elements.formNumber && !currentFormNumber) {
                    elements.formNumber.value = '0';
                    showToast('לא זוהה קובץ תשובות. הופעל מצב שאלון 0 עם ערבוב תשובות אוטומטי.', 'info', 5000);
                }
            }

            state.questions = normalizedQuestions;
            renderPreview();
            disableOutputActions(false);
            tryMergeAnswersFromCsv(false);
            setStatus(`נטענו ${normalizedQuestions.length} שאלות בהצלחה מקובץ ${file.name}!`, false, true);
        } catch (error) {
            console.error('Error loading question file:', error);
            setStatus(error.message || `נכשלה טעינת קובץ ${file.name}.`, true);
        }
    });

    elements.csvFile?.addEventListener('change', () => {
        const file = elements.csvFile.files?.[0];
        if (file) {
            tryMergeAnswersFromCsv(false);
            showToast(`קובץ תשובות (${file.name}) נבחר. הזן מספר שאלון ולחץ "🔗 מזג תשובות נכונות לשאלות".`, 'info', 4000);
        }
    });

    elements.formNumber?.addEventListener('input', () => tryMergeAnswersFromCsv(false));

    function toggleProcessingSettings(showOnly = false) {
        if (!elements.processingSettingsContainer) return;
        if (showOnly) {
            elements.processingSettingsContainer.classList.remove('hidden');
        } else {
            elements.processingSettingsContainer.classList.toggle('hidden');
        }

        if (!elements.processingSettingsContainer.classList.contains('hidden')) {
            elements.processingSettingsContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }

    elements.toggleProcessingSettingsBtn?.addEventListener('click', () => toggleProcessingSettings(false));

    // Copy prompt helper listener
    elements.copyPromptBtn?.addEventListener('click', async () => {
        const textToCopy = elements.llmPromptBox ? elements.llmPromptBox.value : DEFAULT_LLM_PROMPT;
        try {
            await navigator.clipboard.writeText(textToCopy);
            const originalText = elements.copyPromptBtn.textContent;
            elements.copyPromptBtn.textContent = '✓ הועתק!';
            setTimeout(() => {
                elements.copyPromptBtn.textContent = originalText;
            }, 3000);
        } catch (e) {
            setStatus('נכשלה העתקת הפרומפט ללוח.', true);
        }
    });

    elements.showDigitalPromptBtn?.addEventListener('click', () => {
        if (!elements.digitalPromptExpandable) return;
        const isHidden = elements.digitalPromptExpandable.classList.toggle('hidden');
        elements.showDigitalPromptBtn.textContent = isHidden ? '📋 הצג פרומפט ל-AI חיצוני' : '📋 הסתר פרומפט';
    });

    // Compression Modal Listeners
    elements.compressSettingsCancel?.addEventListener('click', () => {
        if (elements.compressSettingsPopup) elements.compressSettingsPopup.classList.remove('show');
    });

    elements.compressExportImages?.addEventListener('change', (e) => {
        if (!elements.compressSliderWrap) return;
        elements.compressSliderWrap.style.opacity = e.target.checked ? '1' : '0.4';
        elements.compressSliderWrap.style.pointerEvents = e.target.checked ? 'auto' : 'none';
    });

    elements.compressQualitySlider?.addEventListener('input', (e) => {
        const val = Number(e.target.value) || 75;
        if (!elements.compressQualityVal) return;
        let note = '(מומלץ)';
        if (val < 40) note = '(דחיסה גבוהה)';
        else if (val < 70) note = '(איכות בינונית)';
        else if (val > 80) note = '(איכות גבוהה)';
        elements.compressQualityVal.textContent = `${val}% ${note}`;
    });

    elements.copyDigitalPromptBtn?.addEventListener('click', async () => {
        const textToCopy = elements.digitalLlmPromptBox ? elements.digitalLlmPromptBox.value : DEFAULT_LLM_PROMPT;
        try {
            await navigator.clipboard.writeText(textToCopy);
            const originalText = elements.copyDigitalPromptBtn.textContent;
            elements.copyDigitalPromptBtn.textContent = '✓ הועתק!';
            setTimeout(() => {
                elements.copyDigitalPromptBtn.textContent = originalText;
            }, 3000);
        } catch (e) {
            setStatus('נכשלה העתקת הפרומפט ללוח.', true);
        }
    });

    elements.htmlFile.addEventListener('change', async () => {
        const file = elements.htmlFile.files?.[0];
        if (!file) return;
        try {
            setStatus('טוען מבחן קיים...');
            const html = await file.text();
            const marker = 'window.__INLINE_QUESTIONS__=';
            const startIdx = html.indexOf(marker);
            if (startIdx < 0) throw new Error('לא נמצאו שאלות מוטמעות בקובץ.');
            const jsonStart = startIdx + marker.length;
            const endMarker = ';(function()';
            const jsonEnd = html.indexOf(endMarker, jsonStart);
            if (jsonEnd < 0) throw new Error('פורמט השאלות המוטמעות בקובץ אינו תקין.');
            const jsonText = html.substring(jsonStart, jsonEnd).trim();
            const questions = JSON.parse(jsonText);
            if (!Array.isArray(questions) || !questions.length || !questions[0].question) {
                throw new Error('מבנה השאלות בקובץ אינו תקין.');
            }
            state.questions = questions;
            state.proofPageImages = [];
            renderPreview();
            disableOutputActions(false);
            setStatus(`נטענו ${questions.length} שאלות מקובץ HTML קיים.`);
        } catch (error) {
            setStatus(error.message || 'נכשלה טעינת קובץ HTML.', true);
        }
    });

    elements.runDigitalLocalBtn?.addEventListener('click', async () => {
        if (elements.llmPolicy) {
            elements.llmPolicy.value = 'force_no_llm';
        }
        try {
            await runParse();
        } catch (error) {
            setStatus(error.message || 'אירעה שגיאה בעיבוד המקומי.', true);
        }
    });

    elements.pdfFile.addEventListener('change', async () => {
        const file = elements.pdfFile.files?.[0];
        if (!file) {
            setPdfTypeNote('');
            if (elements.scannedActionsBox) elements.scannedActionsBox.classList.add('hidden');
            if (elements.digitalActionsBox) elements.digitalActionsBox.classList.add('hidden');
            if (elements.pdfSidebarCard) elements.pdfSidebarCard.classList.add('hidden');
            if (elements.builderLayout) elements.builderLayout.classList.add('no-sidebar');
            return;
        }

        if ((file.name || '').toLowerCase().endsWith('.docx')) {
            setPdfTypeNote('קובץ DOCX זוהה. יש להמיר אותו ל-PDF ואז להעלות מחדש.', 'error');
            if (elements.scannedActionsBox) elements.scannedActionsBox.classList.add('hidden');
            if (elements.digitalActionsBox) elements.digitalActionsBox.classList.add('hidden');
            if (elements.pdfSidebarCard) elements.pdfSidebarCard.classList.add('hidden');
            if (elements.builderLayout) elements.builderLayout.classList.add('no-sidebar');
            state.pdfArrayBuffer = null;
            return;
        }

        try {
            setPdfTypeNote('מזהה את סוג ה-PDF...', 'loading');
            const pdfBuffer = await file.arrayBuffer();
            state.pdfArrayBuffer = pdfBuffer.slice(0);

            const detection = await detectPdfType(state.pdfArrayBuffer.slice(0));
            setPdfTypeNote(
                `${detection.pdfTypeLabel}: ${detection.recommendation}`,
                detection.isScanned ? 'scanned' : 'digital'
            );

            if (elements.scannedActionsBox) {
                elements.scannedActionsBox.classList.toggle('hidden', !detection.isScanned);
            }
            if (elements.digitalActionsBox) {
                elements.digitalActionsBox.classList.toggle('hidden', detection.isScanned);
            }

            // Load sidebar thumbnails & page selection state
            await loadPdfSidebar(state.pdfArrayBuffer.slice(0));
        } catch (error) {
            setPdfTypeNote(error.message || 'לא ניתן היה לזהות את סוג ה-PDF.', 'error');
        }
    });

    document.querySelector('[data-target="pdf-file"]')?.addEventListener('click', () => {
        setPdfTypeNote('');
        if (elements.scannedActionsBox) elements.scannedActionsBox.classList.add('hidden');
        if (elements.digitalActionsBox) elements.digitalActionsBox.classList.add('hidden');
        if (elements.pdfSidebarCard) elements.pdfSidebarCard.classList.add('hidden');
        if (elements.builderLayout) elements.builderLayout.classList.add('no-sidebar');
    });
});
