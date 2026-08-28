// Shared pure data helpers for the quiz player, generator, and tests.
(function (root, factory) {
    if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.QuizCore = factory();
    }
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
    'use strict';

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
            .replace(/\[cite:\s*\d+\]/gi, '')
            .replace(/עמוד\s+\d+\s+מתוך\s+\d+/gi, '')
            .replace(/-+\s*סוף\s+המבחן\s*-+/gi, '')
            .trim();
    }

    function normalizeQuestionsJson(data) {
        if (!Array.isArray(data)) return [];
        return data
            .filter((item) => item && typeof item === 'object')
            .map((item, index) => {
                const question = normalizeWhitespace(stripExamFooterArtifacts(item.question || item.title || ''));
                const options = (Array.isArray(item.options) ? item.options : [])
                    .map((option) => normalizeWhitespace(String(option || '')))
                    .filter(Boolean)
                    .map((text) => text.replace(/^[אבגדהוזחטי1-9][\.\)]\s*/, '').trim());

                let correctIndex = Number(item.correctIndex);
                if (!Number.isInteger(correctIndex) || correctIndex < 0 || correctIndex >= options.length) {
                    correctIndex = 0;
                }

                return {
                    question,
                    options,
                    correctIndex,
                    image: item.image || item.pageImage || null,
                    sourcePage: item.sourcePage || item.page || (index + 1),
                    shuffleOptions: !!(item.shuffleOptions || item.shuffle_options)
                };
            })
            .filter((item) => item.question && item.options.length > 0);
    }

    function parseCsvRows(csvText) {
        const rows = [];
        let row = [];
        let value = '';
        let inQuotes = false;
        const text = String(csvText || '');

        for (let i = 0; i < text.length; i++) {
            const char = text[i];
            const next = text[i + 1];

            if (char === '"') {
                if (inQuotes && next === '"') {
                    value += '"';
                    i++;
                } else {
                    inQuotes = !inQuotes;
                }
            } else if (char === ',' && !inQuotes) {
                row.push(value.trim());
                value = '';
            } else if ((char === '\n' || char === '\r') && !inQuotes) {
                if (char === '\r' && next === '\n') i++;
                row.push(value.trim());
                value = '';
                if (row.some((cell) => cell !== '')) rows.push(row);
                row = [];
            } else {
                value += char;
            }
        }

        if (value.length || row.length) {
            row.push(value.trim());
            if (row.some((cell) => cell !== '')) rows.push(row);
        }

        return rows;
    }

    function normalizeFormNumber(value) {
        const match = String(value == null ? '' : value).trim().match(/\d+/);
        return match ? String(Number(match[0])) : null;
    }

    function detectFormNumber(text, filename = '') {
        const source = `${String(text || '')}\n${String(filename || '')}`;
        const re = /(?:מבחן\s*(?:מספר|מס['׳״\"]?|no\.?|number)?|מספר\s+מבחן|שאלון|טופס|form|test|exam\s*(?:no\.?|number)?)[^\d]{0,24}(\d{1,})/ig;
        const candidates = [];
        let match;
        while ((match = re.exec(source))) {
            const normalized = normalizeFormNumber(match[1]);
            if (normalized !== null) candidates.push({ rawValue: match[1], normalizedValue: normalized, isFormZero: normalized === '0', confidence: match.index < String(text || '').length ? 1 : 0.65 });
        }
        candidates.sort((a, b) => b.confidence - a.confidence);
        return candidates[0] || null;
    }

    function parseAnswer(value) {
        const raw = String(value || '').trim().toUpperCase();
        const numeric = raw.match(/^(?:\((\d+)\)|\[?(\d+)\]?)/);
        if (numeric) return Number(numeric[1] || numeric[2]) - 1;

        const letters = { 'א': 0, A: 0, 'ב': 1, B: 1, 'ג': 2, C: 2, 'ד': 3, D: 3, 'ה': 4, E: 4, 'ו': 5, F: 5 };
        return Object.prototype.hasOwnProperty.call(letters, raw) ? letters[raw] : null;
    }

    function extractAnswersForForm(rows, formNumber) {
        if (!Array.isArray(rows) || !rows.length) return new Map();
        const target = normalizeFormNumber(formNumber);
        let headers = null;
        let selectedRow = null;

        for (const row of rows) {
            if (!Array.isArray(row) || !row.length) continue;
            const first = String(row[0] || '').trim().toLowerCase();
            if (first.includes('שאלון') || first.includes('form')) {
                headers = row;
                continue;
            }
            const normalizedFirst = first.replace(/\.0$/, '');
            if (target && (normalizedFirst === target || normalizedFirst.includes(target))) {
                selectedRow = row;
                break;
            }
        }

        if (!selectedRow && target) {
            selectedRow = rows.find((row) => row.some((cell) => String(cell || '').trim().toLowerCase().replace(/\.0$/, '') === target));
        }
        if (!selectedRow && !target && rows.length > 1) selectedRow = rows[1];
        if (!selectedRow) return new Map();

        const answers = new Map();
        if (headers) {
            headers.forEach((header, columnIndex) => {
                const match = String(header || '').match(/\d+/);
                if (!match) return;
                const answer = parseAnswer(selectedRow[columnIndex]);
                if (answer !== null && answer >= 0) answers.set(Number(match[0]), answer);
            });
        } else {
            const startsAt = String(selectedRow[0] || '').trim().toLowerCase().replace(/\.0$/, '') === target ? 1 : 0;
            for (let columnIndex = startsAt, questionNumber = 1; columnIndex < selectedRow.length; columnIndex++) {
                const answer = parseAnswer(selectedRow[columnIndex]);
                if (answer !== null && answer >= 0) answers.set(questionNumber++, answer);
            }
        }
        return answers;
    }

    function mergeAnswers(questions, answerMap) {
        const answers = answerMap instanceof Map ? answerMap : new Map(Object.entries(answerMap || {}).map(([key, value]) => [Number(key), value]));
        return (Array.isArray(questions) ? questions : []).map((question, index) => {
            const answer = answers.get(index + 1);
            if (typeof answer === 'number' && answer >= 0 && answer < question.options.length) {
                return { ...question, correctIndex: answer, shuffleOptions: false };
            }
            return { ...question, shuffleOptions: false };
        });
    }

    function getStorageKey(questions) {
        if (!questions || !questions.length) return 'quiz_answers_v1';
        const lastIndex = questions.length - 1;
        const middleIndex = Math.floor(questions.length / 2);
        const sample = (questions[0]?.question || '') + (questions[middleIndex]?.question || '') + (questions[lastIndex]?.question || '') + questions.length;
        let hash = 0;
        for (let i = 0; i < sample.length; i++) {
            hash = ((hash << 5) - hash) + sample.charCodeAt(i);
            hash |= 0;
        }
        return `quiz_answers_${Math.abs(hash)}`;
    }

    function validateQuestions(questions) {
        const errors = [];
        if (!Array.isArray(questions) || questions.length === 0) {
            return ['לא נמצאו שאלות.'];
        }
        questions.forEach((question, index) => {
            const number = index + 1;
            if (!question || typeof question !== 'object') {
                errors.push(`שאלה ${number}: המבנה אינו אובייקט.`);
                return;
            }
            if (!String(question.question || '').trim()) errors.push(`שאלה ${number}: חסר טקסט.`);
            if (!Array.isArray(question.options) || question.options.length < 2) {
                errors.push(`שאלה ${number}: נדרשות לפחות 2 תשובות.`);
            }
            if (Array.isArray(question.options) && (!Number.isInteger(question.correctIndex) || question.correctIndex < 0 || question.correctIndex >= question.options.length)) {
                errors.push(`שאלה ${number}: correctIndex אינו תקין.`);
            }
            if (question.sourcePage !== undefined && (!Number.isInteger(Number(question.sourcePage)) || Number(question.sourcePage) < 1)) {
                errors.push(`שאלה ${number}: sourcePage אינו תקין.`);
            }
        });
        return errors;
    }

    function getCustomSelectedIndices(questions, userAnswers, userFlags, categories = {}, manualIndices = []) {
        const selected = new Set();
        (questions || []).forEach((question, index) => {
            const answer = userAnswers?.[index];
            if (categories.wrong && answer && !answer.isCorrect) selected.add(index);
            if (categories.unanswered && !answer) selected.add(index);
            if (categories.flagged && userFlags?.[index]) selected.add(index);
        });
        (manualIndices || []).forEach((index) => {
            if (index >= 0 && index < (questions || []).length) selected.add(index);
        });
        return Array.from(selected).sort((a, b) => a - b);
    }        return {
            normalizeWhitespace,

        stripExamFooterArtifacts,
        normalizeQuestionsJson,
        parseCsvRows,
        extractAnswersForForm,
        mergeAnswers,
        getStorageKey,
        getCustomSelectedIndices,
        validateQuestions,
        normalizeFormNumber,
        detectFormNumber
    };
}));
