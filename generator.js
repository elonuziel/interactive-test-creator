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
        jsonFile: document.getElementById('json-file'),
        csvFile: document.getElementById('csv-file'),
        formNumber: document.getElementById('form-number'),
        mergeAnswersBtn: document.getElementById('merge-answers-btn'),
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
        showApiSettingsBtn: document.getElementById('show-api-settings-btn'),
        toggleProcessingSettingsBtn: document.getElementById('toggle-processing-settings-btn'),
        processingSettingsContainer: document.getElementById('processing-settings-container'),
        copyPromptBtn: document.getElementById('copy-prompt-btn'),
        llmPromptBox: document.getElementById('llm-prompt-box'),
        downloadCleanPdfMain: document.getElementById('download-clean-pdf-main'),
        presetStdBtnMain: document.getElementById('preset-std-btn-main'),
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
        compressExportImages: document.getElementById('compress-export-images'),
        status: document.getElementById('status'),
        preview: document.getElementById('preview'),
        proofModeToggle: document.getElementById('proof-mode-toggle'),
        useCleanPdfForApi: document.getElementById('use-clean-pdf-for-api'),
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

    function setStatus(message, isError = false, triggerToast = false) {
        elements.status.textContent = message;
        elements.status.classList.toggle('muted', !isError);
        elements.status.style.color = isError ? 'var(--danger)' : 'var(--text-primary)';
        if (triggerToast || isError) {
            showToast(message, isError ? 'error' : 'success');
        }
    }

    function disableOutputActions(disabled) {
        elements.downloadQuiz.disabled = disabled;
        elements.takeQuiz.disabled = disabled;
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
        return value.replace(/-+\s*סוף\s+המבחן\s*-+/g, ' ');
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

        return reversedSignals > normalSignals ? fixHebrewWordOrder(text) : text;
    }

    function groupPdfTextItemsToLines(items) {
        const normalized = items
            .filter((item) => item.str && item.str.trim())
            .map((item) => ({ text: item.str.trim(), x: item.transform[4], y: item.transform[5] }));

        normalized.sort((a, b) => {
            if (Math.abs(a.y - b.y) > 2) return b.y - a.y;
            return a.x - b.x;
        });

        const lines = [];
        for (const item of normalized) {
            const line = lines.find((candidate) => Math.abs(candidate.y - item.y) <= 2);
            if (!line) {
                lines.push({ y: item.y, chunks: [item] });
            } else {
                line.chunks.push(item);
            }
        }

        lines.sort((a, b) => b.y - a.y);

        return lines.map((line) => line.chunks.sort((a, b) => a.x - b.x).map((chunk) => chunk.text).join(' '));
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
        if (!window.pdfjsLib?.getDocument) {
            throw new Error('PDF.js לא נטען. רענן את העמוד ונסה שוב.');
        }

        const freshData = new Uint8Array(inputBuffer);
        const loadingTask = window.pdfjsLib.getDocument({ data: freshData });
        const pdf = await loadingTask.promise;
        const pages = [];
        const pageImages = []; // index = pageNumber-1, value = base64 data URL or null
        let nonWhitespaceChars = 0;

        for (let pageNumber = 1; pageNumber <= pdf.numPages; pageNumber++) {
            const page = await pdf.getPage(pageNumber);
            const textContent = await page.getTextContent();
            const lineText = groupPdfTextItemsToLines(textContent.items).join('\n');
            pages.push(lineText);
            nonWhitespaceChars += lineText.replace(/\s/g, '').length;

            // Detect if this page has embedded images via operator list.
            // Fallback to hardcoded PDF.js OPS values if .OPS is not exported.
            try {
                const ops = await page.getOperatorList();
                const PAINT_IMAGE = (window.pdfjsLib.OPS && window.pdfjsLib.OPS.paintImageXObject) || 85;
                const PAINT_INLINE = (window.pdfjsLib.OPS && window.pdfjsLib.OPS.paintInlineImageXObject) || 86;
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
        if (!window.pdfjsLib?.getDocument) {
            throw new Error('PDF.js לא נטען. רענן את העמוד ונסה שוב.');
        }

        const freshData = new Uint8Array(inputBuffer);
        const loadingTask = window.pdfjsLib.getDocument({ data: freshData });
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
            pdfTypeLabel: isScanned ? 'PDF סרוק (תמונה)' : 'PDF דיגיטלי (עם טקסט)',
            recommendation: isScanned
                ? 'יזדקק ל-OCR. אפשר להשתמש ב-Gemini או ב-OCR החינמי בדפדפן.'
                : 'יעובד מקומית ללא OCR וללא צורך ב-API Key.'
        };
    }

    async function renderPageImageData(page, scale = 1.3) {
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
                retryNextModel: false,
                userMessage: 'חריגה ממכסה או קצב בקשות Gemini (429). נסה שוב מאוחר יותר.'
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

        if (status >= 500) {
            return {
                code: 'server',
                retryNextModel: true,
                userMessage: 'שגיאת שרת זמנית של Gemini. מנסה מודל חלופי...'
            };
        }

        return {
            code: 'unknown',
            retryNextModel: false,
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

        // Prefer pro model for complex OCR
        const sortedCandidates = [...candidates].sort((a, b) => b.model.localeCompare(a.model)); // pro before flash

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
                    // Split the text by the delimiter to return an array of pages
                    const extractedPages = text.split(/---PAGE_BOUNDARY---/i).map(s => s.trim());
                    // Pad with empty strings if Gemini returned fewer pages than expected
                    while (extractedPages.length < imageDatas.length) {
                        extractedPages.push('');
                    }
                    return extractedPages;
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


    async function extractTextViaGeminiNativePdf(pdfFile, pdf, apiKey) {
        if (!apiKey) {
            throw new Error('ה-PDF נראה סרוק ואין מפתח Gemini זמין לחילוץ טקסט. הזן API key או Passcode תקין.');
        }

        setStatus('מעלה את מסמך ה-PDF ישירות ל-Gemini (Native PDF)...');

        const base64Pdf = await fileToBase64(pdfFile);
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
        // Prefer pro model for complex PDF Native processing
        const sortedCandidates = [...candidates].sort((a, b) => b.model.localeCompare(a.model));
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
                        throw new Error(`Gemini returned empty OCR text. Finish Reason: ${finishReason}`);
                    }

                    extractedPages = text.split(/---PAGE_BOUNDARY---/i).map((s) => s.trim());
                    break;
                }

                const errorText = await response.text();
                const errorInfo = getGeminiErrorInfo(response.status, errorText);

                if (errorInfo.code === 'quota' && retryCount < GEMINI_CONFIG.maxQuotaRetries) {
                    const delayMs = computeRetryDelayMs(response, retryCount);
                    setStatus(`Gemini החזיר 429 ב-Native PDF. ממתין ${Math.ceil(delayMs / 1000)} שניות ומנסה שוב...`);
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
            setStatus(`מכין תצוגה מקדימה לעמוד ${pageNumber}/${pdf.numPages}...`);
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
        const sortedCandidates = [...candidates].sort((a, b) => b.model.localeCompare(a.model));
        const candidate = sortedCandidates[0]; // Pro model preferred
        const endpoint = buildGeminiEndpoint(candidate.version, candidate.model, apiKey);

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

        if (!response.ok) {
            console.warn('Gemini verification failed, using original parsed questions.');
            return parsedQuestions;
        }

        const payload = await response.json();
        const responseParts = payload.candidates?.[0]?.content?.parts || [];
        let text = responseParts.map((part) => part.text || '').join('\n').trim();

        // Remove markdown formatting if Gemini included it despite instructions
        text = text.replace(/^```json\s*/i, '').replace(/```\s*$/i, '').trim();

        try {
            const verified = JSON.parse(text);
            if (Array.isArray(verified) && verified.length > 0 && verified[0].question) {
                return verified;
            }
        } catch (e) {
            console.error('Failed to parse Gemini verification JSON:', e);
        }

        // Fallback to original if parsing failed
        return parsedQuestions;
    }

    function parseQuestionsFromText(text, rawPages, pageImages) {
        if (!text) return [];

        let trimmedText = text.trim();
        if (trimmedText.startsWith('```json')) {
            trimmedText = trimmedText.replace(/^```json\s*/i, '').replace(/\s*```$/, '').trim();
        } else if (trimmedText.startsWith('```')) {
            trimmedText = trimmedText.replace(/^```\s*/i, '').replace(/\s*```$/, '').trim();
        }

        if (trimmedText.startsWith('[') || trimmedText.startsWith('{')) {
            try {
                const parsed = JSON.parse(trimmedText);
                const questionsArray = Array.isArray(parsed) ? parsed : (parsed.questions || parsed.data);
                if (Array.isArray(questionsArray) && questionsArray.length > 0) {
                    return normalizeQuestionsJson(questionsArray);
                }
            } catch (e) {
                console.warn('JSON parse attempt failed, falling back to line-by-line parser:', e);
            }
        }

        const lines = text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
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
        // Matches common Hebrew exam question headers in both normal and extracted-reversed forms.
        // Supports numeric-start styles such as "22.", "22)", "22 -", and optional leading dot artifacts (". 22").
        const qPattern = /(?:שאלה\s+(?:מספר\s*)?:?\s*\d+\s*:?|\d+\s*:?\s*מספר\s+שאלה|^\.?\s*\d+\s*[\.\)]\s+(?![אבגדהוזחטי]\s*$)|^\.?\s*\d+\s*-\s+(?![אבגדהוזחטי]\s*$))/;
        // Matches: 'א. text', 'א . text' (space between letter and dot from PDF.js visual layout)
        // Also: '.א text' or '. א text' (dot-before-letter, another Hebrew PDF extraction artifact)
        const ansPatternStart = /^([אבגדהוזחטי1-9])\s*[\.]\s*(.*)$|^([אבגדהוזחטי1-9])[\)]\s*(.*)$|^[\.]\s*([אבגדהוזחטי])\s*(.*)$/;
        // Matches: 'text א.' or 'text .א' at end of line
        const ansPatternEnd = /^(.*)\s+([אבגדהוזחטי1-9])\s*[\.\)]$|^(.*)\s+[\.]\s*([אבגדהוזחטי])$/;
        const noisePattern = /^עמוד\s+\d+\s+מתוך\s+\d+$/;
        const footerPattern = /^-+\s*סוף\s+המבחן\s*-+$/;

        const rawQuestions = [];
        let current = null;
        let stateMode = 0;

        function pushCurrent() {
            if (!current) return;
            rawQuestions.push(current);
            current = null;
        }

        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            if (!line || noisePattern.test(line) || line.includes('קוד מבחן') || line.includes("מבחן מס") || line.includes('מבחן מס')) {
                continue;
            }

            const reversedLine = line.split(/\s+/).reverse().join(' ');
            if (footerPattern.test(line) || footerPattern.test(reversedLine)) {
                continue;
            }

            if (qPattern.test(line) || qPattern.test(reversedLine)) {
                pushCurrent();
                current = { text: [], answers: [], lineIdx: i }; // use i, not indexOf
                stateMode = 1;
                continue;
            }

            if (!current) {
                continue;
            }

            // ansPatternStart captures: (1,2) => 'א. text', (3,4) => 'א) text', (5,6) => '. א text'.
            let match = line.match(ansPatternStart) || reversedLine.match(ansPatternStart);
            let endMatch = (!match) && (line.match(ansPatternEnd) || reversedLine.match(ansPatternEnd));

            if (match || endMatch) {
                stateMode = 2;
                let letter, answerText;
                if (match) {
                    letter = match[1] || match[3] || match[5];
                    answerText = (match[2] || match[4] || match[6] || '').trim();
                } else {
                    letter = endMatch[2] || endMatch[4];
                    answerText = (endMatch[1] || '').trim();
                }

                if (!letter) {
                    continue;
                }
                current.answers.push({ text: answerText ? [answerText] : [] });
                continue;
            }

            if (stateMode === 1) {
                current.text.push(line);
            } else if (stateMode === 2 && current.answers.length > 0) {
                current.answers[current.answers.length - 1].text.push(line);
            }
        }

        pushCurrent();

        const imageKeywords = /לפניכם|גרף|תרשים|תמונה|טבלה|לוח|איור|מפה|ציור|דיאגרמה|צילום|סכמה|טבלאות|תרשים/;

        const diagnostics = [];
        const formatted = rawQuestions
            .map((q, idx) => {
                const question = normalizeWhitespace(stripExamFooterArtifacts(q.text.join(' ')));
                const options = q.answers
                    .map((a) => normalizeWhitespace(stripExamFooterArtifacts(a.text.join(' '))))
                    .filter(Boolean);
                const pageIdx = filteredLinePageMap[q.lineIdx] ?? 0;
                const obj = { question, options, correctIndex: 0, sourcePage: pageIdx + 1 };

                // Attach embedded image if available; visual-keyword questions without
                // an embedded image will get a full-page render later in runParse.
                if (imageKeywords.test(question)) {
                    if (pageImages && pageIdx >= 0 && pageIdx < pageImages.length && pageImages[pageIdx]) {
                        obj.image = pageImages[pageIdx];
                    }
                    // Mark for fallback page render (handled by caller)
                    obj._needsPageRender = true;
                }

                if (!question || options.length < 2) {
                    diagnostics.push({
                        index: idx + 1,
                        sourcePage: pageIdx + 1,
                        lineIdx: q.lineIdx,
                        questionPreview: question.slice(0, 80),
                        optionCount: options.length,
                        dropReason: !question ? 'empty-question' : 'insufficient-options'
                    });
                }

                return obj;
            })
            .filter((q) => q.question && q.options.length >= 2);

        if (diagnostics.length) {
            console.warn(`[parseQuestionsFromText] Dropped ${diagnostics.length} question candidate(s).`, diagnostics);
        }

        if (!formatted.length) {
            throw new Error('לא נמצאו שאלות בפורמט הנתמך.');
        }

        return formatted;
    }

    function parseCsvRows(csvText) {
        const rows = [];
        let row = [];
        let value = '';
        let inQuotes = false;

        for (let i = 0; i < csvText.length; i++) {
            const char = csvText[i];
            const next = csvText[i + 1];

            if (char === '"') {
                if (inQuotes && next === '"') {
                    value += '"';
                    i++;
                } else {
                    inQuotes = !inQuotes;
                }
            } else if (char === ',' && !inQuotes) {
                row.push(value);
                value = '';
            } else if ((char === '\n' || char === '\r') && !inQuotes) {
                if (char === '\r' && next === '\n') i++;
                row.push(value);
                value = '';
                if (row.some((cell) => cell.trim() !== '')) rows.push(row);
                row = [];
            } else {
                value += char;
            }
        }

        if (value.length || row.length) {
            row.push(value);
            if (row.some((cell) => cell.trim() !== '')) rows.push(row);
        }

        return rows;
    }

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

    function extractAnswersForForm(rows, formNumber) {
        let headers = null;
        let selectedRow = null;

        for (const row of rows) {
            if (!row.length) continue;
            if ((row[0] || '').includes('שאלון')) {
                headers = row;
                continue;
            }
            if (headers && (row[0] || '').trim() === formNumber.trim()) {
                selectedRow = row;
                break;
            }
        }

        if (!headers || !selectedRow) {
            throw new Error(`לא נמצאה שורת שאלון ${formNumber} בקובץ התשובות.`);
        }

        const answers = new Map();

        for (let i = 0; i < headers.length; i++) {
            const header = (headers[i] || '').trim();
            if (!header.startsWith('שאלה')) continue;

            const qNumMatch = header.match(/\d+/);
            if (!qNumMatch) continue;

            const questionNumber = Number(qNumMatch[0]);
            const rawCell = String(selectedRow[i] || '');

            const answerMatch = rawCell.match(/\((\d+)\)/);
            if (answerMatch) {
                answers.set(questionNumber, Number(answerMatch[1]) - 1);
                continue;
            }

            if (rawCell.includes('מבוטלת') || rawCell.includes('והת')) {
                answers.set(questionNumber, null);
            }
        }

        return answers;
    }

    function mergeAnswers(questions, answerMap) {
        return questions.map((question, index) => {
            const answer = answerMap.get(index + 1);
            if (typeof answer === 'number' && answer >= 0 && answer < question.options.length) {
                return { ...question, correctIndex: answer, shuffleOptions: false };
            }
            return { ...question, shuffleOptions: false };
        });
    }

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

            // Image thumbnail
            if (question.image) {
                const imgWrap = document.createElement('div');
                imgWrap.style.cssText = 'grid-column:1/-1;display:flex;align-items:center;gap:8px;margin-bottom:6px;';
                const thumb = document.createElement('img');
                thumb.src = question.image;
                thumb.style.cssText = 'max-height:120px;max-width:100%;border-radius:8px;border:1px solid var(--border-color);cursor:zoom-in;';
                thumb.title = 'לחץ להצגה מלאה';
                thumb.addEventListener('click', () => window.open(question.image, '_blank'));
                const removeBtn = document.createElement('button');
                removeBtn.type = 'button';
                removeBtn.textContent = '✕ הסר תמונה';
                removeBtn.style.cssText = 'font-size:.8rem;padding:4px 8px;';
                removeBtn.addEventListener('click', () => {
                    delete state.questions[index].image;
                    imgWrap.remove();
                });
                imgWrap.append(thumb, removeBtn);
                card.appendChild(imgWrap);
            }

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

            if (state.proofMode && question.sourcePage && state.proofPageImages.length) {
                const sourcePageIndex = Number(question.sourcePage) - 1;
                const sourcePageImage = state.proofPageImages[sourcePageIndex];
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
                    sourceImg.addEventListener('click', () => window.open(sourcePageImage, '_blank'));
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
            const [indexHtml, styleCss, appJs] = await Promise.all([
                fetch('quiz_player.html').then((response) => {
                    if (!response.ok) throw new Error(`HTTP ${response.status}`);
                    return response.text();
                }),
                fetch('style.css').then((response) => {
                    if (!response.ok) throw new Error(`HTTP ${response.status}`);
                    return response.text();
                }),
                fetch('app.js').then((response) => {
                    if (!response.ok) throw new Error(`HTTP ${response.status}`);
                    return response.text();
                })
            ]);

            state.templateCache = { indexHtml, styleCss, appJs };
            return state.templateCache;
        } catch (err) {
            if (window.location.protocol === 'file:') {
                throw new Error('לא ניתן ליצור קובץ מבחן בעת הרצה ישירה מקובץ מקומי (file://). דפדפנים חוסמים טעינת תבניות מסיבות אבטחה. הפעל שרת מקומי (כגון Live Server או npx serve) ונסה שוב.');
            }
            throw new Error(`טעינת תבניות המבחן נכשלה (${err.message}). ודא שהקבצים quiz_player.html, style.css, app.js קיימים בתיקייה.`);
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
        const shouldCompress = elements.compressExportImages ? elements.compressExportImages.checked : true;

        const cleanedQuestions = await Promise.all(state.questions.map(async (q) => {
            let img = q.image;
            if (shouldCompress && img) {
                img = await compressImageBase64(img, 0.75);
            }
            return {
                question: normalizeWhitespace(q.question),
                options: q.options.map((opt) => normalizeWhitespace(opt)),
                correctIndex: q.correctIndex,
                ...(q.shuffleOptions ? { shuffleOptions: true } : {}),
                ...(img ? { image: img } : {}) // embed base64 image directly
            };
        }));

        const { indexHtml, styleCss, appJs } = await getTemplateSources();
        const inlinedCssHtml = indexHtml.replace(
            /<link rel="stylesheet" href="style\.css">/,
            `<style>${styleCss}</style>`
        );

        const appScript = appJs.replace(/<\/(script)/gi, '<\\/$1');
        const payload = JSON.stringify(cleanedQuestions, null, 2);

        return inlinedCssHtml.replace(
            /<script src="app\.js"><\/script>/,
            `<script>window.__INLINE_QUESTIONS__=${payload};(function(){const originalFetch=window.fetch.bind(window);window.fetch=function(input,init){const url=typeof input==='string'?input:(input&&input.url)||'';if(typeof url==='string'&&/questions\\.json(?:\\?|$)/.test(url)){return Promise.resolve(new Response(JSON.stringify(window.__INLINE_QUESTIONS__),{headers:{'Content-Type':'application/json'}}));}return originalFetch(input,init);};})();</script><script>${appScript}</script>`
        );
    }

    async function runParse() {
        disableOutputActions(true);
        elements.preview.innerHTML = '';
        state.proofPageImages = [];

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

        setStatus('מחלץ טקסט מה-PDF...');
        const extracted = await extractPdfText(pdfBufferForParse);

        let examText = extracted.text;
        let sourcePages = extracted.rawPages;
        const useLlmExtraction = llmPolicy === 'force_llm' || (llmPolicy === 'auto' && extracted.isScanned && ocrEngine !== 'offline_local');
        const useOfflineOcr = extracted.isScanned && (llmPolicy === 'force_no_llm' || ocrEngine === 'offline_local');

        if (!extracted.isScanned && llmPolicy !== 'force_llm') {
            setStatus('זוהה PDF דיגיטלי. ממשיך בעיבוד מקומי ללא LLM.');
        }

        if (useOfflineOcr) {
            setStatus('זוהה PDF סרוק. מפעיל OCR חינמי בדפדפן; האיכות כנראה תהיה נמוכה יותר מ-Gemini.');
            const offlineExtraction = await extractTextViaOfflineOcr(extracted.pdf);
            examText = offlineExtraction.text;
            sourcePages = offlineExtraction.pages;
            state.proofPageImages = offlineExtraction.pagePreviews || [];
        } else if (useLlmExtraction) {
            apiKey = await resolveGeminiApiKey(true);
            if (ocrEngine === 'gemini_native') {
                setStatus(extracted.isScanned ? 'זוהה PDF סרוק. מנסה חילוץ עם Gemini Native PDF...' : 'נבחר מצב LLM כפוי. שולח את ה-PDF ל-Gemini Native PDF...');
                const nativeExtraction = await extractTextViaGeminiNativePdf(pdfFileToParse, extracted.pdf, apiKey);
                examText = nativeExtraction.text;
                sourcePages = nativeExtraction.pages;
                const previews = await renderAllPdfPageImages(extracted.pdf);
                state.proofPageImages = previews.pagePreviews || [];
            } else {
                setStatus(extracted.isScanned ? 'זוהה PDF סרוק. מנסה חילוץ עם Gemini (Page Chunking)...' : 'נבחר מצב LLM כפוי. שולח עמודים ל-Gemini OCR...');
                const geminiExtraction = await extractTextViaGemini(extracted.pdf, apiKey);
                examText = geminiExtraction.text;
                sourcePages = geminiExtraction.pages;
                state.proofPageImages = geminiExtraction.pagePreviews || [];
            }
        } else if (extracted.isScanned) {
            setStatus('זוהה PDF סרוק במצב מקומי בלבד. מנסה להמשיך בלי LLM, אבל התוצאה עלולה להיות חלקית.');
        }

        let parsedQuestions;
        try {
            parsedQuestions = parseQuestionsFromText(examText, sourcePages, extracted.pageImages);
        } catch (error) {
            if (useLlmExtraction) {
                setStatus('פענוח ה-LLM לא היה בפורמט צפוי. מנסה פרסור מקומי מהטקסט הדיגיטלי...');
                parsedQuestions = parseQuestionsFromText(extracted.text, extracted.rawPages, extracted.pageImages);
            } else {
                throw error;
            }
        }

        if (useLlmExtraction && ocrEngine === 'gemini_chunked' && parsedQuestions.length < 10) {
            setStatus('זוהו מעט שאלות. מנסה פענוח מדויק יותר עמוד-עמוד...');
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

        // Render full-page images for questions that mention visuals but lack embedded images.
        for (const q of parsedQuestions) {
            if (q._needsPageRender && !q.image && extracted.pdf) {
                try {
                    const page = await extracted.pdf.getPage(q.sourcePage);
                    q.image = await extractPageImage(page);
                } catch { /* skip if render fails */ }
            }
            delete q._needsPageRender;
        }

        if (answerRows && formNumber) {
            const answerMap = extractAnswersForForm(answerRows, formNumber);
            state.questions = mergeAnswers(parsedQuestions, answerMap);
        } else {
            // No answer file: Default correct answer to index 0 ('א')
            state.questions = parsedQuestions.map(q => ({
                ...q,
                correctIndex: 0,
                shuffleOptions: true
            }));
        }

        // Verification step using Gemini Pro
        if (llmPolicy === 'force_llm' && apiKey) {
            state.questions = await verifyTestWithGemini(state.questions, apiKey);
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

    elements.downloadQuiz.addEventListener('click', async () => {
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
        try {
            setStatus('פותח תצוגת מבחן...');
            const html = await createStandaloneQuizHtml();
            const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.target = '_blank';
            a.rel = 'noopener';
            a.click();
            setTimeout(() => URL.revokeObjectURL(url), 60_000);
            setStatus('המבחן נפתח בלשונית חדשה.');
        } catch (error) {
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
                question: rawQuestion,
                options: options,
                correctIndex: correctIndex,
                image: item.image || item.pageImage || null,
                sourcePage: item.sourcePage || item.page || (index + 1),
                shuffleOptions: shuffleOptions
            };
        });
    }

    // ── PDF Page Sidebar & Thumbnail Generator ─────────────────────────────────
    async function loadPdfSidebar(pdfBytesInput) {
        if (pdfBytesInput) {
            state.pdfBytes = new Uint8Array(pdfBytesInput);
        }
        state.pdfPagesState = [];
        if (elements.pageThumbnailsContainer) elements.pageThumbnailsContainer.innerHTML = '';

        if (!state.pdfBytes || state.pdfBytes.length === 0 || !window.pdfjsLib) return;

        try {
            const freshCopy = new Uint8Array(state.pdfBytes);
            const loadingTask = window.pdfjsLib.getDocument({ data: freshCopy });
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

    const DEFAULT_LLM_PROMPT = `Please extract all multiple-choice questions into a clean \`questions.json\` array for an interactive quiz app.

---------------------------------------------------------------------------
EXTRACTION & PROOFREADING RULES:
---------------------------------------------------------------------------
1. HEBREW TEXT ORDER:
   - Extract text in natural, correct Hebrew reading order (sentences left-to-right, Hebrew words right-to-left).
   - Do NOT reverse word order or letters.
   - Ensure mixed Hebrew and English/scientific terms (e.g. "ATP", "DNA", "pH") read correctly.

2. OPTIONS FORMATTING:
   - Extract all choices into the \`options\` array (questions can have 4, 5, 6 or more choices).
   - Remove option letter prefixes (e.g. convert "א. תגובה מהירה" to "תגובה מהירה").

3. DIAGRAM & IMAGE REFERENCES (\`pageImage\`):
   - If a question includes or references a visual element (diagram, chart, graph, illustration), set \`"pageImage": "pages_output/page_X.png"\` where X is the page number (e.g., \`"pages_output/page_4.png"\`).
   - If the question is purely text-based, DO NOT include the \`pageImage\` key.

4. ANSWER KEY (\`correctIndex\`):
   - Set \`"correctIndex": 0\` by default.

5. SELF-PROOFREADING PASS:
   - Once extraction is complete, perform a self-proofreading pass to verify Hebrew word order, punctuation, and JSON formatting before outputting.

---------------------------------------------------------------------------
REQUIRED JSON SCHEMA:
---------------------------------------------------------------------------
[
  {
    "question": "שאלה לדוגמה בעברית...",
    "options": [
      "תשובה ראשונה",
      "תשובה שנייה",
      "תשובה שלישית",
      "תשובה רביעית"
    ],
    "correctIndex": 0,
    "sourcePage": 1
  }
]

---------------------------------------------------------------------------
OUTPUT & DELIVERABLE REQUIREMENTS:
---------------------------------------------------------------------------
1. Provide your final response either as a downloadable \`questions.json\` file OR as a single clean code block formatted for easy copy-pasting into \`questions.json\`.
2. Do NOT include conversational commentary or explanation text. Output raw, valid JSON only.`;

    if (elements.llmPromptBox) {
        elements.llmPromptBox.value = DEFAULT_LLM_PROMPT;
    }

    // Preset buttons & Clean PDF download listeners
    elements.presetStdBtn?.addEventListener('click', applyStandardFilter);
    elements.presetStdBtnMain?.addEventListener('click', applyStandardFilter);
    elements.presetEvenOddBtn?.addEventListener('click', toggleEvenOddFilter);
    elements.presetBlankBtn?.addEventListener('click', toggleEvenOddFilter);
    elements.presetSelectAllBtn?.addEventListener('click', () => selectAllPages(true));
    elements.presetDeselectAllBtn?.addEventListener('click', () => selectAllPages(false));
    elements.downloadCleanPdf?.addEventListener('click', downloadCleanPdf);
    elements.downloadCleanPdfMain?.addEventListener('click', downloadCleanPdf);

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
                showToast('יש להעלות קודם קובץ questions.json!', 'error');
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
            if (explicit && (!answerMap || !Object.keys(answerMap).length)) {
                showToast(`לא נמצאו תשובות לשאלון ${formNumber} בקובץ שנבחר.`, 'error');
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

    elements.mergeAnswersBtn?.addEventListener('click', () => tryMergeAnswersFromCsv(true));

    // jsonFile Upload Listener
    elements.jsonFile?.addEventListener('change', async () => {
        const file = elements.jsonFile.files?.[0];
        if (!file) return;
        try {
            setStatus(`מעבד קובץ ${file.name}...`);
            const text = await file.text();
            const rawData = JSON.parse(text);
            const normalizedQuestions = normalizeQuestionsJson(rawData);

            state.questions = normalizedQuestions;
            renderPreview();
            disableOutputActions(false);
            setStatus(`נטענו ${normalizedQuestions.length} שאלות בהצלחה מקובץ ${file.name}!`, false, true);

            await tryMergeAnswersFromCsv();
        } catch (error) {
            console.error('Error loading JSON file:', error);
            setStatus(error.message || `נכשלה טעינת קובץ ${file.name}.`, true);
        }
    });

    elements.csvFile?.addEventListener('change', tryMergeAnswersFromCsv);
    elements.formNumber?.addEventListener('change', tryMergeAnswersFromCsv);
    elements.formNumber?.addEventListener('blur', tryMergeAnswersFromCsv);

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

    elements.showApiSettingsBtn?.addEventListener('click', () => toggleProcessingSettings(true));
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

    elements.htmlFile.addEventListener('change', async () => {
        const file = elements.htmlFile.files?.[0];
        if (!file) return;
        try {
            setStatus('טוען מבחן קיים...');
            const html = await file.text();
            const match = html.match(/window\.__INLINE_QUESTIONS__\s*=\s*(\[[\s\S]*?\])\s*;/);
            if (!match) throw new Error('לא נמצאו שאלות מוטמעות בקובץ.');
            const questions = JSON.parse(match[1]);
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

    elements.pdfFile.addEventListener('change', async () => {
        const file = elements.pdfFile.files?.[0];
        if (!file) {
            setPdfTypeNote('');
            if (elements.scannedActionsBox) elements.scannedActionsBox.classList.add('hidden');
            if (elements.pdfSidebarCard) elements.pdfSidebarCard.classList.add('hidden');
            if (elements.builderLayout) elements.builderLayout.classList.add('no-sidebar');
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

            // Load sidebar thumbnails & page selection state
            await loadPdfSidebar(state.pdfArrayBuffer.slice(0));
        } catch (error) {
            setPdfTypeNote(error.message || 'לא ניתן היה לזהות את סוג ה-PDF.', 'error');
        }
    });

    document.querySelector('[data-target="pdf-file"]')?.addEventListener('click', () => {
        setPdfTypeNote('');
        if (elements.scannedActionsBox) elements.scannedActionsBox.classList.add('hidden');
        if (elements.pdfSidebarCard) elements.pdfSidebarCard.classList.add('hidden');
        if (elements.builderLayout) elements.builderLayout.classList.add('no-sidebar');
    });
});
