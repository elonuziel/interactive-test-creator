(function (root, factory) {
    if (typeof define === 'function' && define.amd) {
        define([], factory);
    } else if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.ExportService = factory();
    }
}(typeof self !== 'undefined' ? self : this, function () {
    'use strict';

    let templateCache = null;

    async function getTemplateSources() {
        if (templateCache) {
            return templateCache;
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

            templateCache = { indexHtml, styleCss, quizCoreJs, appJs };
            return templateCache;
        } catch (err) {
            if (typeof window !== 'undefined' && window.location?.protocol === 'file:') {
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

    async function createStandaloneQuizHtml({ questions, elements, task = null, normalizeWhitespaceFn, validateQuestionsFn, quizExportModule } = {}) {
        const validator = validateQuestionsFn || (typeof window !== 'undefined' && window.QuizCore ? window.QuizCore.validateQuestions : () => []);
        const validationErrors = validator(questions);
        if (validationErrors.length) {
            throw new Error(`לא ניתן לייצא: ${validationErrors.slice(0, 5).join(' ')}`);
        }

        const shouldCompress = elements?.compressExportImages ? elements.compressExportImages.checked : false;
        const qualityVal = Number(elements?.compressQualitySlider?.value) || 75;
        const quality = Math.min(Math.max(qualityVal, 10), 90) / 100;

        const totalQ = questions.length;
        let processedQ = 0;
        const normFn = normalizeWhitespaceFn || (str => String(str || '').replace(/\u00A0/g, ' ').replace(/\s+/g, ' ').trim());

        const cleanedQuestions = [];
        for (const q of questions) {
            if (task && task.isAborted()) throw new Error('הפעולה בוטלה על ידי המשתמש.');
            processedQ++;
            let img = q.image;
            if (shouldCompress && img) {
                const skipCompression = q.imageNoCompress === true;
                if (!skipCompression) {
                    if (task) {
                        const progressPct = 10 + Math.round((processedQ / totalQ) * 70);
                        task.update(progressPct, `דוחס תמונה לשאלה ${processedQ} מתוך ${totalQ}...`);
                    }
                    img = await compressImageBase64(img, quality);
                }
            } else if (task && processedQ % 5 === 0) {
                const progressPct = 10 + Math.round((processedQ / totalQ) * 70);
                task.update(progressPct, `מעבד שאלה ${processedQ} מתוך ${totalQ}...`);
            }

            cleanedQuestions.push({
                question: normFn(q.question),
                options: q.options.map((opt) => normFn(opt)),
                correctIndex: q.correctIndex,
                ...(q.shuffleOptions ? { shuffleOptions: true } : {}),
                ...(img ? { image: img } : {})
            });
        }

        if (task) task.update(85, 'טוען קובצי תבנית HTML/CSS/JS...');
        const { indexHtml, styleCss, quizCoreJs, appJs } = await getTemplateSources();
        if (task) task.update(92, 'משלב קוד ונתונים למסמך עצמאי...');

        const exporter = quizExportModule || (typeof window !== 'undefined' ? window.QuizExport : null);
        if (!exporter) {
            throw new Error('QuizExport מודול לא נמצא.');
        }

        const styledHtml = exporter.injectStylesheet(indexHtml, styleCss);
        const onlineBuilderUrl = 'https://elonuziel.github.io/interactive-test-creator/';
        const standaloneNavHtml = exporter.setBuilderLink(styledHtml, onlineBuilderUrl);
        const dataHtml = exporter.injectInlineQuestions(standaloneNavHtml, cleanedQuestions);
        const withCore = exporter.injectScript(dataHtml, 'quiz-core.js', quizCoreJs);
        return exporter.injectScript(withCore, 'app.js', appJs);
    }

    return {
        getTemplateSources,
        compressImageBase64,
        createStandaloneQuizHtml
    };
}));

