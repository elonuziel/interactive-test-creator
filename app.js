(function (root, factory) {
    if (typeof define === 'function' && define.amd) {
        define([], factory);
    } else if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.QuizApp = factory();
    }
}(typeof self !== 'undefined' ? self : this, function () {
    'use strict';

    // ── Helper Utilities ───────────────────────────────────────────────────────
    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    // ── Quiz Session State ─────────────────────────────────────────────────────
    class QuizSessionState {
        constructor() {
            this.questions = [];
            this.allMasterQuestions = [];
            this.currentQuestionIndex = 0;
            this.userAnswers = [];
            this.userFlags = [];
            this.questionTimes = [];
            this.totalElapsedSeconds = 0;
            this.remainingCountdownSeconds = 0;
            this.currentQuestionStartTimestamp = null;
            this.manualSelectedIndices = new Set();
            this.isReviewMode = false;
            this.reviewFilter = 'all';
            this.croppedImages = {};

            // User Settings
            this.isImmediateFeedback = false;
            this.isTimerEnabled = false;
            this.timerMode = 'stopwatch'; // 'stopwatch' | 'countdown'
            this.timerCountdownMinutes = 30;
            this.isQuestionTimerEnabled = true;
        }

        initSession({ mode, questions = null, savedState = null, defaultCountdownMinutes = 30 }) {
            if (mode === 'resume' && savedState) {
                this.userAnswers = Array.isArray(savedState.answers) ? savedState.answers : new Array(this.questions.length).fill(null);
                this.userFlags = Array.isArray(savedState.flags) ? savedState.flags : new Array(this.questions.length).fill(false);
                this.currentQuestionIndex = typeof savedState.index === 'number' ? savedState.index : 0;
                this.questionTimes = Array.isArray(savedState.questionTimes) ? savedState.questionTimes : new Array(this.questions.length).fill(0);
                this.totalElapsedSeconds = typeof savedState.totalElapsedSeconds === 'number' ? savedState.totalElapsedSeconds : 0;
                this.remainingCountdownSeconds = typeof savedState.remainingCountdownSeconds === 'number'
                    ? savedState.remainingCountdownSeconds
                    : (this.timerCountdownMinutes || defaultCountdownMinutes) * 60;
                this.isReviewMode = false;
                this.currentQuestionStartTimestamp = Date.now();
                return;
            }

            if (mode === 'restart') {
                if (this.allMasterQuestions && this.allMasterQuestions.length > 0) {
                    this.questions = [...this.allMasterQuestions];
                }
            } else if (questions) {
                this.questions = [...questions];
            }

            const count = this.questions.length;
            this.userAnswers = new Array(count).fill(null);
            this.userFlags = (mode === 'retry-flagged') ? new Array(count).fill(true) : new Array(count).fill(false);
            this.questionTimes = new Array(count).fill(0);
            this.currentQuestionIndex = 0;
            this.totalElapsedSeconds = 0;
            this.remainingCountdownSeconds = (this.timerCountdownMinutes || defaultCountdownMinutes) * 60;
            this.isReviewMode = false;
            this.reviewFilter = 'all';
            this.manualSelectedIndices.clear();
            this.currentQuestionStartTimestamp = Date.now();
        }

        commitCurrentQuestionTime() {
            if (this.currentQuestionStartTimestamp && this.currentQuestionIndex >= 0 && this.currentQuestionIndex < this.questions.length) {
                const now = Date.now();
                const diffSecs = Math.max(0, Math.round((now - this.currentQuestionStartTimestamp) / 1000));
                this.questionTimes[this.currentQuestionIndex] = (this.questionTimes[this.currentQuestionIndex] || 0) + diffSecs;
                this.currentQuestionStartTimestamp = null;
            }
        }

        recordAnswer(index, selectedOptionId, correctId) {
            if (index < 0 || index >= this.questions.length) return false;
            const isCorrect = selectedOptionId === correctId;
            this.userAnswers[index] = { selectedOptionId, isCorrect };
            return isCorrect;
        }

        toggleFlag(index) {
            if (index >= 0 && index < this.questions.length) {
                this.userFlags[index] = !this.userFlags[index];
                return this.userFlags[index];
            }
            return false;
        }

        getStoragePayload() {
            return {
                answers: this.userAnswers,
                flags: this.userFlags,
                index: this.currentQuestionIndex,
                questionTimes: this.questionTimes,
                totalElapsedSeconds: this.totalElapsedSeconds,
                remainingCountdownSeconds: this.remainingCountdownSeconds
            };
        }

        getWrongOrUnansweredQuestions() {
            return this.questions.filter((q, i) => !this.userAnswers[i] || !this.userAnswers[i].isCorrect);
        }

        getFlaggedQuestions() {
            return this.questions.filter((q, i) => this.userFlags[i]);
        }

        getCustomPracticeIndices(chkWrong, chkUnanswered, chkFlagged) {
            const quizCore = (typeof window !== 'undefined' ? window.QuizCore : null) || (typeof require !== 'undefined' ? require('./quiz-core.js') : null);
            if (!quizCore) return Array.from(this.manualSelectedIndices);
            return quizCore.getCustomSelectedIndices(
                this.questions,
                this.userAnswers,
                this.userFlags,
                { wrong: chkWrong, unanswered: chkUnanswered, flagged: chkFlagged },
                Array.from(this.manualSelectedIndices)
            );
        }
    }

    // ── Quiz Timer Engine ──────────────────────────────────────────────────────
    class QuizTimerEngine {
        constructor() {
            this.examInterval = null;
            this.autoAdvanceTimer = null;
            this.autoAdvanceInterval = null;
        }

        startExamTimer({ state, onTick, onExpire, onWarning }) {
            this.stopExamTimer();
            state.currentQuestionStartTimestamp = Date.now();

            this.examInterval = setInterval(() => {
                state.totalElapsedSeconds++;
                if (state.timerMode === 'countdown') {
                    state.remainingCountdownSeconds--;
                    if (state.remainingCountdownSeconds <= 0) {
                        state.remainingCountdownSeconds = 0;
                        this.stopExamTimer();
                        if (onWarning) onWarning(true);
                        if (onTick) onTick();
                        if (onExpire) onExpire();
                        return;
                    } else if (state.remainingCountdownSeconds <= 60 && onWarning) {
                        onWarning(false);
                    }
                }
                if (onTick) onTick();
            }, 1000);
        }

        stopExamTimer(state) {
            if (this.examInterval) {
                clearInterval(this.examInterval);
                this.examInterval = null;
            }
            if (state) {
                state.commitCurrentQuestionTime();
            }
        }

        startAutoAdvance({ durationMs = 1500, onTick, onComplete }) {
            this.clearAutoAdvance();
            const startTime = Date.now();

            this.autoAdvanceInterval = setInterval(() => {
                const elapsed = Date.now() - startTime;
                const remainingMs = Math.max(0, durationMs - elapsed);
                const remainingSeconds = Math.ceil(remainingMs / 1000);
                if (onTick) onTick(remainingSeconds, remainingMs);
                if (remainingMs <= 0) {
                    if (this.autoAdvanceInterval) {
                        clearInterval(this.autoAdvanceInterval);
                        this.autoAdvanceInterval = null;
                    }
                }
            }, 100);

            this.autoAdvanceTimer = setTimeout(() => {
                this.clearAutoAdvance();
                if (onComplete) onComplete();
            }, durationMs);
        }

        clearAutoAdvance() {
            if (this.autoAdvanceTimer) {
                clearTimeout(this.autoAdvanceTimer);
                this.autoAdvanceTimer = null;
            }
            if (this.autoAdvanceInterval) {
                clearInterval(this.autoAdvanceInterval);
                this.autoAdvanceInterval = null;
            }
        }

        cleanup(state) {
            this.stopExamTimer(state);
            this.clearAutoAdvance();
        }
    }

    // ── Persistence Service ────────────────────────────────────────────────────
    const QuizPersistence = {
        getStorageKey(questions) {
            const quizCore = (typeof window !== 'undefined' ? window.QuizCore : null) || (typeof require !== 'undefined' ? require('./quiz-core.js') : null);
            return quizCore ? quizCore.getStorageKey(questions) : 'quiz_answers_v1';
        },

        saveProgress(storageKey, state) {
            if (typeof localStorage === 'undefined' || !storageKey) return;
            state.commitCurrentQuestionTime();
            if (!state.isReviewMode) {
                state.currentQuestionStartTimestamp = Date.now();
            }
            try {
                localStorage.setItem(storageKey, JSON.stringify(state.getStoragePayload()));
            } catch (e) {
                console.warn('Failed saving quiz progress to localStorage:', e);
            }
        },

        loadProgress(storageKey) {
            if (typeof localStorage === 'undefined' || !storageKey) return null;
            try {
                const raw = localStorage.getItem(storageKey);
                return raw ? JSON.parse(raw) : null;
            } catch (e) {
                return null;
            }
        },

        clearProgress(storageKey) {
            if (typeof localStorage === 'undefined' || !storageKey) return;
            try {
                localStorage.removeItem(storageKey);
            } catch (e) {}
        }
    };

    // ── Cropper Controller ─────────────────────────────────────────────────────
    class CropperController {
        constructor() {
            this.cropperLibLoaded = false;
            this.cropperInstance = null;
        }

        loadCropperLib() {
            if (this.cropperLibLoaded) return Promise.resolve();
            return new Promise((resolve, reject) => {
                const link = document.createElement('link');
                link.rel = 'stylesheet';
                link.href = 'https://cdnjs.cloudflare.com/ajax/libs/cropperjs/1.6.1/cropper.min.css';
                document.head.appendChild(link);

                const script = document.createElement('script');
                script.src = 'https://cdnjs.cloudflare.com/ajax/libs/cropperjs/1.6.1/cropper.min.js';
                script.onload = () => { this.cropperLibLoaded = true; resolve(); };
                script.onerror = reject;
                document.head.appendChild(script);
            });
        }

        async open({ fullSrc, elements }) {
            if (!fullSrc || !elements.cropperModal || !elements.cropperImage) return;
            await this.loadCropperLib();

            elements.cropperModal.classList.remove('hidden');
            document.body.style.overflow = 'hidden';

            const initCropper = () => {
                if (this.cropperInstance) this.cropperInstance.destroy();
                this.cropperInstance = new Cropper(elements.cropperImage, {
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

            elements.cropperImage.onload = initCropper;
            elements.cropperImage.src = fullSrc;
            if (elements.cropperImage.complete) {
                initCropper();
            }
        }

        close(elements) {
            if (elements.cropperModal) {
                elements.cropperModal.classList.add('hidden');
            }
            document.body.style.overflow = '';
            if (this.cropperInstance) {
                this.cropperInstance.destroy();
                this.cropperInstance = null;
            }
        }

        getCroppedDataUrl() {
            if (!this.cropperInstance) return null;
            const canvas = this.cropperInstance.getCroppedCanvas();
            return canvas ? canvas.toDataURL('image/png') : null;
        }
    }

    // ── Quiz UI Controller ─────────────────────────────────────────────────────
    class QuizUIController {
        constructor() {
            this.state = new QuizSessionState();
            this.timer = new QuizTimerEngine();
            this.cropper = new CropperController();
            this.elements = {};
            this.onlineBuilderUrl = 'https://elonuziel.github.io/interactive-test-creator/';
        }

        init() {
            this.cacheElements();
            this.initSettings();
            this.initTimerControls();
            this.bindEvents();
            this.loadQuestions();
        }

        cacheElements() {
            const get = (id) => document.getElementById(id);
            this.elements = {
                // Screens
                setupScreen: get('setup-screen'),
                quizScreen: get('quiz-screen'),
                resultsScreen: get('results-screen'),

                // Controls
                startBtn: get('start-btn'),
                resumeBtn: get('resume-btn'),
                resumeNotice: get('resume-notice'),
                prevBtn: get('prev-btn'),
                nextBtn: get('next-btn'),
                submitBtn: get('submit-btn'),
                restartBtn: get('restart-btn'),
                retryIncorrectBtn: get('retry-incorrect-btn'),
                retryFlaggedBtn: get('retry-flagged-btn'),
                reviewBackBtn: get('review-back-btn'),
                flagBtn: get('flag-btn'),

                // Badges & Counters
                flaggedCountBadgeAction: get('flagged-count-badge-action'),
                flaggedCountBadgeFilter: get('flagged-count-badge-filter'),
                incorrectCountBadge: get('incorrect-count-badge'),
                questionCounter: get('question-counter'),
                progressBar: get('progress-bar') || document.querySelector('.progress-bar'),

                // Custom practice mix
                chkMixWrong: get('chk-mix-wrong'),
                chkMixUnanswered: get('chk-mix-unanswered'),
                chkMixFlagged: get('chk-mix-flagged'),
                cntMixWrong: get('cnt-mix-wrong'),
                cntMixUnanswered: get('cnt-mix-unanswered'),
                cntMixFlagged: get('cnt-mix-flagged'),
                startCustomPracticeBtn: get('start-custom-practice-btn'),
                customSelectedCount: get('custom-selected-count'),

                // Question card elements
                questionText: get('question-text'),
                questionImage: get('question-image'),
                openCropperBtn: get('open-cropper-btn'),
                optionsContainer: get('options-container'),
                feedbackMessage: get('feedback-message'),
                jumpBar: get('question-jump-bar') || get('jump-bar'),

                // Zoom modal
                zoomOverlay: get('zoom-overlay'),
                zoomImg: get('zoom-img'),

                // Header toggles & navigation
                themeToggle: get('theme-toggle'),
                themeIcon: get('theme-icon'),
                feedbackToggle: get('immediate-feedback-toggle') || get('feedback-toggle'),
                welcomeFeedbackToggle: get('welcome-immediate-feedback-toggle') || get('welcome-feedback-toggle'),
                builderNavLink: get('builder-nav-link'),

                // Timer Controls & Badges
                quizTimerToggle: get('quiz-timer-toggle'),
                timerOptionsContainer: get('timer-options-container'),
                timerModeStopwatch: get('timer-mode-stopwatch'),
                timerModeCountdown: get('timer-mode-countdown'),
                timerCountdownMinutesInput: get('timer-countdown-minutes'),
                questionTimerToggle: get('question-timer-toggle'),
                examTimerBadge: get('exam-timer-badge'),
                timerDisplay: get('timer-display'),
                questionTimeBadge: get('question-time-badge'),
                questionTimeDisplay: get('question-time-display'),

                // Results Timing Analytics
                timingAnalyticsCard: get('timing-analytics-card'),
                totalTimeStat: get('total-time-stat'),
                meanTimeStat: get('mean-time-stat'),
                timedQuestionsStat: get('timed-questions-stat'),
                finalScore: get('final-score'),
                scoreCircle: document.querySelector('.score-circle'),
                scoreText: get('score-text'),
                reviewContainer: get('review-container'),
                filterBtns: document.querySelectorAll('.filter-btn'),

                // Cropper Modal
                cropperModal: get('cropper-modal'),
                cropperImage: get('cropper-image'),
                closeCropperBtn: get('close-cropper-btn'),
                confirmCropBtn: get('confirm-crop-btn')
            };

            if (this.elements.builderNavLink) {
                this.elements.builderNavLink.href = this.onlineBuilderUrl;
                this.elements.builderNavLink.textContent = 'יוצר מבחן אונליין ←';
            }
        }

        initSettings() {
            // Theme setup
            const currentTheme = localStorage.getItem('theme') || 'light';
            this.setTheme(currentTheme);
            this.elements.themeToggle?.addEventListener('click', () => {
                const nextTheme = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
                this.setTheme(nextTheme);
            });

            // Immediate Feedback setup
            const savedFeedback = localStorage.getItem('quiz_immediate_feedback');
            const feedbackEnabled = savedFeedback !== null ? savedFeedback === 'true' : false;
            this.setImmediateFeedback(feedbackEnabled);
            this.elements.feedbackToggle?.addEventListener('change', (e) => this.setImmediateFeedback(e.target.checked));
            this.elements.welcomeFeedbackToggle?.addEventListener('change', (e) => this.setImmediateFeedback(e.target.checked));
        }

        setTheme(theme) {
            document.documentElement.setAttribute('data-theme', theme);
            localStorage.setItem('theme', theme);
            if (this.elements.themeIcon) {
                this.elements.themeIcon.innerHTML = theme === 'dark'
                    ? '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>'
                    : '<circle cx="12" cy="12" r="4"></circle><path d="M12 2v2"></path><path d="M12 20v2"></path><path d="m4.93 4.93 1.41 1.41"></path><path d="m17.66 17.66 1.41 1.41"></path><path d="M2 12h2"></path><path d="M20 12h2"></path><path d="m6.34 17.66-1.41 1.41"></path><path d="m19.07 4.93-1.41 1.41"></path>';
            }
        }

        setImmediateFeedback(enabled) {
            this.state.isImmediateFeedback = Boolean(enabled);
            if (this.elements.feedbackToggle) this.elements.feedbackToggle.checked = this.state.isImmediateFeedback;
            if (this.elements.welcomeFeedbackToggle) this.elements.welcomeFeedbackToggle.checked = this.state.isImmediateFeedback;
            localStorage.setItem('quiz_immediate_feedback', this.state.isImmediateFeedback);
        }

        initTimerControls() {
            this.state.isTimerEnabled = localStorage.getItem('quiz_timer_enabled') === 'true';
            this.state.timerMode = localStorage.getItem('quiz_timer_mode') || 'stopwatch';
            this.state.timerCountdownMinutes = parseInt(localStorage.getItem('quiz_timer_minutes') || '30', 10);
            this.state.isQuestionTimerEnabled = localStorage.getItem('quiz_question_timer_enabled') !== 'false';

            if (this.elements.quizTimerToggle) {
                this.elements.quizTimerToggle.checked = this.state.isTimerEnabled;
                if (this.elements.timerOptionsContainer) {
                    this.elements.timerOptionsContainer.classList.toggle('hidden', !this.state.isTimerEnabled);
                }
                this.elements.quizTimerToggle.addEventListener('change', (e) => {
                    this.state.isTimerEnabled = e.target.checked;
                    localStorage.setItem('quiz_timer_enabled', this.state.isTimerEnabled);
                    if (this.elements.timerOptionsContainer) {
                        this.elements.timerOptionsContainer.classList.toggle('hidden', !this.state.isTimerEnabled);
                    }
                });
            }

            if (this.elements.timerModeStopwatch && this.elements.timerModeCountdown) {
                if (this.state.timerMode === 'countdown') {
                    this.elements.timerModeCountdown.checked = true;
                } else {
                    this.elements.timerModeStopwatch.checked = true;
                }
                this.elements.timerModeStopwatch.addEventListener('change', () => {
                    if (this.elements.timerModeStopwatch.checked) {
                        this.state.timerMode = 'stopwatch';
                        localStorage.setItem('quiz_timer_mode', 'stopwatch');
                    }
                });
                this.elements.timerModeCountdown.addEventListener('change', () => {
                    if (this.elements.timerModeCountdown.checked) {
                        this.state.timerMode = 'countdown';
                        localStorage.setItem('quiz_timer_mode', 'countdown');
                    }
                });
            }

            if (this.elements.timerCountdownMinutesInput) {
                this.elements.timerCountdownMinutesInput.value = this.state.timerCountdownMinutes;
                this.elements.timerCountdownMinutesInput.addEventListener('input', () => {
                    const val = parseInt(this.elements.timerCountdownMinutesInput.value, 10);
                    if (val && val >= 1) {
                        this.state.timerCountdownMinutes = val;
                        localStorage.setItem('quiz_timer_minutes', val);
                    }
                });
            }

            if (this.elements.questionTimerToggle) {
                this.elements.questionTimerToggle.checked = this.state.isQuestionTimerEnabled;
                this.elements.questionTimerToggle.addEventListener('change', (e) => {
                    this.state.isQuestionTimerEnabled = e.target.checked;
                    localStorage.setItem('quiz_question_timer_enabled', this.state.isQuestionTimerEnabled);
                });
            }
        }

        switchScreen(from, to) {
            from?.classList.remove('active');
            to?.classList.add('active');
        }

        updateTimerDisplays() {
            if (this.elements.timerDisplay && this.state.isTimerEnabled) {
                const secs = (this.state.timerMode === 'countdown') ? this.state.remainingCountdownSeconds : this.state.totalElapsedSeconds;
                this.elements.timerDisplay.textContent = window.QuizCore ? window.QuizCore.formatDuration(secs) : `${secs}s`;
            }

            if (this.elements.questionTimeDisplay && this.state.isQuestionTimerEnabled) {
                const alreadySpent = this.state.questionTimes[this.state.currentQuestionIndex] || 0;
                const currentActive = (!this.state.isReviewMode && this.state.currentQuestionStartTimestamp)
                    ? Math.max(0, Math.round((Date.now() - this.state.currentQuestionStartTimestamp) / 1000))
                    : 0;
                const totalForThisQ = alreadySpent + currentActive;
                this.elements.questionTimeDisplay.textContent = window.QuizCore ? window.QuizCore.formatDuration(totalForThisQ) : `${totalForThisQ}s`;
            }
        }

        startSession(mode) {
            this.timer.cleanup(this.state);

            if (mode === 'new') {
                QuizPersistence.clearProgress(QuizPersistence.getStorageKey(this.state.questions));
                this.state.initSession({ mode: 'new', questions: this.state.allMasterQuestions });
                this.switchScreen(this.elements.setupScreen, this.elements.quizScreen);
                this.startTimerEngine();
                this.renderQuestion();
            } else if (mode === 'resume') {
                const storageKey = QuizPersistence.getStorageKey(this.state.questions);
                const saved = QuizPersistence.loadProgress(storageKey);
                this.state.initSession({ mode: 'resume', savedState: saved });
                this.switchScreen(this.elements.setupScreen, this.elements.quizScreen);
                this.startTimerEngine(true);
                this.renderQuestion();
            } else if (mode === 'restart') {
                QuizPersistence.clearProgress(QuizPersistence.getStorageKey(this.state.questions));
                this.state.initSession({ mode: 'restart' });
                this.elements.filterBtns.forEach(b => b.classList.toggle('active', b.dataset.filter === 'all'));
                this.switchScreen(this.elements.resultsScreen, this.elements.setupScreen);
            } else if (mode === 'retry-incorrect') {
                const wrongList = this.state.getWrongOrUnansweredQuestions();
                if (!wrongList.length) return;
                QuizPersistence.clearProgress(QuizPersistence.getStorageKey(this.state.questions));
                this.state.initSession({ mode: 'retry-incorrect', questions: wrongList });
                this.elements.filterBtns.forEach(b => b.classList.toggle('active', b.dataset.filter === 'all'));
                this.switchScreen(this.elements.resultsScreen, this.elements.quizScreen);
                this.startTimerEngine();
                this.renderQuestion();
            } else if (mode === 'retry-flagged') {
                const flaggedList = this.state.getFlaggedQuestions();
                if (!flaggedList.length) return;
                QuizPersistence.clearProgress(QuizPersistence.getStorageKey(this.state.questions));
                this.state.initSession({ mode: 'retry-flagged', questions: flaggedList });
                this.elements.filterBtns.forEach(b => b.classList.toggle('active', b.dataset.filter === 'all'));
                this.switchScreen(this.elements.resultsScreen, this.elements.quizScreen);
                this.startTimerEngine();
                this.renderQuestion();
            } else if (mode === 'custom-practice') {
                const selectedIndices = this.state.getCustomPracticeIndices(
                    !!this.elements.chkMixWrong?.checked,
                    !!this.elements.chkMixUnanswered?.checked,
                    !!this.elements.chkMixFlagged?.checked
                );
                if (!selectedIndices.length) return;

                const customQuestions = selectedIndices.map(i => this.state.questions[i]);
                const customFlags = selectedIndices.map(i => this.state.userFlags[i]);

                QuizPersistence.clearProgress(QuizPersistence.getStorageKey(this.state.questions));
                this.state.initSession({ mode: 'custom-practice', questions: customQuestions });
                this.state.userFlags = customFlags;
                this.elements.filterBtns.forEach(b => b.classList.toggle('active', b.dataset.filter === 'all'));
                this.switchScreen(this.elements.resultsScreen, this.elements.quizScreen);
                this.startTimerEngine();
                this.renderQuestion();
            }
        }

        startTimerEngine(resume = false) {
            this.timer.stopExamTimer(this.state);

            if (!resume) {
                this.state.totalElapsedSeconds = 0;
                this.state.remainingCountdownSeconds = this.state.timerCountdownMinutes * 60;
            }

            if (this.elements.examTimerBadge) {
                this.elements.examTimerBadge.classList.toggle('hidden', !this.state.isTimerEnabled);
                this.elements.examTimerBadge.classList.remove('warning');
            }
            if (this.elements.questionTimeBadge) {
                this.elements.questionTimeBadge.classList.toggle('hidden', !this.state.isQuestionTimerEnabled);
            }

            this.updateTimerDisplays();

            this.timer.startExamTimer({
                state: this.state,
                onTick: () => this.updateTimerDisplays(),
                onWarning: (isExpired) => {
                    if (this.elements.examTimerBadge) {
                        this.elements.examTimerBadge.classList.add('warning');
                    }
                },
                onExpire: () => {
                    setTimeout(() => {
                        if (this.elements.submitBtn) this.elements.submitBtn.click();
                    }, 800);
                }
            });
        }

        renderQuestion() {
            this.timer.clearAutoAdvance();
            const q = this.state.questions[this.state.currentQuestionIndex];
            const answered = this.state.userAnswers[this.state.currentQuestionIndex];

            // Badges & Timer Visibility
            if (this.state.isReviewMode) {
                this.elements.examTimerBadge?.classList.add('hidden');
                this.elements.questionTimeBadge?.classList.add('hidden');
            } else {
                this.elements.examTimerBadge?.classList.toggle('hidden', !this.state.isTimerEnabled);
                this.elements.questionTimeBadge?.classList.toggle('hidden', !this.state.isQuestionTimerEnabled);
                this.updateTimerDisplays();
            }

            if (this.elements.questionCounter) {
                this.elements.questionCounter.textContent = `שאלה ${this.state.currentQuestionIndex + 1} מתוך ${this.state.questions.length}`;
            }
            if (this.elements.questionText) {
                this.elements.questionText.textContent = q.question;
                requestAnimationFrame(() => this.elements.questionText.focus({ preventScroll: true }));
            }

            // Flag state
            if (this.elements.flagBtn) {
                const isFlagged = !!this.state.userFlags[this.state.currentQuestionIndex];
                this.elements.flagBtn.classList.toggle('starred', isFlagged);
                const starSpan = this.elements.flagBtn.querySelector('.flag-star');
                const textSpan = this.elements.flagBtn.querySelector('.flag-text');
                if (starSpan) starSpan.textContent = isFlagged ? '★' : '☆';
                if (textSpan) textSpan.textContent = isFlagged ? 'מסומנת' : 'סמן שאלה';
            }

            // Question Image
            if (this.elements.questionImage && this.elements.openCropperBtn) {
                if (q.image) {
                    const activeSrc = this.state.croppedImages[q.image] || q.image;
                    this.elements.questionImage.src = activeSrc;
                    this.elements.questionImage.dataset.fullSrc = q.image;
                    this.elements.questionImage.classList.remove('hidden');
                    this.elements.openCropperBtn.classList.remove('hidden');
                } else {
                    this.elements.questionImage.classList.add('hidden');
                    this.elements.openCropperBtn.classList.add('hidden');
                    this.elements.questionImage.src = '';
                    this.elements.questionImage.dataset.fullSrc = '';
                }
            }

            // Progress bar
            if (this.elements.progressBar) {
                this.elements.progressBar.style.width = `${(this.state.currentQuestionIndex / this.state.questions.length) * 100}%`;
            }

            // Feedback Message reset
            if (this.elements.feedbackMessage) {
                this.elements.feedbackMessage.classList.add('hidden');
                this.elements.feedbackMessage.className = 'feedback-message hidden';
                this.elements.feedbackMessage.innerHTML = '';
            }

            // Navigation buttons
            if (this.elements.prevBtn) this.elements.prevBtn.disabled = this.state.currentQuestionIndex === 0;
            const isLast = this.state.currentQuestionIndex === this.state.questions.length - 1;
            if (this.elements.nextBtn) this.elements.nextBtn.classList.remove('hidden');
            if (this.elements.submitBtn) {
                this.elements.submitBtn.classList.toggle('hidden', !isLast);
                if (this.state.isReviewMode) {
                    this.elements.submitBtn.textContent = 'חזרה לתוצאות';
                    this.elements.submitBtn.classList.remove('hidden');
                } else {
                    this.elements.submitBtn.textContent = 'הגש מבחן';
                }
            }

            // Options
            if (this.elements.optionsContainer) {
                this.elements.optionsContainer.innerHTML = '';
                q.options.forEach((option, posIndex) => {
                    const btn = document.createElement('button');
                    btn.type = 'button';
                    btn.className = 'option';
                    btn.textContent = option.text;
                    btn.setAttribute('data-key', posIndex + 1);

                    if (answered) {
                        if (answered.selectedOptionId === option.id) btn.classList.add('selected');
                        if (this.state.isImmediateFeedback) {
                            btn.classList.add('disabled');
                            if (option.id === q.correctIndex) btn.classList.add('correct');
                            else if (answered.selectedOptionId === option.id) btn.classList.add('incorrect');
                        }
                    }

                    btn.setAttribute('aria-label', `תשובה ${posIndex + 1}: ${option.text}`);
                    btn.addEventListener('click', () => this.handleOptionSelect(option.id, btn, q.correctIndex));
                    this.elements.optionsContainer.appendChild(btn);
                });
            }

            if (answered && this.state.isImmediateFeedback) {
                this.showFeedbackMessage(answered.isCorrect);
            }

            this.renderJumpBar();
        }

        handleOptionSelect(selectedId, btnElement, correctId) {
            const answered = this.state.userAnswers[this.state.currentQuestionIndex];
            if (this.state.isImmediateFeedback && answered) return;

            const isCorrect = this.state.recordAnswer(this.state.currentQuestionIndex, selectedId, correctId);
            QuizPersistence.saveProgress(QuizPersistence.getStorageKey(this.state.questions), this.state);

            if (this.elements.optionsContainer) {
                this.elements.optionsContainer.querySelectorAll('.option').forEach(opt => opt.classList.remove('selected'));
            }
            btnElement?.classList.add('selected');

            if (this.state.isImmediateFeedback) {
                this.renderQuestion();
                if (isCorrect && !this.state.isReviewMode) {
                    const isLast = this.state.currentQuestionIndex === this.state.questions.length - 1;
                    const targetText = isLast ? 'לסיום המבחן' : 'לשאלה הבאה';
                    this.showFeedbackMessage(true, true, targetText);

                    this.timer.startAutoAdvance({
                        durationMs: 1500,
                        onTick: (sec) => {
                            const secElem = this.elements.feedbackMessage?.querySelector('.auto-advance-seconds');
                            if (secElem) secElem.textContent = String(sec > 0 ? sec : 1);
                        },
                        onComplete: () => {
                            if (isLast) {
                                this.elements.submitBtn?.click();
                            } else {
                                this.state.commitCurrentQuestionTime();
                                this.state.currentQuestionIndex++;
                                this.state.currentQuestionStartTimestamp = Date.now();
                                this.renderQuestion();
                            }
                        }
                    });
                }
            } else {
                this.renderJumpBar();
            }
        }

        renderJumpBar() {
            if (!this.elements.jumpBar) return;
            this.elements.jumpBar.innerHTML = '';

            this.state.questions.forEach((q, i) => {
                const btn = document.createElement('button');
                btn.className = 'jump-btn';
                btn.textContent = i + 1;
                btn.setAttribute('aria-label', `שאלה ${i + 1}`);

                const answer = this.state.userAnswers[i];
                if (answer) {
                    if (this.state.isImmediateFeedback) {
                        btn.classList.add(answer.isCorrect ? 'answered-correct' : 'answered-wrong');
                    } else {
                        btn.classList.add('answered-neutral');
                    }
                }
                if (this.state.userFlags[i]) {
                    btn.classList.add('flagged');
                }
                if (i === this.state.currentQuestionIndex) {
                    btn.classList.add('current');
                    btn.setAttribute('aria-current', 'step');
                }

                btn.addEventListener('click', () => {
                    this.state.commitCurrentQuestionTime();
                    this.state.currentQuestionIndex = i;
                    this.state.currentQuestionStartTimestamp = Date.now();
                    this.renderQuestion();
                });
                this.elements.jumpBar.appendChild(btn);
            });
        }

        showFeedbackMessage(isCorrect, autoAdvance = false, targetName = 'לשאלה הבאה') {
            if (!this.elements.feedbackMessage) return;
            this.elements.feedbackMessage.classList.remove('hidden');
            this.elements.feedbackMessage.innerHTML = '';

            if (isCorrect) {
                this.elements.feedbackMessage.className = 'feedback-message success';
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

                    this.elements.feedbackMessage.appendChild(titleSpan);
                    this.elements.feedbackMessage.appendChild(indicatorSpan);
                    this.elements.feedbackMessage.appendChild(barTrack);
                } else {
                    this.elements.feedbackMessage.textContent = 'תשובה נכונה! כל הכבוד.';
                }
            } else {
                this.elements.feedbackMessage.className = 'feedback-message error';
                this.elements.feedbackMessage.textContent = 'תשובה שגויה.';
            }
        }

        renderResults() {
            const correctCount = this.state.userAnswers.filter(a => a && a.isCorrect).length;
            const total = this.state.questions.length;
            const percentage = total > 0 ? Math.round((correctCount / total) * 100) : 0;

            const wrongOrUnansweredCount = total - correctCount;
            if (this.elements.retryIncorrectBtn && this.elements.incorrectCountBadge) {
                if (wrongOrUnansweredCount > 0) {
                    this.elements.retryIncorrectBtn.classList.remove('hidden');
                    this.elements.incorrectCountBadge.textContent = wrongOrUnansweredCount;
                } else {
                    this.elements.retryIncorrectBtn.classList.add('hidden');
                }
            }

            const wrongCount = this.state.userAnswers.filter(a => a && !a.isCorrect).length;
            const unansweredCount = this.state.userAnswers.filter(a => !a).length;
            const flaggedCount = this.state.userFlags.filter(Boolean).length;

            if (this.elements.cntMixWrong) this.elements.cntMixWrong.textContent = wrongCount;
            if (this.elements.cntMixUnanswered) this.elements.cntMixUnanswered.textContent = unansweredCount;
            if (this.elements.cntMixFlagged) this.elements.cntMixFlagged.textContent = flaggedCount;

            if (this.elements.retryFlaggedBtn) {
                if (flaggedCount > 0) {
                    this.elements.retryFlaggedBtn.classList.remove('hidden');
                    if (this.elements.flaggedCountBadgeAction) this.elements.flaggedCountBadgeAction.textContent = flaggedCount;
                } else {
                    this.elements.retryFlaggedBtn.classList.add('hidden');
                }
            }
            if (this.elements.flaggedCountBadgeFilter) this.elements.flaggedCountBadgeFilter.textContent = flaggedCount;

            this.updateCustomPracticeSelection();

            if (this.elements.scoreText) {
                this.elements.scoreText.textContent = `ענית נכונה על ${correctCount} מתוך ${total} שאלות.`;
            }

            // Results Timing Analytics
            if (this.elements.timingAnalyticsCard) {
                if (this.state.isTimerEnabled || this.state.isQuestionTimerEnabled) {
                    const stats = window.QuizCore ? window.QuizCore.calculateTimingStats(this.state.questionTimes) : null;
                    if (stats) {
                        const totalSec = this.state.isTimerEnabled ? this.state.totalElapsedSeconds : stats.totalSeconds;
                        if (this.elements.totalTimeStat) {
                            this.elements.totalTimeStat.textContent = window.QuizCore ? window.QuizCore.formatDuration(totalSec) : `${totalSec}s`;
                        }
                        if (this.elements.meanTimeStat) {
                            this.elements.meanTimeStat.textContent = stats.formattedMean;
                        }
                        if (this.elements.timedQuestionsStat) {
                            this.elements.timedQuestionsStat.textContent = String(stats.activeCount);
                        }
                        this.elements.timingAnalyticsCard.classList.remove('hidden');
                    }
                } else {
                    this.elements.timingAnalyticsCard.classList.add('hidden');
                }
            }

            // Score Circle Animation
            if (this.elements.scoreCircle && this.elements.finalScore) {
                this.elements.scoreCircle.style.background = 'conic-gradient(var(--primary-color) 0%, var(--option-bg) 0%)';
                this.elements.finalScore.textContent = '0%';

                let startTs = null;
                const duration = 900;
                const animateScore = (ts) => {
                    if (!startTs) startTs = ts;
                    const elapsed = ts - startTs;
                    const progress = Math.min(elapsed / duration, 1);
                    const eased = 1 - Math.pow(1 - progress, 3);
                    const current = Math.round(eased * percentage);
                    this.elements.finalScore.textContent = `${current}%`;
                    this.elements.scoreCircle.style.background = `conic-gradient(var(--primary-color) ${current}%, var(--option-bg) 0%)`;
                    if (progress < 1) requestAnimationFrame(animateScore);
                };
                requestAnimationFrame(animateScore);
            }

            this.renderReviewList();
        }

        renderReviewList() {
            if (!this.elements.reviewContainer) return;
            this.elements.reviewContainer.innerHTML = '';

            this.state.questions.forEach((q, i) => {
                const answer = this.state.userAnswers[i];
                const isCorrect = answer && answer.isCorrect;
                const isUnanswered = !answer;

                if (this.state.reviewFilter === 'wrong'      && (isCorrect || isUnanswered)) return;
                if (this.state.reviewFilter === 'unanswered' && !isUnanswered)                return;
                if (this.state.reviewFilter === 'flagged'    && !this.state.userFlags[i])     return;

                const div = document.createElement('div');
                div.className = 'review-item';

                const isManuallySelected = this.state.manualSelectedIndices.has(i);
                const timeSpent = this.state.questionTimes[i] || 0;
                const timeBadgeHtml = (this.state.isQuestionTimerEnabled && timeSpent > 0)
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
                    html += '<div class="review-option incorrect">לא נענה</div>';
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
                            this.state.manualSelectedIndices.add(idx);
                        } else {
                            this.state.manualSelectedIndices.delete(idx);
                        }
                        this.updateCustomPracticeSelection();
                    });
                }

                div.addEventListener('click', () => {
                    this.state.isReviewMode = true;
                    this.state.currentQuestionIndex = i;
                    this.switchScreen(this.elements.resultsScreen, this.elements.quizScreen);
                    this.renderQuestion();
                });
                this.elements.reviewContainer.appendChild(div);
            });

            if (!this.elements.reviewContainer.hasChildNodes()) {
                this.elements.reviewContainer.innerHTML =
                    '<p style="text-align:center;color:var(--text-secondary);padding:2rem;">אין שאלות להצגה בסינון זה.</p>';
            }
        }

        updateCustomPracticeSelection() {
            const count = this.state.getCustomPracticeIndices(
                !!this.elements.chkMixWrong?.checked,
                !!this.elements.chkMixUnanswered?.checked,
                !!this.elements.chkMixFlagged?.checked
            ).length;
            if (this.elements.customSelectedCount) this.elements.customSelectedCount.textContent = count;
            if (this.elements.startCustomPracticeBtn) this.elements.startCustomPracticeBtn.disabled = count === 0;
        }

        bindEvents() {
            // Start / Resume / Restart
            this.elements.startBtn?.addEventListener('click', () => this.startSession('new'));
            this.elements.resumeBtn?.addEventListener('click', () => this.startSession('resume'));
            this.elements.restartBtn?.addEventListener('click', () => this.startSession('restart'));
            this.elements.retryIncorrectBtn?.addEventListener('click', () => this.startSession('retry-incorrect'));
            this.elements.retryFlaggedBtn?.addEventListener('click', () => this.startSession('retry-flagged'));
            this.elements.startCustomPracticeBtn?.addEventListener('click', () => this.startSession('custom-practice'));

            // Review Back
            this.elements.reviewBackBtn?.addEventListener('click', () => {
                this.state.isReviewMode = true;
                this.state.currentQuestionIndex = this.state.questions.length - 1;
                this.switchScreen(this.elements.resultsScreen, this.elements.quizScreen);
                this.renderQuestion();
            });

            // Navigation
            this.elements.nextBtn?.addEventListener('click', () => {
                if (this.state.currentQuestionIndex < this.state.questions.length - 1) {
                    this.state.commitCurrentQuestionTime();
                    this.state.currentQuestionIndex++;
                    this.state.currentQuestionStartTimestamp = Date.now();
                    this.renderQuestion();
                }
            });

            this.elements.prevBtn?.addEventListener('click', () => {
                if (this.state.currentQuestionIndex > 0) {
                    this.state.commitCurrentQuestionTime();
                    this.state.currentQuestionIndex--;
                    this.state.currentQuestionStartTimestamp = Date.now();
                    this.renderQuestion();
                }
            });

            this.elements.submitBtn?.addEventListener('click', () => {
                if (this.state.isReviewMode) {
                    this.state.isReviewMode = false;
                    this.switchScreen(this.elements.quizScreen, this.elements.resultsScreen);
                    this.renderResults();
                    return;
                }
                this.timer.stopExamTimer(this.state);
                QuizPersistence.clearProgress(QuizPersistence.getStorageKey(this.state.questions));
                this.switchScreen(this.elements.quizScreen, this.elements.resultsScreen);
                this.renderResults();
            });

            // Flag Button
            this.elements.flagBtn?.addEventListener('click', () => {
                this.state.toggleFlag(this.state.currentQuestionIndex);
                QuizPersistence.saveProgress(QuizPersistence.getStorageKey(this.state.questions), this.state);
                this.renderQuestion();
            });

            // Review Filter Buttons
            this.elements.filterBtns.forEach(btn => {
                btn.addEventListener('click', () => {
                    this.elements.filterBtns.forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    this.state.reviewFilter = btn.dataset.filter;
                    this.renderReviewList();
                });
            });

            // Custom practice checkbox listeners
            [this.elements.chkMixWrong, this.elements.chkMixUnanswered, this.elements.chkMixFlagged].forEach(chk => {
                chk?.addEventListener('change', () => this.updateCustomPracticeSelection());
            });

            // Image Zoom
            this.elements.questionImage?.addEventListener('click', () => {
                if (this.elements.questionImage.classList.contains('hidden')) return;
                if (this.elements.zoomImg && this.elements.zoomOverlay) {
                    this.elements.zoomImg.src = this.elements.questionImage.src;
                    this.elements.zoomOverlay.classList.remove('hidden');
                    document.body.style.overflow = 'hidden';
                }
            });

            const closeZoom = () => {
                if (this.elements.zoomOverlay) {
                    this.elements.zoomOverlay.classList.add('hidden');
                    document.body.style.overflow = '';
                }
            };
            this.elements.zoomOverlay?.addEventListener('click', closeZoom);

            // Cropper
            this.elements.openCropperBtn?.addEventListener('click', () => {
                const fullSrc = this.elements.questionImage?.dataset.fullSrc;
                if (fullSrc) {
                    this.cropper.open({ fullSrc, elements: this.elements });
                }
            });

            this.elements.closeCropperBtn?.addEventListener('click', () => {
                this.cropper.close(this.elements);
            });

            this.elements.confirmCropBtn?.addEventListener('click', () => {
                const croppedData = this.cropper.getCroppedDataUrl();
                const fullSrc = this.elements.questionImage?.dataset.fullSrc;
                if (croppedData && fullSrc) {
                    this.state.croppedImages[fullSrc] = croppedData;
                    if (this.elements.questionImage) {
                        this.elements.questionImage.src = croppedData;
                    }
                }
                this.cropper.close(this.elements);
            });

            // Keyboard Navigation
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape') {
                    if (this.elements.zoomOverlay && !this.elements.zoomOverlay.classList.contains('hidden')) {
                        closeZoom();
                        return;
                    }
                }

                const onQuiz = this.elements.quizScreen && this.elements.quizScreen.classList.contains('active');
                const onResults = this.elements.resultsScreen && this.elements.resultsScreen.classList.contains('active');
                if (!onQuiz && !onResults) return;

                if (onResults) {
                    if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
                        this.state.isReviewMode = true;
                        this.state.currentQuestionIndex = this.state.questions.length - 1;
                        this.switchScreen(this.elements.resultsScreen, this.elements.quizScreen);
                        this.renderQuestion();
                    }
                    return;
                }

                const keyNum = parseInt(e.key, 10);
                if (keyNum >= 1 && keyNum <= 9) {
                    const opts = this.elements.optionsContainer?.querySelectorAll('.option');
                    if (opts && opts[keyNum - 1] && !opts[keyNum - 1].classList.contains('disabled')) {
                        opts[keyNum - 1].click();
                    }
                    return;
                }

                if (e.key === 'ArrowRight') {
                    if (this.elements.prevBtn && !this.elements.prevBtn.disabled) this.elements.prevBtn.click();
                }
                if (e.key === 'ArrowLeft') {
                    if (this.elements.submitBtn && !this.elements.submitBtn.classList.contains('hidden')) {
                        this.elements.submitBtn.click();
                    } else if (this.elements.nextBtn && !this.elements.nextBtn.classList.contains('hidden')) {
                        this.elements.nextBtn.click();
                    }
                }
            });
        }

        loadQuestions() {
            const inlineData = document.getElementById('quiz-data')?.textContent.trim();
            const questionsSource = inlineData
                ? Promise.resolve(JSON.parse(inlineData))
                : fetch('questions.json').then(r => {
                    if (!r.ok) throw new Error(`HTTP ${r.status}`);
                    return r.json();
                });

            questionsSource
                .then(data => {
                    if (!Array.isArray(data) || data.length === 0) {
                        throw new Error('questions.json is empty or malformed');
                    }
                    this.state.questions = data.map(q => {
                        const options = q.options.map((text, id) => ({ id, text }));
                        if (q.shuffleOptions) {
                            for (let i = options.length - 1; i > 0; i--) {
                                const j = Math.floor(Math.random() * (i + 1));
                                [options[i], options[j]] = [options[j], options[i]];
                            }
                        }
                        return { ...q, options };
                    });
                    this.state.allMasterQuestions = [...this.state.questions];

                    const welcomeDesc = document.querySelector('.welcome-card > p');
                    if (welcomeDesc) {
                        const shuffled = this.state.questions.filter(q => q.shuffleOptions).length;
                        welcomeDesc.textContent = shuffled
                            ? `נטענו ${this.state.questions.length} שאלות בהצלחה. סדר התשובות מעורבב אוטומטית במבחני 000 ללא קובץ תשובות.`
                            : `נטענו ${this.state.questions.length} שאלות בהצלחה.`;
                    }

                    const saved = QuizPersistence.loadProgress(QuizPersistence.getStorageKey(this.state.questions));
                    if (saved && saved.answers && saved.answers.length === this.state.questions.length) {
                        this.elements.resumeNotice?.classList.remove('hidden');
                    }
                })
                .catch(err => {
                    console.error('Error loading questions.json:', err);
                    const welcomeCard = document.querySelector('.welcome-card');
                    if (welcomeCard) {
                        const errDiv = document.createElement('div');
                        errDiv.style.cssText = 'margin-top:1rem;padding:1rem;border-radius:.75rem;background:var(--error-bg);color:var(--error-color);border:1px solid var(--error-color);font-size:.9rem;';
                        errDiv.innerHTML = `⚠️ לא נמצא קובץ שאלות. <a href="${this.onlineBuilderUrl}" id="builder-nav-error-link" style="color:inherit;text-decoration:underline;">יוצר מבחן אונליין</a> כדי לטעון שאלות, או השתמש בכפתור "פתור מבחן כעת".`;
                        welcomeCard.appendChild(errDiv);
                    }
                    if (this.elements.startBtn) {
                        this.elements.startBtn.disabled = true;
                        this.elements.startBtn.style.opacity = '0.4';
                    }
                });
        }
    }

    // ── Auto-bootstrap on DOMContentLoaded in browser ──────────────────────────
    if (typeof document !== 'undefined') {
        const bootstrap = () => {
            const app = new QuizUIController();
            app.init();
            if (typeof window !== 'undefined') {
                window._quizAppInstance = app;
            }
        };

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', bootstrap);
        } else {
            bootstrap();
        }
    }

    return {
        escapeHtml,
        QuizSessionState,
        QuizTimerEngine,
        QuizPersistence,
        CropperController,
        QuizUIController
    };
}));
