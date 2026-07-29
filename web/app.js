document.addEventListener('DOMContentLoaded', () => {

    // ── State ────────────────────────────────────────────────────────────────
    let questions = [];
    let currentQuestionIndex = 0;
    let userAnswers = []; // { selectedOptionId: number, isCorrect: boolean } | null
    let isImmediateFeedback = false;
    let reviewFilter = 'all'; // 'all' | 'wrong' | 'unanswered'
    let theme = localStorage.getItem('theme') || 'light';

    // ── DOM Elements ─────────────────────────────────────────────────────────
    const setupScreen   = document.getElementById('setup-screen');
    const quizScreen    = document.getElementById('quiz-screen');
    const resultsScreen = document.getElementById('results-screen');
    const menuScreen    = document.getElementById('menu-screen');

    const startBtn      = document.getElementById('start-btn');
    const resumeBtn     = document.getElementById('resume-btn');
    const resumeNotice  = document.getElementById('resume-notice');
    const prevBtn       = document.getElementById('prev-btn');
    const nextBtn       = document.getElementById('next-btn');
    const submitBtn     = document.getElementById('submit-btn');
    const restartBtn    = document.getElementById('restart-btn');

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
    const themeIcon      = document.getElementById('theme-icon');
    const filterBtns     = document.querySelectorAll('.filter-btn');

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
    feedbackToggle.addEventListener('change', e => { isImmediateFeedback = e.target.checked; });

    // ── localStorage Persistence ──────────────────────────────────────────────
    function saveProgress() {
        localStorage.setItem(STORAGE_KEY, JSON.stringify({
            answers: userAnswers,
            index: currentQuestionIndex
        }));
    }

    function loadProgress() {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            return raw ? JSON.parse(raw) : null;
        } catch(e) { return null; }
    }

    function clearProgress() {
        localStorage.removeItem(STORAGE_KEY);
    }

    // ── Study Deck Storage Manager ────────────────────────────────────────────
    const STUDY_DECK_KEY = 'study_deck_v1';

    function getStudyDeck() {
        try {
            const raw = localStorage.getItem(STUDY_DECK_KEY);
            return raw ? JSON.parse(raw) : [];
        } catch(e) {
            return [];
        }
    }

    function saveStudyDeck(deck) {
        localStorage.setItem(STUDY_DECK_KEY, JSON.stringify(deck));
        updateStudyBadge();
    }

    function addMissedQuestionsToDeck(testId, questionsList, answers) {
        let deck = getStudyDeck();
        const currentTestTitle = testId || 'מבחן';

        questionsList.forEach((q, i) => {
            const ans = answers[i];
            const isCorrect = ans && ans.isCorrect;
            if (!isCorrect) {
                const cardId = `${currentTestTitle}::${q.id || i}::${(q.question || '').substring(0, 30)}`;
                const existingIndex = deck.findIndex(item => item.id === cardId);
                const correctOption = q.options ? q.options.find(o => o.id === q.correctIndex) : null;

                const cardData = {
                    id: cardId,
                    testId: currentTestTitle,
                    questionText: q.question,
                    options: q.options || [],
                    correctIndex: q.correctIndex,
                    correctText: correctOption ? correctOption.text : '',
                    explanation: q.explanation || 'אין הסבר נוסף לשאלה זו.',
                    image: q.image || '',
                    pageImage: q.pageImage || '',
                    dateAdded: Date.now(),
                    mastered: false
                };

                if (existingIndex >= 0) {
                    deck[existingIndex] = { ...deck[existingIndex], ...cardData, mastered: false };
                } else {
                    deck.push(cardData);
                }
            }
        });

        saveStudyDeck(deck);
    }

    function toggleCardMasteredStatus(cardId) {
        let deck = getStudyDeck();
        const card = deck.find(c => c.id === cardId);
        if (card) {
            card.mastered = !card.mastered;
            saveStudyDeck(deck);
        }
        return card ? card.mastered : false;
    }

    function updateStudyBadge() {
        const badge = document.getElementById('study-due-badge');
        if (!badge) return;
        const deck = getStudyDeck();
        const dueCount = deck.filter(c => !c.mastered).length;
        badge.textContent = dueCount;
    }

    // ── Parse URL Parameter ───────────────────────────────────────────────────
    const urlParams = new URLSearchParams(window.location.search);
    const testPath = urlParams.get('test');

    // ── Scoped Storage Key (per test) ─────────────────────────────────────────
    const STORAGE_KEY = testPath ? ('quiz_answers_v1_' + testPath) : 'quiz_answers_v1';

    const errorScreen      = document.getElementById('error-screen');
    const errorMessageText = document.getElementById('error-message-text');
    const backToMenuBtn    = document.getElementById('back-to-menu-btn');
    const testListContainer = document.getElementById('test-list');
    const loadCustomTestBtn = document.getElementById('load-custom-test-btn');

    // ── Back to menu button ──────────────────────────────────────────────────
    if (backToMenuBtn) {
        backToMenuBtn.addEventListener('click', () => {
            clearProgress();
            switchScreen(errorScreen, menuScreen);
            window.location.search = '';
        });
    }

    // ── Custom test path button ──────────────────────────────────────────────
    if (loadCustomTestBtn) {
        loadCustomTestBtn.addEventListener('click', () => {
            const customPath = document.getElementById('custom-test-path').value.trim();
            if (customPath) {
                window.location.search = '?test=' + encodeURIComponent(customPath);
            }
        });
    }

    // ── Error Screen ─────────────────────────────────────────────────────────
    function showError(message) {
        if (errorMessageText) {
            errorMessageText.textContent = message;
        }
        // Hide all other screens
        [setupScreen, quizScreen, resultsScreen, menuScreen].forEach(s => {
            if (s) s.classList.remove('active');
        });
        if (errorScreen) errorScreen.classList.add('active');
    }

    if (!testPath && !window.__EMBEDDED_QUESTIONS) {
        // No test selected and no embedded questions: show exam selection menu
        setupScreen.classList.remove('active');
        if(menuScreen) menuScreen.classList.add('active');
        // Load dynamic test list
        loadTestList();
        return; // Stop execution, don't fetch questions
    }

    // ── Fetch Questions ───────────────────────────────────────────────────────
    function initQuestions(data) {
        questions = data.map(q => {
            const options = q.options.map((text, id) => ({ id, text }));
            // Fisher-Yates shuffle
            for (let i = options.length - 1; i > 0; i--) {
                const j = Math.floor(Math.random() * (i + 1));
                [options[i], options[j]] = [options[j], options[i]];
            }

            // Adjust relative image path if present (skip for data URIs)
            let img = q.image;
            if (img && !img.startsWith('http') && !img.startsWith('data:') && testPath) {
                img = `../${testPath}/${img}`;
            }
            let pageImg = q.pageImage;
            if (pageImg && !pageImg.startsWith('http') && !pageImg.startsWith('data:') && testPath) {
                pageImg = `../${testPath}/${pageImg}`;
            }

            return { ...q, options, image: img, pageImage: pageImg };
        });

        // Check for saved progress
        const saved = loadProgress();
        if (saved && saved.answers && saved.answers.length === questions.length) {
            resumeNotice.classList.remove('hidden');
        }
    }

    // Support embedded questions (single-file HTML mode)
    if (window.__EMBEDDED_QUESTIONS) {
        initQuestions(window.__EMBEDDED_QUESTIONS);
    } else {
        const jsonUrl = `../${testPath}/questions.json?v=` + new Date().getTime();
        fetch(jsonUrl)
            .then(r => {
                if (!r.ok) throw new Error("Could not load " + jsonUrl);
                return r.json();
            })
            .then(data => initQuestions(data))
            .catch(err => {
                console.error('Error loading questions:', err);
                showError('שגיאה בטעינת המבחן. אנא ודא שהנתיב נכון וקיים קובץ questions.json בתיקיית המבחן.');
            });
    }

    // ── Dynamic Test List ────────────────────────────────────────────────────
    function loadTestList() {
        if (!testListContainer) return;

        // Load manifests from both 'tests' and 'test' folders, merge results
        const fetches = [
            fetch('../tests/manifest.json').then(r => r.ok ? r.json() : []).catch(() => []),
            fetch('../test/manifest.json').then(r => r.ok ? r.json() : []).catch(() => [])
        ];

        Promise.all(fetches)
            .then(([testsList, testList]) => {
                const allTests = [...testsList, ...testList];
                if (!allTests.length) throw new Error('No manifest found');

                testListContainer.innerHTML = '';
                allTests.forEach(test => {
                    const link = document.createElement('a');
                    link.href = '?test=' + encodeURIComponent(test.path);
                    link.className = 'secondary-btn';
                    link.style.cssText = 'display: block; margin-bottom: 10px; text-decoration: none;';
                    link.textContent = test.name;
                    testListContainer.appendChild(link);
                });
            })
            .catch(() => {
                testListContainer.innerHTML = '<p style="color: var(--text-secondary);">אין מבחנים זמינים כרגע. ניתן להזין נתיב ידנית למטה.</p>';
            });
    }

    // ── Also load test list on menu screen when not using ?test= parameter ──
    // (loadTestList is called above when !testPath; also expose for manual use)

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

        // Study Mode Shortcuts
        if (studyScreen && studyScreen.classList.contains('active')) {
            if (e.key === ' ' || e.key === 'Enter') {
                e.preventDefault();
                if (flashcard) flashcard.classList.toggle('flipped');
                return;
            }
            if (['1', '2', '3', '4'].includes(e.key) && flashcardOptions) {
                const idx = parseInt(e.key) - 1;
                const opts = flashcardOptions.querySelectorAll('.option');
                if (opts[idx]) opts[idx].click();
                return;
            }
            if (e.key === 'm' || e.key === 'M') {
                if (flashcardMasteredBtn) flashcardMasteredBtn.click();
                return;
            }
            if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
                if (flashcardNextBtn) flashcardNextBtn.click();
                return;
            }
        }

        // Only act when quiz screen is active
        if (!quizScreen.classList.contains('active')) return;

        // Option selection: 1–9
        if (['1', '2', '3', '4', '5', '6', '7', '8', '9'].includes(e.key)) {
            const idx = parseInt(e.key) - 1;
            const opts = optionsContainer.querySelectorAll('.option');
            if (opts[idx] && !opts[idx].classList.contains('disabled')) {
                opts[idx].click();
            }
            return;
        }

        // Navigation (RTL: ArrowRight = go back/previous, ArrowLeft = go forward/next)
        if (e.key === 'ArrowRight') {
            if (!prevBtn.disabled) prevBtn.click();
        }
        if (e.key === 'ArrowLeft') {
            if (!nextBtn.classList.contains('hidden')) nextBtn.click();
            else if (!submitBtn.classList.contains('hidden')) submitBtn.click();
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
        currentQuestionIndex = 0;
        switchScreen(setupScreen, quizScreen);
        renderQuestion();
    });

    resumeBtn.addEventListener('click', () => {
        const saved = loadProgress();
        userAnswers = saved.answers;
        currentQuestionIndex = saved.index;
        switchScreen(setupScreen, quizScreen);
        renderQuestion();
    });

    restartBtn.addEventListener('click', () => {
        clearProgress();
        reviewFilter = 'all';
        filterBtns.forEach(b => {
            b.classList.toggle('active', b.dataset.filter === 'all');
        });
        switchScreen(resultsScreen, setupScreen);
    });

    // ── Navigation Buttons ────────────────────────────────────────────────────
    nextBtn.addEventListener('click', () => {
        if (currentQuestionIndex < questions.length - 1) {
            currentQuestionIndex++;
            renderQuestion();
        }
    });

    prevBtn.addEventListener('click', () => {
        if (currentQuestionIndex > 0) {
            currentQuestionIndex--;
            renderQuestion();
        }
    });

    submitBtn.addEventListener('click', () => {
        clearProgress();
        addMissedQuestionsToDeck(testPath || 'מבחן', questions, userAnswers);
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
            if (i === currentQuestionIndex) {
                btn.classList.add('current');
            }

            btn.addEventListener('click', () => {
                currentQuestionIndex = i;
                renderQuestion();
            });
            jumpBar.appendChild(btn);
        });
    }

    // ── Render Question ───────────────────────────────────────────────────────
    function renderQuestion() {
        const q = questions[currentQuestionIndex];
        const answered = userAnswers[currentQuestionIndex];

        questionCounter.textContent = `שאלה ${currentQuestionIndex + 1} מתוך ${questions.length}`;
        questionText.innerHTML = q.question;

        // Image & Page Image Cropping Support
        const imageSrc = q.image || q.pageImage;
        const fullPageSrc = q.pageImage || q.image;

        if (imageSrc) {
            if (croppedImages[fullPageSrc]) {
                questionImage.src = croppedImages[fullPageSrc];
            } else if (croppedImages[imageSrc]) {
                questionImage.src = croppedImages[imageSrc];
            } else {
                questionImage.src = imageSrc;
            }
            questionImage.classList.remove('hidden');
            // Cropper: use full page when available, fall back to main image
            questionImage.dataset.fullSrc = fullPageSrc;
            openCropperBtn.classList.remove('hidden');
        } else {
            questionImage.classList.add('hidden');
            questionImage.src = '';
            questionImage.dataset.fullSrc = '';
            openCropperBtn.classList.add('hidden');
        }

        // Progress bar
        progressBar.style.width = `${(currentQuestionIndex / questions.length) * 100}%`;

        // Feedback
        feedbackMessage.classList.add('hidden');
        feedbackMessage.className = 'feedback-message hidden';

        // Navigation buttons
        prevBtn.disabled = currentQuestionIndex === 0;
        const isLast = currentQuestionIndex === questions.length - 1;
        nextBtn.classList.toggle('hidden', isLast);
        submitBtn.classList.toggle('hidden', !isLast);

        // Options
        optionsContainer.innerHTML = '';
        q.options.forEach((option, posIndex) => {
            const btn = document.createElement('div');
            btn.className = 'option';
            btn.setAttribute('role', 'option');
            btn.textContent = option.text;
            btn.setAttribute('data-key', posIndex + 1); // keyboard shortcut hint

            // Restore previous selection
            if (answered) {
                if (answered.selectedOptionId === option.id) {
                    btn.classList.add('selected');
                    btn.setAttribute('aria-selected', 'true');
                } else {
                    btn.setAttribute('aria-selected', 'false');
                }

                if (isImmediateFeedback) {
                    btn.classList.add('disabled');
                    if (option.id === q.correctIndex) btn.classList.add('correct');
                    else if (answered.selectedOptionId === option.id) btn.classList.add('incorrect');
                }
            } else {
                btn.setAttribute('aria-selected', 'false');
            }

            btn.addEventListener('click', () => handleOptionSelect(option.id, btn, q.correctIndex));
            optionsContainer.appendChild(btn);
        });

        // Show feedback if already answered
        if (answered && isImmediateFeedback) showFeedbackMessage(answered.isCorrect);

        // Update jump bar
        renderJumpBar();
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
        } else {
            // Just update jump bar dot
            renderJumpBar();
        }
    }

    // ── Feedback Message ──────────────────────────────────────────────────────
    function showFeedbackMessage(isCorrect) {
        feedbackMessage.classList.remove('hidden');
        if (isCorrect) {
            feedbackMessage.textContent = 'תשובה נכונה! כל הכבוד.';
            feedbackMessage.classList.add('success');
        } else {
            feedbackMessage.textContent = 'תשובה שגויה.';
            feedbackMessage.classList.add('error');
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

        document.getElementById('final-score').textContent = `${percentage}%`;
        document.getElementById('score-text').textContent =
            `ענית נכונה על ${correctCount} מתוך ${total} שאלות.`;

        const circle = document.querySelector('.score-circle');
        circle.style.background =
            `conic-gradient(var(--primary-color) ${percentage}%, var(--option-bg) 0%)`;

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

            const div = document.createElement('div');
            div.className = 'review-item';

            let html = `<div class="review-question">${i + 1}. ${q.question}</div>`;

            q.options.forEach(opt => {
                let cls = 'review-option';
                if (opt.id === q.correctIndex)                              cls += ' correct';
                else if (answer && answer.selectedOptionId === opt.id)      cls += ' incorrect';
                html += `<div class="${cls}">${opt.text}</div>`;
            });

            if (isUnanswered) {
                html += `<div class="review-option incorrect">לא נענה</div>`;
            }

            div.innerHTML = html;
            reviewContainer.appendChild(div);
        });

        // Empty state message
        if (!reviewContainer.hasChildNodes()) {
            reviewContainer.innerHTML =
                `<p style="text-align:center;color:var(--text-secondary);padding:2rem;">אין שאלות להצגה בסינון זה.</p>`;
        }
    }

    // ── Cropper Logic ─────────────────────────────────────────────────────────
    openCropperBtn.addEventListener('click', () => {
        const fullSrc = questionImage.dataset.fullSrc;
        if (!fullSrc) return;

        cropperImage.src = fullSrc;
        cropperModal.classList.remove('hidden');
        document.body.style.overflow = 'hidden';

        // Initialize Cropper when image is loaded
        cropperImage.onload = () => {
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

    // ── Study Mode UI Controller ──────────────────────────────────────────────
    const studyScreen           = document.getElementById('study-screen');
    const studyModeNavBtn       = document.getElementById('study-mode-nav-btn');
    const practiceMissedBtn     = document.getElementById('practice-missed-btn');
    const exitStudyBtn          = document.getElementById('exit-study-btn');
    const studyFilterToggle     = document.getElementById('study-filter-toggle');
    const studyEmptyState       = document.getElementById('study-empty-state');
    const studyEmptyBackBtn     = document.getElementById('study-empty-back-btn');
    const flashcardContainer    = document.getElementById('flashcard-container');
    const flashcard             = document.getElementById('flashcard');
    const flashcardQuestionText = document.getElementById('flashcard-question-text');
    const flashcardQuestionImg  = document.getElementById('flashcard-question-image');
    const flashcardOptions      = document.getElementById('flashcard-options-container');
    const flashcardRevealBtn    = document.getElementById('flashcard-reveal-btn');
    const flashcardCorrectAns   = document.getElementById('flashcard-correct-answer');
    const flashcardExpText      = document.getElementById('flashcard-explanation-text');
    const flashcardMasteredBtn  = document.getElementById('flashcard-mastered-btn');
    const masteredBtnText       = document.getElementById('mastered-btn-text');
    const flashcardNextBtn      = document.getElementById('flashcard-next-btn');
    const flashcardTestName     = document.getElementById('flashcard-test-name');
    const studyDeckStats        = document.getElementById('study-deck-stats');

    let activeStudyCards = [];
    let currentStudyIndex = 0;
    let filterCurrentTestOnly = false;

    function openStudyScreen() {
        const deck = getStudyDeck();
        const currentTestId = testPath || 'מבחן';

        if (filterCurrentTestOnly) {
            activeStudyCards = deck.filter(c => !c.mastered && c.testId === currentTestId);
        } else {
            activeStudyCards = deck.filter(c => !c.mastered);
        }

        // Hide other screens
        [setupScreen, quizScreen, resultsScreen, menuScreen, errorScreen].forEach(s => {
            if (s) s.classList.remove('active');
        });
        if (studyScreen) studyScreen.classList.add('active');

        if (activeStudyCards.length === 0) {
            if (flashcardContainer) flashcardContainer.classList.add('hidden');
            if (studyEmptyState) studyEmptyState.classList.remove('hidden');
            if (studyDeckStats) studyDeckStats.textContent = '0 שאלות לתרגול';
        } else {
            if (flashcardContainer) flashcardContainer.classList.remove('hidden');
            if (studyEmptyState) studyEmptyState.classList.add('hidden');
            currentStudyIndex = 0;
            renderFlashcard();
        }
    }

    function renderFlashcard() {
        if (!activeStudyCards.length) return;

        // Reset flip state
        if (flashcard) flashcard.classList.remove('flipped');

        const card = activeStudyCards[currentStudyIndex];
        if (studyDeckStats) studyDeckStats.textContent = `כרטיסייה ${currentStudyIndex + 1} מתוך ${activeStudyCards.length}`;
        if (flashcardTestName) flashcardTestName.textContent = card.testId || 'מבחן';
        if (flashcardQuestionText) flashcardQuestionText.innerHTML = card.questionText;

        // Image
        if (flashcardQuestionImg) {
            if (card.image || card.pageImage) {
                const imgSrc = card.image || card.pageImage;
                flashcardQuestionImg.src = imgSrc;
                flashcardQuestionImg.classList.remove('hidden');
                flashcardQuestionImg.onclick = () => {
                    if (zoomImg && zoomOverlay) {
                        zoomImg.src = imgSrc;
                        zoomOverlay.classList.remove('hidden');
                        document.body.style.overflow = 'hidden';
                    }
                };
            } else {
                flashcardQuestionImg.classList.add('hidden');
                flashcardQuestionImg.src = '';
            }
        }

        // Options
        if (flashcardOptions) {
            flashcardOptions.innerHTML = '';
            (card.options || []).forEach((opt, idx) => {
                const btn = document.createElement('div');
                btn.className = 'option';
                btn.textContent = opt.text;
                btn.setAttribute('data-key', idx + 1);
                btn.addEventListener('click', () => {
                    flashcardOptions.querySelectorAll('.option').forEach(o => o.classList.remove('selected', 'correct', 'incorrect'));
                    if (opt.id === card.correctIndex) {
                        btn.classList.add('correct');
                    } else {
                        btn.classList.add('incorrect');
                    }
                    setTimeout(() => {
                        if (flashcard) flashcard.classList.add('flipped');
                    }, 400);
                });
                flashcardOptions.appendChild(btn);
            });
        }

        // Back Side content
        if (flashcardCorrectAns) flashcardCorrectAns.textContent = card.correctText;
        if (flashcardExpText) flashcardExpText.textContent = card.explanation || 'אין הסבר נוסף לשאלה זו.';
        
        updateMasteredBtnUI(card.mastered);
    }

    function updateMasteredBtnUI(isMastered) {
        if (!flashcardMasteredBtn || !masteredBtnText) return;
        if (isMastered) {
            flashcardMasteredBtn.classList.add('active');
            masteredBtnText.textContent = 'נשלט (M) ✓';
        } else {
            flashcardMasteredBtn.classList.remove('active');
            masteredBtnText.textContent = 'סימון כנשלט (M)';
        }
    }

    if (studyModeNavBtn) {
        studyModeNavBtn.addEventListener('click', openStudyScreen);
    }
    if (practiceMissedBtn) {
        practiceMissedBtn.addEventListener('click', openStudyScreen);
    }
    if (exitStudyBtn) {
        exitStudyBtn.addEventListener('click', () => {
            if (studyScreen) studyScreen.classList.remove('active');
            if (questions.length > 0 && setupScreen) setupScreen.classList.add('active');
            else if (menuScreen) menuScreen.classList.add('active');
        });
    }
    if (studyEmptyBackBtn) {
        studyEmptyBackBtn.addEventListener('click', () => {
            if (studyScreen) studyScreen.classList.remove('active');
            if (menuScreen) menuScreen.classList.add('active');
            else if (setupScreen) setupScreen.classList.add('active');
        });
    }
    if (studyFilterToggle) {
        studyFilterToggle.addEventListener('click', () => {
            filterCurrentTestOnly = !filterCurrentTestOnly;
            studyFilterToggle.textContent = filterCurrentTestOnly ? 'הצג את כל המבחנים' : 'הצג מבחן נוכחי בלבד';
            openStudyScreen();
        });
    }
    if (flashcardRevealBtn) {
        flashcardRevealBtn.addEventListener('click', () => {
            if (flashcard) flashcard.classList.toggle('flipped');
        });
    }
    if (flashcardMasteredBtn) {
        flashcardMasteredBtn.addEventListener('click', () => {
            if (!activeStudyCards.length) return;
            const card = activeStudyCards[currentStudyIndex];
            const isMastered = toggleCardMasteredStatus(card.id);
            card.mastered = isMastered;
            updateMasteredBtnUI(isMastered);
        });
    }
    if (flashcardNextBtn) {
        flashcardNextBtn.addEventListener('click', () => {
            if (!activeStudyCards.length) return;
            currentStudyIndex = (currentStudyIndex + 1) % activeStudyCards.length;
            renderFlashcard();
        });
    }

    // Initialize study badge counter
    updateStudyBadge();

});
