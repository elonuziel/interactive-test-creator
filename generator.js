document.addEventListener('DOMContentLoaded', () => {
    const STORAGE = {
        theme: 'theme',
        builderPrefill: 'builderPrefillV1'
    };

    const GEMINI_CONFIG = {
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
        proofPageImages: [],
        proofMode: true,
        geminiRuntimeHealth: null
    };

    const elements = {
        pdfFile: document.getElementById('pdf-file'),
        csvFile: document.getElementById('csv-file'),
        formNumber: document.getElementById('form-number'),
        ocrEngine: document.getElementById('ocr-engine'),
        llmPolicy: document.getElementById('llm-policy'),
        htmlFile: document.getElementById('html-file'),
        pdfTypeNote: document.getElementById('pdf-type-note'),
        runParse: document.getElementById('run-parse'),
        downloadQuiz: document.getElementById('download-quiz'),
        takeQuiz: document.getElementById('take-quiz'),
        status: document.getElementById('status'),
        geminiRuntimeNote: document.getElementById('gemini-runtime-note'),
        preview: document.getElementById('preview'),
        proofModeToggle: document.getElementById('proof-mode-toggle'),
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

    function setStatus(message, isError = false) {
        elements.status.textContent = message;
        elements.status.classList.toggle('muted', !isError);
        elements.status.style.color = isError ? 'var(--danger)' : 'var(--text-primary)';
    }

    function applyBuilderPrefill() {
        const raw = localStorage.getItem(STORAGE.builderPrefill);
        if (!raw) return;

        try {
            const payload = JSON.parse(raw);
            if (payload && typeof payload === 'object') {
                if (typeof payload.formNumber === 'string' && payload.formNumber.trim()) {
                    elements.formNumber.value = payload.formNumber.trim();
                }
                if (typeof payload.llmPolicy === 'string' && elements.llmPolicy.querySelector(`option[value="${payload.llmPolicy}"]`)) {
                    elements.llmPolicy.value = payload.llmPolicy;
                }
                if (typeof payload.ocrEngine === 'string' && elements.ocrEngine.querySelector(`option[value="${payload.ocrEngine}"]`)) {
                    elements.ocrEngine.value = payload.ocrEngine;
                }
                setStatus('הוגדרו ערכי ברירת מחדל ממסך ה-React. אפשר להמשיך בהעלאת קבצים ולהפעיל ניתוח.');
            }
        } catch {
            // Ignore malformed prefill payloads.
        } finally {
            localStorage.removeItem(STORAGE.builderPrefill);
        }
    }

    setTheme(theme);
    elements.themeToggle.addEventListener('click', () => setTheme(theme === 'light' ? 'dark' : 'light'));
    applyBuilderPrefill();
    if (elements.proofModeToggle) {
        state.proofMode = !!elements.proofModeToggle.checked;
        elements.proofModeToggle.addEventListener('change', () => {
            state.proofMode = !!elements.proofModeToggle.checked;
            renderPreview();
        });
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

    function setGeminiRuntimeNote(message = '', tone = 'neutral') {
        const note = elements.geminiRuntimeNote;
        if (!note) return;
        note.textContent = message;
        note.classList.toggle('hidden', !message);
        note.classList.remove('is-loading', 'is-digital', 'is-scanned', 'is-error');
        if (!message) return;
        if (tone === 'loading') note.classList.add('is-loading');
        else if (tone === 'ok') note.classList.add('is-digital');
        else if (tone === 'warn') note.classList.add('is-scanned');
        else if (tone === 'error') note.classList.add('is-error');
    }

    function isGeminiMissingKeyMessage(message) {
        return /gemini api key is not configured on server/i.test(String(message || ''));
    }

    function normalizeGeminiErrorMessage(message) {
        if (isGeminiMissingKeyMessage(message)) {
            return 'Gemini לא מוגדר בשרת. יש להגדיר GEMINI_API_KEY או GOOGLE_API_KEY בסביבת הריצה, או לעבור ל-OCR מקומי חינמי.';
        }
        return message;
    }

    async function refreshGeminiRuntimeHealth() {
        setGeminiRuntimeNote('בודק זמינות Gemini בשרת...', 'loading');
        try {
            const response = await fetch('/api/gemini/health');
            if (!response.ok) {
                throw new Error(`Gemini health check failed: ${response.status}`);
            }

            const payload = await response.json();
            state.geminiRuntimeHealth = payload;
            if (payload.configured) {
                setGeminiRuntimeNote('Gemini זמין בשרת ומוכן לעיבוד OCR.', 'ok');
            } else {
                setGeminiRuntimeNote('Gemini לא מוגדר בשרת. אם צריך OCR סרוק, הגדר מפתח בשרת או בחר OCR מקומי.', 'warn');
            }
            return payload;
        } catch {
            state.geminiRuntimeHealth = { ok: false, configured: false };
            setGeminiRuntimeNote('לא ניתן לאמת זמינות Gemini מהשרת כרגע. אפשר להמשיך עם OCR מקומי.', 'error');
            return state.geminiRuntimeHealth;
        }
    }

    async function ensureGeminiRuntimeReady() {
        const health = state.geminiRuntimeHealth || await refreshGeminiRuntimeHealth();
        if (health && health.configured) return;
        throw new Error('Gemini לא מוגדר בשרת. הגדר GEMINI_API_KEY/GOOGLE_API_KEY או בחר OCR מקומי (offline_local).');
    }

    async function callGeminiApiViaProxy(parts, generationConfig) {
        const response = await fetch('/api/gemini/generate-content', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                modelCandidates: GEMINI_CONFIG.preferredModels,
                contents: [{ parts }],
                generationConfig
            })
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(normalizeGeminiErrorMessage(errorText || 'Gemini proxy request failed.'));
        }

        const payload = await response.json();
        const responseParts = payload.candidates?.[0]?.content?.parts || [];
        return responseParts.map((part) => part.text || '').join('\n').trim();
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

    async function extractPdfText(arrayBuffer) {
        if (!window.pdfjsLib?.getDocument) {
            throw new Error('PDF.js לא נטען. רענן את העמוד ונסה שוב.');
        }

        const loadingTask = window.pdfjsLib.getDocument({ data: arrayBuffer });
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

    async function detectPdfType(arrayBuffer) {
        if (!window.pdfjsLib?.getDocument) {
            throw new Error('PDF.js לא נטען. רענן את העמוד ונסה שוב.');
        }

        const loadingTask = window.pdfjsLib.getDocument({ data: arrayBuffer });
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

    function delay(ms) {
        return new Promise((resolve) => setTimeout(resolve, ms));
    }

    async function callGeminiOcr(imageDatas) {
        const prompt = [
            'You are an OCR engine for scanned Hebrew exams.',
            'Extract visible text exactly as printed.',
            'Do NOT translate, summarize, reorder, paraphrase, or explain.',
            'Keep Hebrew text in its original reading order.',
            'Preserve line breaks and option markers exactly.',
            'Preserve question and option structure (e.g., "שאלה מספר", "א.", "ב.", "ג.", "ד.", "ה.", "ו." etc.).',
            'If text is unclear, keep best-effort literal OCR and do not invent content.',
            'Return plain text only.',
            '',
            'CRITICAL: You are receiving multiple page images.',
            'You MUST separate each page output with the exact delimiter "---PAGE_BOUNDARY---" on its own line.'
        ].join('\n');

        const parts = [{ text: prompt }];
        for (const data of imageDatas) {
            parts.push({ inlineData: { mimeType: 'image/png', data } });
        }

        const text = await callGeminiApiViaProxy(parts, {
            temperature: 0,
            topP: 0.1,
            maxOutputTokens: 8192
        });

        if (!text) {
            throw new Error('Gemini החזיר טקסט ריק מהפרוקסי.');
        }

        const extractedPages = text.split(/---PAGE_BOUNDARY---/i).map((s) => s.trim());
        while (extractedPages.length < imageDatas.length) {
            extractedPages.push('');
        }
        return extractedPages;
    }

    async function extractTextViaGemini(pdf, chunkSizeOverride = null) {
        const pages = [];
        const { imageDatas, pagePreviews } = await renderAllPdfPageImages(pdf);

        const CHUNK_SIZE = Math.max(1, Number(chunkSizeOverride || GEMINI_CONFIG.ocrChunkSize) || 1);
        for (let i = 0; i < imageDatas.length; i += CHUNK_SIZE) {
            const chunk = imageDatas.slice(i, i + CHUNK_SIZE);
            setStatus(`מפענח עמודים ${i + 1}-${Math.min(i + CHUNK_SIZE, imageDatas.length)} מתוך ${imageDatas.length} ב-Gemini...`);
            
            const chunkPagesText = await callGeminiOcr(chunk);
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


    async function extractTextViaGeminiNativePdf(pdfFile, pdf) {
        setStatus('מעלה את מסמך ה-PDF ישירות ל-Gemini (Native PDF)...');

        const base64Pdf = await fileToBase64(pdfFile);
        const prompt = [
            'You are an OCR engine for scanned Hebrew exams.',
            'Extract visible text exactly as printed. Keep Hebrew text in its original reading order.',
            'Do NOT translate, summarize, reorder, paraphrase, or explain.',
            'Preserve line breaks and option markers exactly.',
            'Return plain text only.',
            '',
            'CRITICAL: You are receiving a multipage PDF.',
            'You MUST insert the exact delimiter "---PAGE_BOUNDARY---" on its own line between the text of EACH physical page of the PDF to allow us to map text back to the original page number.'
        ].join('\n');

        const text = await callGeminiApiViaProxy(
            [
                { text: prompt },
                { inlineData: { mimeType: 'application/pdf', data: base64Pdf } }
            ],
            {
                temperature: 0,
                topP: 0.1,
                maxOutputTokens: 8192
            }
        );

        if (!text) {
            throw new Error('Gemini Native PDF OCR failed: התקבלה תשובה ריקה מהפרוקסי.');
        }

        const extractedPages = text.split(/---PAGE_BOUNDARY---/i).map((s) => s.trim());
        
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


    async function verifyTestWithGemini(parsedQuestions) {
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

        let text;
        try {
            text = await callGeminiApiViaProxy([{ text: prompt }], {
                temperature: 0.1,
                topP: 0.8,
                maxOutputTokens: 8192
            });
        } catch {
            console.warn('Gemini verification failed, using original parsed questions.');
            return parsedQuestions;
        }
        
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

        const [indexHtml, styleCss, appJs] = await Promise.all([
            fetch('index.html').then((response) => response.text()),
            fetch('style.css').then((response) => response.text()),
            fetch('app.js').then((response) => response.text())
        ]);

        state.templateCache = { indexHtml, styleCss, appJs };
        return state.templateCache;
    }

    async function createStandaloneQuizHtml() {
        const cleanedQuestions = state.questions.map((q) => ({
            question: normalizeWhitespace(q.question),
            options: q.options.map((opt) => normalizeWhitespace(opt)),
            correctIndex: q.correctIndex,
            ...(q.shuffleOptions ? { shuffleOptions: true } : {}),
            ...(q.image ? { image: q.image } : {}) // embed base64 image directly
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

        const pdfBuffer = await pdf.arrayBuffer();
        const pdfBufferForParse = pdfBuffer.slice(0);
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

        if (useLlmExtraction) {
            await ensureGeminiRuntimeReady();
        }

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
            if (ocrEngine === 'gemini_native') {
                setStatus(extracted.isScanned ? 'זוהה PDF סרוק. מנסה חילוץ עם Gemini Native PDF...' : 'נבחר מצב LLM כפוי. שולח את ה-PDF ל-Gemini Native PDF...');
                const nativeExtraction = await extractTextViaGeminiNativePdf(pdf, extracted.pdf);
                examText = nativeExtraction.text;
                sourcePages = nativeExtraction.pages;
                const previews = await renderAllPdfPageImages(extracted.pdf);
                state.proofPageImages = previews.pagePreviews || [];
            } else {
                setStatus(extracted.isScanned ? 'זוהה PDF סרוק. מנסה חילוץ עם Gemini (Page Chunking)...' : 'נבחר מצב LLM כפוי. שולח עמודים ל-Gemini OCR...');
                const geminiExtraction = await extractTextViaGemini(extracted.pdf);
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
            const fallbackExtraction = await extractTextViaGemini(extracted.pdf, 1);
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
        if (llmPolicy === 'force_llm') {
            state.questions = await verifyTestWithGemini(state.questions);
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
            return;
        }

        try {
            setPdfTypeNote('מזהה את סוג ה-PDF...', 'loading');
            const pdfBuffer = await file.arrayBuffer();
            const detection = await detectPdfType(pdfBuffer);
            setPdfTypeNote(
                `${detection.pdfTypeLabel}: ${detection.recommendation}`,
                detection.isScanned ? 'scanned' : 'digital'
            );
        } catch (error) {
            setPdfTypeNote(error.message || 'לא ניתן היה לזהות את סוג ה-PDF.', 'error');
        }
    });

    document.querySelector('[data-target="pdf-file"]')?.addEventListener('click', () => {
        setPdfTypeNote('');
    });

    refreshGeminiRuntimeHealth();
});
