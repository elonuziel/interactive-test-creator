const assert = require('assert');

// ── Test Helpers & Component Logics ──────────────────────────────────────────

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

// ── Test Runner ───────────────────────────────────────────────────────────────

console.log('🧪 Running Interactive Test Creator Component Unit Tests...\n');
let testsPassed = 0;
let testsFailed = 0;

function runTest(name, fn) {
    try {
        fn();
        console.log(`  ✅ PASS: ${name}`);
        testsPassed++;
    } catch (err) {
        console.error(`  ❌ FAIL: ${name}`);
        console.error(`     Error: ${err.message}`);
        testsFailed++;
    }
}

// 1. normalizeQuestionsJson Tests
runTest('normalizeQuestionsJson cleans whitespace & strips option prefixes', () => {
    const raw = [
        {
            question: '  שאלה  1.  מהו DNA?  ',
            options: ['א. חומצת גרעין', 'ב. חלבון', 'ג. שומן'],
            correctIndex: 1
        }
    ];
    const result = normalizeQuestionsJson(raw);
    assert.strictEqual(result.length, 1);
    assert.strictEqual(result[0].question, 'שאלה 1. מהו DNA?');
    assert.deepStrictEqual(result[0].options, ['חומצת גרעין', 'חלבון', 'שומן']);
    assert.strictEqual(result[0].correctIndex, 1);
});

// 2. parseCsvRows & extractAnswersForForm Tests
runTest('extractAnswersForForm extracts correct 0-based option indices for specified form', () => {
    const csv = 'Form,Q1,Q2,Q3,Q4\n76,א,ב,ג,ד\n32,4,3,2,1';
    const rows = parseCsvRows(csv);
    assert.strictEqual(rows.length, 3);

    const form76Map = extractAnswersForForm(rows, '76');
    assert.deepStrictEqual(form76Map, { 1: 0, 2: 1, 3: 2, 4: 3 });

    const form32Map = extractAnswersForForm(rows, '32');
    assert.deepStrictEqual(form32Map, { 1: 3, 2: 2, 3: 1, 4: 0 });
});

// 3. mergeAnswers Tests
runTest('mergeAnswers applies CSV answer map to questions array', () => {
    const questions = [
        { question: 'Q1', options: ['A', 'B', 'C'], correctIndex: 0 },
        { question: 'Q2', options: ['A', 'B', 'C'], correctIndex: 0 }
    ];
    const answerMap = { 1: 2, 2: 1 };
    const merged = mergeAnswers(questions, answerMap);
    assert.strictEqual(merged[0].correctIndex, 2);
    assert.strictEqual(merged[1].correctIndex, 1);
});

// 4. getStorageKey Hash Tests
runTest('getStorageKey generates deterministic keys based on question content', () => {
    const questionsA = [{ question: 'Sample Q', options: ['1', '2'] }];
    const questionsB = [{ question: 'Different Q', options: ['1', '2'] }];

    const keyA1 = getStorageKey(questionsA);
    const keyA2 = getStorageKey(questionsA);
    const keyB = getStorageKey(questionsB);

    assert.strictEqual(keyA1, keyA2);
    assert.notStrictEqual(keyA1, keyB);
    assert.ok(keyA1.startsWith('quiz_answers_'));
});

// ── Summary ──────────────────────────────────────────────────────────────────

console.log(`\n──────────────────────────────────────────────────`);
console.log(`📊 Test Summary: ${testsPassed} Passed, ${testsFailed} Failed.`);
console.log(`──────────────────────────────────────────────────\n`);

if (testsFailed > 0) {
    process.exit(1);
} else {
    process.exit(0);
}
