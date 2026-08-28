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
    validateQuestions
} = require('../quiz-core.js');

function runTest(suiteName, name, fn) {
    const startMs = Date.now();
    try {
        fn();
        const durationMs = Date.now() - startMs;
        console.log(`  ✅ [PASS] ${suiteName} -> ${name} (${durationMs}ms)`);
        testsPassed++;
    } catch (err) {
        console.error(`  ❌ [FAIL] ${suiteName} -> ${name}`);
        console.error(`     Error: ${err.message}`);
        testsFailed++;
    }
}

console.log('🧪 Interactive Test Creator — Node.js Component Integration Unit Tests\n');
let testsPassed = 0;
let testsFailed = 0;

runTest('JSON Normalization', 'Strips option letter prefixes and cleans double spaces', () => {
    const input = [{ question: '  שאלה  1.  מהו DNA?  ', options: ['א. חומצת גרעין', 'ב. חלבון', 'ג. שומן'] }];
    const result = normalizeQuestionsJson(input);
    assert.strictEqual(result.length, 1);
    assert.strictEqual(result[0].question, 'שאלה 1. מהו DNA?');
    assert.deepStrictEqual(result[0].options, ['חומצת גרעין', 'חלבון', 'שומן']);
});

runTest('JSON Normalization', 'Removes PDF footer artifacts', () => {
    const input = [{ question: 'מהו תפקוד המיטוכונדריה? עמוד 3 מתוך 12 - סוף המבחן -', options: ['ייצור אנרגיה', 'תפיסת סוכרים'] }];
    const result = normalizeQuestionsJson(input);
    assert.strictEqual(result[0].question, 'מהו תפקוד המיטוכונדריה?');
    assert.strictEqual(stripExamFooterArtifacts('x [cite: 12]'), 'x');
});

runTest('JSON Normalization', 'Filters empty questions and resets invalid correctIndex', () => {
    const input = [
        { question: '', options: ['תשובה 1'] },
        { question: 'שאלה תקינה', options: ['תשובה 1', 'תשובה 2'], correctIndex: 99 }
    ];
    const result = normalizeQuestionsJson(input);
    assert.strictEqual(result.length, 1);
    assert.strictEqual(result[0].correctIndex, 0);
});

runTest('CSV Answer Key Merging', 'Parses quoted CSV and extracts Hebrew/numeric answers', () => {
    const csv = 'Form,Q1,Q2,Q3,Q4\n76,א,ב,ג,ד\n32,4,3,2,1';
    const rows = parseCsvRows(csv);
    assert.deepStrictEqual(Array.from(extractAnswersForForm(rows, '76').entries()), [[1, 0], [2, 1], [3, 2], [4, 3]]);
    assert.deepStrictEqual(Array.from(extractAnswersForForm(rows, '32').entries()), [[1, 3], [2, 2], [3, 1], [4, 0]]);
});

runTest('CSV Answer Key Merging', 'Merges correctIndex and disables random shuffling', () => {
    const questions = [
        { question: 'Q1', options: ['A', 'B', 'C'], correctIndex: 0, shuffleOptions: true },
        { question: 'Q2', options: ['A', 'B', 'C'], correctIndex: 0, shuffleOptions: true }
    ];
    const merged = mergeAnswers(questions, new Map([[1, 2], [2, 1]]));
    assert.strictEqual(merged[0].correctIndex, 2);
    assert.strictEqual(merged[1].correctIndex, 1);
    assert.strictEqual(merged[0].shuffleOptions, false);
});

runTest('Storage Hashing', 'Generates deterministic keys based on the full question sample', () => {
    const first = [{ question: 'Botany question test', options: ['1', '2'] }];
    const second = [{ question: 'Physics question test', options: ['1', '2'] }];
    assert.strictEqual(getStorageKey(first), getStorageKey(first));
    assert.notStrictEqual(getStorageKey(first), getStorageKey(second));
    assert.ok(getStorageKey(first).startsWith('quiz_answers_'));
});

runTest('Question Validation', 'Rejects malformed questions with actionable errors', () => {
    const errors = validateQuestions([
        { question: '', options: ['only one'], correctIndex: 3 },
        { question: 'Valid', options: ['A', 'B'], correctIndex: 0, sourcePage: 0 }
    ]);
    assert.strictEqual(errors.length, 4);
    assert.ok(errors.some((error) => error.includes('שאלה 1: חסר טקסט')));
    assert.ok(errors.some((error) => error.includes('שאלה 2: sourcePage אינו תקין')));
});

runTest('Mix & Match Custom Practice', 'Combines categories and manual selections without duplicates', () => {
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

runTest('Standalone Export', 'Escapes script terminators and inlines scripts', () => {
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

runTest('Progress System DOM & Styles', 'Verifies progress bar DOM markup in index.html and style.css', () => {
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

runTest('Progress Controller Lifecycle', 'Validates AbortController and progress state calculation', () => {
    const abortCtrl = new AbortController();
    assert.strictEqual(abortCtrl.signal.aborted, false);
    abortCtrl.abort();
    assert.strictEqual(abortCtrl.signal.aborted, true);

    const clamp = (val) => Math.max(0, Math.min(100, Math.round(val || 0)));
    assert.strictEqual(clamp(-10), 0);
    assert.strictEqual(clamp(50.4), 50);
    assert.strictEqual(clamp(150), 100);
});

runTest('Auto-Advance Countdown', 'Verifies countdown markup generation and styles in player', () => {
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

runTest('Progress Controller Module', 'Verifies ProgressController starts tasks, dispatches updates, and handles abort signals', () => {
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

runTest('Question Parser - Markdown', 'Parses Hebrew exam questions formatted in Markdown', () => {
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

runTest('Question Parser - Hebrew Word Order & Heuristics', 'Detects reversed Hebrew and cleans header prefixes', () => {
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

runTest('Question Parser - Text Extraction & Inline Options', 'Parses text with inline answer options', () => {
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

runTest('PDF Service - Heuristics & Geometry', 'Evaluates direction detection and Hebrew breakage scores', () => {
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

runTest('Gemini Service - Models & Error Classification', 'Classifies Gemini errors and sorts candidate models', () => {
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

runTest('Module Scripts Loading in index.html', 'Verifies all modular scripts are referenced in correct dependency order', () => {
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

runTest('PWA Manifest & Service Worker Integrity', 'Verifies web manifest and service worker precache assets exist', () => {
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

console.log('\n──────────────────────────────────────────────────────────────');
console.log(`📊 Final Execution Summary: ${testsPassed} Passed, ${testsFailed} Failed.`);
console.log('──────────────────────────────────────────────────────────────\n');

if (testsFailed > 0) process.exit(1);

