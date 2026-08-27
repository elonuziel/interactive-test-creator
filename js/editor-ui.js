(function (root, factory) {
    if (typeof define === 'function' && define.amd) {
        define([], factory);
    } else if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.EditorUi = factory();
    }
}(typeof self !== 'undefined' ? self : this, function () {
    'use strict';

    let appState = null;
    let appElements = null;
    let callbacks = {};

    function init(state, elements, cb = {}) {
        appState = state;
        appElements = elements;
        callbacks = cb;
    }

    function setTheme(nextTheme, elements) {
        const theme = nextTheme || 'light';
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
        const icon = elements?.themeIcon || document.getElementById('theme-icon');
        if (icon) {
            if (theme === 'dark') {
                icon.innerHTML = '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"></path>';
            } else {
                icon.innerHTML = '<circle cx="12" cy="12" r="4"></circle><path d="M12 2v2"></path><path d="M12 20v2"></path><path d="m4.93 4.93 1.41 1.41"></path><path d="m17.66 17.66 1.41 1.41"></path><path d="M2 12h2"></path><path d="M20 12h2"></path><path d="m6.34 17.66-1.41 1.41"></path><path d="m19.07 4.93-1.41 1.41"></path>';
            }
        }
        return theme;
    }

    function updateVerificationUI(elements) {
        const targetElements = elements || appElements;
        if (!targetElements?.enableLlmVerification) return;
        const isChecked = targetElements.enableLlmVerification.checked;
        if (targetElements.verificationWarningBox) {
            targetElements.verificationWarningBox.classList.toggle('hidden', !isChecked);
        }
        if (targetElements.verificationBadge) {
            if (isChecked) {
                targetElements.verificationBadge.textContent = '🔍 2 קריאות API';
                targetElements.verificationBadge.style.background = 'rgba(217, 119, 6, 0.15)';
                targetElements.verificationBadge.style.color = '#d97706';
                targetElements.verificationBadge.style.borderColor = 'rgba(217, 119, 6, 0.35)';
            } else {
                targetElements.verificationBadge.textContent = '⚡ קריאה 1 (מהיר)';
                targetElements.verificationBadge.style.background = 'rgba(16, 185, 129, 0.12)';
                targetElements.verificationBadge.style.color = '#059669';
                targetElements.verificationBadge.style.borderColor = 'rgba(16, 185, 129, 0.3)';
            }
        }
    }

    function showToast(message, type = 'success', duration = 4000) {
        const container = document.getElementById('toast-container');
        if (!container) return;

        const toast = document.createElement('div');
        toast.className = `toast ${type}`;

        const iconMap = {
            success: '✅',
            error: '⚠️',
            info: '💡'
        };

        const iconSpan = document.createElement('span');
        iconSpan.textContent = iconMap[type] || 'ℹ️';

        const textSpan = document.createElement('span');
        textSpan.textContent = message;

        toast.append(iconSpan, textSpan);
        container.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(10px)';
            toast.style.transition = 'all 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }

    function setStatus(message, isError = false, triggerToast = false, elements = null) {
        const targetElements = elements || appElements;
        if (targetElements?.status) {
            targetElements.status.textContent = message;
            targetElements.status.classList.toggle('muted', !isError);
            targetElements.status.style.color = isError ? 'var(--danger)' : 'var(--text-primary)';
        }
        if (triggerToast || isError) {
            showToast(message, isError ? 'error' : 'success');
        }
    }

    async function showImageZoom(src, pageNum = null, state = null) {
        const targetState = state || appState;
        let overlay = document.getElementById('gen-zoom-overlay');
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.id = 'gen-zoom-overlay';
            overlay.style.cssText = [
                'position:fixed;inset:0;z-index:99999',
                'background:rgba(0,0,0,0.88)',
                'display:flex;flex-direction:column;align-items:center;justify-content:center;gap:12px',
                'cursor:zoom-out;padding:24px;box-sizing:border-box'
            ].join(';');

            const spinner = document.createElement('div');
            spinner.id = 'gen-zoom-spinner';
            spinner.style.cssText = [
                'width:40px;height:40px',
                'border:4px solid rgba(255,255,255,0.2)',
                'border-top-color:#fff',
                'border-radius:50%',
                'animation:gen-spin 0.7s linear infinite',
                'display:none'
            ].join(';');
            if (!document.getElementById('gen-spin-style')) {
                const s = document.createElement('style');
                s.id = 'gen-spin-style';
                s.textContent = '@keyframes gen-spin{to{transform:rotate(360deg)}}';
                document.head.appendChild(s);
            }

            const zoomImg = document.createElement('img');
            zoomImg.id = 'gen-zoom-img';
            zoomImg.style.cssText = [
                'max-width:100%;max-height:88vh',
                'border-radius:10px',
                'box-shadow:0 8px 40px rgba(0,0,0,0.7)',
                'object-fit:contain'
            ].join(';');

            overlay.appendChild(spinner);
            overlay.appendChild(zoomImg);

            overlay.addEventListener('click', (e) => {
                if (e.target === overlay || e.target === zoomImg) {
                    overlay.style.display = 'none';
                    document.body.style.overflow = '';
                }
            });
            document.body.appendChild(overlay);

            overlay._keyHandler = (e) => {
                if (e.key === 'Escape' && overlay.style.display !== 'none') {
                    overlay.style.display = 'none';
                    document.body.style.overflow = '';
                }
            };
            document.addEventListener('keydown', overlay._keyHandler);
        }

        const zoomImg = document.getElementById('gen-zoom-img');
        const spinner = document.getElementById('gen-zoom-spinner');

        zoomImg.src = src;
        zoomImg.style.opacity = '1';
        overlay.style.display = 'flex';
        document.body.style.overflow = 'hidden';

        if (pageNum && targetState?.pdfBytes && targetState.pdfBytes.length > 0) {
            const pdfjs = (typeof window !== 'undefined' ? (window.pdfjsLib || window['pdfjs-dist/build/pdf'] || window.pdfjs) : null);
            if (pdfjs?.getDocument) {
                spinner.style.display = 'block';
                zoomImg.style.opacity = '0.4';
                try {
                    const pdfDoc = await pdfjs.getDocument({ data: new Uint8Array(targetState.pdfBytes) }).promise;
                    const page = await pdfDoc.getPage(pageNum);
                    const renderFn = callbacks.renderPageImageData || (typeof window !== 'undefined' && window.PdfService ? window.PdfService.renderPageImageData : null);
                    if (renderFn) {
                        const hiResSrc = 'data:image/png;base64,' + await renderFn(page);
                        if (overlay.style.display !== 'none') {
                            zoomImg.src = hiResSrc;
                            zoomImg.style.opacity = '1';
                        }
                    }
                } catch (err) {
                    console.warn('Hi-res zoom render failed:', err);
                } finally {
                    spinner.style.display = 'none';
                    zoomImg.style.opacity = '1';
                }
            }
        }
    }

    function getQuestionValidationErrors(questions) {
        const targetQuestions = questions || appState?.questions || [];
        const validator = typeof window !== 'undefined' && window.QuizCore ? window.QuizCore.validateQuestions : null;
        return validator ? validator(targetQuestions) : [];
    }

    function updateValidationUI(elements = null, questions = null) {
        const targetElements = elements || appElements;
        const targetQuestions = questions || appState?.questions || [];
        const errors = getQuestionValidationErrors(targetQuestions);
        const invalidQuestionNumbers = new Set(
            errors.map((error) => {
                const match = String(error).match(/^שאלה\s+(\d+)/);
                return match ? Number(match[1]) : null;
            }).filter(Boolean)
        );

        targetElements?.preview?.querySelectorAll('.question-card').forEach((card, index) => {
            const invalid = invalidQuestionNumbers.has(index + 1);
            card.classList.toggle('is-invalid', invalid);
            card.setAttribute('aria-invalid', String(invalid));

            const cardErrors = errors.filter((err) => err.startsWith(`שאלה ${index + 1}:`));
            let errorBox = card.querySelector('.question-validation-error');
            if (cardErrors.length) {
                if (!errorBox) {
                    errorBox = document.createElement('div');
                    errorBox.className = 'question-validation-error';
                    errorBox.setAttribute('role', 'alert');
                    card.appendChild(errorBox);
                }
                errorBox.textContent = cardErrors.join(' ');
            } else if (errorBox) {
                errorBox.remove();
            }
        });

        if (targetElements?.validationSummary) {
            targetElements.validationSummary.classList.toggle('hidden', errors.length === 0);
            targetElements.validationSummary.textContent = errors.length
                ? `נמצאו ${invalidQuestionNumbers.size} שאלות לא תקינות (${errors.length} בעיות): ${errors.slice(0, 3).join(' ')}`
                : '';
        }
        return errors;
    }

    function disableOutputActions(disabled, elements = null, questions = null) {
        const targetElements = elements || appElements;
        const targetQuestions = questions || appState?.questions || [];
        const hasValidationErrors = getQuestionValidationErrors(targetQuestions).length > 0;
        const outputDisabled = disabled || hasValidationErrors;
        if (targetElements?.downloadQuiz) targetElements.downloadQuiz.disabled = outputDisabled;
        if (targetElements?.takeQuiz) targetElements.takeQuiz.disabled = outputDisabled;
        if (targetElements?.compressSettingsBtn) targetElements.compressSettingsBtn.disabled = outputDisabled;
        if (targetElements?.compressExportImages) targetElements.compressExportImages.disabled = outputDisabled;
    }

    function setPdfTypeNote(message = '', tone = 'neutral', elements = null) {
        const targetElements = elements || appElements;
        if (!targetElements?.pdfTypeNote) return;
        targetElements.pdfTypeNote.textContent = message;
        targetElements.pdfTypeNote.classList.toggle('hidden', !message);
        targetElements.pdfTypeNote.classList.remove('is-loading', 'is-digital', 'is-scanned', 'is-error');
        if (!message) return;
        if (tone === 'loading') targetElements.pdfTypeNote.classList.add('is-loading');
        else if (tone === 'digital') targetElements.pdfTypeNote.classList.add('is-digital');
        else if (tone === 'scanned') targetElements.pdfTypeNote.classList.add('is-scanned');
        else if (tone === 'error') targetElements.pdfTypeNote.classList.add('is-error');
    }

    function renderPreview(state = null, elements = null) {
        const targetState = state || appState;
        const targetElements = elements || appElements;
        if (!targetElements?.preview) return;

        targetElements.preview.innerHTML = '';

        targetState.questions.forEach((question, index) => {
            const card = document.createElement('article');
            card.className = 'question-card';
            card.setAttribute('aria-label', `שאלה ${index + 1}`);

            const questionRow = document.createElement('div');
            questionRow.className = 'row';
            questionRow.style.gridTemplateColumns = '80px 1fr 28px';

            const qLabel = document.createElement('label');
            qLabel.textContent = `שאלה ${index + 1}`;
            questionRow.appendChild(qLabel);

            const imageControlsWrap = document.createElement('div');
            imageControlsWrap.style.cssText = 'grid-column:1/-1;margin-bottom:8px;padding:8px 10px;background:var(--input-bg);border:1px solid var(--border-color);border-radius:10px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;';

            const leftBox = document.createElement('div');
            leftBox.style.cssText = 'display:flex;align-items:center;gap:6px;';

            const pageLabel = document.createElement('label');
            pageLabel.style.cssText = 'font-size:.82rem;font-weight:600;color:var(--text-secondary);';
            pageLabel.textContent = 'עמוד מקור:';

            const pageInput = document.createElement('input');
            pageInput.type = 'number';
            pageInput.min = '1';
            pageInput.value = question.sourcePage || 1;
            pageInput.style.cssText = 'width:55px;padding:3px 6px;border-radius:6px;border:1px solid var(--border-color);font:inherit;font-size:.82rem;background:var(--card-bg);color:var(--text-primary);';
            pageInput.addEventListener('change', () => {
                const p = parseInt(pageInput.value, 10);
                if (p && p >= 1) {
                    targetState.questions[index].sourcePage = p;
                    const c = pageInput.closest('.question-card');
                    if (c) {
                        const summary = c.querySelector('details summary');
                        if (summary) summary.textContent = `מצב הגהה: עמוד מקור ${p}`;
                        const sourceImg = c.querySelector('details img');
                        const sourcePageIndex = p - 1;
                        const newSrc = targetState.proofPageImages[sourcePageIndex] || targetState.pdfPagesState[sourcePageIndex]?.thumbnailDataUrl;
                        if (sourceImg && newSrc) {
                            sourceImg.src = newSrc;
                            sourceImg.alt = `עמוד מקור ${p}`;
                        }
                    }
                }
            });
            leftBox.append(pageLabel, pageInput);

            const rightBox = document.createElement('div');
            rightBox.style.cssText = 'display:flex;gap:6px;flex-wrap:wrap;align-items:center;';

            const cropBtn = document.createElement('button');
            cropBtn.type = 'button';
            cropBtn.className = 'secondary-btn sm-btn';
            cropBtn.textContent = question.image ? '🖼️ החלף לעמוד מקור מלא' : '🖼️ הוסף עמוד מקור מלא';
            cropBtn.style.cssText = 'font-size:.8rem;padding:4px 10px;';
            cropBtn.addEventListener('click', async () => {
                cropBtn.disabled = true;
                const prevText = cropBtn.textContent;
                cropBtn.textContent = 'מוסיף עמוד...';
                if (callbacks.attachFullSourcePageImage) {
                    await callbacks.attachFullSourcePageImage(index, question.sourcePage || 1);
                }
                cropBtn.disabled = false;
                cropBtn.textContent = prevText;
            });

            const fileInput = document.createElement('input');
            fileInput.type = 'file';
            fileInput.accept = 'image/*';
            fileInput.style.display = 'none';
            fileInput.addEventListener('change', (e) => {
                const f = e.target.files?.[0];
                if (f) {
                    const reader = new FileReader();
                    reader.onload = (ev) => {
                        targetState.questions[index].image = ev.target.result;
                        delete targetState.questions[index].imageNoCompress;
                        renderPreview(targetState, targetElements);
                    };
                    reader.readAsDataURL(f);
                }
            });

            const uploadBtn = document.createElement('button');
            uploadBtn.type = 'button';
            uploadBtn.className = 'secondary-btn sm-btn';
            uploadBtn.textContent = '📁 העלה תמונה מקובץ';
            uploadBtn.style.cssText = 'font-size:.8rem;padding:4px 10px;';
            uploadBtn.addEventListener('click', () => fileInput.click());

            rightBox.append(cropBtn, uploadBtn, fileInput);

            if (question.image) {
                const removeBtn = document.createElement('button');
                removeBtn.type = 'button';
                removeBtn.className = 'secondary-btn sm-btn';
                removeBtn.textContent = '✕ הסר תמונה';
                removeBtn.style.cssText = 'font-size:.8rem;padding:4px 8px;color:var(--danger);';
                removeBtn.addEventListener('click', () => {
                    delete targetState.questions[index].image;
                    renderPreview(targetState, targetElements);
                });
                rightBox.appendChild(removeBtn);
            }

            imageControlsWrap.append(leftBox, rightBox);

            if (question.image) {
                const imgWrap = document.createElement('div');
                imgWrap.style.cssText = 'grid-column:1/-1;display:flex;align-items:center;gap:8px;margin-bottom:6px;';
                const thumb = document.createElement('img');
                thumb.src = question.image;
                thumb.style.cssText = 'max-height:140px;max-width:100%;border-radius:8px;border:1px solid var(--border-color);cursor:zoom-in;';
                thumb.title = 'לחץ להצגה בגודל מלא';
                thumb.addEventListener('click', () => showImageZoom(question.image, null, targetState));
                imgWrap.appendChild(thumb);
                card.appendChild(imgWrap);
            }

            card.appendChild(imageControlsWrap);

            const questionTextarea = document.createElement('textarea');
            questionTextarea.value = question.question;
            questionTextarea.setAttribute('aria-label', `נוסח שאלה ${index + 1}`);
            questionTextarea.addEventListener('input', () => {
                targetState.questions[index].question = questionTextarea.value;
                updateValidationUI(targetElements, targetState.questions);
                disableOutputActions(false, targetElements, targetState.questions);
            });
            questionRow.appendChild(questionTextarea);

            const deleteQBtn = document.createElement('button');
            deleteQBtn.type = 'button';
            deleteQBtn.textContent = '✕';
            deleteQBtn.title = 'מחק שאלה';
            deleteQBtn.style.cssText = 'width:28px;height:28px;border-radius:50%;border:1px solid var(--border-color);background:var(--input-bg);color:var(--danger);cursor:pointer;font-size:.85rem;display:flex;align-items:center;justify-content:center;padding:0;flex-shrink:0;';
            deleteQBtn.addEventListener('click', () => {
                targetState.questions.splice(index, 1);
                renderPreview(targetState, targetElements);
            });
            questionRow.appendChild(deleteQBtn);

            card.appendChild(questionRow);

            if (targetState.proofMode && question.sourcePage) {
                const sourcePageIndex = Number(question.sourcePage) - 1;
                const sourcePageImage = targetState.proofPageImages?.[sourcePageIndex] || targetState.pdfPagesState?.[sourcePageIndex]?.thumbnailDataUrl;
                if (sourcePageImage) {
                    const proofWrap = document.createElement('details');
                    proofWrap.style.cssText = 'grid-column:1/-1;border:1px solid var(--border-color);border-radius:10px;background:var(--card-bg);padding:8px;';
                    proofWrap.open = false;

                    const summary = document.createElement('summary');
                    summary.textContent = `מצב הגהה: עמוד מקור ${question.sourcePage}`;
                    summary.style.cssText = 'cursor:pointer;font-weight:600;margin-bottom:8px;';
                    proofWrap.appendChild(summary);

                    const sourceImg = document.createElement('img');
                    sourceImg.src = sourcePageImage;
                    sourceImg.alt = `עמוד מקור ${question.sourcePage}`;
                    sourceImg.style.cssText = 'max-width:100%;border-radius:8px;border:1px solid var(--border-color);cursor:zoom-in;';
                    sourceImg.addEventListener('click', () => showImageZoom(sourcePageImage, Number(question.sourcePage), targetState));
                    proofWrap.appendChild(sourceImg);

                    card.appendChild(proofWrap);
                }
            }

            const questionErrors = getQuestionValidationErrors(targetState.questions).filter((error) => error.startsWith(`שאלה ${index + 1}:`));
            if (questionErrors.length) {
                const errorBox = document.createElement('div');
                errorBox.className = 'question-validation-error';
                errorBox.setAttribute('role', 'alert');
                errorBox.textContent = questionErrors.join(' ');
                card.appendChild(errorBox);
            }

            question.options.forEach((option, optIndex) => {
                const optionRow = document.createElement('div');
                optionRow.className = 'option-row';

                const radio = document.createElement('input');
                radio.type = 'radio';
                radio.name = `correct-${index}`;
                radio.checked = question.correctIndex === optIndex;
                radio.title = 'סמן תשובה נכונה';
                radio.addEventListener('change', () => {
                    targetState.questions[index].correctIndex = optIndex;
                });

                const optionInput = document.createElement('input');
                optionInput.type = 'text';
                optionInput.value = option;
                optionInput.setAttribute('aria-label', `שאלה ${index + 1}, תשובה ${optIndex + 1}`);
                optionInput.addEventListener('input', () => {
                    targetState.questions[index].options[optIndex] = optionInput.value;
                    updateValidationUI(targetElements, targetState.questions);
                    disableOutputActions(false, targetElements, targetState.questions);
                });

                const delBtn = document.createElement('button');
                delBtn.type = 'button';
                delBtn.textContent = '✕';
                delBtn.title = 'הסר תשובה';
                delBtn.style.cssText = 'width:26px;height:26px;border-radius:50%;border:1px solid var(--border-color);background:var(--input-bg);color:var(--danger);cursor:pointer;font-size:.85rem;display:flex;align-items:center;justify-content:center;padding:0;flex-shrink:0;';
                delBtn.addEventListener('click', () => {
                    if (targetState.questions[index].options.length <= 2) {
                        alert('שאלה חייבת להכיל לפחות 2 תשובות.');
                        return;
                    }
                    targetState.questions[index].options.splice(optIndex, 1);
                    if (targetState.questions[index].correctIndex >= targetState.questions[index].options.length) {
                        targetState.questions[index].correctIndex = Math.max(0, targetState.questions[index].options.length - 1);
                    }
                    renderPreview(targetState, targetElements);
                });

                optionRow.append(radio, optionInput, delBtn);
                card.appendChild(optionRow);
            });

            const addBtn = document.createElement('button');
            addBtn.type = 'button';
            addBtn.textContent = '+ הוסף תשובה';
            addBtn.style.cssText = 'margin-top:4px;padding:6px 14px;border-radius:8px;border:1px dashed var(--border-color);background:var(--input-bg);color:var(--text-secondary);cursor:pointer;font:inherit;font-size:.85rem;width:100%;';
            addBtn.addEventListener('click', () => {
                targetState.questions[index].options.push('');
                renderPreview(targetState, targetElements);
            });
            card.appendChild(addBtn);

            targetElements.preview.appendChild(card);
        });

        const addQBtn = document.createElement('button');
        addQBtn.type = 'button';
        addQBtn.textContent = '+ הוסף שאלה';
        addQBtn.style.cssText = 'margin-top:12px;padding:10px 16px;border-radius:10px;border:2px dashed var(--border-color);background:var(--card-bg);color:var(--text-secondary);cursor:pointer;font:inherit;font-size:.95rem;width:100%;';
        addQBtn.addEventListener('click', () => {
            targetState.questions.push({
                question: '',
                options: ['', '', '', ''],
                correctIndex: 0
            });
            renderPreview(targetState, targetElements);
        });
        targetElements.preview.appendChild(addQBtn);
        updateValidationUI(targetElements, targetState.questions);
        disableOutputActions(false, targetElements, targetState.questions);
    }

    return {
        init,
        setTheme,
        updateVerificationUI,
        showToast,
        setStatus,
        showImageZoom,
        getQuestionValidationErrors,
        updateValidationUI,
        disableOutputActions,
        setPdfTypeNote,
        renderPreview
    };
}));

