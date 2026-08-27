(function (root, factory) {
    if (typeof define === 'function' && define.amd) {
        define([], factory);
    } else if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.ProgressController = factory();
    }
}(typeof self !== 'undefined' ? self : this, function () {
    'use strict';

    let domElements = {};
    let setStatusFn = null;

    const ProgressController = {
        activeTask: null,
        dismissTimeout: null,

        init(elements, setStatusCallback) {
            domElements = elements || {};
            setStatusFn = setStatusCallback || null;

            if (domElements.progressAbortBtn) {
                domElements.progressAbortBtn.addEventListener('click', () => {
                    if (this.activeTask) {
                        this.abort(this.activeTask.id);
                    }
                });
            }
            if (domElements.stickyProgressAbortBtn) {
                domElements.stickyProgressAbortBtn.addEventListener('click', () => {
                    if (this.activeTask) {
                        this.abort(this.activeTask.id);
                    }
                });
            }
        },

        startTask(title, { cancellable = true, icon = '⚡', detail = 'מתחיל בעיבוד...', indeterminate = false } = {}) {
            if (this.dismissTimeout) {
                clearTimeout(this.dismissTimeout);
                this.dismissTimeout = null;
            }

            const abortController = new AbortController();
            const taskId = Symbol('task');

            const task = {
                id: taskId,
                title,
                cancellable,
                abortController,
                signal: abortController.signal,
                isAborted: () => abortController.signal.aborted,
                update: (percent, newDetail, opts) => this.update(taskId, percent, newDetail, opts),
                finish: (msg, opts) => this.finish(taskId, msg, opts),
                fail: (err, opts) => this.fail(taskId, err, opts),
                abort: (reason) => this.abort(taskId, reason)
            };

            this.activeTask = task;

            if (domElements.progressCard) {
                domElements.progressCard.classList.remove('hidden', 'is-success', 'is-error', 'is-aborted');
            }
            if (domElements.stickyProgressBanner) {
                domElements.stickyProgressBanner.classList.remove('hidden', 'is-success', 'is-error', 'is-aborted');
            }

            if (domElements.progressTitle) domElements.progressTitle.textContent = title;
            if (domElements.stickyProgressTitle) domElements.stickyProgressTitle.textContent = title;
            if (domElements.progressDetail) domElements.progressDetail.textContent = detail;
            if (domElements.stickyProgressDetail) domElements.stickyProgressDetail.textContent = detail;
            if (domElements.progressIcon) domElements.progressIcon.textContent = icon;

            if (domElements.progressAbortBtn) {
                domElements.progressAbortBtn.style.display = cancellable ? 'inline-flex' : 'none';
                domElements.progressAbortBtn.disabled = false;
            }
            if (domElements.stickyProgressAbortBtn) {
                domElements.stickyProgressAbortBtn.style.display = cancellable ? 'inline-flex' : 'none';
                domElements.stickyProgressAbortBtn.disabled = false;
            }

            this.update(taskId, indeterminate ? 0 : 0, detail, { indeterminate });
            return task;
        },

        update(taskId, percent, detailText, { indeterminate = false } = {}) {
            if (this.activeTask && this.activeTask.id !== taskId) return;
            const clamped = Math.max(0, Math.min(100, Math.round(percent || 0)));

            if (domElements.progressFill) {
                domElements.progressFill.classList.toggle('indeterminate', !!indeterminate);
                if (!indeterminate) domElements.progressFill.style.width = `${clamped}%`;
            }
            if (domElements.stickyProgressFill) {
                domElements.stickyProgressFill.classList.toggle('indeterminate', !!indeterminate);
                if (!indeterminate) domElements.stickyProgressFill.style.width = `${clamped}%`;
            }

            const percentLabel = indeterminate ? '...' : `${clamped}%`;
            if (domElements.progressPercent) domElements.progressPercent.textContent = percentLabel;
            if (domElements.stickyProgressPercent) domElements.stickyProgressPercent.textContent = percentLabel;

            if (domElements.mainProgressBar) {
                domElements.mainProgressBar.setAttribute('aria-valuenow', String(indeterminate ? 50 : clamped));
            }

            if (detailText !== undefined) {
                if (domElements.progressDetail) domElements.progressDetail.textContent = detailText;
                if (domElements.stickyProgressDetail) domElements.stickyProgressDetail.textContent = detailText;
            }
        },

        finish(taskId, successMessage = 'הפעולה הסתיימה בהצלחה!', { duration = 2000 } = {}) {
            if (this.activeTask && this.activeTask.id !== taskId) return;
            this.update(taskId, 100, successMessage, { indeterminate: false });

            if (domElements.progressCard) domElements.progressCard.classList.add('is-success');
            if (domElements.stickyProgressBanner) domElements.stickyProgressBanner.classList.add('is-success');
            if (domElements.progressIcon) domElements.progressIcon.textContent = '✅';

            if (domElements.progressAbortBtn) domElements.progressAbortBtn.style.display = 'none';
            if (domElements.stickyProgressAbortBtn) domElements.stickyProgressAbortBtn.style.display = 'none';

            if (setStatusFn) setStatusFn(successMessage, false);

            this.dismissTimeout = setTimeout(() => {
                if (domElements.progressCard) domElements.progressCard.classList.add('hidden');
                if (domElements.stickyProgressBanner) domElements.stickyProgressBanner.classList.add('hidden');
                this.activeTask = null;
            }, duration);
        },

        fail(taskId, errorMessage = 'אירעה שגיאה בתהליך.') {
            if (this.activeTask && this.activeTask.id !== taskId) return;
            if (domElements.progressCard) domElements.progressCard.classList.add('is-error');
            if (domElements.stickyProgressBanner) domElements.stickyProgressBanner.classList.add('is-error');
            if (domElements.progressIcon) domElements.progressIcon.textContent = '⚠️';
            if (domElements.progressDetail) domElements.progressDetail.textContent = errorMessage;
            if (domElements.stickyProgressDetail) domElements.stickyProgressDetail.textContent = errorMessage;

            if (domElements.progressAbortBtn) domElements.progressAbortBtn.style.display = 'none';
            if (domElements.stickyProgressAbortBtn) domElements.stickyProgressAbortBtn.style.display = 'none';

            if (setStatusFn) setStatusFn(errorMessage, true, true);

            this.dismissTimeout = setTimeout(() => {
                if (domElements.progressCard) domElements.progressCard.classList.add('hidden');
                if (domElements.stickyProgressBanner) domElements.stickyProgressBanner.classList.add('hidden');
                this.activeTask = null;
            }, 4500);
        },

        abort(taskId, reason = 'הפעולה בוטלה על ידי המשתמש.') {
            if (this.activeTask && this.activeTask.id !== taskId) return;
            if (this.activeTask) {
                this.activeTask.abortController.abort();
            }

            if (domElements.progressCard) domElements.progressCard.classList.add('is-aborted');
            if (domElements.stickyProgressBanner) domElements.stickyProgressBanner.classList.add('is-aborted');
            if (domElements.progressIcon) domElements.progressIcon.textContent = '🛑';
            if (domElements.progressDetail) domElements.progressDetail.textContent = reason;
            if (domElements.stickyProgressDetail) domElements.stickyProgressDetail.textContent = reason;

            if (domElements.progressAbortBtn) domElements.progressAbortBtn.disabled = true;
            if (domElements.stickyProgressAbortBtn) domElements.stickyProgressAbortBtn.disabled = true;

            if (setStatusFn) setStatusFn(reason, true, true);

            this.dismissTimeout = setTimeout(() => {
                if (domElements.progressCard) domElements.progressCard.classList.add('hidden');
                if (domElements.stickyProgressBanner) domElements.stickyProgressBanner.classList.add('hidden');
                this.activeTask = null;
            }, 2500);
        }
    };

    return ProgressController;
}));

