document.addEventListener('DOMContentLoaded', () => {
    'use strict';

    const state = {
        questions: [],
        templateCache: null,
        geminiModelCandidates: null,
        proofPageImages: [],
        proofMode: true,
        pdfArrayBuffer: null,
        pdfBytes: null,
        pdfPagesState: [],
        evenOddMode: null
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
        showDigitalPromptBtn: document.getElementById('show-digital-prompt-btn'),
        copyDigitalPromptBtn: document.getElementById('copy-digital-prompt-btn'),
        digitalLlmPromptBox: document.getElementById('digital-llm-prompt-box'),
        toggleProcessingSettingsBtn: document.getElementById('toggle-processing-settings-btn'),
        processingSettingsContainer: document.getElementById('processing-settings-container'),
        copyPromptBtn: document.getElementById('copy-prompt-btn'),
        llmPromptBox: document.getElementById('llm-prompt-box'),
        freebuffButtons: [
            document.getElementById('freebuff-digital-btn'),
            document.getElementById('freebuff-scanned-btn')
        ].filter(Boolean),
        freebuffInfoButtons: [
            document.getElementById('freebuff-digital-info'),
            document.getElementById('freebuff-scanned-info')
        ].filter(Boolean),
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
        validationSummary: document.getElementById('validation-summary'),
        preview: document.getElementById('preview'),
        proofModeToggle: document.getElementById('proof-mode-toggle'),
        useCleanPdfForApi: document.getElementById('use-clean-pdf-for-api'),
        enableLlmVerification: document.getElementById('enable-llm-verification'),
        verificationWarningBox: document.getElementById('verification-warning-box'),
        verificationBadge: document.getElementById('verification-badge'),
        progressCard: document.getElementById('progress-card'),
        progressTitle: document.getElementById('progress-title'),
        progressDetail: document.getElementById('progress-detail'),
        progressPercent: document.getElementById('progress-percent'),
        progressFill: document.getElementById('progress-fill'),
        progressAbortBtn: document.getElementById('progress-abort-btn'),
        progressIcon: document.getElementById('progress-icon'),
        mainProgressBar: document.getElementById('main-progressbar'),
        stickyProgressBanner: document.getElementById('sticky-progress-banner'),
        stickyProgressTitle: document.getElementById('sticky-progress-title'),
        stickyProgressDetail: document.getElementById('sticky-progress-detail'),
        stickyProgressPercent: document.getElementById('sticky-progress-percent'),
        stickyProgressFill: document.getElementById('sticky-progress-fill'),
        stickyProgressAbortBtn: document.getElementById('sticky-progress-abort-btn'),
        themeToggle: document.getElementById('theme-toggle'),
        themeIcon: document.getElementById('theme-icon')
    };

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

    // Initialize Services & UI Components
    ProgressController.init(elements, (msg, isErr, toast) => EditorUi.setStatus(msg, isErr, toast, elements));
    EditorUi.init(state, elements, {
        renderPageImageData: PdfService.renderPageImageData,
        attachFullSourcePageImage: CropperModal.attachFullSourcePageImage
    });
    CropperModal.init(state, elements, {
        showToast: EditorUi.showToast,
        renderPreview: () => EditorUi.renderPreview(state, elements),
        renderPageImageData: PdfService.renderPageImageData
    });

    // Theme Setup
    let currentTheme = localStorage.getItem('theme') || 'light';
    EditorUi.setTheme(currentTheme, elements);
    elements.themeToggle?.addEventListener('click', () => {
        currentTheme = currentTheme === 'light' ? 'dark' : 'light';
        EditorUi.setTheme(currentTheme, elements);
    });

    // Proof Mode Toggle
    if (elements.proofModeToggle) {
        state.proofMode = !!elements.proofModeToggle.checked;
        elements.proofModeToggle.addEventListener('change', () => {
            state.proofMode = !!elements.proofModeToggle.checked;
            EditorUi.renderPreview(state, elements);
        });
    }

    // LLM Verification UI
    if (elements.enableLlmVerification) {
        EditorUi.updateVerificationUI(elements);
        elements.enableLlmVerification.addEventListener('change', () => EditorUi.updateVerificationUI(elements));
    }

    // Default Prompt Injections
    if (elements.llmPromptBox) elements.llmPromptBox.value = DEFAULT_LLM_PROMPT;
    if (elements.digitalLlmPromptBox) elements.digitalLlmPromptBox.value = DEFAULT_LLM_PROMPT;

    // Main Parse Orchestrator
    async function runParse() {
        EditorUi.disableOutputActions(true, elements, state.questions);
        if (elements.preview) elements.preview.innerHTML = '';
        state.proofPageImages = [];
        state.pdfBytes = null;
        let apiKey = '';        const pdf = elements.pdfFile?.files?.[0];
        const csv = elements.csvFile?.files?.[0];
        state.pdfFileName = pdf?.name || '';
            const formNumber = elements.formNumber?.value?.trim();

        const ocrEngine = (elements.ocrEngine?.value || 'gemini_chunked').trim();
        const llmPolicy = (elements.llmPolicy?.value || 'auto').trim();

        if (!pdf) {
            throw new Error('יש לבחור קובץ PDF לפענוח.');
        }

        const task = ProgressController.startTask('מחלץ ומפענח שאלות', {
            icon: '🔍',
            cancellable: true,
            detail: 'קורא קובצי מקור ומנתח מבנה PDF...'
        });

        try {
            task.update(5, 'קורא קובצי מקור...');
            EditorUi.setStatus('קורא קובצי מקור...', false, false, elements);

            let pdfFileToParse = pdf;
            let pdfBufferForParse = (await pdf.arrayBuffer()).slice(0);
            if (!state.pdfBytes || state.pdfBytes.length === 0) {
                state.pdfBytes = new Uint8Array(pdfBufferForParse.slice(0));
            }

            const useCleanPdf = elements.useCleanPdfForApi ? elements.useCleanPdfForApi.checked : true;
            if (useCleanPdf) {
                try {
                    const cleanBuffer = await PdfService.getCleanPdfBuffer(state, elements);
                    if (cleanBuffer) {
                        pdfBufferForParse = cleanBuffer.slice(0);
                        pdfFileToParse = new File([cleanBuffer], `cleaned_${pdf.name}`, { type: 'application/pdf' });
                        const keptCount = state.pdfPagesState.filter(p => p.keep).length;
                        task.update(10, `משתמש ב-PDF נקי (${keptCount} עמודים נבחרו בסרגל)...`);
                        EditorUi.setStatus(`משתמש ב-PDF נקי (${keptCount} עמודים נבחרו בסרגל) לעיבוד...`, false, false, elements);
                    }
                } catch (e) {
                    console.warn('Could not build clean PDF for parse:', e);
                }
            }

            if (csv) {
                const fileName = csv.name.toLowerCase();
                let answerRows = null;
                if (fileName.endsWith('.xlsx') || fileName.endsWith('.xls')) {
                    const xlsxBuffer = await csv.arrayBuffer();
                    answerRows = QuestionParser.parseXlsxToRows(xlsxBuffer);
                } else {
                    const csvText = await csv.text();
                    answerRows = window.QuizCore ? window.QuizCore.parseCsvRows(csvText.replace(/^\uFEFF/, '')) : [];
                }
                if (!formNumber) {
                    throw new Error('אם הועלה קובץ תשובות, יש להזין מספר שאלון.');
                }
            }

            if (task.isAborted()) throw new Error('הפעולה בוטלה על ידי המשתמש.');

            task.update(15, 'טוען ומנתח את מבנה קובץ ה-PDF...');
            EditorUi.setStatus('טוען ומנתח את מבנה קובץ ה-PDF...', false, false, elements);
            const extracted = await PdfService.extractPdfText(pdfBufferForParse, QuestionParser.maybeFixHebrewWordOrder);

            let examText = extracted.text;
            state.examText = examText;
            let sourcePages = extracted.rawPages;
            const detectedForm = extracted.form || (window.QuizCore?.detectFormNumber ? window.QuizCore.detectFormNumber(examText, pdf.name) : null);
            if (detectedForm && elements.formNumber && !elements.formNumber.value.trim()) {
                elements.formNumber.value = detectedForm.rawValue;
                EditorUi.showToast(`זוהה מספר שאלון ${detectedForm.rawValue} אוטומטית מקובץ ה-PDF.`, 'info', 4000);
            }
            const useLlmExtraction = llmPolicy === 'force_llm' || (llmPolicy === 'auto' && extracted.isScanned && ocrEngine !== 'offline_local');
            const useOfflineOcr = extracted.isScanned && (llmPolicy === 'force_no_llm' || ocrEngine === 'offline_local');

            if (!extracted.isScanned && llmPolicy !== 'force_llm') {
                task.update(50, 'זוהה PDF דיגיטלי. מחלץ שאלות ישירות מטקסט המסמך...');
                EditorUi.setStatus('זוהה PDF דיגיטלי. מחלץ שאלות מקומית מתוך טקסט ה-PDF ללא LLM.', false, false, elements);
            }

            if (useOfflineOcr) {
                EditorUi.setStatus('מפעיל OCR מקומי בדפדפן (ללא API Key)...', false, false, elements);
                const offlineExtraction = await TesseractOcrService.extractTextViaOfflineOcr(extracted.pdf, {
                    task,
                    statusCallback: (msg) => EditorUi.setStatus(msg, false, false, elements),
                    renderAllPdfPageImagesFn: PdfService.renderAllPdfPageImages,
                    maybeFixHebrewWordOrderFn: QuestionParser.maybeFixHebrewWordOrder
                });
                examText = offlineExtraction.text;
                sourcePages = offlineExtraction.pages;
                state.proofPageImages = offlineExtraction.pagePreviews || [];
            } else if (useLlmExtraction) {
                apiKey = await GeminiService.resolveGeminiApiKey(elements, true);
                if (ocrEngine.startsWith('gemini_native')) {
                    const mode = ocrEngine === 'gemini_native_markdown' ? 'markdown' : 'schema';
                    EditorUi.setStatus(`שולח את מסמך ה-PDF המלא ל-Gemini API (Native PDF - ${mode === 'schema' ? 'Enforced Schema' : 'Clean Markdown'})...`, false, false, elements);
                    const nativeExtraction = await GeminiService.extractTextViaGeminiNativePdf(pdfFileToParse, extracted.pdf, apiKey, {
                        mode,
                        task,
                        statusCallback: (msg) => EditorUi.setStatus(msg, false, false, elements),
                        fileToBase64Fn: PdfService.fileToBase64,
                        renderPageImageDataFn: PdfService.renderPageImageData,
                        maybeFixHebrewWordOrderFn: QuestionParser.maybeFixHebrewWordOrder
                    });
                    examText = nativeExtraction.text;
                    sourcePages = nativeExtraction.pages;
                    const previews = await PdfService.renderAllPdfPageImages(extracted.pdf, task);
                    state.proofPageImages = previews.pagePreviews || [];
                } else {
                    EditorUi.setStatus('שולח עמודי תמונה ל-Gemini API (מצב Page Chunking)...', false, false, elements);
                    const geminiExtraction = await GeminiService.extractTextViaGemini(extracted.pdf, apiKey, {
                        chunkSizeOverride: null,
                        task,
                        statusCallback: (msg) => EditorUi.setStatus(msg, false, false, elements),
                        renderAllPdfPageImagesFn: PdfService.renderAllPdfPageImages,
                        maybeFixHebrewWordOrderFn: QuestionParser.maybeFixHebrewWordOrder
                    });
                    examText = geminiExtraction.text;
                    sourcePages = geminiExtraction.pages;
                    state.proofPageImages = geminiExtraction.pagePreviews || [];
                }
            } else if (extracted.isScanned) {
                EditorUi.setStatus('זוהה PDF סרוק במצב מקומי בלבד (ללא LLM). התוצאה עלולה להיות חלקית.', false, false, elements);
            }

            if (task.isAborted()) throw new Error('הפעולה בוטלה על ידי המשתמש.');

            task.update(85, 'מפרק ומבנה שאלות ותשובות מתוך הטקסט...');
            let parsedQuestions;
            try {
                parsedQuestions = QuestionParser.parseQuestionsFromText(examText, sourcePages, extracted.pageImages, {
                    setStatus: (msg, isErr) => EditorUi.setStatus(msg, isErr, false, elements),
                    showToast: EditorUi.showToast
                });
            } catch (error) {
                if (useLlmExtraction) {
                    task.update(88, 'מנסה ניתוח מקומי מהטקסט הדיגיטלי...');
                    EditorUi.setStatus('פורמט תשובת ה-LLM לא תאם מודל צפוי, מנסה ניתוח מקומי מהטקסט הדיגיטלי...', false, false, elements);
                    parsedQuestions = QuestionParser.parseQuestionsFromText(extracted.text, extracted.rawPages, extracted.pageImages, {
                        setStatus: (msg, isErr) => EditorUi.setStatus(msg, isErr, false, elements),
                        showToast: EditorUi.showToast
                    });
                } else {
                    throw error;
                }
            }

            if (useLlmExtraction && ocrEngine === 'gemini_chunked' && parsedQuestions.length < 10) {
                task.update(60, 'זוהה מספר נמוך של שאלות. מנסה פענוח פרטני עמוד-עמוד...');
                EditorUi.setStatus('זוהה מספר נמוך של שאלות. מנסה פענוח פרטני עמוד-עמוד...', false, false, elements);
                const fallbackExtraction = await GeminiService.extractTextViaGemini(extracted.pdf, apiKey, {
                    chunkSizeOverride: 1,
                    task,
                    statusCallback: (msg) => EditorUi.setStatus(msg, false, false, elements),
                    renderAllPdfPageImagesFn: PdfService.renderAllPdfPageImages,
                    maybeFixHebrewWordOrderFn: QuestionParser.maybeFixHebrewWordOrder
                });
                const fallbackQuestions = QuestionParser.parseQuestionsFromText(
                    fallbackExtraction.text,
                    fallbackExtraction.pages,
                    extracted.pageImages,
                    {
                        setStatus: (msg, isErr) => EditorUi.setStatus(msg, isErr, false, elements),
                        showToast: EditorUi.showToast
                    }
                );

                if (fallbackQuestions.length > parsedQuestions.length) {
                    parsedQuestions = fallbackQuestions;
                    examText = fallbackExtraction.text;
                    sourcePages = fallbackExtraction.pages;
                    state.proofPageImages = fallbackExtraction.pagePreviews || [];
                }
            }

            for (const q of parsedQuestions) {
                if (task.isAborted()) throw new Error('הפעולה בוטלה על ידי המשתמש.');
                if (q._needsPageRender && !q.image && extracted.pdf && q.sourcePage) {
                    try {
                        const page = await extracted.pdf.getPage(q.sourcePage);
                        const imageData = await PdfService.renderPageImageData(page, 2.5);
                        q.image = `data:image/png;base64,${imageData}`;
                    } catch { /* skip if render fails */ }
                }
                delete q._needsPageRender;
            }

            state.questions = parsedQuestions.map(q => ({
                ...q,
                correctIndex: (typeof q.correctIndex === 'number' && q.correctIndex >= 0) ? q.correctIndex : 0,
                shuffleOptions: true
            }));

            const enableVerification = elements.enableLlmVerification ? elements.enableLlmVerification.checked : false;
            if (enableVerification) {
                if (!apiKey) {
                    apiKey = await GeminiService.resolveGeminiApiKey(elements, true);
                }
                if (apiKey) {
                    EditorUi.setStatus('מבצע סבב הגהה ותיקון נוסף מול Gemini API (Verification Pass)...', false, false, elements);
                    state.questions = await GeminiService.verifyTestWithGemini(state.questions, apiKey, {
                        task,
                        statusCallback: (msg) => EditorUi.setStatus(msg, false, false, elements)
                    });
                }
            }

            const validationErrors = EditorUi.getQuestionValidationErrors(state.questions);
            if (validationErrors.length) {
                throw new Error(`נמצאו שאלות לא תקינות: ${validationErrors.slice(0, 5).join(' ')}`);
            }

            EditorUi.renderPreview(state, elements);
            EditorUi.disableOutputActions(false, elements, state.questions);
            task.finish(`הסתיים בהצלחה: נטענו ${state.questions.length} שאלות לעריכה!`);
        } catch (error) {
            if (task.isAborted()) {
                task.abort('פעולת חילוץ השאלות בוטלה.');
            } else {
                task.fail(error.message || 'אירעה שגיאה לא צפויה.');
            }
            throw error;
        }
    }

    // Wiring UI Events
    elements.runParse?.addEventListener('click', async () => {
        try {
            await runParse();
        } catch (error) {
            console.warn('runParse finished with notice/error:', error);
        }
    });

    elements.downloadQuiz?.addEventListener('click', () => {
        if (!state.questions || state.questions.length === 0) {
            EditorUi.showToast('אין שאלות זמינות ליצירת מבחן.', 'info');
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
        const task = ProgressController.startTask('מייצא מבחן עצמאי (HTML)', {
            icon: '📥',
            cancellable: true,
            detail: 'מכין קובץ HTML ודוחס תמונות...'
        });

        try {
            task.update(10, 'מכין קובץ HTML להורדה...');
            EditorUi.setStatus('מכין קובץ HTML להורדה...', false, false, elements);
            const html = await ExportService.createStandaloneQuizHtml({
                questions: state.questions,
                elements,
                task,
                normalizeWhitespaceFn: QuestionParser.normalizeWhitespace,
                validateQuestionsFn: EditorUi.getQuestionValidationErrors
            });
            if (task.isAborted()) {
                task.abort('ייצוא המבחן בוטל.');
                return;
            }
            task.update(95, 'יוצר קובץ HTML עצמאי ומוריד...');
            const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const anchor = document.createElement('a');
            anchor.href = url;
            anchor.download = 'interactive_quiz.html';
            anchor.click();
            URL.revokeObjectURL(url);
            task.finish('הקובץ נוצר בהצלחה וההורדה התחילה!');
        } catch (error) {
            if (task.isAborted()) {
                task.abort('ייצוא המבחן בוטל.');
            } else {
                task.fail(error.message || 'נכשלה יצירת קובץ HTML.');
            }
        }
    });

    elements.takeQuiz?.addEventListener('click', async () => {
        const previewWindow = window.open('', '_blank');
        if (!previewWindow) {
            EditorUi.setStatus('הדפדפן חסם את פתיחת לשונית המבחן. אפשר חלונות קופצים ונסה שוב.', true, false, elements);
            return;
        }

        const task = ProgressController.startTask('מכין מבחן לפתרון', {
            icon: '▶️',
            cancellable: true,
            detail: 'בונה את נתוני המבחן ומפעיל בלשונית חדשה...'
        });

        try {
            previewWindow.document.write('<!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8"><title>מכין מבחן...</title><style>body{display:flex;align-items:center;justify-content:center;height:100vh;margin:0;font-family:Rubik,system-ui,sans-serif;background:#f8fafc;color:#0f172a;direction:rtl}@keyframes bspin{to{transform:rotate(360deg)}}.sp{width:40px;height:40px;border:4px solid #e2e8f0;border-top-color:#3b82f6;border-radius:50%;animation:bspin .7s linear infinite;margin-bottom:16px}.wr{text-align:center}p{font-size:1.1rem;margin:0}</style></head><body><div class="wr"><div class="sp"></div><p>מכין מבחן...</p></div></body></html>');
            previewWindow.document.title = 'מכין מבחן...';
            task.update(15, 'פותח תצוגת מבחן ומעבד תמונות...');
            EditorUi.setStatus('פותח תצוגת מבחן...', false, false, elements);
            const html = await ExportService.createStandaloneQuizHtml({
                questions: state.questions,
                elements,
                task,
                normalizeWhitespaceFn: QuestionParser.normalizeWhitespace,
                validateQuestionsFn: EditorUi.getQuestionValidationErrors
            });
            if (task.isAborted()) {
                previewWindow.close();
                task.abort('טעינת המבחן בוטלה.');
                return;
            }
            previewWindow.document.open();
            previewWindow.document.write(html);
            previewWindow.document.close();
            task.finish('המבחן נפתח בלשונית חדשה!');
        } catch (error) {
            previewWindow?.close();
            if (task.isAborted()) {
                task.abort('טעינת המבחן בוטלה.');
            } else {
                task.fail(error.message || 'נכשלה פתיחת המבחן.');
            }
        }
    });

    elements.mergeAnswersBtn?.addEventListener('click', () => {
        QuestionParser.tryMergeAnswersFromCsv({
            explicit: true,
            elements,
            state,
            progressController: ProgressController,
            showToastFn: EditorUi.showToast,
            setStatusFn: (msg, isErr, toast) => EditorUi.setStatus(msg, isErr, toast, elements),
            renderPreviewFn: () => EditorUi.renderPreview(state, elements)
        });
    });

    elements.autoAttachDiagramsBtn?.addEventListener('click', () => {
        QuestionParser.autoAttachDiagramPageImages({
            state,
            elements,
            progressController: ProgressController,
            setStatusFn: (msg, isErr, toast) => EditorUi.setStatus(msg, isErr, toast, elements),
            showToastFn: EditorUi.showToast,
            renderPreviewFn: () => EditorUi.renderPreview(state, elements),
            renderPageImageDataFn: PdfService.renderPageImageData
        });
    });

    elements.stripQuestionHeadersBtnPreview?.addEventListener('click', () => {
        QuestionParser.stripAllQuestionHeaderPrefixes({
            state,
            renderPreviewFn: () => EditorUi.renderPreview(state, elements),
            showToastFn: EditorUi.showToast
        });
    });

    // jsonFile Upload Listener
    elements.jsonFile?.addEventListener('change', async () => {
        const file = elements.jsonFile.files?.[0];
        if (!file) return;
        try {
            EditorUi.setStatus(`מעבד קובץ ${file.name}...`, false, false, elements);
            const text = await file.text();
            let normalizedQuestions = [];

            const trimmed = text.trim();
            const isJson = trimmed.startsWith('{') || trimmed.startsWith('[') || trimmed.startsWith('```json');

            if (isJson) {
                let cleanJsonText = trimmed;
                if (cleanJsonText.startsWith('```json')) {
                    cleanJsonText = cleanJsonText.replace(/^```json\s*/i, '').replace(/\s*```$/, '').trim();
                }

                let parsedAsStrictJson = false;
                try {
                    const rawData = JSON.parse(cleanJsonText);
                    normalizedQuestions = QuestionParser.normalizeQuestionsFromAnyJson(rawData);
                    if (Array.isArray(normalizedQuestions) && normalizedQuestions.length > 0) {
                        parsedAsStrictJson = true;
                    }
                } catch (jsonErr) {
                    console.warn('JSON parse failed for uploaded question file. Trying markdown/text fallback.', jsonErr);
                }

                if (!parsedAsStrictJson) {
                    const markdownQuestions = QuestionParser.parseQuestionsFromMarkdown(text);
                    normalizedQuestions = markdownQuestions.length > 0
                        ? markdownQuestions
                        : QuestionParser.parseQuestionsFromText(text, [], []);
                }
            } else {
                const markdownQuestions = QuestionParser.parseQuestionsFromMarkdown(text);
                normalizedQuestions = markdownQuestions.length > 0
                    ? markdownQuestions
                    : QuestionParser.parseQuestionsFromText(text, [], []);
            }

            if (!normalizedQuestions || !normalizedQuestions.length) {
                throw new Error('לא פוענחו שאלות מהקובץ שנבחר.');
            }

            const selectedCsv = elements.csvFile?.files?.[0] || null;
            const currentFormNumber = (elements.formNumber?.value || '').trim();
            const isFormZero = currentFormNumber === '0';
            const hasShuffleFlag = normalizedQuestions.some((q) => q && q.shuffleOptions === true);
            const allAnswersDefaultToAlef = normalizedQuestions.every((q) => q && Number(q.correctIndex) === 0);

            const shouldAutoEnableFormZeroShuffle = !selectedCsv && !hasShuffleFlag && allAnswersDefaultToAlef;
            if (isFormZero || shouldAutoEnableFormZeroShuffle) {
                normalizedQuestions = normalizedQuestions.map((q) => ({ ...q, shuffleOptions: true }));

                if (shouldAutoEnableFormZeroShuffle && elements.formNumber && !currentFormNumber) {
                    elements.formNumber.value = '0';
                    EditorUi.showToast('לא זוהה קובץ תשובות. הופעל מצב שאלון 0 עם ערבוב תשובות אוטומטי.', 'info', 5000);
                }
            }

            state.questions = normalizedQuestions;
            EditorUi.renderPreview(state, elements);
            EditorUi.disableOutputActions(false, elements, state.questions);
            QuestionParser.tryMergeAnswersFromCsv({
                explicit: false,
                elements,
                state,
                progressController: ProgressController,
                showToastFn: EditorUi.showToast,
                setStatusFn: (msg, isErr, toast) => EditorUi.setStatus(msg, isErr, toast, elements),
                renderPreviewFn: () => EditorUi.renderPreview(state, elements)
            });
            EditorUi.setStatus(`נטענו ${normalizedQuestions.length} שאלות בהצלחה מקובץ ${file.name}!`, false, true, elements);
        } catch (error) {
            console.error('Error loading question file:', error);
            EditorUi.setStatus(error.message || `נכשלה טעינת קובץ ${file.name}.`, true, false, elements);
        }
    });

    elements.csvFile?.addEventListener('change', () => {
        const file = elements.csvFile.files?.[0];
        if (file) {
            QuestionParser.tryMergeAnswersFromCsv({
                explicit: false,
                elements,
                state,
                progressController: ProgressController,
                showToastFn: EditorUi.showToast,
                setStatusFn: (msg, isErr, toast) => EditorUi.setStatus(msg, isErr, toast, elements),
                renderPreviewFn: () => EditorUi.renderPreview(state, elements)
            });
            EditorUi.showToast(`קובץ תשובות (${file.name}) נבחר. הזן מספר שאלון ולחץ "🔗 מזג תשובות נכונות לשאלות".`, 'info', 4000);
        }
    });

    elements.formNumber?.addEventListener('input', () => {
        QuestionParser.tryMergeAnswersFromCsv({
            explicit: false,
            elements,
            state,
            progressController: ProgressController,
            showToastFn: EditorUi.showToast,
            setStatusFn: (msg, isErr, toast) => EditorUi.setStatus(msg, isErr, toast, elements),
            renderPreviewFn: () => EditorUi.renderPreview(state, elements)
        });
    });

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
            EditorUi.setStatus('נכשלה העתקת הפרומפט ללוח.', true, false, elements);
        }
    });

    elements.showDigitalPromptBtn?.addEventListener('click', () => {
        if (!elements.digitalPromptExpandable) return;
        const isHidden = elements.digitalPromptExpandable.classList.toggle('hidden');
        elements.showDigitalPromptBtn.textContent = isHidden ? '📋 הצג פרומפט ל-AI חיצוני' : '📋 הסתר פרומפט';
    });

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
            EditorUi.setStatus('נכשלה העתקת הפרומפט ללוח.', true, false, elements);
        }
    });

    elements.htmlFile?.addEventListener('change', async () => {
        const file = elements.htmlFile.files?.[0];
        if (!file) return;
        try {
            EditorUi.setStatus('טוען מבחן קיים...', false, false, elements);
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
            EditorUi.renderPreview(state, elements);
            EditorUi.disableOutputActions(false, elements, state.questions);
            EditorUi.setStatus(`נטענו ${questions.length} שאלות מקובץ HTML קיים.`, false, false, elements);
        } catch (error) {
            EditorUi.setStatus(error.message || 'נכשלה טעינת קובץ HTML.', true, false, elements);
        }
    });

    elements.runDigitalLocalBtn?.addEventListener('click', async () => {
        if (elements.llmPolicy) {
            elements.llmPolicy.value = 'force_no_llm';
        }
        try {
            await runParse();
        } catch (error) {
            EditorUi.setStatus(error.message || 'אירעה שגיאה בעיבוד המקומי.', true, false, elements);
        }
    });

    elements.pdfFile?.addEventListener('change', async () => {
        const file = elements.pdfFile.files?.[0];
        if (!file) {
            EditorUi.setPdfTypeNote('', 'neutral', elements);
            if (elements.scannedActionsBox) elements.scannedActionsBox.classList.add('hidden');
            if (elements.digitalActionsBox) elements.digitalActionsBox.classList.add('hidden');
            if (elements.pdfSidebarCard) elements.pdfSidebarCard.classList.add('hidden');
            if (elements.builderLayout) elements.builderLayout.classList.add('no-sidebar');
            return;
        }

        if ((file.name || '').toLowerCase().endsWith('.docx')) {
            EditorUi.setPdfTypeNote('קובץ DOCX זוהה. יש להמיר אותו ל-PDF ואז להעלות מחדש.', 'error', elements);
            if (elements.scannedActionsBox) elements.scannedActionsBox.classList.add('hidden');
            if (elements.digitalActionsBox) elements.digitalActionsBox.classList.add('hidden');
            if (elements.pdfSidebarCard) elements.pdfSidebarCard.classList.add('hidden');
            if (elements.builderLayout) elements.builderLayout.classList.add('no-sidebar');
            state.pdfArrayBuffer = null;
            return;
        }

        try {
            EditorUi.setPdfTypeNote('מזהה את סוג ה-PDF...', 'loading', elements);
            const pdfBuffer = await file.arrayBuffer();
            state.pdfArrayBuffer = pdfBuffer.slice(0);

            const detection = await PdfService.detectPdfType(state.pdfArrayBuffer.slice(0));
            EditorUi.setPdfTypeNote(
                `${detection.pdfTypeLabel}: ${detection.recommendation}`,
                detection.isScanned ? 'scanned' : 'digital',
                elements
            );

            if (elements.scannedActionsBox) {
                elements.scannedActionsBox.classList.toggle('hidden', !detection.isScanned);
            }
            if (elements.digitalActionsBox) {
                elements.digitalActionsBox.classList.toggle('hidden', detection.isScanned);
            }

            await PdfService.loadPdfSidebar(state.pdfArrayBuffer.slice(0), state, elements, ProgressController);
        } catch (error) {
            EditorUi.setPdfTypeNote(error.message || 'לא ניתן היה לזהות את סוג ה-PDF.', 'error', elements);
        }
    });

    document.querySelector('[data-target="pdf-file"]')?.addEventListener('click', () => {
        EditorUi.setPdfTypeNote('', 'neutral', elements);
        if (elements.scannedActionsBox) elements.scannedActionsBox.classList.add('hidden');
        if (elements.digitalActionsBox) elements.digitalActionsBox.classList.add('hidden');
        if (elements.pdfSidebarCard) elements.pdfSidebarCard.classList.add('hidden');
        if (elements.builderLayout) elements.builderLayout.classList.add('no-sidebar');
    });

    // Preset & Clean PDF listeners
    elements.presetStdBtn?.addEventListener('click', () => PdfService.applyStandardFilter(state, elements));
    elements.presetEvenOddBtn?.addEventListener('click', () => PdfService.toggleEvenOddFilter(state, elements, EditorUi.showToast));
    elements.presetBlankBtn?.addEventListener('click', () => PdfService.toggleEvenOddFilter(state, elements, EditorUi.showToast));
    elements.presetSelectAllBtn?.addEventListener('click', () => PdfService.selectAllPages(state, elements, true));
    elements.presetDeselectAllBtn?.addEventListener('click', () => PdfService.selectAllPages(state, elements, false));
    elements.downloadCleanPdf?.addEventListener('click', () => PdfService.downloadCleanPdf(state, elements, ProgressController, (msg) => EditorUi.setStatus(msg, false, false, elements)));

    elements.toggleSidebarCollapseBtn?.addEventListener('click', () => {
        if (!elements.pdfSidebarCard) return;
        const isCollapsed = elements.pdfSidebarCard.classList.toggle('is-collapsed');
        elements.toggleSidebarCollapseBtn.textContent = isCollapsed ? '▶ פתח סרגל' : '◀ קפל סרגל';
        EditorUi.showToast(isCollapsed ? 'סרגל עמודים קופל' : 'סרגל עמודים הורחב', 'info', 2000);
    });

    // Freebuff handlers
    function openFreebuffChat() {
        const opened = window.open('https://freebuff.com/chat', '_blank', 'noopener,noreferrer');
        if (!opened) {
            EditorUi.setStatus('הדפדפן חסם פתיחת לשונית חדשה עבור Freebuff.', true, false, elements);
        }
    }

    elements.freebuffButtons.forEach((button) => {
        button.addEventListener('click', openFreebuffChat);
    });

    elements.freebuffInfoButtons.forEach((button) => {
        button.addEventListener('click', () => {
            const tooltip = document.getElementById(button.getAttribute('aria-describedby'));
            if (tooltip) tooltip.classList.toggle('is-open');
        });
    });

    document.addEventListener('click', (event) => {
        elements.freebuffInfoButtons.forEach((button) => {
            const tooltip = document.getElementById(button.getAttribute('aria-describedby'));
            if (tooltip && !button.parentElement.contains(event.target)) {
                tooltip.classList.remove('is-open');
            }
        });
    });
});
