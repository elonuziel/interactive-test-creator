(function (root, factory) {
    if (typeof define === 'function' && define.amd) {
        define([], factory);
    } else if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.TesseractOcrService = factory();
    }
}(typeof self !== 'undefined' ? self : this, function () {
    'use strict';

    async function extractTextViaOfflineOcr(pdf, { task = null, statusCallback = null, renderAllPdfPageImagesFn, maybeFixHebrewWordOrderFn } = {}) {
        const tesseract = (typeof window !== 'undefined' ? window.Tesseract : null);
        if (!tesseract?.createWorker) {
            throw new Error('רכיב OCR חינמי לא נטען בדפדפן. רענן את העמוד ונסה שוב, או בחר Gemini.');
        }

        if (task) {
            task.update(5, 'מכין OCR חינמי בדפדפן...');
        } else if (statusCallback) {
            statusCallback('מכין OCR חינמי בדפדפן. האיכות כנראה תהיה נמוכה יותר מ-Gemini...');
        }

        const { imageDatas, pagePreviews } = await renderAllPdfPageImagesFn(pdf, task, statusCallback);
        const pages = [];
        const worker = await tesseract.createWorker('heb');

        try {
            for (let i = 0; i < imageDatas.length; i++) {
                if (task && task.isAborted()) {
                    throw new Error('הפעולה בוטלה על ידי המשתמש.');
                }
                const ocrPercent = 25 + Math.round(((i + 1) / imageDatas.length) * 65);
                const msg = `OCR מקומי מעבד עמוד ${i + 1} מתוך ${imageDatas.length} (${ocrPercent}%)...`;
                if (task) {
                    task.update(ocrPercent, msg);
                } else if (statusCallback) {
                    statusCallback(`OCR חינמי מעבד עמוד ${i + 1}/${imageDatas.length}... האיכות כנראה תהיה נמוכה יותר מ-Gemini.`);
                }
                const { data } = await worker.recognize(`data:image/png;base64,${imageDatas[i]}`);
                const fixFn = maybeFixHebrewWordOrderFn || (str => str);
                pages.push(fixFn((data && data.text) || ''));
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

    return {
        extractTextViaOfflineOcr
    };
}));

