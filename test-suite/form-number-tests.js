const assert = require('node:assert/strict');
const QuizCore = require('../quiz-core.js');

assert.equal(QuizCore.normalizeFormNumber('063'), '63');
assert.equal(QuizCore.normalizeFormNumber('000'), '0');

const detected = QuizCore.detectFormNumber("מבחן מס' 063");
assert.equal(detected.rawValue, '063');
assert.equal(detected.normalizedValue, '63');

const zero = QuizCore.detectFormNumber('טופס 0');
assert.equal(zero.isFormZero, true);

const rows = [
  ['שאלון', 'שאלה 1', 'שאלה 2'],
  ['63', '(2)', '(1)']
];
const answers = QuizCore.extractAnswersForForm(rows, '063');
assert.deepEqual(Array.from(answers.entries()), [[1, 1], [2, 0]]);

console.log('Form-number tests passed.');
