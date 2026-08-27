export function createQuizState(questionCount) {
    return {
        currentQuestionIndex: 0,
        userAnswers: Array(questionCount).fill(null),
        userFlags: Array(questionCount).fill(false),
        isImmediateFeedback: false,
        reviewFilter: 'all',
        isReviewMode: false
    };
}

export function storageKey(questions) {
    const sample = questions.map((question) => [question.question, question.options, question.correctIndex]);
    let hash = 0;
    for (const char of JSON.stringify(sample)) hash = ((hash << 5) - hash) + char.charCodeAt(0) | 0;
    return `quiz_answers_${Math.abs(hash)}`;
}

export function saveProgress(questions, state, storage = window.localStorage) {
    storage.setItem(storageKey(questions), JSON.stringify({
        answers: state.userAnswers,
        flags: state.userFlags,
        index: state.currentQuestionIndex
    }));
}

export function loadProgress(questions, storage = window.localStorage) {
    try {
        const raw = storage.getItem(storageKey(questions));
        return raw ? JSON.parse(raw) : null;
    } catch {
        return null;
    }
}
