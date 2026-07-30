const assert = require('assert');

// ── Test Helpers & Component Logic Under Test ─────────────────────────────────

function normalizeWhitespace(value) {
    if (!value) return '';
    return String(value)
        .replace(/[\u200B-\u200D\uFEFF]/g, '')
        .replace(/[ \t]+/g, ' ')
        .trim();
}

function stripExamFooterArtifacts(value) {
    if (!value) return '';
    return String(value)
        .replace(/עמוד\s+\d+\s+מתוך\s+\d+/gi, '')
        .replace(/-+\s*סוף\s+המבחן\s*-+/gi, '')
        .trim();
}

function normalizeQuestionsJson(data) {
    if (!Array.isArray(data)) return [];
    return data
        .filter((item) => item && typeof item === 'object')
        .map((item, index) => {
            const rawQuestion = normalizeWhitespace(stripExamFooterArtifacts(item.question || item.title || ''));
            const rawOptions = Array.isArray(item.options) ? item.options : [];

            const options = rawOptions
                .map((opt) => normalizeWhitespace(String(opt || '')))
                .filter(Boolean)
                .map((text) => text.replace(/^[אבגדהוזחטי1-9][\.\)]\s*/, '').trim());

            let correctIndex = Number(item.correctIndex);
            if (isNaN(correctIndex) || correctIndex < 0 || correctIndex >= options.length) {
                correctIndex = 0;
            }

            const shuffleOptions = !!(item.shuffleOptions || item.shuffle_options);

            return {
                question: rawQuestion,
                options: options,
                correctIndex: correctIndex,
                image: item.image || item.pageImage || null,
                sourcePage: item.sourcePage || item.page || (index + 1),
                shuffleOptions: shuffleOptions
            };
        })
        .filter((q) => q.question && q.options.length > 0);
}

function parseCsvRows(csvText) {
    const lines = csvText.split(/\r?\n/).filter((line) => line.trim().length > 0);
    const rows = [];

    for (const line of lines) {
        const row = [];
        let current = '';
        let inQuotes = false;

        for (let i = 0; i < line.length; i++) {
            const ch = line[i];
            if (ch === '"') {
                if (inQuotes && line[i + 1] === '"') {
                    current += '"';
                    i++;
                } else {
                    inQuotes = !inQuotes;
                }
            } else if (ch === ',' && !inQuotes) {
                row.push(current.trim());
                current = '';
            } else {
                current += ch;
            }
        }
        row.push(current.trim());
        if (row.some((cell) => cell.trim() !== '')) rows.push(row);
    }

    return rows;
}

function extractAnswersForForm(rows, formNumber) {
    if (!rows || !rows.length) return {};
    const cleanFormTarget = String(formNumber).trim().toLowerCase();
    const answerMap = {};

    let formRow = null;
    let headerRow = null;

    for (let i = 0; i < rows.length; i++) {
        const firstCell = String(rows[i][0] || '').trim().toLowerCase();
        if (firstCell === cleanFormTarget || firstCell.includes(cleanFormTarget)) {
            formRow = rows[i];
            if (i > 0) headerRow = rows[i - 1];
            break;
        }
    }

    if (!formRow) return {};

    for (let colIdx = 1; colIdx < formRow.length; colIdx++) {
        let qNum = colIdx;
        if (headerRow && headerRow[colIdx]) {
            const match = String(headerRow[colIdx]).match(/\d+/);
            if (match) qNum = parseInt(match[0], 10);
        }

        const rawVal = String(formRow[colIdx] || '').trim().toUpperCase();
        let correctIdx = -1;

        if (/^[1-9]\d*$/.test(rawVal)) {
            correctIdx = parseInt(rawVal, 10) - 1;
        } else if (rawVal === 'א' || rawVal === 'A') correctIdx = 0;
        else if (rawVal === 'ב' || rawVal === 'B') correctIdx = 1;
        else if (rawVal === 'ג' || rawVal === 'C') correctIdx = 2;
        else if (rawVal === 'ד' || rawVal === 'D') correctIdx = 3;
        else if (rawVal === 'ה' || rawVal === 'E') correctIdx = 4;
        else if (rawVal === 'ו' || rawVal === 'F') correctIdx = 5;

        if (correctIdx >= 0) {
            answerMap[qNum] = correctIdx;
        }
    }

    return answerMap;
}

function mergeAnswers(questions, answerMap) {
    if (!answerMap || !Object.keys(answerMap).length) return questions;
    return questions.map((q, index) => {
        const qNum = index + 1;
        if (answerMap.hasOwnProperty(qNum)) {
            const correctIndex = answerMap[qNum];
            if (correctIndex < q.options.length) {
                return { ...q, correctIndex, shuffleOptions: false };
            }
        }
        return q;
    });
}

function getStorageKey(questions) {
    if (!questions || !questions.length) return 'quiz_answers_v1';
    let hash = 0;
    const sampleText = (questions[0].question || '') + questions.length;
    for (let i = 0; i < sampleText.length; i++) {
        hash = ((hash << 5) - hash) + sampleText.charCodeAt(i);
        hash |= 0;
    }
    return `quiz_answers_${Math.abs(hash)}`;
}

// ── Test Execution Pipeline ───────────────────────────────────────────────────

console.log('🧪 Interactive Test Creator — Node.js Component Integration Unit Tests\n');
let testsPassed = 0;
let testsFailed = 0;

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

// 1. JSON Schema Normalization & Cleanup
runTest('JSON Normalization', 'Strips option letter prefixes (א., ב., ג.) and cleans double spaces', () => {
    const input = [{ question: '  שאלה  1.  מהו DNA?  ', options: ['א. חומצת גרעין', 'ב. חלבון', 'ג. שומן'] }];
    const res = normalizeQuestionsJson(input);
    assert.strictEqual(res.length, 1);
    assert.strictEqual(res[0].question, 'שאלה 1. מהו DNA?');
    assert.deepStrictEqual(res[0].options, ['חומצת גרעין', 'חלבון', 'שומן']);
});

runTest('JSON Normalization', 'Removes PDF exam footer artifacts (עמוד X מתוך Y)', () => {
    const input = [{ question: 'מהו תפקוד המיטוכונדריה? עמוד 3 מתוך 12 - סוף המבחן -', options: ['ייצור אנרגיה', 'תפיסת סוכרים'] }];
    const res = normalizeQuestionsJson(input);
    assert.strictEqual(res[0].question, 'מהו תפקוד המיטוכונדריה?');
});

runTest('JSON Normalization', 'Filters out empty questions & resets out-of-bounds correctIndex', () => {
    const input = [
        { question: '', options: ['תשובה 1'] },
        { question: 'שאלה תקינה', options: ['תשובה 1', 'תשובה 2'], correctIndex: 99 }
    ];
    const res = normalizeQuestionsJson(input);
    assert.strictEqual(res.length, 1);
    assert.strictEqual(res[0].correctIndex, 0);
});

// 2. CSV & XLS Answer Key Merging
runTest('CSV Answer Key Merging', 'Parses quoted CSV rows and extracts Form 76 and Form 32 answer maps', () => {
    const csv = 'Form,Q1,Q2,Q3,Q4\n76,א,ב,ג,ד\n32,4,3,2,1';
    const rows = parseCsvRows(csv);
    const map76 = extractAnswersForForm(rows, '76');
    const map32 = extractAnswersForForm(rows, '32');
    assert.deepStrictEqual(map76, { 1: 0, 2: 1, 3: 2, 4: 3 });
    assert.deepStrictEqual(map32, { 1: 3, 2: 2, 3: 1, 4: 0 });
});

runTest('CSV Answer Key Merging', 'Merges correctIndex into questions array and disables random shuffling', () => {
    const questions = [
        { question: 'Q1', options: ['A', 'B', 'C'], correctIndex: 0, shuffleOptions: true },
        { question: 'Q2', options: ['A', 'B', 'C'], correctIndex: 0, shuffleOptions: true }
    ];
    const answerMap = { 1: 2, 2: 1 };
    const merged = mergeAnswers(questions, answerMap);
    assert.strictEqual(merged[0].correctIndex, 2);
    assert.strictEqual(merged[1].correctIndex, 1);
    assert.strictEqual(merged[0].shuffleOptions, false);
});

// 3. LocalStorage Progress & Storage Hashing
runTest('Storage Hashing', 'Generates deterministic storage keys based on question contents', () => {
    const q1 = [{ question: 'Botany question test', options: ['1', '2'] }];
    const q2 = [{ question: 'Physics question test', options: ['1', '2'] }];
    const key1 = getStorageKey(q1);
    const key1_repeat = getStorageKey(q1);
    const key2 = getStorageKey(q2);

    assert.strictEqual(key1, key1_repeat);
    assert.notStrictEqual(key1, key2);
    assert.ok(key1.startsWith('quiz_answers_'));
});

// 4. Question Flagging State
runTest('Question Flagging State', 'Initializes and updates userFlags boolean array correctly', () => {
    const userFlags = new Array(5).fill(false);
    userFlags[1] = true;
    userFlags[3] = true;

    const flaggedIndices = userFlags.reduce((acc, isFlagged, idx) => {
        if (isFlagged) acc.push(idx + 1);
        return acc;
    }, []);

    assert.deepStrictEqual(flaggedIndices, [2, 4]);
    assert.strictEqual(userFlags.filter(Boolean).length, 2);
});

// 5. Mix & Match Custom Practice Selection
runTest('Mix & Match Custom Practice', 'Combines category presets and manual cherrypicking with zero duplicates', () => {
    const userAnswers = [
        { selectedOptionId: 1, isCorrect: false }, // Q1 Wrong
        { selectedOptionId: 0, isCorrect: true },  // Q2 Correct
        null,                                     // Q3 Unanswered
        { selectedOptionId: 0, isCorrect: true }   // Q4 Correct
    ];
    const userFlags = [true, false, false, true]; // Q1 & Q4 Starred

    const selected = new Set();
    userAnswers.forEach((a, i) => { if (a && !a.isCorrect) selected.add(i); });
    userFlags.forEach((f, i) => { if (f) selected.add(i); });
    selected.add(2); // Manual cherrypick Q3

    const sortedIndices = Array.from(selected).sort((a, b) => a - b);
    assert.deepStrictEqual(sortedIndices, [0, 2, 3]);
});

// ── Summary Metrics ───────────────────────────────────────────────────────────

console.log(`\n──────────────────────────────────────────────────────────────`);
console.log(`📊 Final Execution Summary: ${testsPassed} Passed, ${testsFailed} Failed.`);
console.log(`──────────────────────────────────────────────────────────────\n`);

if (testsFailed > 0) {
    process.exit(1);
} else {
    process.exit(0);
}
