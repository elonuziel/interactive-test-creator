(function (root, factory) {
    if (typeof define === 'function' && define.amd) {
        define([], factory);
    } else if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.PdfService = factory();
    }
}(typeof self !== 'undefined' ? self : this, function () {
    'use strict';

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
                    gap = prev.x - (curr.x + currW);
                } else {
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
        const viewport = page.getViewport({ scale: 1.5 });
        const canvas = document.createElement('canvas');
        canvas.width = Math.floor(viewport.width);
        canvas.height = Math.floor(viewport.height);
        const ctx = canvas.getContext('2d');
        await page.render({ canvasContext: ctx, viewport }).promise;
        return canvas.toDataURL('image/png');
    }

    async function extractPdfText(inputBuffer, maybeFixHebrewWordOrderFn) {
        const pdfjs = (typeof window !== 'undefined' ? (window.pdfjsLib || window['pdfjs-dist/build/pdf'] || window.pdfjs) : null);
        if (!pdfjs?.getDocument) {
            throw new Error('PDF.js לא נטען. רענן את העמוד ונסה שוב.');
        }

        const freshData = new Uint8Array(inputBuffer);
        const loadingTask = pdfjs.getDocument({ data: freshData });
        const pdf = await loadingTask.promise;
        const pages = [];
        const pageImages = [];
        let nonWhitespaceChars = 0;

        for (let pageNumber = 1; pageNumber <= pdf.numPages; pageNumber++) {
            const page = await pdf.getPage(pageNumber);
            const textContent = await page.getTextContent({ normalizeWhitespace: true, disableCombineTextItems: false });
            const geoLines = groupPdfTextItemsToLines(textContent.items);
            const streamLines = buildLinesFromStreamOrder(textContent.items);
            const lineText = chooseBestPageText(geoLines, streamLines);
            pages.push(lineText);
            nonWhitespaceChars += lineText.replace(/\s/g, '').length;

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

        const fixFn = maybeFixHebrewWordOrderFn || (str => str);
        const fullText = pages.join('\n');
        const form = (typeof window !== 'undefined' && window.QuizCore?.detectFormNumber)
            ? window.QuizCore.detectFormNumber(fullText)
            : null;
        return {
            pdf,
            pageImages,
            form,
            isScanned: nonWhitespaceChars < Math.max(pdf.numPages * 60, 120),
            text: fixFn(pages.join('\n')),
            rawPages: pages
        };
    }

    async function detectPdfType(inputBuffer) {
        const pdfjs = (typeof window !== 'undefined' ? (window.pdfjsLib || window['pdfjs-dist/build/pdf'] || window.pdfjs) : null);
        if (!pdfjs?.getDocument) {
            throw new Error('PDF.js לא נטען. אם העמוד נפתח ישירות מהדיסק (file://), יש להשתמש בשרת מקומי (start_test_server.bat) או לוודא חיבור לרשת.');
        }

        const freshData = new Uint8Array(inputBuffer);
        const loadingTask = pdfjs.getDocument({ data: freshData });
        const pdf = await loadingTask.promise;
        let nonWhitespaceChars = 0;
        let firstPageText = '';

        for (let pageNumber = 1; pageNumber <= pdf.numPages; pageNumber++) {
            const page = await pdf.getPage(pageNumber);
            const textContent = await page.getTextContent();
            const pageText = textContent.items.map((item) => (item.str || '').trim()).join(' ');
            if (pageNumber === 1) {
                firstPageText = pageText;
            }
            nonWhitespaceChars += pageText.replace(/\s/g, '').length;
        }

        const isScanned = nonWhitespaceChars < Math.max(pdf.numPages * 60, 120);
        return {
            isScanned,
            rawSnippet: firstPageText,
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

    async function renderAllPdfPageImages(pdf, task = null, statusCallback = null) {
        const imageDatas = [];
        const pagePreviews = [];

        for (let pageNumber = 1; pageNumber <= pdf.numPages; pageNumber++) {
            if (task && task.isAborted()) {
                throw new Error('הפעולה בוטלה על ידי המשתמש.');
            }
            if (task) {
                const prepPercent = Math.round((pageNumber / pdf.numPages) * 25);
                task.update(prepPercent, `מכין עמוד ${pageNumber} מתוך ${pdf.numPages} לשליחה...`);
            } else if (statusCallback) {
                statusCallback(`מכין עמוד ${pageNumber}/${pdf.numPages} לשליחה...`);
            }
            const page = await pdf.getPage(pageNumber);
            const imageData = await renderPageImageData(page);
            imageDatas.push(imageData);
            pagePreviews.push(`data:image/png;base64,${imageData}`);
        }

        return { imageDatas, pagePreviews };
    }

    async function loadPdfSidebar(pdfBytesInput, state, elements, progressController) {
        const pdfjs = (typeof window !== 'undefined' ? (window.pdfjsLib || window['pdfjs-dist/build/pdf'] || window.pdfjs) : null);
        if (pdfBytesInput) {
            state.pdfBytes = new Uint8Array(pdfBytesInput);
        }
        state.pdfPagesState = [];
        if (elements.pageThumbnailsContainer) elements.pageThumbnailsContainer.innerHTML = '';

        if (!state.pdfBytes || state.pdfBytes.length === 0 || !pdfjs?.getDocument) return;

        const task = progressController ? progressController.startTask('טוען ומעבד עמודי PDF', {
            icon: '📄',
            cancellable: true,
            detail: 'טוען מסמך PDF ומכין תצוגות עמודים...'
        }) : null;

        try {
            const freshCopy = new Uint8Array(state.pdfBytes);
            const loadingTask = pdfjs.getDocument({ data: freshCopy });
            const pdfDoc = await loadingTask.promise;
            const numPages = pdfDoc.numPages;

            if (elements.pdfSidebarCard) elements.pdfSidebarCard.classList.remove('hidden');
            if (elements.builderLayout) elements.builderLayout.classList.remove('no-sidebar');

            for (let i = 1; i <= numPages; i++) {
                if (task && task.isAborted()) {
                    task.abort('טעינת תצוגות העמודים נעצרה.');
                    return;
                }

                const percent = Math.round((i / numPages) * 100);
                if (task) {
                    task.update(percent, `יוצר תצוגה מקדימה לעמוד ${i} מתוך ${numPages} (${percent}%)...`);
                }

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

            renderSidebarThumbnails(state, elements);
            if (elements.downloadCleanPdf) elements.downloadCleanPdf.disabled = false;
            if (task) task.finish(`נטענו ${numPages} עמודים בהצלחה!`);
        } catch (err) {
            console.error('Error rendering PDF sidebar thumbnails:', err);
            if (task) task.fail(`שגיאה בטעינת עמודי PDF: ${err.message || err}`);
        }
    }

    function renderSidebarThumbnails(state, elements) {
        if (!elements?.pageThumbnailsContainer) return;
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
                renderSidebarThumbnailsBadgeOnly(state, elements);
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
                    renderSidebarThumbnailsBadgeOnly(state, elements);
                }
            });

            elements.pageThumbnailsContainer.appendChild(item);
        });
    }

    function renderSidebarThumbnailsBadgeOnly(state, elements) {
        const total = state?.pdfPagesState?.length || 0;
        const kept = state?.pdfPagesState?.filter(p => p.keep).length || 0;
        if (elements?.pageCountBadge) {
            elements.pageCountBadge.textContent = `${kept} מתוך ${total} עמודים נבחרו`;
        }
    }

    function applyStandardFilter(state, elements) {
        if (!state?.pdfPagesState || !state.pdfPagesState.length) return;
        state.evenOddMode = null;
        const btn = elements.presetEvenOddBtn || elements.presetBlankBtn;
        if (btn) btn.textContent = '📄 עמודים זוגיים';
        state.pdfPagesState.forEach(p => {
            if (p.pageNum <= 4) p.keep = false;
            else if (p.pageNum >= 6 && p.pageNum % 2 === 0) p.keep = false;
            else p.keep = true;
        });
        renderSidebarThumbnails(state, elements);
    }

    function toggleEvenOddFilter(state, elements, showToastCallback) {
        if (!state?.pdfPagesState || !state.pdfPagesState.length) return;

        if (!state.evenOddMode || state.evenOddMode === 'odd') {
            state.evenOddMode = 'even';
            state.pdfPagesState.forEach(p => {
                p.keep = (p.pageNum % 2 === 0);
            });
            const btn = elements.presetEvenOddBtn || elements.presetBlankBtn;
            if (btn) btn.textContent = '📄 עמודים אי-זוגיים';
            if (showToastCallback) showToastCallback('נבחרו עמודים זוגיים (2, 4, 6...)', 'info', 2000);
        } else {
            state.evenOddMode = 'odd';
            state.pdfPagesState.forEach(p => {
                p.keep = (p.pageNum % 2 !== 0);
            });
            const btn = elements.presetEvenOddBtn || elements.presetBlankBtn;
            if (btn) btn.textContent = '📄 עמודים זוגיים';
            if (showToastCallback) showToastCallback('נבחרו עמודים אי-זוגיים (1, 3, 5...)', 'info', 2000);
        }

        renderSidebarThumbnails(state, elements);
    }

    function selectAllPages(state, elements, keepState) {
        if (!state?.pdfPagesState || !state.pdfPagesState.length) return;
        state.evenOddMode = null;
        const btn = elements.presetEvenOddBtn || elements.presetBlankBtn;
        if (btn) btn.textContent = '📄 עמודים זוגיים';
        state.pdfPagesState.forEach(p => {
            p.keep = keepState;
        });
        renderSidebarThumbnails(state, elements);
    }

    async function getCleanPdfBuffer(state, elements) {
        if (!state?.pdfPagesState || !state.pdfPagesState.length) return null;
        const totalPages = state.pdfPagesState.length;
        const keptIndices = state.pdfPagesState
            .filter(p => p.keep)
            .map(p => p.pageNum - 1);

        if (keptIndices.length === 0 || keptIndices.length === totalPages) {
            return null;
        }
        const pdfLib = (typeof window !== 'undefined' ? window.PDFLib : null);
        if (!pdfLib) return null;

        let bytes = state.pdfBytes;
        if (!bytes || bytes.length === 0 || bytes.buffer.byteLength === 0) {
            const file = elements?.pdfFile?.files?.[0];
            if (!file) return null;
            const buffer = await file.arrayBuffer();
            state.pdfBytes = new Uint8Array(buffer);
            bytes = state.pdfBytes;
        }

        const freshCopy = new Uint8Array(bytes.buffer.slice(0));
        const srcDoc = await pdfLib.PDFDocument.load(freshCopy);
        const newDoc = await pdfLib.PDFDocument.create();
        const copiedPages = await newDoc.copyPages(srcDoc, keptIndices);
        copiedPages.forEach(page => newDoc.addPage(page));
        const cleanPdfBytes = await newDoc.save();
        return cleanPdfBytes.buffer;
    }

    async function downloadCleanPdf(state, elements, progressController, setStatusCallback) {
        const pdfLib = (typeof window !== 'undefined' ? window.PDFLib : null);
        if (!pdfLib) {
            alert('ספריית PDFLib אינה זמינה בדפדפן. יש לוודא חיבור לאינטרנט או לרענן את העמוד.');
            return;
        }

        const task = progressController ? progressController.startTask('יוצר קובץ PDF נקי', {
            icon: '✂️',
            cancellable: false,
            detail: 'מסיר עמודים ומכין קובץ PDF חדש...'
        }) : null;

        try {
            if (task) task.update(15, 'קורא קובץ PDF מקור...');
            if (setStatusCallback) setStatusCallback('מכין קובץ PDF נקי להורדה...');

            let bytes = state.pdfBytes;
            if (!bytes || bytes.length === 0 || bytes.buffer.byteLength === 0) {
                const file = elements?.pdfFile?.files?.[0];
                if (!file) {
                    alert('אנא בחר קובץ PDF ראשית.');
                    if (task) task.fail('לא נבחר קובץ PDF.');
                    return;
                }
                const buffer = await file.arrayBuffer();
                state.pdfBytes = new Uint8Array(buffer);
                bytes = state.pdfBytes;
            }

            if (task) task.update(40, 'מעבד ומסנן עמודים נבחרים...');
            const freshCopy = new Uint8Array(bytes.buffer.slice(0));
            const srcDoc = await pdfLib.PDFDocument.load(freshCopy);
            const newDoc = await pdfLib.PDFDocument.create();

            let keptIndices = [];
            if (state.pdfPagesState && state.pdfPagesState.length > 0) {
                keptIndices = state.pdfPagesState
                    .filter(p => p.keep)
                    .map(p => p.pageNum - 1);
            }

            if (keptIndices.length === 0) {
                const totalPages = srcDoc.getPageCount();
                for (let i = 0; i < totalPages; i++) {
                    keptIndices.push(i);
                }
            }

            if (task) task.update(70, `מעתיק ${keptIndices.length} עמודים ל-PDF החדש...`);
            const copiedPages = await newDoc.copyPages(srcDoc, keptIndices);
            copiedPages.forEach(page => newDoc.addPage(page));

            if (task) task.update(90, 'שומר ומייצר קובץ להורדה...');
            const pdfDataUri = await newDoc.saveAsBase64({ dataUri: true });

            const anchor = document.createElement('a');
            anchor.href = pdfDataUri;
            anchor.download = 'cleaned_test.pdf';
            document.body.appendChild(anchor);
            anchor.click();
            document.body.removeChild(anchor);

            if (task) task.finish(`PDF נקי נוצר בהצלחה עם ${keptIndices.length} עמודים וההורדה התחילה!`);
        } catch (err) {
            console.error('Failed to export clean PDF:', err);
            alert(`שגיאה ביצירת PDF נקי: ${err.message || err}`);
            if (task) task.fail(err.message || 'שגיאה ביצירת PDF נקי.');
        }
    }

    return {
        hasHebrew,
        detectLineDirection,
        joinChunksByGeometry,
        buildLinesFromStreamOrder,
        computeHebrewBreakageScore,
        computeStructureSignal,
        chooseBestPageText,
        groupPdfTextItemsToLines,
        extractPageImage,
        extractPdfText,
        detectPdfType,
        renderPageImageData,
        fileToBase64,
        renderAllPdfPageImages,
        loadPdfSidebar,
        renderSidebarThumbnails,
        renderSidebarThumbnailsBadgeOnly,
        applyStandardFilter,
        toggleEvenOddFilter,
        selectAllPages,
        getCleanPdfBuffer,
        downloadCleanPdf
    };
}));

