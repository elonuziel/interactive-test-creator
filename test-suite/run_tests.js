const assert = require('assert');
const {
    normalizeWhitespace,
    stripExamFooterArtifacts,
    normalizeQuestionsJson,
    parseCsvRows,
    extractAnswersForForm,
    mergeAnswers,
    getStorageKey,
    getCustomSelectedIndices
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

console.log('\n──────────────────────────────────────────────────────────────');
console.log(`📊 Final Execution Summary: ${testsPassed} Passed, ${testsFailed} Failed.`);
console.log('──────────────────────────────────────────────────────────────\n');

if (testsFailed > 0) process.exit(1);
