(() => {
  const rawTextInput = document.getElementById('raw-text-input');
  const runParseBtn = document.getElementById('run-parse-btn');
  const addQuestionBtn = document.getElementById('add-question-btn');
  const previewContainer = document.getElementById('preview-container');
  const useLlmToggle = document.getElementById('use-llm-toggle');
  const useOfflineOcrToggle = document.getElementById('use-offline-ocr-toggle');
  const parseModeNote = document.getElementById('parse-mode-note');

  // Question headers:
  // 1) "שאלה מספר 1:" / "שאלה 1:"
  // 2) "מספר שאלה 1:"
  // 3) "1. ..." / "1) ..."
  const questionHeaderPatterns = [
    String.raw`שאלה\s+(?:מספר\s+)?:?\d+\s*:?`,
    String.raw`(?:מספר\s+)?שאלה\s*:?\s*\d+\s*:?`,
    String.raw`^\d+[\.)]\s*`
  ];
  const qPattern = new RegExp(questionHeaderPatterns.join('|'));
  const answerPattern = /^([אבגד1-4])\s*[\.)]\s*(.*)$/;
  const noisePattern = /(?:^עמוד\s+\d+\s+מתוך\s+\d+$|^\d+\s+מתוך\s*\d+\s+עמוד$)/;
  const endExamPattern = /-*\s*סוף\s+המבחן\s*-*/g;
  const endExamLinePattern = /^\s*-*\s*סוף\s+המבחן\s*-*\s*$/i;

  let questions = [];

  function isMissing(value) {
    return value === undefined || value === '';
  }

  function sanitizeText(text) {
    return (text || '').replace(endExamPattern, '').replace(/\s+/g, ' ').trim();
  }

  function isNoise(line) {
    const clean = line.trim();
    return !clean || noisePattern.test(clean) || endExamLinePattern.test(clean);
  }

  function updateParseModeNote() {
    if (useLlmToggle.checked) {
      parseModeNote.textContent = useOfflineOcrToggle.checked
        ? 'מצב נוכחי: LLM פעיל + OCR אופליין לסרוקים (יתכן דיוק נמוך).'
        : 'מצב נוכחי: LLM פעיל. למסמך דיגיטלי מומלץ לכבות LLM.';
    } else {
      parseModeNote.textContent = 'מצב נוכחי: ללא LLM (מומלץ ל‑PDF דיגיטלי).';
    }
  }

  function parseQuestions(rawText) {
    const lines = rawText.split(/\r?\n/);
    const parsed = [];
    let current = null;

    for (const lineRaw of lines) {
      const line = lineRaw.trim();
      if (isNoise(line)) continue;

      if (qPattern.test(line)) {
        if (current && current.options.length >= 2 && current.question) parsed.push(current);
        current = { question: '', options: [], correctIndex: 0 };
        continue;
      }

      if (!current) continue;

      const ansMatch = line.match(answerPattern);
      if (ansMatch) {
        current.options.push(sanitizeText(ansMatch[2]));
      } else if (current.options.length === 0) {
        current.question = sanitizeText([current.question, line].filter(Boolean).join(' '));
      } else if (current.options.length > 0) {
        const last = current.options.length - 1;
        current.options[last] = sanitizeText(`${current.options[last]} ${line}`);
      }
    }

    if (current && current.options.length >= 2 && current.question) parsed.push(current);
    return parsed;
  }

  function renderQuestions() {
    previewContainer.innerHTML = '';

    if (questions.length === 0) {
      previewContainer.innerHTML = '<div class="review-item">אין עדיין שאלות לתצוגה מקדימה.</div>';
      return;
    }

    questions.forEach((q, qIndex) => {
      const card = document.createElement('div');
      card.className = 'review-item';

      const optionsHtml = q.options.map((opt, optIndex) => `
        <div style="display:flex; gap:0.5rem; margin-bottom:0.5rem; align-items:center;">
          <input data-type="option" data-q="${qIndex}" data-opt="${optIndex}" value="${escapeHtml(opt)}" style="flex:1; padding:0.55rem; border:1px solid var(--border-color); border-radius:0.5rem; background:var(--surface-color); color:var(--text-primary);" />
        </div>
      `).join('');

      card.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.75rem;">
          <strong>שאלה ${qIndex + 1}</strong>
          <button class="secondary-btn" data-action="delete-question" data-q="${qIndex}">מחק שאלה</button>
        </div>
        <textarea data-type="question" data-q="${qIndex}" rows="3" style="width:100%; margin-bottom:0.75rem; border:1px solid var(--border-color); border-radius:0.5rem; padding:0.55rem; background:var(--surface-color); color:var(--text-primary);">${escapeHtml(q.question)}</textarea>
        <div>${optionsHtml}</div>
        <label style="display:flex; gap:0.5rem; align-items:center;">
          תשובה נכונה
          <select data-type="correct" data-q="${qIndex}" style="padding:0.45rem; border:1px solid var(--border-color); border-radius:0.5rem; background:var(--surface-color); color:var(--text-primary);">
            ${q.options.map((_, i) => `<option value="${i}" ${q.correctIndex === i ? 'selected' : ''}>אפשרות ${i + 1}</option>`).join('')}
          </select>
        </label>
      `;

      previewContainer.appendChild(card);
    });
  }

  function escapeHtml(text) {
    return (text || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  runParseBtn.addEventListener('click', () => {
    const raw = rawTextInput.value.trim();
    questions = raw ? parseQuestions(raw) : [];
    renderQuestions();
  });

  addQuestionBtn.addEventListener('click', () => {
    questions.push({
      question: 'שאלה חדשה',
      options: ['אפשרות 1', 'אפשרות 2', 'אפשרות 3', 'אפשרות 4'],
      correctIndex: 0
    });
    renderQuestions();
  });

  previewContainer.addEventListener('click', (event) => {
    const btn = event.target.closest('[data-action="delete-question"]');
    if (!btn) return;

    const qIndex = Number(btn.dataset.q);
    questions.splice(qIndex, 1);
    renderQuestions();
  });

  previewContainer.addEventListener('input', (event) => {
    const { type, q, opt } = event.target.dataset;
    if (type !== 'question' && type !== 'option') return;
    if ((type === 'question' || type === 'option') && isMissing(q)) return;

    const qIndex = Number(q);
    if (!Number.isInteger(qIndex) || !questions[qIndex]) return;

    if (type === 'question') {
      questions[qIndex].question = sanitizeText(event.target.value);
    }
    if (type === 'option') {
      if (isMissing(opt)) return;
      const optIndex = Number(opt);
      if (!Number.isInteger(optIndex) || !questions[qIndex].options[optIndex]) return;
      questions[qIndex].options[optIndex] = sanitizeText(event.target.value);
    }
  });

  previewContainer.addEventListener('change', (event) => {
    const { type, q } = event.target.dataset;
    if (type !== 'correct' || isMissing(q)) return;
    const qIndex = Number(q);
    if (!Number.isInteger(qIndex) || !questions[qIndex]) return;
    questions[qIndex].correctIndex = Number(event.target.value);
  });

  useLlmToggle.addEventListener('change', updateParseModeNote);
  useOfflineOcrToggle.addEventListener('change', updateParseModeNote);

  updateParseModeNote();
  renderQuestions();
})();
