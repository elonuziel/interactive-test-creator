const assert = require('assert');
const {
    normalizeWhitespace,
    stripExamFooterArtifacts,
    normalizeQuestionsJson,
    parseCsvRows,
    extractAnswersForForm,
    mergeAnswers,
    getStorageKey,
    getCustomSelectedIndices,
    validateQuestions,
    formatDuration,
    calculateTimingStats
} = require('../quiz-core.js');


let testsPassed = 0;
let testsFailed = 0;

async function runTest(suiteName, name, fn) {
    const startMs = Date.now();
    try {
        await fn();
        const durationMs = Date.now() - startMs;
        console.log(`  ✅ [PASS] ${suiteName} -> ${name} (${durationMs}ms)`);
        testsPassed++;
    } catch (err) {
        console.error(`  ❌ [FAIL] ${suiteName} -> ${name}`);
        console.error(`     Error: ${err.message}`);
        testsFailed++;
    }
}

async function main() {
console.log('🧪 Interactive Test Creator — Node.js Component Integration Unit Tests\n');
testsPassed = 0;
testsFailed = 0;

await runTest('JSON Normalization', 'Strips option letter prefixes and cleans double spaces', () => {
    const input = [{ question: '  שאלה  1.  מהו DNA?  ', options: ['א. חומצת גרעין', 'ב. חלבון', 'ג. שומן'] }];
    const result = normalizeQuestionsJson(input);
    assert.strictEqual(result.length, 1);
    assert.strictEqual(result[0].question, 'שאלה 1. מהו DNA?');
    assert.deepStrictEqual(result[0].options, ['חומצת גרעין', 'חלבון', 'שומן']);
});

await runTest('JSON Normalization', 'Removes PDF footer artifacts', () => {
    const input = [{ question: 'מהו תפקוד המיטוכונדריה? עמוד 3 מתוך 12 - סוף המבחן -', options: ['ייצור אנרגיה', 'תפיסת סוכרים'] }];
    const result = normalizeQuestionsJson(input);
    assert.strictEqual(result[0].question, 'מהו תפקוד המיטוכונדריה?');
    assert.strictEqual(stripExamFooterArtifacts('x [cite: 12]'), 'x');
});

await runTest('JSON Normalization', 'Filters empty questions and resets invalid correctIndex', () => {
    const input = [
        { question: '', options: ['תשובה 1'] },
        { question: 'שאלה תקינה', options: ['תשובה 1', 'תשובה 2'], correctIndex: 99 }
    ];
    const result = normalizeQuestionsJson(input);
    assert.strictEqual(result.length, 1);
    assert.strictEqual(result[0].correctIndex, 0);
});

await runTest('CSV Answer Key Merging', 'Parses quoted CSV and extracts Hebrew/numeric answers', () => {
    const csv = 'Form,Q1,Q2,Q3,Q4\n76,א,ב,ג,ד\n32,4,3,2,1';
    const rows = parseCsvRows(csv);
    assert.deepStrictEqual(Array.from(extractAnswersForForm(rows, '76').entries()), [[1, 0], [2, 1], [3, 2], [4, 3]]);
    assert.deepStrictEqual(Array.from(extractAnswersForForm(rows, '32').entries()), [[1, 3], [2, 2], [3, 1], [4, 0]]);
});

await runTest('CSV Answer Key Merging', 'Performance benchmark & edge case validation for extractAnswersForForm', () => {
    const rowsWithHeaders = [
        ['שאלון', 'Q1', 'Q2', 'Q3', 'Q4'],
        ['101.0', 'א', 'ב', 'ג', 'ד'],
        ['102', '1', '2', '3', '4']
    ];
    assert.deepStrictEqual(Array.from(extractAnswersForForm(rowsWithHeaders, '101').entries()), [[1, 0], [2, 1], [3, 2], [4, 3]]);
    assert.deepStrictEqual(Array.from(extractAnswersForForm(rowsWithHeaders, '102').entries()), [[1, 0], [2, 1], [3, 2], [4, 3]]);

    assert.strictEqual(extractAnswersForForm(rowsWithHeaders, '999').size, 0);
    assert.deepStrictEqual(Array.from(extractAnswersForForm(rowsWithHeaders, '').entries()), [[1, 0], [2, 1], [3, 2], [4, 3]]);

    const largeRows = [['שאלון']];
    for (let col = 1; col <= 50; col++) {
        largeRows[0].push('Q' + col);
    }
    for (let r = 1; r <= 5000; r++) {
        const row = [String(r)];
        for (let col = 1; col <= 50; col++) {
            row.push(['א', 'ב', 'ג', 'ד'][(r + col) % 4]);
        }
        largeRows.push(row);
    }

    const startMs = Date.now();
    const iterations = 50;
    let resMap;
    for (let i = 0; i < iterations; i++) {
        resMap = extractAnswersForForm(largeRows, '4999');
    }
    const durationMs = Date.now() - startMs;
    assert.strictEqual(resMap.size, 50);
    console.log('     📊 [BENCHMARK] extractAnswersForForm (' + iterations + ' calls x 5,000 rows x 50 cols): ' + durationMs + 'ms');
});

await runTest('CSV Answer Key Merging', 'Merges correctIndex and disables random shuffling', () => {
    const questions = [
        { question: 'Q1', options: ['A', 'B', 'C'], correctIndex: 0, shuffleOptions: true },
        { question: 'Q2', options: ['A', 'B', 'C'], correctIndex: 0, shuffleOptions: true }
    ];
    const merged = mergeAnswers(questions, new Map([[1, 2], [2, 1]]));
    assert.strictEqual(merged[0].correctIndex, 2);
    assert.strictEqual(merged[1].correctIndex, 1);
    assert.strictEqual(merged[0].shuffleOptions, false);
});

await runTest('Storage Hashing', 'Generates deterministic keys based on the full question sample', () => {
    const first = [{ question: 'Botany question test', options: ['1', '2'] }];
    const second = [{ question: 'Physics question test', options: ['1', '2'] }];
    assert.strictEqual(getStorageKey(first), getStorageKey(first));
    assert.notStrictEqual(getStorageKey(first), getStorageKey(second));
    assert.ok(getStorageKey(first).startsWith('quiz_answers_'));
});

await runTest('Question Validation', 'Rejects malformed questions with actionable errors', () => {
    const errors = validateQuestions([
        { question: '', options: ['only one'], correctIndex: 3 },
        { question: 'Valid', options: ['A', 'B'], correctIndex: 0, sourcePage: 0 }
    ]);
    assert.strictEqual(errors.length, 4);
    assert.ok(errors.some((error) => error.includes('שאלה 1: חסר טקסט')));
    assert.ok(errors.some((error) => error.includes('שאלה 2: sourcePage אינו תקין')));
});

await runTest('Mix & Match Custom Practice', 'Combines categories and manual selections without duplicates', () => {
    const answers = [
        { selectedOptionId: 1, isCorrect: false },
        { selectedOptionId: 0, isCorrect: true },
        null,
        { selectedOptionId: 0, isCorrect: true }
    ];
    const flags = [true, false, false, true];
    const questions = answers.map((_, index) => ({ question: `Q${index + 1}` }));
    const selected = getCustomSelectedIndices(questions, answers, flags, {
        wrong: true,
        unanswered: true,
        flagged: true
    }, [2]);
    assert.deepStrictEqual(selected, [0, 2, 3]);
});

await runTest('updateCustomPracticeSelection Helper', 'Updates DOM elements or handles null elements gracefully', () => {
    let customSelectedCount = { textContent: '' };
    let startCustomPracticeBtn = { disabled: false };

    function updateCustomPracticeSelection(getIndicesFn, countEl, btnEl) {
        const count = getIndicesFn().length;
        if (countEl) countEl.textContent = count;
        if (btnEl) btnEl.disabled = (count === 0);
    }

    updateCustomPracticeSelection(() => [0, 1, 2], customSelectedCount, startCustomPracticeBtn);
    assert.strictEqual(customSelectedCount.textContent, 3);
    assert.strictEqual(startCustomPracticeBtn.disabled, false);

    updateCustomPracticeSelection(() => [], customSelectedCount, startCustomPracticeBtn);
    assert.strictEqual(customSelectedCount.textContent, 0);
    assert.strictEqual(startCustomPracticeBtn.disabled, true);

    // Test null elements
    updateCustomPracticeSelection(() => [1], null, null);
});


await runTest('Standalone Export', 'Escapes script terminators and inlines scripts', () => {
    const QuizExport = require('../quiz-export.js');
    const template = '<link rel="stylesheet" href="style.css"><script id="quiz-data" type="application/json"></script><script src="quiz-core.js"></script><script src="app.js"></script>';
    let html = QuizExport.injectStylesheet(template, 'body{}');
    html = QuizExport.injectInlineQuestions(html, [{ question: '</script><script>alert(1)</script>', options: ['A', 'B'], correctIndex: 0 }]);
    html = QuizExport.injectScript(html, 'quiz-core.js', 'console.log("core");');
    html = QuizExport.injectScript(html, 'app.js', 'console.log("app");');

    assert.strictEqual((html.match(/id="quiz-data"/g) || []).length, 1);
    assert.ok(!html.includes('</script><script>alert(1)'));
    assert.ok(html.includes('<style>body{}</style>'));
    assert.ok(html.includes('<script>console.log("core");</script>'));
    assert.ok(html.includes('<script>console.log("app");</script>'));
    assert.ok(!html.includes('src="quiz-core.js"'));
    assert.ok(!html.includes('src="app.js"'));
});

await runTest('Progress System DOM & Styles', 'Verifies progress bar DOM markup in index.html and style.css', () => {
    const fs = require('fs');
    const path = require('path');
    const indexHtml = fs.readFileSync(path.join(__dirname, '../index.html'), 'utf8');
    const styleCss = fs.readFileSync(path.join(__dirname, '../style.css'), 'utf8');

    // Check DOM elements exist
    assert.ok(indexHtml.includes('id="sticky-progress-banner"'), 'sticky-progress-banner missing');
    assert.ok(indexHtml.includes('id="sticky-progress-fill"'), 'sticky-progress-fill missing');
    assert.ok(indexHtml.includes('id="sticky-progress-abort-btn"'), 'sticky-progress-abort-btn missing');
    assert.ok(indexHtml.includes('id="progress-card"'), 'progress-card missing');
    assert.ok(indexHtml.includes('id="progress-fill"'), 'progress-fill missing');
    assert.ok(indexHtml.includes('id="progress-abort-btn"'), 'progress-abort-btn missing');

    // Check CSS rules exist
    assert.ok(styleCss.includes('.sticky-progress-banner'), '.sticky-progress-banner CSS missing');
    assert.ok(styleCss.includes('.progress-card'), '.progress-card CSS missing');
    assert.ok(styleCss.includes('.progress-bar-fill'), '.progress-bar-fill CSS missing');
    assert.ok(styleCss.includes('.progress-abort-btn'), '.progress-abort-btn CSS missing');
    assert.ok(styleCss.includes('.indeterminate'), '.indeterminate animation CSS missing');
});

await runTest('Progress Controller Lifecycle', 'Validates AbortController and progress state calculation', () => {
    const abortCtrl = new AbortController();
    assert.strictEqual(abortCtrl.signal.aborted, false);
    abortCtrl.abort();
    assert.strictEqual(abortCtrl.signal.aborted, true);

    const clamp = (val) => Math.max(0, Math.min(100, Math.round(val || 0)));
    assert.strictEqual(clamp(-10), 0);
    assert.strictEqual(clamp(50.4), 50);
    assert.strictEqual(clamp(150), 100);
});

await runTest('Auto-Advance Countdown', 'Verifies countdown markup generation and styles in player', () => {
    const fs = require('fs');
    const path = require('path');
    const appJs = fs.readFileSync(path.join(__dirname, '../app.js'), 'utf8');
    const styleCss = fs.readFileSync(path.join(__dirname, '../style.css'), 'utf8');

    assert.ok(appJs.includes('autoAdvanceInterval'), 'autoAdvanceInterval missing in app.js');
    assert.ok(appJs.includes('auto-advance-seconds'), 'auto-advance-seconds class missing in app.js');
    assert.ok(appJs.includes('auto-advance-bar-fill'), 'auto-advance-bar-fill missing in app.js');

    assert.ok(styleCss.includes('.auto-advance-indicator'), '.auto-advance-indicator missing in style.css');
    assert.ok(styleCss.includes('.auto-advance-seconds'), '.auto-advance-seconds missing in style.css');
    assert.ok(styleCss.includes('.auto-advance-bar-fill'), '.auto-advance-bar-fill missing in style.css');
    assert.ok(styleCss.includes('@keyframes autoAdvanceShrink'), 'autoAdvanceShrink animation missing in style.css');
});

await runTest('Progress Controller Initialization', 'Verifies ProgressController init sets elements, callbacks, and attaches abort button click handlers', () => {
    const ProgressController = require('../js/progress-controller.js');

    function createMockElement() {
        const listeners = {};
        return {
            listeners,
            classList: {
                add: () => {},
                remove: () => {},
                toggle: () => {}
            },
            style: {},
            textContent: '',
            disabled: false,
            setAttribute: () => {},
            addEventListener(event, fn) {
                if (!listeners[event]) listeners[event] = [];
                listeners[event].push(fn);
            },
            click() {
                if (listeners['click']) {
                    listeners['click'].forEach(fn => fn());
                }
            }
        };
    }

    // Test init with null/undefined parameters (default fallbacks)
    ProgressController.init();

    let statusMsg = null;
    let isError = null;
    const statusCallback = (msg, err) => {
        statusMsg = msg;
        isError = err;
    };

    const progressAbortBtn = createMockElement();
    const stickyProgressAbortBtn = createMockElement();
    const progressCard = createMockElement();

    ProgressController.init({
        progressAbortBtn,
        stickyProgressAbortBtn,
        progressCard
    }, statusCallback);

    // Ensure event listeners were registered
    assert.ok(progressAbortBtn.listeners['click'] && progressAbortBtn.listeners['click'].length > 0);
    assert.ok(stickyProgressAbortBtn.listeners['click'] && stickyProgressAbortBtn.listeners['click'].length > 0);

    // Clicking when activeTask is null should not fail or trigger abort
    progressAbortBtn.click();
    assert.strictEqual(ProgressController.activeTask, null);

    // Start task and test abort button click on progressAbortBtn
    const task1 = ProgressController.startTask('Task 1', { cancellable: true });
    assert.strictEqual(task1.isAborted(), false);

    progressAbortBtn.click();
    assert.strictEqual(task1.isAborted(), true);
    assert.strictEqual(statusMsg, 'הפעולה בוטלה על ידי המשתמש.');

    if (ProgressController.dismissTimeout) {
        clearTimeout(ProgressController.dismissTimeout);
        ProgressController.dismissTimeout = null;
    }

    // Start another task and test stickyProgressAbortBtn click
    const task2 = ProgressController.startTask('Task 2', { cancellable: true });
    assert.strictEqual(task2.isAborted(), false);

    stickyProgressAbortBtn.click();
    assert.strictEqual(task2.isAborted(), true);

    if (ProgressController.dismissTimeout) {
        clearTimeout(ProgressController.dismissTimeout);
        ProgressController.dismissTimeout = null;
    }
});

await runTest('Progress Controller Module', 'Verifies ProgressController starts tasks, dispatches updates, and handles abort signals', () => {
    const ProgressController = require('../js/progress-controller.js');
    const task = ProgressController.startTask('Test task', { cancellable: true, detail: 'Processing...' });
    assert.ok(task);
    assert.strictEqual(task.isAborted(), false);
    assert.strictEqual(ProgressController.activeTask.id, task.id);

    task.update(45, 'Working on 45%');
    assert.strictEqual(task.isAborted(), false);

    task.abort('User cancelled');
    assert.strictEqual(task.isAborted(), true);
});

await runTest('Question Parser - WhiteSpace Normalization', 'Handles null, undefined, NBSP, multiline, and extra whitespace correctly', () => {
    const QuestionParser = require('../js/question-parser.js');
    assert.strictEqual(QuestionParser.normalizeWhitespace(null), '');
    assert.strictEqual(QuestionParser.normalizeWhitespace(undefined), '');
    assert.strictEqual(QuestionParser.normalizeWhitespace(''), '');
    assert.strictEqual(QuestionParser.normalizeWhitespace('   '), '');
    assert.strictEqual(QuestionParser.normalizeWhitespace('hello\u00A0world'), 'hello world');
    assert.strictEqual(QuestionParser.normalizeWhitespace('  hello \t \n world  '), 'hello world');
    assert.strictEqual(QuestionParser.normalizeWhitespace('\u00A0\u00A0test\u00A0\u00A0'), 'test');
    assert.strictEqual(QuestionParser.normalizeWhitespace(123), '123');
    assert.strictEqual(QuestionParser.normalizeWhitespace('  שאלה   מספר  1  '), 'שאלה מספר 1');
});

await runTest('Question Parser - Markdown', 'Parses Hebrew exam questions formatted in Markdown', () => {
    const QuestionParser = require('../js/question-parser.js');
    const md = [
        '### שאלה 1: מהו התפקיד העיקרי של ההמוגלובין? (עמוד 2)',
        '- א. נשיאת חמצן בדם',
        '- ב. פירוק סוכרים',
        '- ג. הגנה מפני נגיפים',
        '- ד. ייצור הורמונים',
        '',
        '### שאלה 2: איזה מהבאים אינו אב-מזון?',
        '- א. ויטמין C',
        '- ב. חלבון',
        '- ג. פחמימה',
        '- ד. שומן'
    ].join('\n');

    const parsed = QuestionParser.parseQuestionsFromMarkdown(md);
    assert.strictEqual(parsed.length, 2);
    assert.strictEqual(parsed[0].question, 'מהו התפקיד העיקרי של ההמוגלובין?');
    assert.strictEqual(parsed[0].sourcePage, 2);
    assert.strictEqual(parsed[0].options.length, 4);
    assert.strictEqual(parsed[0].options[0], 'נשיאת חמצן בדם');
    assert.strictEqual(parsed[1].question, 'איזה מהבאים אינו אב-מזון?');
    assert.strictEqual(parsed[1].sourcePage, 1);
});

await runTest('Question Parser - Hebrew Word Order & Heuristics', 'Detects reversed Hebrew and cleans header prefixes', () => {
    const QuestionParser = require('../js/question-parser.js');
    const normalHebrew = 'שאלה מספר 1: מהי הביולוגיה?\nשאלה מספר 2: מהי הכימיה?';
    assert.strictEqual(QuestionParser.maybeFixHebrewWordOrder(normalHebrew), normalHebrew);

    const reversedHebrew = [
        '1 שאלה מספר :מהי',
        '2 שאלה מספר :מהי',
        '3 שאלה מספר :מהי',
        '4 שאלה מספר :מהי'
    ].join('\n');
    const fixed = QuestionParser.maybeFixHebrewWordOrder(reversedHebrew);
    assert.ok(fixed.includes('שאלה מספר'));

    assert.strictEqual(QuestionParser.stripQuestionHeaderPrefix('### שאלה מספר 12: מהו מבנה התא?'), 'מהו מבנה התא?');
    assert.strictEqual(QuestionParser.stripQuestionHeaderPrefix('14) מהו לחץ הדם?'), 'מהו לחץ הדם?');
    assert.strictEqual(QuestionParser.stripQuestionHeaderPrefix('שאלה 5: הסבר את תהליך הפוטוסינתזה'), 'הסבר את תהליך הפוטוסינתזה');
});

await runTest('Question Parser - Text Extraction & Inline Options', 'Parses text with inline answer options', () => {
    const QuestionParser = require('../js/question-parser.js');
    const rawText = [
        'שאלה 1',
        'איזה מהאיברים הבאים שייך למערכת הנשימה?',
        'א. ריאות ב. כליות ג. קיבה ד. טחול',
        '',
        'שאלה 2',
        'מהי יחידת המבנה הבסיסית של כל היצורים החיים?',
        'א. התא',
        'ב. הרקמה',
        'ג. האיבר',
        'ד. המערכת'
    ].join('\n');

    const parsed = QuestionParser.parseQuestionsFromText(rawText);
    assert.strictEqual(parsed.length, 2);
    assert.strictEqual(parsed[0].options.length, 4);
    assert.strictEqual(parsed[0].options[0], 'ריאות');
    assert.strictEqual(parsed[0].options[1], 'כליות');
    assert.strictEqual(parsed[1].options.length, 4);
    assert.strictEqual(parsed[1].options[0], 'התא');
});

await runTest('Question Parser - CSV Merging Error Handling', 'Handles errors silently in non-explicit mode and reports errors in explicit mode', async () => {
    const QuestionParser = require('../js/question-parser.js');

    let toastMsg = null;
    let taskFailedMsg = null;

    const mockState = {
        questions: [{ question: "Q1", options: ["A", "B"] }]
    };
    const mockElements = {
        csvFile: { files: [{ name: "answers.csv", text: async () => { throw new Error("Read error"); } }] },
        formNumber: { value: "101" }
    };
    const mockProgressController = {
        startTask: () => ({
            update: () => {},
            finish: () => {},
            fail: (msg) => { taskFailedMsg = msg; }
        })
    };

    // Non-explicit merge failure should handle quietly without console output or toasts/task failures
    await QuestionParser.tryMergeAnswersFromCsv({
        explicit: false,
        elements: mockElements,
        state: mockState,
        progressController: mockProgressController,
        showToastFn: (msg) => { toastMsg = msg; }
    });

    assert.strictEqual(toastMsg, null);
    assert.strictEqual(taskFailedMsg, null);

    // Explicit merge failure should report errors via toast and task failure
    await QuestionParser.tryMergeAnswersFromCsv({
        explicit: true,
        elements: mockElements,
        state: mockState,
        progressController: mockProgressController,
        showToastFn: (msg) => { toastMsg = msg; }
    });

    assert.ok(toastMsg && toastMsg.includes("Read error"));
    assert.ok(taskFailedMsg && taskFailedMsg.includes("Read error"));
});

await runTest('PDF Service - groupPdfTextItemsToLines Line Grouping & Performance', 'Groups items by y geometry efficiently', () => {
    const PdfService = require('../js/pdf-service.js');

    const items = [
        { str: 'שאלה 1', transform: [1, 0, 0, 1, 100, 700], dir: 'rtl', width: 50 },
        { str: 'מהו DNA?', transform: [1, 0, 0, 1, 40, 702], dir: 'rtl', width: 50 },
        { str: 'א. חומצת גרעין', transform: [1, 0, 0, 1, 40, 680], dir: 'rtl', width: 80 },
        { str: 'ב. חלבון', transform: [1, 0, 0, 1, 40, 660], dir: 'rtl', width: 50 }
    ];

    const lines = PdfService.groupPdfTextItemsToLines(items);
    assert.strictEqual(lines.length, 3);
    assert.ok(lines[0].includes('שאלה 1') && lines[0].includes('מהו DNA?'));
    assert.strictEqual(lines[1], 'א. חומצת גרעין');
    assert.strictEqual(lines[2], 'ב. חלבון');

    const largeItems = [];
    for (let i = 0; i < 5000; i++) {
        const lineIdx = Math.floor(i / 5);
        const y = 10000 - (lineIdx * 12) + (i % 2);
        const x = (i % 5) * 100;
        largeItems.push({
            str: 'item_' + i,
            transform: [1, 0, 0, 1, x, y],
            dir: 'ltr',
            width: 40
        });
    }

    const startMs = Date.now();
    const benchmarkLines = PdfService.groupPdfTextItemsToLines(largeItems);
    const durationMs = Date.now() - startMs;

    assert.strictEqual(benchmarkLines.length, 1000);
    console.log('     📊 [BENCHMARK] groupPdfTextItemsToLines (5,000 items): ' + durationMs + 'ms');
});

await runTest('PDF Service - Heuristics & Geometry', 'Evaluates direction detection and Hebrew breakage scores', () => {
    const PdfService = require('../js/pdf-service.js');
    assert.strictEqual(PdfService.hasHebrew('שלום עולם'), true);
    assert.strictEqual(PdfService.hasHebrew('Hello World 123'), false);

    const dirHeb = PdfService.detectLineDirection([{ text: 'שלום', dir: 'rtl' }]);
    assert.strictEqual(dirHeb, 'rtl');

    const dirEng = PdfService.detectLineDirection([{ text: 'Hello', dir: 'ltr' }]);
    assert.strictEqual(dirEng, 'ltr');

    const breakageClean = PdfService.computeHebrewBreakageScore('משפט שלם בעברית תקינה לחלוטין');
    const breakageBroken = PdfService.computeHebrewBreakageScore('מ ש פ ט מ פ ו ז ר ב ע ב ר י ת');
    assert.ok(breakageClean < breakageBroken);
});

await runTest('Gemini Service - Models & Error Classification', 'Classifies Gemini errors and sorts candidate models', () => {
    const GeminiService = require('../js/gemini-service.js');
    const err401 = GeminiService.getGeminiErrorInfo(401, 'Unauthorized');
    assert.strictEqual(err401.code, 'auth');
    assert.strictEqual(err401.retryNextModel, false);

    const err429 = GeminiService.getGeminiErrorInfo(429, 'Quota exceeded');
    assert.strictEqual(err429.code, 'quota');
    assert.strictEqual(err429.retryNextModel, true);

    const candidates = [
        { version: 'v1beta', model: 'gemini-1.5-flash' },
        { version: 'v1', model: 'gemini-2.5-flash' },
        { version: 'v1beta', model: 'gemini-2.0-flash' }
    ];
    const sorted = GeminiService.sortGeminiModelCandidates(candidates);
    assert.strictEqual(sorted[0].model, 'gemini-2.5-flash');
    assert.strictEqual(sorted[1].model, 'gemini-2.0-flash');
    assert.strictEqual(sorted[2].model, 'gemini-1.5-flash');
});

await runTest('Gemini Service - Pacing Configuration', 'Maintains safe sequential interPageDelayMs between 1000ms and 2500ms', () => {
    const GeminiService = require('../js/gemini-service.js');
    assert.ok(GeminiService.GEMINI_CONFIG.interPageDelayMs >= 1000 && GeminiService.GEMINI_CONFIG.interPageDelayMs <= 2500,
        `interPageDelayMs (${GeminiService.GEMINI_CONFIG.interPageDelayMs}ms) should be balanced between 1000ms and 2500ms for free-tier rate safety`);
});

await runTest('Gemini Service - verifyTestWithGemini Fallback', 'Gracefully falls back to original parsedQuestions on API/JSON failure', async () => {
    const GeminiService = require('../js/gemini-service.js');
    const sampleQuestions = [{ question: 'מהו DNA?', options: ['חומצת גרעין', 'חלבון'], correctIndex: 0 }];

    // Mock global fetch to return invalid non-JSON or HTTP errors
    const originalFetch = global.fetch;
    global.fetch = async () => ({
        ok: true,
        json: async () => ({
            candidates: [{ content: { parts: [{ text: 'Invalid non-JSON response' }] } }]
        })
    });

    try {
        const result = await GeminiService.verifyTestWithGemini(sampleQuestions, 'dummy-api-key');
        assert.deepStrictEqual(result, sampleQuestions);
    } finally {
        global.fetch = originalFetch;
    }
});

await runTest('Module Scripts Loading in index.html', 'Verifies all modular scripts are referenced in correct dependency order', () => {
    const fs = require('fs');
    const path = require('path');
    const indexHtml = fs.readFileSync(path.join(__dirname, '../index.html'), 'utf8');

    const expectedScripts = [
        'quiz-core.js',
        'quiz-export.js',
        'js/progress-controller.js',
        'js/gemini-service.js',
        'js/pdf-service.js',
        'js/ocr-tesseract.js',
        'js/question-parser.js',
        'js/cropper-modal.js',
        'js/editor-ui.js',
        'js/export-service.js',
        'generator.js'
    ];

    let lastIndex = -1;
    for (const script of expectedScripts) {
        const escaped = script.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        const regex = new RegExp(`src="${escaped}(?:\\?[^"]*)?"`);
        const match = regex.exec(indexHtml);
        assert.ok(match !== null, `Script ${script} is missing from index.html`);
        const idx = match.index;
        assert.ok(idx > lastIndex, `Script ${script} is loaded out of order in index.html`);
        lastIndex = idx;
    }
});

await runTest('PWA Manifest & Service Worker Integrity', 'Verifies web manifest and service worker precache assets exist', () => {
    const fs = require('fs');
    const path = require('path');
    const manifestPath = path.join(__dirname, '../manifest.webmanifest');
    const swPath = path.join(__dirname, '../sw.js');

    assert.ok(fs.existsSync(manifestPath), 'manifest.webmanifest is missing');
    assert.ok(fs.existsSync(swPath), 'sw.js is missing');

    const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
    assert.ok(manifest.name && manifest.name.length > 0, 'PWA manifest name is missing');
    assert.strictEqual(manifest.display, 'standalone');
    assert.ok(Array.isArray(manifest.icons) && manifest.icons.length > 0, 'PWA manifest icons are missing');

    const swContent = fs.readFileSync(swPath, 'utf8');
    assert.ok(swContent.includes('CACHE_NAME'), 'CACHE_NAME missing in sw.js');
    assert.ok(swContent.includes('PRECACHE_ASSETS'), 'PRECACHE_ASSETS missing in sw.js');
});


await runTest('Cropper Modal - getPdfBytesForCrop', 'Returns null when appState is uninitialized or missing PDF data', async () => {
    const CropperModal = require('../js/cropper-modal.js');
    CropperModal.initCropperModal({}, {});
    const result = await CropperModal.getPdfBytesForCrop();
    assert.strictEqual(result, null);
});

await runTest('Cropper Modal - getPdfBytesForCrop', 'Returns Uint8Array when appState contains pdfBytes array', async () => {
    const CropperModal = require('../js/cropper-modal.js');
    const pdfBytes = [1, 2, 3, 4, 5];
    CropperModal.initCropperModal({ pdfBytes }, {});
    const result = await CropperModal.getPdfBytesForCrop();
    assert.ok(result instanceof Uint8Array);
    assert.deepStrictEqual(Array.from(result), pdfBytes);
});

await runTest('Cropper Modal - getPdfBytesForCrop', 'Converts and caches pdfArrayBuffer into pdfBytes', async () => {
    const CropperModal = require('../js/cropper-modal.js');
    const buffer = new Uint8Array([10, 20, 30]).buffer;
    const state = { pdfArrayBuffer: buffer };
    CropperModal.initCropperModal(state, {});
    const result = await CropperModal.getPdfBytesForCrop();
    assert.ok(result instanceof Uint8Array);
    assert.deepStrictEqual(Array.from(result), [10, 20, 30]);
    assert.ok(state.pdfBytes instanceof Uint8Array);
});

await runTest('Cropper Modal - getPdfBytesForCrop', 'Reads file input arrayBuffer when state lacks cached bytes', async () => {
    const CropperModal = require('../js/cropper-modal.js');
    const state = {};
    const mockFile = {
        arrayBuffer: async () => new Uint8Array([100, 200]).buffer
    };
    CropperModal.initCropperModal(state, { pdfFile: { files: [mockFile] } });
    const result = await CropperModal.getPdfBytesForCrop();
    assert.ok(result instanceof Uint8Array);
    assert.deepStrictEqual(Array.from(result), [100, 200]);
    assert.ok(state.pdfBytes instanceof Uint8Array);
});

await runTest('Cropper Modal - getPdfBytesForCrop', 'Propagates error when pdfFile input arrayBuffer fails to read', async () => {
    const CropperModal = require('../js/cropper-modal.js');
    const mockFile = {
        arrayBuffer: async () => { throw new Error('Failed to read PDF file bytes'); }
    };
    CropperModal.initCropperModal({}, { pdfFile: { files: [mockFile] } });
    await assert.rejects(
        async () => { await CropperModal.getPdfBytesForCrop(); },
        { message: 'Failed to read PDF file bytes' }
    );
});

await runTest('Exam Timing & Analytics', 'Formats durations into mm:ss and hh:mm:ss correctly', () => {
    assert.strictEqual(formatDuration(0), '00:00');
    assert.strictEqual(formatDuration(45), '00:45');
    assert.strictEqual(formatDuration(65), '01:05');
    assert.strictEqual(formatDuration(3600), '01:00:00');
    assert.strictEqual(formatDuration(3725), '01:02:05');
});

await runTest('Exam Timing & Analytics', 'Calculates total time, per-question active times, and mean time', () => {
    const questionTimes = [20, 40, 60, 0]; // 3 answered with times, 1 skipped/zero
    const stats = calculateTimingStats(questionTimes);
    assert.strictEqual(stats.totalSeconds, 120);
    assert.strictEqual(stats.activeCount, 3);
    assert.strictEqual(stats.meanSeconds, 40); // 120 / 3 = 40
    assert.strictEqual(stats.formattedTotal, '02:00');
    assert.strictEqual(stats.formattedMean, '40 שנ\'');

    const emptyStats = calculateTimingStats([]);
    assert.strictEqual(emptyStats.totalSeconds, 0);
    assert.strictEqual(emptyStats.meanSeconds, 0);
});

await runTest('Exam Timing & Analytics DOM & Styles', 'Verifies timer elements in quiz_player.html and styles in style.css', () => {
    const fs = require('fs');
    const path = require('path');
    const quizPlayerHtml = fs.readFileSync(path.join(__dirname, '../quiz_player.html'), 'utf8');
    const styleCss = fs.readFileSync(path.join(__dirname, '../style.css'), 'utf8');
    const indexHtml = fs.readFileSync(path.join(__dirname, '../index.html'), 'utf8');

    assert.ok(quizPlayerHtml.includes('id="quiz-timer-toggle"'), 'quiz-timer-toggle missing in quiz_player.html');
    assert.ok(quizPlayerHtml.includes('id="exam-timer-badge"'), 'exam-timer-badge missing in quiz_player.html');
    assert.ok(quizPlayerHtml.includes('id="question-time-badge"'), 'question-time-badge missing in quiz_player.html');
    assert.ok(quizPlayerHtml.includes('id="timing-analytics-card"'), 'timing-analytics-card missing in quiz_player.html');

    assert.ok(styleCss.includes('.timer-badge'), '.timer-badge missing in style.css');
    assert.ok(styleCss.includes('.question-time-badge'), '.question-time-badge missing in style.css');
    assert.ok(styleCss.includes('.timing-analytics-card'), '.timing-analytics-card missing in style.css');
    assert.ok(styleCss.includes('.review-time-badge'), '.review-time-badge missing in style.css');
    assert.ok(styleCss.includes('.thumbnail-placeholder'), '.thumbnail-placeholder missing in style.css');
    assert.ok(indexHtml.includes('thumbnail-placeholder'), 'thumbnail-placeholder missing in index.html');
});

await runTest('PDF Service - Lazy Sidebar Thumbnails', 'Verifies renderSingleThumbnail export and lazy loading setup', () => {
    const pdfService = require('../js/pdf-service.js');
    assert.strictEqual(typeof pdfService.renderSingleThumbnail, 'function', 'renderSingleThumbnail must be exported');
});

await runTest('Quiz Player Refactor - QuizSessionState', 'Manages session lifecycle, answers, flags, and timing committing', () => {
    const { QuizSessionState } = require('../app.js');
    const state = new QuizSessionState();
    const sampleQuestions = [
        { question: 'שאלה 1', options: [{ id: 0, text: 'א' }, { id: 1, text: 'ב' }], correctIndex: 0 },
        { question: 'שאלה 2', options: [{ id: 0, text: 'א' }, { id: 1, text: 'ב' }], correctIndex: 1 },
        { question: 'שאלה 3', options: [{ id: 0, text: 'א' }, { id: 1, text: 'ב' }], correctIndex: 0 }
    ];

    state.allMasterQuestions = [...sampleQuestions];
    state.initSession({ mode: 'new', questions: sampleQuestions });

    assert.strictEqual(state.questions.length, 3);
    assert.strictEqual(state.currentQuestionIndex, 0);
    assert.strictEqual(state.userAnswers.length, 3);
    assert.strictEqual(state.userFlags.length, 3);
    assert.strictEqual(state.questionTimes.length, 3);

    // Record answer
    const isCorrect1 = state.recordAnswer(0, 0, 0);
    assert.strictEqual(isCorrect1, true);
    assert.deepStrictEqual(state.userAnswers[0], { selectedOptionId: 0, isCorrect: true });

    const isCorrect2 = state.recordAnswer(1, 0, 1);
    assert.strictEqual(isCorrect2, false);
    assert.deepStrictEqual(state.userAnswers[1], { selectedOptionId: 0, isCorrect: false });

    // Flags
    assert.strictEqual(state.toggleFlag(1), true);
    assert.strictEqual(state.userFlags[1], true);
    assert.strictEqual(state.toggleFlag(1), false);
    assert.strictEqual(state.userFlags[1], false);

    // Timing commit
    state.currentQuestionStartTimestamp = Date.now() - 3000; // 3 seconds ago
    state.currentQuestionIndex = 0;
    state.commitCurrentQuestionTime();
    assert.ok(state.questionTimes[0] >= 3, `Expected at least 3 seconds, got ${state.questionTimes[0]}`);
    assert.strictEqual(state.currentQuestionStartTimestamp, null);

    // Payload
    const payload = state.getStoragePayload();
    assert.strictEqual(payload.answers.length, 3);
    assert.strictEqual(payload.questionTimes.length, 3);

    // Resume session
    const resumeState = new QuizSessionState();
    resumeState.questions = [...sampleQuestions];
    resumeState.initSession({
        mode: 'resume',
        savedState: {
            answers: payload.answers,
            flags: [false, true, false],
            index: 1,
            questionTimes: [5, 10, 0],
            totalElapsedSeconds: 15,
            remainingCountdownSeconds: 1785
        }
    });
    assert.strictEqual(resumeState.currentQuestionIndex, 1);
    assert.strictEqual(resumeState.userFlags[1], true);
    assert.strictEqual(resumeState.totalElapsedSeconds, 15);
    assert.deepStrictEqual(resumeState.questionTimes, [5, 10, 0]);

    // Retry incorrect
    const wrongOnly = state.getWrongOrUnansweredQuestions();
    assert.strictEqual(wrongOnly.length, 2); // Q2 (wrong) + Q3 (unanswered)
});

await runTest('Quiz Player Refactor - QuizTimerEngine', 'Controls intervals and auto-advance safely without memory leaks', () => {
    const { QuizTimerEngine, QuizSessionState } = require('../app.js');
    const timer = new QuizTimerEngine();
    const state = new QuizSessionState();
    state.questions = [{ question: 'Q1' }];
    state.initSession({ mode: 'new' });

    timer.startExamTimer({ state });
    assert.ok(timer.examInterval !== null, 'examInterval must be active');
    timer.stopExamTimer(state);
    assert.strictEqual(timer.examInterval, null, 'examInterval must be cleared');

    timer.startAutoAdvance({ durationMs: 500 });
    assert.ok(timer.autoAdvanceTimer !== null, 'autoAdvanceTimer must be set');
    timer.clearAutoAdvance();
    assert.strictEqual(timer.autoAdvanceTimer, null, 'autoAdvanceTimer must be cleared');
    assert.strictEqual(timer.autoAdvanceInterval, null, 'autoAdvanceInterval must be cleared');

    timer.cleanup(state);
});

await runTest('Quiz Player Refactor - QuizUIController DOM Integrity & Settings Sync', 'Resolves player element IDs and synchronizes immediate feedback toggles', () => {
    const { QuizUIController } = require('../app.js');
    const fs = require('fs');
    const path = require('path');

    // 1. Verify quiz_player.html contains correct IDs
    const html = fs.readFileSync(path.join(__dirname, '../quiz_player.html'), 'utf8');
    assert.ok(html.includes('id="immediate-feedback-toggle"'), 'immediate-feedback-toggle missing in quiz_player.html');
    assert.ok(html.includes('id="welcome-immediate-feedback-toggle"'), 'welcome-immediate-feedback-toggle missing in quiz_player.html');
    assert.ok(html.includes('id="question-jump-bar"'), 'question-jump-bar missing in quiz_player.html');
    assert.ok(html.includes('id="progress-bar"'), 'progress-bar missing in quiz_player.html');

    // 2. Test cacheElements and initSettings behavior with mock DOM
    const mockStorage = {};
    const mockElements = {
        'immediate-feedback-toggle': { checked: false, listeners: {}, addEventListener(ev, cb) { this.listeners[ev] = cb; } },
        'welcome-immediate-feedback-toggle': { checked: false, listeners: {}, addEventListener(ev, cb) { this.listeners[ev] = cb; } },
        'question-jump-bar': { innerHTML: '', appendChild() {} },
        'progress-bar': { style: {} },
        'theme-toggle': { listeners: {}, addEventListener(ev, cb) { this.listeners[ev] = cb; } },
        'theme-icon': { innerHTML: '' },
        'builder-nav-link': { href: '', textContent: '' }
    };

    global.document = {
        getElementById: (id) => mockElements[id] || null,
        querySelector: (sel) => sel === '.progress-bar' ? mockElements['progress-bar'] : null,
        querySelectorAll: () => [],
        documentElement: { setAttribute: () => {}, getAttribute: () => 'light' }
    };
    global.localStorage = {
        getItem: (k) => mockStorage[k] || null,
        setItem: (k, v) => { mockStorage[k] = String(v); }
    };

    try {
        const app = new QuizUIController();
        app.cacheElements();
        assert.ok(app.elements.feedbackToggle, 'feedbackToggle must be resolved');
        assert.ok(app.elements.welcomeFeedbackToggle, 'welcomeFeedbackToggle must be resolved');
        assert.ok(app.elements.jumpBar, 'jumpBar must be resolved');
        assert.ok(app.elements.progressBar, 'progressBar must be resolved');

        app.initSettings();
        assert.strictEqual(app.state.isImmediateFeedback, false);

        // Simulate user clicking welcome feedback toggle
        mockElements['welcome-immediate-feedback-toggle'].listeners['change']({ target: { checked: true } });
        assert.strictEqual(app.state.isImmediateFeedback, true);
        assert.strictEqual(mockElements['immediate-feedback-toggle'].checked, true);
        assert.strictEqual(mockElements['welcome-immediate-feedback-toggle'].checked, true);

        // Simulate user clicking top nav toggle
        mockElements['immediate-feedback-toggle'].listeners['change']({ target: { checked: false } });
        assert.strictEqual(app.state.isImmediateFeedback, false);
        assert.strictEqual(mockElements['immediate-feedback-toggle'].checked, false);
        assert.strictEqual(mockElements['welcome-immediate-feedback-toggle'].checked, false);
    } finally {
        delete global.document;
        delete global.localStorage;
    }
});

console.log('\n──────────────────────────────────────────────────────────────');
console.log(`📊 Final Execution Summary: ${testsPassed} Passed, ${testsFailed} Failed.`);
console.log('──────────────────────────────────────────────────────────────\n');


}

main().catch((err) => {
    console.error('Unhandled test runner error:', err);
    process.exit(1);
});
