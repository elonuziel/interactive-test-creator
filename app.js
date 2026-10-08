document.addEventListener('DOMContentLoaded', () => {

    // ── State ────────────────────────────────────────────────────────────────
    let questions = [];
    let allMasterQuestions = [];
    let currentQuestionIndex = 0;
    let userAnswers = []; // { selectedOptionId: number, isCorrect: boolean } | null
    let userFlags = []; // boolean per question
    let isImmediateFeedback = false;
    let autoAdvanceTimer = null;
    let autoAdvanceInterval = null;
    let reviewFilter = 'all'; // 'all' | 'wrong' | 'unanswered' | 'flagged'
    let isReviewMode = false; // true when reviewing from results screen
    let theme = localStorage.getItem('theme') || 'light';

    // ── Timer & Timing Analytics State ──────────────────────────────────────
    let isTimerEnabled = localStorage.getItem('quiz_timer_enabled') === 'true';
    let timerMode = localStorage.getItem('quiz_timer_mode') || 'stopwatch'; // 'stopwatch' | 'countdown'
    let timerCountdownMinutes = parseInt(localStorage.getItem('quiz_timer_minutes') || '30', 10);
    let isQuestionTimerEnabled = localStorage.getItem('quiz_question_timer_enabled') !== 'false'; // default true

    let totalElapsedSeconds = 0;
    let remainingCountdownSeconds = timerCountdownMinutes * 60;
    let questionTimes = []; // number of active seconds spent per question
    let currentQuestionStartTimestamp = null;
    let examTimerInterval = null;

    const STORAGE_KEY = 'quiz_answers_v1';

    function clearAutoAdvance() {
        if (autoAdvanceTimer) {
            clearTimeout(autoAdvanceTimer);
            autoAdvanceTimer = null;
        }
        if (autoAdvanceInterval) {
            clearInterval(autoAdvanceInterval);
            autoAdvanceInterval = null;
        }
    }

    // ── DOM Elements ─────────────────────────────────────────────────────────
    const setupScreen   = document.getElementById('setup-screen');
    const quizScreen    = document.getElementById('quiz-screen');
    const resultsScreen = document.getElementById('results-screen');

    const startBtn          = document.getElementById('start-btn');
    const resumeBtn         = document.getElementById('resume-btn');
    const resumeNotice      = document.getElementById('resume-notice');
    const prevBtn           = document.getElementById('prev-btn');
    const nextBtn           = document.getElementById('next-btn');
    const submitBtn         = document.getElementById('submit-btn');
    const restartBtn        = document.getElementById('restart-btn');
    const retryIncorrectBtn = document.getElementById('retry-incorrect-btn');
    const retryFlaggedBtn   = document.getElementById('retry-flagged-btn');
    const reviewBackBtn     = document.getElementById('review-back-btn');
    const flagBtn           = document.getElementById('flag-btn');

    const flaggedCountBadgeAction = document.getElementById('flagged-count-badge-action');
    const flaggedCountBadgeFilter = document.getElementById('flagged-count-badge-filter');

    const chkMixWrong            = document.getElementById('chk-mix-wrong');
    const chkMixUnanswered       = document.getElementById('chk-mix-unanswered');
    const chkMixFlagged          = document.getElementById('chk-mix-flagged');
    const cntMixWrong            = document.getElementById('cnt-mix-wrong');
    const cntMixUnanswered       = document.getElementById('cnt-mix-unanswered');
    const cntMixFlagged          = document.getElementById('cnt-mix-flagged');
    const startCustomPracticeBtn = document.getElementById('start-custom-practice-btn');
    const customSelectedCount    = document.getElementById('custom-selected-count');

    let manualSelectedIndices = new Set();

    const questionCounter   = document.getElementById('question-counter');
    const questionText      = document.getElementById('question-text');
    const questionImage     = document.getElementById('question-image');
    const optionsContainer  = document.getElementById('options-container');
    const progressBar       = document.getElementById('progress-bar');
    const feedbackMessage   = document.getElementById('feedback-message');
    const jumpBar           = document.getElementById('question-jump-bar');
    const zoomOverlay       = document.getElementById('zoom-overlay');
    const zoomImg           = document.getElementById('zoom-img');

    // Cropper Elements
    const openCropperBtn    = document.getElementById('open-cropper-btn');
    const cropperModal      = document.getElementById('cropper-modal');
    const closeCropperBtn   = document.getElementById('close-cropper-btn');
    const confirmCropBtn    = document.getElementById('confirm-crop-btn');
    const cropperImage      = document.getElementById('cropper-image');
    let cropperInstance     = null;
    let croppedImages       = {}; // Store crop data URLs per full image path
    const themeToggle    = document.getElementById('theme-toggle');
    const feedbackToggle = document.getElementById('immediate-feedback-toggle');
    const welcomeFeedbackToggle = document.getElementById('welcome-immediate-feedback-toggle');
    const themeIcon      = document.getElementById('theme-icon');
    const filterBtns     = document.querySelectorAll('.filter-btn');
    const builderNavLink = document.getElementById('builder-nav-link');
    const onlineBuilderUrl = 'https://elonuziel.github.io/interactive-test-creator/';

    // Timer Elements
    const quizTimerToggle           = document.getElementById('quiz-timer-toggle');
    const timerOptionsContainer     = document.getElementById('timer-options-container');
    const timerModeStopwatch        = document.getElementById('timer-mode-stopwatch');
    const timerModeCountdown        = document.getElementById('timer-mode-countdown');
    const timerCountdownMinutesInput = document.getElementById('timer-countdown-minutes');
    const questionTimerToggle       = document.getElementById('question-timer-toggle');

    const examTimerBadge            = document.getElementById('exam-timer-badge');
    const timerDisplay              = document.getElementById('timer-display');
    const questionTimeBadge         = document.getElementById('question-time-badge');
    const questionTimeDisplay       = document.getElementById('question-time-display');

    const timingAnalyticsCard       = document.getElementById('timing-analytics-card');
    const totalTimeStat             = document.getElementById('total-time-stat');
    const meanTimeStat              = document.getElementById('mean-time-stat');
    const timedQuestionsStat        = document.getElementById('timed-questions-stat');

    if (builderNavLink) {
        builderNavLink.href = onlineBuilderUrl;
        builderNavLink.textContent = 'יוצר מבחן אונליין ←';
        builderNavLink.title = 'פתח יוצר מבחן אונליין';
    }

    // A live quiz is opened from a blob URL, so a relative `index.html` link
    // cannot resolve back to the builder. Return through the opener instead.
    // For downloaded standalone quizzes (or direct quiz_player.html visits),
    // there is no opener and the normal link remains available.
    builderNavLink?.addEventListener('click', (event) => {
        if (!window.opener || window.opener.closed) return;

        event.preventDefault();
        const builderWindow = window.opener;
        try {
            builderWindow.focus();
        } catch {
            // Focusing another tab can be denied by the browser; closing still works.
        }

        window.close();

        // Some browsers refuse to close a tab they do not consider script-opened.
        // In that case, use the opener's current URL rather than resolving the
        // relative link against the blob URL (which produces about:blank#blocked).
        setTimeout(() => {
            if (window.closed) return;
            try {
                window.location.replace(builderWindow.location.href);
            } catch {
                // Keep the page usable if the browser blocks opener inspection.
            }
        }, 100);
    });

    // ── Theme ────────────────────────────────────────────────────────────────
    function setTheme(newTheme) {
        theme = newTheme;
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
        if (theme === 'dark') {
            themeIcon.innerHTML = '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"></path>';
        } else {
            themeIcon.innerHTML = '<circle cx="12" cy="12" r="4"></circle><path d="M12 2v2"></path><path d="M12 20v2"></path><path d="m4.93 4.93 1.41 1.41"></path><path d="m17.66 17.66 1.41 1.41"></path><path d="M2 12h2"></path><path d="M20 12h2"></path><path d="m6.34 17.66-1.41 1.41"></path><path d="m19.07 4.93-1.41 1.41"></path>';
        }
    }
    setTheme(theme);

    themeToggle.addEventListener('click', () => setTheme(theme === 'light' ? 'dark' : 'light'));

    // ── Immediate Feedback / Auto-Review ──────────────────────────────────────
    const savedFeedback = localStorage.getItem('quiz_immediate_feedback');
    if (savedFeedback !== null) {
        isImmediateFeedback = savedFeedback === 'true';
    }

    function setImmediateFeedback(enabled) {
        isImmediateFeedback = Boolean(enabled);
        if (feedbackToggle) feedbackToggle.checked = isImmediateFeedback;
        if (welcomeFeedbackToggle) welcomeFeedbackToggle.checked = isImmediateFeedback;
        localStorage.setItem('quiz_immediate_feedback', isImmediateFeedback);
    }
    setImmediateFeedback(isImmediateFeedback);

    feedbackToggle?.addEventListener('change', e => setImmediateFeedback(e.target.checked));
    welcomeFeedbackToggle?.addEventListener('change', e => setImmediateFeedback(e.target.checked));

    // ── Timer Configuration & Handlers ───────────────────────────────────────
    function initTimerControls() {
        if (quizTimerToggle) {
            quizTimerToggle.checked = isTimerEnabled;
            if (timerOptionsContainer) {
                timerOptionsContainer.classList.toggle('hidden', !isTimerEnabled);
            }
            quizTimerToggle.addEventListener('change', (e) => {
                isTimerEnabled = e.target.checked;
                localStorage.setItem('quiz_timer_enabled', isTimerEnabled);
                if (timerOptionsContainer) {
                    timerOptionsContainer.classList.toggle('hidden', !isTimerEnabled);
                }
            });
        }

        if (timerModeStopwatch && timerModeCountdown) {
            if (timerMode === 'countdown') {
                timerModeCountdown.checked = true;
            } else {
                timerModeStopwatch.checked = true;
            }
            timerModeStopwatch.addEventListener('change', () => {
                if (timerModeStopwatch.checked) {
                    timerMode = 'stopwatch';
                    localStorage.setItem('quiz_timer_mode', 'stopwatch');
                }
            });
            timerModeCountdown.addEventListener('change', () => {
                if (timerModeCountdown.checked) {
                    timerMode = 'countdown';
                    localStorage.setItem('quiz_timer_mode', 'countdown');
                }
            });
        }

        if (timerCountdownMinutesInput) {
            timerCountdownMinutesInput.value = timerCountdownMinutes;
            timerCountdownMinutesInput.addEventListener('input', () => {
                const val = parseInt(timerCountdownMinutesInput.value, 10);
                if (val && val >= 1) {
                    timerCountdownMinutes = val;
                    localStorage.setItem('quiz_timer_minutes', val);
                }
            });
        }

        if (questionTimerToggle) {
            questionTimerToggle.checked = isQuestionTimerEnabled;
            questionTimerToggle.addEventListener('change', (e) => {
                isQuestionTimerEnabled = e.target.checked;
                localStorage.setItem('quiz_question_timer_enabled', isQuestionTimerEnabled);
            });
        }
    }
    initTimerControls();

    function startExamTimer(resume = false) {
        stopExamTimer();

        if (!resume) {
            totalElapsedSeconds = 0;
            remainingCountdownSeconds = timerCountdownMinutes * 60;
        }

        if (examTimerBadge) {
            examTimerBadge.classList.toggle('hidden', !isTimerEnabled);
            examTimerBadge.classList.remove('warning');
        }
        if (questionTimeBadge) {
            questionTimeBadge.classList.toggle('hidden', !isQuestionTimerEnabled);
        }

        currentQuestionStartTimestamp = Date.now();
        updateTimerDisplays();

        examTimerInterval = setInterval(() => {
            totalElapsedSeconds++;
            if (timerMode === 'countdown') {
                remainingCountdownSeconds--;
                if (remainingCountdownSeconds <= 0) {
                    remainingCountdownSeconds = 0;
                    stopExamTimer();
                    if (examTimerBadge) examTimerBadge.classList.add('warning');
                    updateTimerDisplays();
                    // Auto submit when time has elapsed
                    setTimeout(() => {
                        if (submitBtn) submitBtn.click();
                    }, 800);
                    return;
                } else if (remainingCountdownSeconds <= 60 && examTimerBadge) {
                    examTimerBadge.classList.add('warning');
                }
            }

            updateTimerDisplays();
        }, 1000);
    }

    function stopExamTimer() {
        if (examTimerInterval) {
            clearInterval(examTimerInterval);
            examTimerInterval = null;
        }
        commitCurrentQuestionTime();
    }

    function commitCurrentQuestionTime() {
        if (currentQuestionStartTimestamp && currentQuestionIndex >= 0 && currentQuestionIndex < questions.length) {
            const now = Date.now();
            const diffSecs = Math.max(0, Math.round((now - currentQuestionStartTimestamp) / 1000));
            questionTimes[currentQuestionIndex] = (questionTimes[currentQuestionIndex] || 0) + diffSecs;
            currentQuestionStartTimestamp = null;
        }
    }

    function updateTimerDisplays() {
        if (timerDisplay && isTimerEnabled) {
            const secs = (timerMode === 'countdown') ? remainingCountdownSeconds : totalElapsedSeconds;
            timerDisplay.textContent = window.QuizCore ? window.QuizCore.formatDuration(secs) : `${secs}s`;
        }

        if (questionTimeDisplay && isQuestionTimerEnabled) {
            const alreadySpent = questionTimes[currentQuestionIndex] || 0;
            const currentActive = (!isReviewMode && currentQuestionStartTimestamp) ? Math.max(0, Math.round((Date.now() - currentQuestionStartTimestamp) / 1000)) : 0;
            const totalForThisQ = alreadySpent + currentActive;
            questionTimeDisplay.textContent = window.QuizCore ? window.QuizCore.formatDuration(totalForThisQ) : `${totalForThisQ}s`;
        }
    }

    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    // ── localStorage Persistence ──────────────────────────────────────────────
    const getStorageKey = () => window.QuizCore.getStorageKey(questions);

    function saveProgress() {
        commitCurrentQuestionTime();
        if (!isReviewMode) {
            currentQuestionStartTimestamp = Date.now();
        }
        localStorage.setItem(getStorageKey(), JSON.stringify({
            answers: userAnswers,
            flags: userFlags,
            index: currentQuestionIndex,
            questionTimes,
            totalElapsedSeconds,
            remainingCountdownSeconds
        }));
    }

    function loadProgress() {
        try {
            const raw = localStorage.getItem(getStorageKey());
            return raw ? JSON.parse(raw) : null;
        } catch(e) { return null; }
    }

    function clearProgress() {
        localStorage.removeItem(getStorageKey());
    }

    // ── Fetch Questions ───────────────────────────────────────────────────────
    const inlineQuestions = document.getElementById('quiz-data')?.textContent.trim();
    const questionsSource = inlineQuestions
        ? Promise.resolve(JSON.parse(inlineQuestions))
        : fetch('questions.json').then(r => {
            if (!r.ok) throw new Error(`HTTP ${r.status}`);
            return r.json();
        });

    questionsSource
        .then(data => {
            if (!Array.isArray(data) || data.length === 0) {
                throw new Error('questions.json is empty or malformed');
            }
            questions = data.map(q => {
                const options = q.options.map((text, id) => ({ id, text }));
                if (q.shuffleOptions) {
                    // Fisher-Yates shuffle for 000-style tests that default all answers to א.
                    for (let i = options.length - 1; i > 0; i--) {
                        const j = Math.floor(Math.random() * (i + 1));
                        [options[i], options[j]] = [options[j], options[i]];
                    }
                }
                return { ...q, options };
            });
            allMasterQuestions = [...questions];

            // Update welcome text now that questions are confirmed loaded
            const welcomeDesc = document.querySelector('.welcome-card > p');
            if (welcomeDesc) {
                const shuffledQuestions = questions.filter(q => q.shuffleOptions).length;
                welcomeDesc.textContent = shuffledQuestions
                    ? `נטענו ${questions.length} שאלות בהצלחה. סדר התשובות מעורבב אוטומטית במבחני 000 ללא קובץ תשובות.`
                    : `נטענו ${questions.length} שאלות בהצלחה.`;
            }

            // Check for saved progress
            const saved = loadProgress();
            if (saved && saved.answers && saved.answers.length === questions.length) {
                resumeNotice.classList.remove('hidden');
            }
        })
        .catch(err => {
            console.error('Error loading questions.json:', err);
            const welcomeCard = document.querySelector('.welcome-card');
            if (welcomeCard) {
                const errDiv = document.createElement('div');
                errDiv.style.cssText = 'margin-top:1rem;padding:1rem;border-radius:.75rem;background:var(--error-bg);color:var(--error-color);border:1px solid var(--error-color);font-size:.9rem;';
                errDiv.innerHTML = `⚠️ לא נמצא קובץ שאלות. <a href="${onlineBuilderUrl}" id="builder-nav-error-link" style="color:inherit;text-decoration:underline;">יוצר מבחן אונליין</a> כדי לטעון שאלות, או השתמש בכפתור "פתור מבחן כעת".`;
                welcomeCard.appendChild(errDiv);
            }
            startBtn.disabled = true;
            startBtn.style.opacity = '0.4';
        });

    // ── Image Zoom ────────────────────────────────────────────────────────────
    questionImage.addEventListener('click', () => {
        if (questionImage.classList.contains('hidden')) return;
        zoomImg.src = questionImage.src;
        zoomOverlay.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
    });

    zoomOverlay.addEventListener('click', closeZoom);

    function closeZoom() {
        zoomOverlay.classList.add('hidden');
        document.body.style.overflow = '';
    }

    // ── Keyboard Navigation ───────────────────────────────────────────────────
    document.addEventListener('keydown', e => {
        // Close zoom
        if (e.key === 'Escape') {
            if (!zoomOverlay.classList.contains('hidden')) { closeZoom(); return; }
        }

        // Only act when quiz or results screen is active
        const onQuiz = quizScreen.classList.contains('active');
        const onResults = resultsScreen.classList.contains('active');
        if (!onQuiz && !onResults) return;

        if (onResults) {
            if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
                isReviewMode = true;
                currentQuestionIndex = questions.length - 1;
                switchScreen(resultsScreen, quizScreen);
                renderQuestion();
            }
            return;
        }

        // Option selection: dynamic keys based on number of options (1-9)
        const keyNum = parseInt(e.key);
        if (keyNum >= 1 && keyNum <= 9) {
            const opts = optionsContainer.querySelectorAll('.option');
            if (opts[keyNum - 1] && !opts[keyNum - 1].classList.contains('disabled')) {
                opts[keyNum - 1].click();
            }
            return;
        }

        // Navigation (RTL: ArrowRight = go back/previous, ArrowLeft = go forward/next)
        if (e.key === 'ArrowRight') {
            if (!prevBtn.disabled) prevBtn.click();
        }
        if (e.key === 'ArrowLeft') {
            if (!submitBtn.classList.contains('hidden')) submitBtn.click();
            else if (!nextBtn.classList.contains('hidden')) nextBtn.click();
        }
    });

    // ── Screen Switching ──────────────────────────────────────────────────────
    function switchScreen(from, to) {
        from.classList.remove('active');
        to.classList.add('active');
    }

    // ── Start / Resume / Restart ──────────────────────────────────────────────
    startBtn.addEventListener('click', () => {
        clearProgress();
        userAnswers = new Array(questions.length).fill(null);
        userFlags = new Array(questions.length).fill(false);
        questionTimes = new Array(questions.length).fill(0);
        currentQuestionIndex = 0;
        isReviewMode = false;
        switchScreen(setupScreen, quizScreen);
        startExamTimer(false);
        renderQuestion();
    });

    resumeBtn.addEventListener('click', () => {
        const saved = loadProgress();
        userAnswers = (saved && saved.answers) ? saved.answers : new Array(questions.length).fill(null);
        userFlags = (saved && saved.flags) ? saved.flags : new Array(questions.length).fill(false);
        currentQuestionIndex = saved ? saved.index : 0;
        if (saved && Array.isArray(saved.questionTimes)) {
            questionTimes = saved.questionTimes;
        } else {
            questionTimes = new Array(questions.length).fill(0);
        }
        if (saved && typeof saved.totalElapsedSeconds === 'number') {
            totalElapsedSeconds = saved.totalElapsedSeconds;
        }
        if (saved && typeof saved.remainingCountdownSeconds === 'number') {
            remainingCountdownSeconds = saved.remainingCountdownSeconds;
        }
        switchScreen(setupScreen, quizScreen);
        startExamTimer(true);
        renderQuestion();
    });

    restartBtn.addEventListener('click', () => {
        stopExamTimer();
        clearProgress();
        if (allMasterQuestions && allMasterQuestions.length > 0) {
            questions = [...allMasterQuestions];
        }
        userAnswers = new Array(questions.length).fill(null);
        userFlags = new Array(questions.length).fill(false);
        questionTimes = new Array(questions.length).fill(0);
        totalElapsedSeconds = 0;
        remainingCountdownSeconds = timerCountdownMinutes * 60;
        currentQuestionIndex = 0;
        isReviewMode = false;
        reviewFilter = 'all';
        filterBtns.forEach(b => {
            b.classList.toggle('active', b.dataset.filter === 'all');
        });
        switchScreen(resultsScreen, setupScreen);
    });

    if (retryIncorrectBtn) {
        retryIncorrectBtn.addEventListener('click', () => {
            const wrongOrUnanswered = questions.filter((q, i) => !userAnswers[i] || !userAnswers[i].isCorrect);
            if (!wrongOrUnanswered.length) return;

            questions = wrongOrUnanswered;
            userAnswers = new Array(questions.length).fill(null);
            userFlags = new Array(questions.length).fill(false);
            questionTimes = new Array(questions.length).fill(0);
            totalElapsedSeconds = 0;
            remainingCountdownSeconds = timerCountdownMinutes * 60;
            currentQuestionIndex = 0;
            isReviewMode = false;
            reviewFilter = 'all';
            filterBtns.forEach(b => {
                b.classList.toggle('active', b.dataset.filter === 'all');
            });
            clearProgress();
            switchScreen(resultsScreen, quizScreen);
            startExamTimer(false);
            renderQuestion();
        });
    }

    if (retryFlaggedBtn) {
        retryFlaggedBtn.addEventListener('click', () => {
            const flaggedList = questions.filter((q, i) => userFlags[i]);
            if (!flaggedList.length) return;

            questions = flaggedList;
            userAnswers = new Array(questions.length).fill(null);
            userFlags = new Array(questions.length).fill(true);
            questionTimes = new Array(questions.length).fill(0);
            totalElapsedSeconds = 0;
            remainingCountdownSeconds = timerCountdownMinutes * 60;
            currentQuestionIndex = 0;
            isReviewMode = false;
            reviewFilter = 'all';
            filterBtns.forEach(b => {
                b.classList.toggle('active', b.dataset.filter === 'all');
            });
            clearProgress();
            switchScreen(resultsScreen, quizScreen);
            startExamTimer(false);
            renderQuestion();
        });
    }

    // ── Custom Practice Mix & Match ───────────────────────────────────────────
    function getCustomSelectedIndices() {
        return window.QuizCore.getCustomSelectedIndices(
            questions,
            userAnswers,
            userFlags,
            {
                wrong: !!chkMixWrong?.checked,
                unanswered: !!chkMixUnanswered?.checked,
                flagged: !!chkMixFlagged?.checked
            },
            Array.from(manualSelectedIndices)
        );
    }

    function updateCustomPracticeSelection() {
        const count = getCustomSelectedIndices().length;
        if (customSelectedCount) customSelectedCount.textContent = count;
        if (startCustomPracticeBtn) startCustomPracticeBtn.disabled = count === 0;
    }

    [chkMixWrong, chkMixUnanswered, chkMixFlagged].forEach(chk => {
        chk?.addEventListener('change', updateCustomPracticeSelection);
    });

    if (startCustomPracticeBtn) {
        startCustomPracticeBtn.addEventListener('click', () => {
            const selectedIndices = getCustomSelectedIndices();
            if (!selectedIndices.length) return;

            const customSubList = selectedIndices.map(i => questions[i]);
            const newFlags = selectedIndices.map(i => userFlags[i]);

            questions = customSubList;
            userAnswers = new Array(questions.length).fill(null);
            userFlags = newFlags;
            questionTimes = new Array(questions.length).fill(0);
            totalElapsedSeconds = 0;
            remainingCountdownSeconds = timerCountdownMinutes * 60;
            manualSelectedIndices.clear();
            currentQuestionIndex = 0;
            isReviewMode = false;
            reviewFilter = 'all';
            filterBtns.forEach(b => {
                b.classList.toggle('active', b.dataset.filter === 'all');
            });
            clearProgress();
            switchScreen(resultsScreen, quizScreen);
            startExamTimer(false);
            renderQuestion();
        });
    }

    if (reviewBackBtn) {
        reviewBackBtn.addEventListener('click', () => {
            isReviewMode = true;
            currentQuestionIndex = questions.length - 1;
            switchScreen(resultsScreen, quizScreen);
            renderQuestion();
        });
    }

    // ── Navigation Buttons ────────────────────────────────────────────────────
    nextBtn.addEventListener('click', () => {
        if (currentQuestionIndex < questions.length - 1) {
            commitCurrentQuestionTime();
            currentQuestionIndex++;
            currentQuestionStartTimestamp = Date.now();
            renderQuestion();
        }
    });

    prevBtn.addEventListener('click', () => {
        if (currentQuestionIndex > 0) {
            commitCurrentQuestionTime();
            currentQuestionIndex--;
            currentQuestionStartTimestamp = Date.now();
            renderQuestion();
        }
    });

    submitBtn.addEventListener('click', () => {
        if (isReviewMode) {
            isReviewMode = false;
            switchScreen(quizScreen, resultsScreen);
            renderResults();
            return;
        }
        stopExamTimer();
        clearProgress();
        switchScreen(quizScreen, resultsScreen);
        renderResults();
    });

    // ── Jump Bar ──────────────────────────────────────────────────────────────
    function renderJumpBar() {
        jumpBar.innerHTML = '';
        questions.forEach((q, i) => {
            const btn = document.createElement('button');
            btn.className = 'jump-btn';
            btn.textContent = i + 1;
            btn.setAttribute('aria-label', `שאלה ${i + 1}`);

            const answer = userAnswers[i];
            if (answer) {
                if (isImmediateFeedback) {
                    btn.classList.add(answer.isCorrect ? 'answered-correct' : 'answered-wrong');
                } else {
                    btn.classList.add('answered-neutral');
                }
            }
            if (userFlags[i]) {
                btn.classList.add('flagged');
            }
            if (i === currentQuestionIndex) {
                btn.classList.add('current');
                btn.setAttribute('aria-current', 'step');
            }

            btn.addEventListener('click', () => {
                commitCurrentQuestionTime();
                currentQuestionIndex = i;
                currentQuestionStartTimestamp = Date.now();
                renderQuestion();
            });
            jumpBar.appendChild(btn);
        });
    }

    // ── Render Question ───────────────────────────────────────────────────────
    function renderQuestion() {
        clearAutoAdvance();
        const q = questions[currentQuestionIndex];
        const answered = userAnswers[currentQuestionIndex];

        // Update timer displays & visibility
        if (isReviewMode) {
            if (examTimerBadge) examTimerBadge.classList.add('hidden');
            if (questionTimeBadge) questionTimeBadge.classList.add('hidden');
        } else {
            if (examTimerBadge) examTimerBadge.classList.toggle('hidden', !isTimerEnabled);
            if (questionTimeBadge) questionTimeBadge.classList.toggle('hidden', !isQuestionTimerEnabled);
            updateTimerDisplays();
        }

        questionCounter.textContent = `שאלה ${currentQuestionIndex + 1} מתוך ${questions.length}`;
        questionText.textContent = q.question;
        requestAnimationFrame(() => questionText.focus({ preventScroll: true }));

        // Flag button state
        if (flagBtn) {
            const isFlagged = !!userFlags[currentQuestionIndex];
            flagBtn.classList.toggle('starred', isFlagged);
            const starSpan = flagBtn.querySelector('.flag-star');
            const textSpan = flagBtn.querySelector('.flag-text');
            if (starSpan) starSpan.textContent = isFlagged ? '★' : '☆';
            if (textSpan) textSpan.textContent = isFlagged ? 'מסומנת' : 'סמן שאלה';
        }

        // Image
        if (q.image) {
            // Check if user has already cropped this image
            if (croppedImages[q.image]) {
                questionImage.src = croppedImages[q.image];
            } else {
                questionImage.src = q.image;
            }
            questionImage.dataset.fullSrc = q.image;
            questionImage.classList.remove('hidden');
            openCropperBtn.classList.remove('hidden');
        } else {
            questionImage.classList.add('hidden');
            openCropperBtn.classList.add('hidden');
            questionImage.src = '';
            questionImage.dataset.fullSrc = '';
        }

        // Progress bar
        progressBar.style.width = `${(currentQuestionIndex / questions.length) * 100}%`;

        // Feedback
        feedbackMessage.classList.add('hidden');
        feedbackMessage.className = 'feedback-message hidden';
        feedbackMessage.innerHTML = '';

        // Navigation buttons
        prevBtn.disabled = currentQuestionIndex === 0;
        const isLast = currentQuestionIndex === questions.length - 1;
        nextBtn.classList.toggle('hidden', false); // never hide next
        submitBtn.classList.toggle('hidden', !isLast);
        if (isReviewMode) {
            submitBtn.textContent = 'חזרה לתוצאות';
            submitBtn.classList.remove('hidden');
        } else {
            submitBtn.textContent = 'הגש מבחן';
        }

        // Options
        optionsContainer.innerHTML = '';
        q.options.forEach((option, posIndex) => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'option';
            btn.textContent = option.text;
            btn.setAttribute('data-key', posIndex + 1); // keyboard shortcut hint

            // Restore previous selection
            if (answered) {
                if (answered.selectedOptionId === option.id) btn.classList.add('selected');

                if (isImmediateFeedback) {
                    btn.classList.add('disabled');
                    if (option.id === q.correctIndex) btn.classList.add('correct');
                    else if (answered.selectedOptionId === option.id) btn.classList.add('incorrect');
                }
            }

            btn.setAttribute('aria-label', `תשובה ${posIndex + 1}: ${option.text}`);
            btn.addEventListener('click', () => handleOptionSelect(option.id, btn, q.correctIndex));
            optionsContainer.appendChild(btn);
        });

        // Show feedback if already answered
        if (answered && isImmediateFeedback) showFeedbackMessage(answered.isCorrect);

        // Update jump bar
        renderJumpBar();
    }

    if (flagBtn) {
        flagBtn.addEventListener('click', () => {
            userFlags[currentQuestionIndex] = !userFlags[currentQuestionIndex];
            saveProgress();
            renderQuestion();
        });
    }

    // ── Handle Option Select ──────────────────────────────────────────────────
    function handleOptionSelect(selectedId, btnElement, correctId) {
        const answered = userAnswers[currentQuestionIndex];

        // Lock in immediate feedback mode
        if (isImmediateFeedback && answered) return;

        const isCorrect = selectedId === correctId;
        userAnswers[currentQuestionIndex] = { selectedOptionId: selectedId, isCorrect };
        saveProgress();

        // Update UI
        optionsContainer.querySelectorAll('.option').forEach(opt => opt.classList.remove('selected'));
        btnElement.classList.add('selected');

        if (isImmediateFeedback) {
            // Re-render to apply correct/incorrect styles cleanly
            renderQuestion();
            if (isCorrect && !isReviewMode) {
                const isLast = currentQuestionIndex === questions.length - 1;
                const targetText = isLast ? 'לסיום המבחן' : 'לשאלה הבאה';
                showFeedbackMessage(true, true, targetText);

                const totalDurationMs = 1500;
                const startTime = Date.now();

                autoAdvanceInterval = setInterval(() => {
                    const elapsed = Date.now() - startTime;
                    const remainingMs = Math.max(0, totalDurationMs - elapsed);
                    const remainingSeconds = Math.ceil(remainingMs / 1000);
                    const secElem = feedbackMessage.querySelector('.auto-advance-seconds');
                    if (secElem) {
                        secElem.textContent = String(remainingSeconds > 0 ? remainingSeconds : 1);
                    }
                    if (remainingMs <= 0) {
                        clearInterval(autoAdvanceInterval);
                        autoAdvanceInterval = null;
                    }
                }, 100);

                autoAdvanceTimer = setTimeout(() => {
                    clearAutoAdvance();
                    if (isLast) {
                        submitBtn.click();
                    } else {
                        commitCurrentQuestionTime();
                        currentQuestionIndex++;
                        currentQuestionStartTimestamp = Date.now();
                        renderQuestion();
                    }
                }, totalDurationMs);
            }
        } else {
            // Just update jump bar dot
            renderJumpBar();
        }
    }

    // ── Feedback Message ──────────────────────────────────────────────────────
    function showFeedbackMessage(isCorrect, autoAdvance = false, targetName = 'לשאלה הבאה') {
        feedbackMessage.classList.remove('hidden');
        feedbackMessage.innerHTML = '';
        if (isCorrect) {
            feedbackMessage.className = 'feedback-message success';
            if (autoAdvance) {
                const titleSpan = document.createElement('span');
                titleSpan.className = 'feedback-title';
                titleSpan.textContent = '✓ תשובה נכונה! כל הכבוד.';

                const indicatorSpan = document.createElement('span');
                indicatorSpan.className = 'auto-advance-indicator';
                indicatorSpan.innerHTML = `⏳ עובר ${targetName} בעוד <strong class="auto-advance-seconds">2</strong> שניות...`;

                const barTrack = document.createElement('div');
                barTrack.className = 'auto-advance-bar-track';
                const barFill = document.createElement('div');
                barFill.className = 'auto-advance-bar-fill';
                barTrack.appendChild(barFill);

                feedbackMessage.appendChild(titleSpan);
                feedbackMessage.appendChild(indicatorSpan);
                feedbackMessage.appendChild(barTrack);
            } else {
                feedbackMessage.textContent = 'תשובה נכונה! כל הכבוד.';
            }
        } else {
            feedbackMessage.className = 'feedback-message error';
            feedbackMessage.textContent = 'תשובה שגויה.';
        }
    }

    // ── Review Filter Buttons ─────────────────────────────────────────────────
    filterBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            filterBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            reviewFilter = btn.dataset.filter;
            renderReviewList();
        });
    });

    // ── Render Results ────────────────────────────────────────────────────────
    function renderResults() {
        const correctCount = userAnswers.filter(a => a && a.isCorrect).length;
        const total = questions.length;
        const percentage = Math.round((correctCount / total) * 100);

        const wrongOrUnansweredCount = total - correctCount;
        const retryBtn = document.getElementById('retry-incorrect-btn');
        const badge = document.getElementById('incorrect-count-badge');
        if (retryBtn && badge) {
            if (wrongOrUnansweredCount > 0) {
                retryBtn.classList.remove('hidden');
                badge.textContent = wrongOrUnansweredCount;
            } else {
                retryBtn.classList.add('hidden');
            }
        }

        const wrongCount = userAnswers.filter(a => a && !a.isCorrect).length;
        const unansweredCount = userAnswers.filter(a => !a).length;
        const flaggedCount = userFlags.filter(Boolean).length;

        if (cntMixWrong) cntMixWrong.textContent = wrongCount;
        if (cntMixUnanswered) cntMixUnanswered.textContent = unansweredCount;
        if (cntMixFlagged) cntMixFlagged.textContent = flaggedCount;

        if (retryFlaggedBtn) {
            if (flaggedCount > 0) {
                retryFlaggedBtn.classList.remove('hidden');
                if (flaggedCountBadgeAction) flaggedCountBadgeAction.textContent = flaggedCount;
            } else {
                retryFlaggedBtn.classList.add('hidden');
            }
        }
        if (flaggedCountBadgeFilter) flaggedCountBadgeFilter.textContent = flaggedCount;

        updateCustomPracticeSelection();

        const scoreText = document.getElementById('score-text');
        if (scoreText) {
            scoreText.textContent = `ענית נכונה על ${correctCount} מתוך ${total} שאלות.`;
        }

        // Timing Analytics
        if (timingAnalyticsCard) {
            if (isTimerEnabled || isQuestionTimerEnabled) {
                const stats = window.QuizCore ? window.QuizCore.calculateTimingStats(questionTimes) : null;
                if (stats) {
                    const totalSec = isTimerEnabled ? totalElapsedSeconds : stats.totalSeconds;
                    if (totalTimeStat) {
                        totalTimeStat.textContent = window.QuizCore ? window.QuizCore.formatDuration(totalSec) : `${totalSec}s`;
                    }
                    if (meanTimeStat) {
                        meanTimeStat.textContent = stats.formattedMean;
                    }
                    if (timedQuestionsStat) {
                        timedQuestionsStat.textContent = String(stats.activeCount);
                    }
                    timingAnalyticsCard.classList.remove('hidden');
                }
            } else {
                timingAnalyticsCard.classList.add('hidden');
            }
        }

        const circle = document.querySelector('.score-circle');
        const scoreEl = document.getElementById('final-score');

        // Animate score circle and counter from 0 → percentage
        circle.style.background = `conic-gradient(var(--primary-color) 0%, var(--option-bg) 0%)`;
        scoreEl.textContent = '0%';

        let start = null;
        const duration = 900;
        function animateScore(ts) {
            if (!start) start = ts;
            const elapsed = ts - start;
            const progress = Math.min(elapsed / duration, 1);
            // Ease out cubic
            const eased = 1 - Math.pow(1 - progress, 3);
            const current = Math.round(eased * percentage);
            scoreEl.textContent = `${current}%`;
            circle.style.background =
                `conic-gradient(var(--primary-color) ${current}%, var(--option-bg) 0%)`;
            if (progress < 1) requestAnimationFrame(animateScore);
        }
        requestAnimationFrame(animateScore);

        renderReviewList();
    }

    function renderReviewList() {
        const reviewContainer = document.getElementById('review-container');
        reviewContainer.innerHTML = '';

        questions.forEach((q, i) => {
            const answer = userAnswers[i];
            const isCorrect = answer && answer.isCorrect;
            const isUnanswered = !answer;

            // Apply filter
            if (reviewFilter === 'wrong'      && (isCorrect || isUnanswered)) return;
            if (reviewFilter === 'unanswered' && !isUnanswered)                return;
            if (reviewFilter === 'flagged'    && !userFlags[i])                return;

            const div = document.createElement('div');
            div.className = 'review-item';

            const isManuallySelected = manualSelectedIndices.has(i);
            const timeSpent = questionTimes[i] || 0;
            const timeBadgeHtml = (isQuestionTimerEnabled && timeSpent > 0)
                ? `<span class="review-time-badge" title="זמן מענה לשאלה">⏱️ ${window.QuizCore ? window.QuizCore.formatDuration(timeSpent) : timeSpent + 's'}</span>`
                : '';

            let html = `
                <div class="review-item-header">
                    <div class="review-question" style="margin:0;">${i + 1}. ${escapeHtml(q.question)}</div>
                    ${timeBadgeHtml}
                    <label class="review-card-select-label" onclick="event.stopPropagation();">
                        <input type="checkbox" class="review-card-checkbox" data-index="${i}" ${isManuallySelected ? 'checked' : ''} style="accent-color:var(--primary-color);">
                        <span>בחירה לתרגול</span>
                    </label>
                </div>
            `;

            q.options.forEach(opt => {
                let cls = 'review-option';
                if (opt.id === q.correctIndex)                              cls += ' correct';
                else if (answer && answer.selectedOptionId === opt.id)      cls += ' incorrect';
                html += `<div class="${cls}">${escapeHtml(opt.text)}</div>`;
            });

            if (isUnanswered) {
                html += `<div class="review-option incorrect">לא נענה</div>`;
            }

            div.innerHTML = html;
            div.style.cursor = 'pointer';
            div.title = 'לחץ למעבר לשאלה';

            const chk = div.querySelector('.review-card-checkbox');
            if (chk) {
                chk.addEventListener('change', (e) => {
                    e.stopPropagation();
                    const idx = parseInt(chk.dataset.index, 10);
                    if (chk.checked) {
                        manualSelectedIndices.add(idx);
                    } else {
                        manualSelectedIndices.delete(idx);
                    }
                    updateCustomPracticeSelection();
                });
            }

            div.addEventListener('click', () => {
                isReviewMode = true;
                currentQuestionIndex = i;
                switchScreen(resultsScreen, quizScreen);
                renderQuestion();
            });
            reviewContainer.appendChild(div);
        });

        // Empty state message
        if (!reviewContainer.hasChildNodes()) {
            reviewContainer.innerHTML =
                `<p style="text-align:center;color:var(--text-secondary);padding:2rem;">אין שאלות להצגה בסינון זה.</p>`;
        }
    }

    // ── Cropper Logic ─────────────────────────────────────────────────────────
    let cropperLibLoaded = false;

    function loadCropperLib() {
        if (cropperLibLoaded) return Promise.resolve();
        return new Promise((resolve, reject) => {
            const link = document.createElement('link');
            link.rel = 'stylesheet';
            link.href = 'https://cdnjs.cloudflare.com/ajax/libs/cropperjs/1.6.1/cropper.min.css';
            document.head.appendChild(link);

            const script = document.createElement('script');
            script.src = 'https://cdnjs.cloudflare.com/ajax/libs/cropperjs/1.6.1/cropper.min.js';
            script.onload = () => { cropperLibLoaded = true; resolve(); };
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }

    openCropperBtn.addEventListener('click', async () => {
        const fullSrc = questionImage.dataset.fullSrc;
        if (!fullSrc) return;

        await loadCropperLib();

        cropperModal.classList.remove('hidden');
        document.body.style.overflow = 'hidden';

        const initCropper = () => {
            if (cropperInstance) cropperInstance.destroy();
            cropperInstance = new Cropper(cropperImage, {
                viewMode: 1,
                dragMode: 'crop',
                autoCropArea: 0.5,
                restore: false,
                guides: true,
                center: true,
                highlight: false,
                cropBoxMovable: true,
                cropBoxResizable: true,
                toggleDragModeOnDblclick: false,
            });
        };

        cropperImage.onload = initCropper;
        cropperImage.src = fullSrc;
        if (cropperImage.complete) {
            initCropper();
        }
    });


    function closeCropper() {
        cropperModal.classList.add('hidden');
        document.body.style.overflow = '';
        if (cropperInstance) {
            cropperInstance.destroy();
            cropperInstance = null;
        }
    }

    closeCropperBtn.addEventListener('click', closeCropper);

    confirmCropBtn.addEventListener('click', () => {
        if (!cropperInstance) return;
        
        // Get the cropped canvas
        const canvas = cropperInstance.getCroppedCanvas();
        if (canvas) {
            const dataUrl = canvas.toDataURL('image/png');
            const fullSrc = questionImage.dataset.fullSrc;
            
            // Save crop for this image
            croppedImages[fullSrc] = dataUrl;
            
            // Update UI
            questionImage.src = dataUrl;
        }
        
        closeCropper();
    });

});
