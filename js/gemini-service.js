(function (root, factory) {
    if (typeof define === 'function' && define.amd) {
        define([], factory);
    } else if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.GeminiService = factory();
    }
}(typeof self !== 'undefined' ? self : this, function () {
    'use strict';

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

    let cachedModelCandidates = null;

    function decodeBase64(base64) {
        if (typeof atob === 'function') {
            const str = atob(base64);
            const bytes = new Uint8Array(str.length);
            for (let i = 0; i < str.length; i++) bytes[i] = str.charCodeAt(i);
            return bytes;
        } else if (typeof Buffer !== 'undefined') {
            return new Uint8Array(Buffer.from(base64, 'base64'));
        }
        return new Uint8Array();
    }

    async function decryptSingleKey(passcode, keyObj) {
        if (!keyObj || !keyObj.encryptedKeyB64 || !keyObj.ivB64 || !keyObj.saltB64 || !passcode) {
            return '';
        }

        try {
            const cryptoObj = typeof crypto !== 'undefined' ? crypto : (typeof window !== 'undefined' ? window.crypto : null);
            if (!cryptoObj?.subtle) return '';

            const encoder = new TextEncoder();
            const keyMaterial = await cryptoObj.subtle.importKey(
                'raw',
                encoder.encode(passcode),
                'PBKDF2',
                false,
                ['deriveKey']
            );

            const aesKey = await cryptoObj.subtle.deriveKey(
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

            const decrypted = await cryptoObj.subtle.decrypt(
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
        return decryptSingleKey(passcode, EMBEDDED_KEY);
    }

    function requestGeminiCredentials(elements) {
        return new Promise((resolve, reject) => {
            const popup = elements?.credentialPopup;
            const apiKeyInput = elements?.credentialApiKey;
            const passcodeInput = elements?.credentialPasscode;
            const submitButton = elements?.credentialSubmit;
            const cancelButton = elements?.credentialCancel;

            if (!popup || !apiKeyInput || !passcodeInput || !submitButton || !cancelButton) {
                reject(new Error('ממשק הזנת האישורים לא נטען. רענן את העמוד ונסה שוב.'));
                return;
            }

            apiKeyInput.value = elements.apiKey?.value?.trim() || '';
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

    async function resolveGeminiApiKey(elements, allowPrompt = false) {
        const typedApiKey = elements?.apiKey?.value?.trim() || '';
        if (typedApiKey) {
            if (typedApiKey.toLowerCase().includes('elza')) {
                throw new Error('שרת Elza בביטול / יוצא משימוש (Phasing Out). אנא הזן מפתח AQ API תקין (AQ...) מ-Google AI Studio.');
            }
            return typedApiKey;
        }

        const currentPasscode = elements?.passcode?.value?.trim() || '';
        if (currentPasscode) {
            const decrypted = await decryptEmbeddedApiKey(currentPasscode);
            if (decrypted) {
                if (elements.apiKey) elements.apiKey.value = decrypted;
                return decrypted;
            }
            if (!allowPrompt) {
                throw new Error('ה-Passcode שגוי או שמפתח ה-API המוצפן לא הוגדר נכון בקובץ generator.js.');
            }
        }

        if (!allowPrompt) {
            return '';
        }

        const { apiKey: promptedApiKey, passcode: promptedPasscode } = await requestGeminiCredentials(elements);
        if (promptedApiKey) {
            if (promptedApiKey.toLowerCase().includes('elza')) {
                throw new Error('שרת Elza בביטול / יוצא משימוש (Phasing Out). אנא הזן מפתח AQ API תקין (AQ...) מ-Google AI Studio.');
            }
            if (elements.apiKey) elements.apiKey.value = promptedApiKey;
            return promptedApiKey;
        }

        if (promptedPasscode) {
            if (elements.passcode) elements.passcode.value = promptedPasscode;
            const decrypted = await decryptEmbeddedApiKey(promptedPasscode);
            if (decrypted) {
                if (elements.apiKey) elements.apiKey.value = decrypted;
                return decrypted;
            }
            throw new Error('ה-Passcode שגוי או שמפתח ה-API המוצפן לא הוגדר נכון בקובץ generator.js.');
        }

        throw new Error('העיבוד הנוכחי דורש Gemini. הזן API Key או Passcode כדי להמשיך, או עבור למצב ללא LLM.');
    }

    function buildGeminiEndpoint(version, model, apiKey) {
        return `https://generativelanguage.googleapis.com/${version}/models/${model}:generateContent?key=${encodeURIComponent(apiKey)}`;
    }

    function normalizeModelName(name) {
        if (!name) return '';
        return name.startsWith('models/') ? name.slice('models/'.length) : name;
    }

    async function discoverGeminiModelCandidates(apiKey) {
        if (cachedModelCandidates) {
            return cachedModelCandidates;
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

        cachedModelCandidates = discovered;
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

    async function callGeminiOcr(apiKey, imageDatas, task = null, statusCallback = null) {
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
            if (task && task.isAborted()) {
                throw new Error('הפעולה בוטלה על ידי המשתמש.');
            }
            const endpoint = buildGeminiEndpoint(candidate.version, candidate.model, apiKey);

            for (let retryCount = 0; retryCount <= GEMINI_CONFIG.maxQuotaRetries; retryCount++) {
                if (task && task.isAborted()) {
                    throw new Error('הפעולה בוטלה על ידי המשתמש.');
                }
                const response = await fetch(endpoint, {
                    method: 'POST',
                    signal: task ? task.signal : undefined,
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
                    return [text];
                }

                const errorText = await response.text();
                const errorInfo = getGeminiErrorInfo(response.status, errorText);

                if (errorInfo.code === 'quota' && retryCount < GEMINI_CONFIG.maxQuotaRetries) {
                    const delayMs = computeRetryDelayMs(response, retryCount);
                    const waitSec = Math.ceil(delayMs / 1000);
                    const msg = `Gemini החזיר 429. ממתין ${waitSec} שניות ומנסה שוב...`;
                    if (task) {
                        task.update(task.percent || 30, msg);
                    } else if (statusCallback) {
                        statusCallback(msg);
                    }
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

    async function extractTextViaGemini(pdf, apiKey, { chunkSizeOverride = null, task = null, statusCallback = null, renderAllPdfPageImagesFn, maybeFixHebrewWordOrderFn } = {}) {
        if (!apiKey) {
            throw new Error('ה-PDF נראה סרוק ואין מפתח Gemini זמין לחילוץ טקסט. הזן API key או Passcode תקין.');
        }

        const pages = [];
        const { imageDatas, pagePreviews } = await renderAllPdfPageImagesFn(pdf, task);

        const CHUNK_SIZE = Math.max(1, Number(chunkSizeOverride || GEMINI_CONFIG.ocrChunkSize) || 1);
        const totalChunks = Math.ceil(imageDatas.length / CHUNK_SIZE);
        let chunkIndex = 0;

        for (let i = 0; i < imageDatas.length; i += CHUNK_SIZE) {
            if (task && task.isAborted()) {
                throw new Error('הפעולה בוטלה על ידי המשתמש.');
            }
            chunkIndex++;
            const chunk = imageDatas.slice(i, i + CHUNK_SIZE);
            const startPage = i + 1;
            const endPage = Math.min(i + CHUNK_SIZE, imageDatas.length);
            const currentPercent = 25 + Math.round((chunkIndex / totalChunks) * 65);
            const detailMsg = `מפענח עמודים ${startPage}-${endPage} מתוך ${imageDatas.length} ב-Gemini (צ'אנק ${chunkIndex}/${totalChunks})...`;

            if (task) {
                task.update(currentPercent, detailMsg);
            } else if (statusCallback) {
                statusCallback(detailMsg);
            }

            const chunkPagesText = await callGeminiOcr(apiKey, chunk, task, statusCallback);
            const fixFn = maybeFixHebrewWordOrderFn || (str => str);
            pages.push(...chunkPagesText.map((pageText) => fixFn(pageText || '')));

            if (i + CHUNK_SIZE < imageDatas.length && GEMINI_CONFIG.interPageDelayMs > 0) {
                if (task) {
                    task.update(currentPercent, `ממתין בין קריאות API (${GEMINI_CONFIG.interPageDelayMs / 1000} שניות)...`);
                }
                await delay(GEMINI_CONFIG.interPageDelayMs);
            }
        }

        return {
            pages,
            pagePreviews,
            text: pages.join('\n')
        };
    }

    async function extractTextViaGeminiNativePdf(pdfFile, pdf, apiKey, { mode = 'schema', task = null, statusCallback = null, fileToBase64Fn, renderPageImageDataFn, maybeFixHebrewWordOrderFn } = {}) {
        if (!apiKey) {
            throw new Error('ה-PDF נראה סרוק ואין מפתח Gemini זמין לחילוץ טקסט. הזן API key או Passcode תקין.');
        }

        if (task) {
            task.update(15, 'מעלה את מסמך ה-PDF ישירות ל-Gemini (Native PDF)...', { indeterminate: true });
        } else if (statusCallback) {
            statusCallback('מעלה את מסמך ה-PDF ישירות ל-Gemini (Native PDF)...');
        }

        const base64Pdf = await fileToBase64Fn(pdfFile);
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
            if (task && task.isAborted()) {
                throw new Error('הפעולה בוטלה על ידי המשתמש.');
            }
            const endpoint = buildGeminiEndpoint(candidate.version, candidate.model, apiKey);

            for (let retryCount = 0; retryCount <= GEMINI_CONFIG.maxQuotaRetries; retryCount++) {
                if (task && task.isAborted()) {
                    throw new Error('הפעולה בוטלה על ידי המשתמש.');
                }
                const response = await fetch(endpoint, {
                    method: 'POST',
                    signal: task ? task.signal : undefined,
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
                    const waitSec = Math.ceil(delayMs / 1000);
                    const msg = `Gemini החזיר 429 ב-Native PDF (${candidate.model}). ממתין ${waitSec} שניות ומנסה שוב...`;
                    if (task) {
                        task.update(40, msg);
                    } else if (statusCallback) {
                        statusCallback(msg);
                    }
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
            if (task && task.isAborted()) throw new Error('הפעולה בוטלה על ידי המשתמש.');
            if (task) {
                const prevPercent = 65 + Math.round((pageNumber / pdf.numPages) * 25);
                task.update(prevPercent, `מכין תצוגות מקדימות לעמוד ${pageNumber}/${pdf.numPages}...`);
            } else if (statusCallback) {
                statusCallback(`מכין תצוגות מקדימות לעמוד ${pageNumber}/${pdf.numPages}...`);
            }
            const page = await pdf.getPage(pageNumber);
            const imageData = await renderPageImageDataFn(page);
            pagePreviews.push(`data:image/png;base64,${imageData}`);
        }

        const fixFn = maybeFixHebrewWordOrderFn || (str => str);
        return {
            pages: extractedPages.map(p => fixFn(p || '')),
            pagePreviews,
            text: extractedPages.join('\n')
        };
    }

    async function verifyTestWithGemini(parsedQuestions, apiKey, { task = null, statusCallback = null } = {}) {
        if (task) {
            task.update(92, 'מבצע הגהה ותיקון שאלות עם Gemini (LLM Proofreader)...');
        } else if (statusCallback) {
            statusCallback('מבצע הגהה ותיקון של המבחן עם Gemini...');
        }
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
            if (task && task.isAborted()) break;
            const endpoint = buildGeminiEndpoint(candidate.version, candidate.model, apiKey);
            try {
                const response = await fetch(endpoint, {
                    method: 'POST',
                    signal: task ? task.signal : undefined,
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

    return {
        EMBEDDED_KEY,
        GEMINI_CONFIG,
        decodeBase64,
        decryptSingleKey,
        decryptEmbeddedApiKey,
        requestGeminiCredentials,
        resolveGeminiApiKey,
        buildGeminiEndpoint,
        normalizeModelName,
        discoverGeminiModelCandidates,
        sortGeminiModelCandidates,
        getGeminiErrorInfo,
        computeRetryDelayMs,
        callGeminiOcr,
        extractTextViaGemini,
        extractTextViaGeminiNativePdf,
        verifyTestWithGemini
    };
}));

