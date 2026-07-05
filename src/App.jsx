import React, { useEffect, useMemo, useState } from 'react';
import { Link, NavLink, Route, Routes } from 'react-router-dom';
import { extractAnswersForForm, parseCsvRows } from './lib/quizParsing';
import { extractPdfTextDigital, mergeAnswers, parseQuestionsFromText } from './lib/pdfLocalParse';

const features = [
  {
    title: 'React-first entry',
    description: 'Google AI Studio can ingest this repo as a React app while the legacy HTML pages stay available.'
  },
  {
    title: 'Legacy builder preserved',
    description: 'The existing PDF-to-quiz builder remains on a separate page so the current workflow is not lost.'
  },
  {
    title: 'AI Studio ready path',
    description: 'This layout matches AI Studio Build mode expectations: React UI plus room to move Gemini calls server-side later.'
  }
];

const links = [
  {
    href: '/builder',
    label: 'Open Quiz Builder',
    description: 'Use the existing upload + OCR builder from a React route.'
  },
  {
    href: '/player',
    label: 'Open Quiz Taker',
    description: 'Launch the preserved quiz player from a React route.'
  },
  {
    href: 'README.md',
    label: 'Read Migration Notes',
    description: 'See how this repo is structured for AI Studio.'
  }
];

function ShellHeader() {
  return (
    <header className="topbar">
      <div>
        <p className="eyebrow">Google AI Studio build target</p>
        <h1>Interactive Hebrew Quiz Generator</h1>
      </div>

      <nav className="route-nav" aria-label="Primary routes">
        <NavLink to="/" end className={({ isActive }) => `route-chip${isActive ? ' active' : ''}`}>
          Home
        </NavLink>
        <NavLink to="/builder" className={({ isActive }) => `route-chip${isActive ? ' active' : ''}`}>
          Builder
        </NavLink>
        <NavLink to="/player" className={({ isActive }) => `route-chip${isActive ? ' active' : ''}`}>
          Player
        </NavLink>
      </nav>
    </header>
  );
}

function LegacyEmbed({ title, src, description }) {
  return (
    <section className="embed-wrap">
      <div className="embed-head">
        <p className="eyebrow">React Route Wrapper</p>
        <h2>{title}</h2>
        <p className="hero-copy">{description}</p>
        <a className="ghost-link" href={src} target="_blank" rel="noreferrer">
          Open Standalone Page
        </a>
      </div>

      <div className="embed-frame-card">
        <iframe title={title} src={src} className="legacy-frame" />
      </div>
    </section>
  );
}

function BuilderPage() {
  const [pdfFile, setPdfFile] = useState(null);
  const [answerFile, setAnswerFile] = useState(null);
  const [formNumber, setFormNumber] = useState('');
  const [llmPolicy, setLlmPolicy] = useState('auto');
  const [ocrEngine, setOcrEngine] = useState('gemini_chunked');
  const [health, setHealth] = useState({ loading: true, configured: false, message: '' });
  const [answersPreview, setAnswersPreview] = useState({ rows: 0, mapped: null, error: '' });
  const [runState, setRunState] = useState({ running: false, message: '', error: '' });
  const [parsedQuestions, setParsedQuestions] = useState([]);

  useEffect(() => {
    if (llmPolicy === 'force_llm' && ocrEngine === 'offline_local') {
      setOcrEngine('gemini_chunked');
      return;
    }

    if (llmPolicy === 'force_no_llm' && ocrEngine !== 'offline_local') {
      setOcrEngine('offline_local');
    }
  }, [llmPolicy, ocrEngine]);

  const ocrOfflineDisabled = llmPolicy === 'force_llm';
  const ocrGeminiDisabled = llmPolicy === 'force_no_llm';
  const policyForceLlmDisabled = ocrEngine === 'offline_local';
  const policyForceNoLlmDisabled = ocrEngine === 'gemini_chunked' || ocrEngine === 'gemini_native';

  const requiresGemini = useMemo(
    () => llmPolicy === 'force_llm' || (llmPolicy === 'auto' && ocrEngine !== 'offline_local'),
    [llmPolicy, ocrEngine]
  );

  async function loadGeminiHealth() {
    setHealth((prev) => ({ ...prev, loading: true }));
    try {
      const response = await fetch('/api/gemini/health');
      if (!response.ok) {
        throw new Error(`Health check failed (${response.status})`);
      }
      const payload = await response.json();
      setHealth({
        loading: false,
        configured: Boolean(payload?.configured),
        message: payload?.message || ''
      });
    } catch {
      setHealth({
        loading: false,
        configured: false,
        message: 'Could not reach Gemini runtime health endpoint.'
      });
    }
  }

  useEffect(() => {
    loadGeminiHealth();
  }, []);

  function openLegacyBuilderWithPrefill() {
    const payload = {
      formNumber: formNumber.trim(),
      llmPolicy,
      ocrEngine,
      createdAt: Date.now()
    };

    localStorage.setItem('builderPrefillV1', JSON.stringify(payload));
    window.open('/quiz_generator.html', '_blank', 'noopener,noreferrer');
  }

  async function runReactParse() {
    if (!pdfFile) {
      setRunState({ running: false, message: '', error: 'יש לבחור קובץ PDF לפני הפעלה.' });
      return;
    }

    setRunState({ running: true, message: 'מחלץ טקסט מה-PDF...', error: '' });
    setParsedQuestions([]);

    try {
      const buffer = await pdfFile.arrayBuffer();
      const extracted = await extractPdfTextDigital(buffer.slice(0));

      if (llmPolicy === 'force_llm') {
        setRunState({
          running: false,
          message: 'נבחר LLM תמיד. יש להמשיך למחולל הישן עבור OCR/LLM בשלב זה.',
          error: ''
        });
        return;
      }

      if (extracted.isScanned) {
        setRunState({
          running: false,
          message: 'זוהה PDF סרוק. במסלול React הנוכחי נתמך פענוח מקומי ל-PDF דיגיטלי בלבד. המשך למחולל הישן.',
          error: ''
        });
        return;
      }

      setRunState({ running: true, message: 'מפענח שאלות...', error: '' });
      let questions = parseQuestionsFromText(extracted.text, extracted.rawPages);

      if (answerFile && answerFile.name.toLowerCase().endsWith('.csv') && formNumber.trim()) {
        const csvText = await answerFile.text();
        const rows = parseCsvRows(csvText.replace(/^\uFEFF/, ''));
        const answerMap = extractAnswersForForm(rows, formNumber.trim());
        questions = mergeAnswers(questions, answerMap);
      } else {
        questions = questions.map((q) => ({ ...q, correctIndex: 0, shuffleOptions: true }));
      }

      setParsedQuestions(questions);
      setRunState({ running: false, message: `הסתיים בהצלחה: ${questions.length} שאלות זוהו במסלול React.`, error: '' });
    } catch (error) {
      setRunState({
        running: false,
        message: '',
        error: error instanceof Error ? error.message : 'אירעה שגיאה לא צפויה בזמן הפענוח.'
      });
    }
  }

  useEffect(() => {
    let cancelled = false;

    async function loadAnswersPreview() {
      if (!answerFile) {
        setAnswersPreview({ rows: 0, mapped: null, error: '' });
        return;
      }

      if (!answerFile.name.toLowerCase().endsWith('.csv')) {
        setAnswersPreview({ rows: 0, mapped: null, error: 'CSV preview is currently supported only for .csv files.' });
        return;
      }

      try {
        const text = await answerFile.text();
        if (cancelled) return;
        const rows = parseCsvRows(text.replace(/^\uFEFF/, ''));
        if (!formNumber.trim()) {
          setAnswersPreview({ rows: rows.length, mapped: null, error: '' });
          return;
        }

        const answers = extractAnswersForForm(rows, formNumber.trim());
        setAnswersPreview({ rows: rows.length, mapped: answers.size, error: '' });
      } catch (error) {
        setAnswersPreview({
          rows: 0,
          mapped: null,
          error: error instanceof Error ? error.message : 'Failed to parse answers file.'
        });
      }
    }

    loadAnswersPreview();
    return () => {
      cancelled = true;
    };
  }, [answerFile, formNumber]);

  return (
    <section className="builder-react-wrap" dir="rtl">
      <article className="builder-react-card">
        <p className="eyebrow">מסלול הגירה ל-React</p>
        <h2>מחולל מבחן ב-React (שלב 1)</h2>
        <div className="builder-info-banner">
          <span>💡</span>
          <p>
            ההגדרות כאן תואמות את המסך הישן. כרגע הפענוח עצמו עדיין רץ במחולל הישן, אבל הערכים שבחרת
            מועברים אוטומטית אליו.
          </p>
        </div>

        <div className="builder-form-grid">
          <label className="builder-field">
            <span>קובץ PDF</span>
            <input type="file" accept="application/pdf" onChange={(e) => setPdfFile(e.target.files?.[0] || null)} />
          </label>

          <label className="builder-field">
            <span>קובץ תשובות (אופציונלי)</span>
            <input
              type="file"
              accept=".csv,.xls,.xlsx,text/csv,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              onChange={(e) => setAnswerFile(e.target.files?.[0] || null)}
            />
          </label>

          <label className="builder-field">
            <span>מספר שאלון (אופציונלי)</span>
            <input
              type="text"
              inputMode="numeric"
              placeholder="לדוגמה: 76"
              value={formNumber}
              onChange={(e) => setFormNumber(e.target.value)}
            />
          </label>

          <label className="builder-field">
            <span>שימוש ב-LLM</span>
            <select value={llmPolicy} onChange={(e) => setLlmPolicy(e.target.value)}>
              <option value="auto">אוטומטי</option>
              <option value="force_llm" disabled={policyForceLlmDisabled}>LLM תמיד (Gemini)</option>
              <option value="force_no_llm" disabled={policyForceNoLlmDisabled}>ללא LLM (מקומי בלבד)</option>
            </select>
          </label>

          <label className="builder-field">
            <span>מנוע OCR</span>
            <select value={ocrEngine} onChange={(e) => setOcrEngine(e.target.value)}>
              <option value="gemini_chunked" disabled={ocrGeminiDisabled}>Gemini - פיצול לעמודים</option>
              <option value="gemini_native" disabled={ocrGeminiDisabled}>Gemini - העלאת PDF ישירה</option>
              <option value="offline_local" disabled={ocrOfflineDisabled}>OCR מקומי חינמי</option>
            </select>
          </label>
        </div>

        <div className="builder-actions-row">
          <button type="button" className="primary-btn" onClick={runReactParse} disabled={runState.running}>
            {runState.running ? 'מפעיל ניתוח...' : 'הפעל ניתוח ב-React'}
          </button>
          <button type="button" className="primary-btn" onClick={openLegacyBuilderWithPrefill}>
            המשך למחולל הישן
          </button>
          <button type="button" className="secondary-btn" onClick={loadGeminiHealth}>
            רענן סטטוס שרת
          </button>
        </div>

        {runState.message ? <p className="runtime-note success">{runState.message}</p> : null}
        {runState.error ? <p className="runtime-warning">{runState.error}</p> : null}

        {parsedQuestions.length ? (
          <div className="builder-preview-block">
            <div className="panel-title">תצוגת שאלות (React)</div>
            <p className="muted">מציג עד 5 שאלות ראשונות מהפענוח המקומי.</p>
            <div className="builder-preview-list">
              {parsedQuestions.slice(0, 5).map((q, idx) => (
                <article key={`${q.sourcePage}-${idx}`} className="builder-preview-item">
                  <h3>שאלה {idx + 1} (עמוד {q.sourcePage})</h3>
                  <p>{q.question}</p>
                  <ol>
                    {q.options.map((opt, oi) => (
                      <li key={oi}>{opt}</li>
                    ))}
                  </ol>
                </article>
              ))}
            </div>
          </div>
        ) : null}
      </article>

      <aside className="builder-side-card">
        <div className="panel-title">סטטוס סביבת ריצה</div>
        <p className={`runtime-pill${health.loading ? ' loading' : health.configured ? ' ok' : ' warn'}`}>
          {health.loading ? 'בודק זמינות Gemini...' : health.configured ? 'Gemini מוגדר בשרת' : 'Gemini לא מוגדר בשרת'}
        </p>
        <p className="muted">{health.message}</p>

        <div className="panel-title">הגדרות נוכחיות</div>
        <ul className="builder-list">
          <li>PDF: {pdfFile ? pdfFile.name : 'לא נבחר קובץ'}</li>
          <li>תשובות: {answerFile ? answerFile.name : 'לא נבחר קובץ'}</li>
          <li>מספר שאלון: {formNumber || 'לא הוגדר'}</li>
          <li>LLM: {llmPolicy}</li>
          <li>OCR: {ocrEngine}</li>
          <li>שורות CSV שזוהו: {answersPreview.rows || 0}</li>
          <li>
            מיפויי תשובות:{' '}
            {answersPreview.mapped == null ? (formNumber ? 'לא זוהו' : 'הזן מספר שאלון להצגה') : answersPreview.mapped}
          </li>
        </ul>

        {answersPreview.error ? <p className="runtime-warning">{answersPreview.error}</p> : null}

        {requiresGemini && !health.loading && !health.configured ? (
          <p className="runtime-warning">
            ההגדרות הנוכחיות דורשות Gemini, אבל מפתח שרת לא מוגדר. עבור ל-OCR מקומי או הגדר
            GEMINI_API_KEY / GOOGLE_API_KEY בסביבת השרת.
          </p>
        ) : null}
      </aside>
    </section>
  );
}

function HomePage() {
  return (
    <>
      <main className="hero-grid">
        <section className="hero-card">
          <p className="hero-kicker">React migration in progress</p>
          <h2>Now route-based for AI Studio app flows.</h2>
          <p className="hero-copy">
            The root app now uses React routes. Builder and player are exposed under dedicated routes while
            preserving the current legacy implementation during migration.
          </p>

          <div className="cta-row">
            <Link className="primary-btn" to="/builder">
              Open Builder Route
            </Link>
            <Link className="secondary-btn" to="/player">
              Open Player Route
            </Link>
          </div>
        </section>

        <aside className="stack-card">
          <div className="panel-title">What changed</div>
          <div className="feature-list">
            {features.map((feature) => (
              <article key={feature.title} className="feature-item">
                <h3>{feature.title}</h3>
                <p>{feature.description}</p>
              </article>
            ))}
          </div>
        </aside>
      </main>

      <section className="link-grid">
        {links.map((link) => {
          const isInternal = link.href.startsWith('/');
          if (isInternal) {
            return (
              <Link key={link.href} className="link-card" to={link.href}>
                <strong>{link.label}</strong>
                <span>{link.description}</span>
              </Link>
            );
          }

          return (
            <a key={link.href} className="link-card" href={link.href}>
              <strong>{link.label}</strong>
              <span>{link.description}</span>
            </a>
          );
        })}
      </section>

      <section className="notes-card">
        <div className="panel-title">AI Studio upload notes</div>
        <ul>
          <li>React is the default web-app framework in AI Studio Build mode.</li>
          <li>Gemini secrets should move to server-side runtime code in the next step.</li>
          <li>Builder and player are now reachable from React routes without removing legacy pages yet.</li>
        </ul>
      </section>
    </>
  );
}

function App() {
  return (
    <div className="shell">
      <div className="orb orb-a" />
      <div className="orb orb-b" />

      <ShellHeader />

      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/builder" element={<BuilderPage />} />
        <Route
          path="/player"
          element={
            <LegacyEmbed
              title="Quiz Player"
              src="/quiz_taker.html"
              description="The legacy quiz taker is exposed under a React route while player components are migrated later."
            />
          }
        />
        <Route path="*" element={<HomePage />} />
      </Routes>
    </div>
  );
}

export default App;