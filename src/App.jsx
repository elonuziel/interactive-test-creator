import React from 'react';

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
    href: 'quiz_generator.html',
    label: 'Open Quiz Builder',
    description: 'Use the existing upload + OCR builder.'
  },
  {
    href: 'quiz_taker.html',
    label: 'Open Quiz Taker',
    description: 'Launch the preserved quiz player.'
  },
  {
    href: 'README.md',
    label: 'Read Migration Notes',
    description: 'See how this repo is structured for AI Studio.'
  }
];

function App() {
  return (
    <div className="shell">
      <div className="orb orb-a" />
      <div className="orb orb-b" />

      <header className="topbar">
        <div>
          <p className="eyebrow">Google AI Studio build target</p>
          <h1>Interactive Hebrew Quiz Generator</h1>
        </div>
        <a className="ghost-link" href="quiz_generator.html">
          Open Builder
        </a>
      </header>

      <main className="hero-grid">
        <section className="hero-card">
          <p className="hero-kicker">React migration in progress</p>
          <h2>Ready to upload to AI Studio as a React app.</h2>
          <p className="hero-copy">
            The root entry is now a React shell. The original quiz player is preserved as a legacy page, and the
            builder remains available while the app is refactored for AI Studio's full-stack workflow.
          </p>

          <div className="cta-row">
            <a className="primary-btn" href="quiz_generator.html">
              Launch Builder
            </a>
            <a className="secondary-btn" href="quiz_taker.html">
              Launch Quiz Taker
            </a>
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
        {links.map((link) => (
          <a key={link.href} className="link-card" href={link.href}>
            <strong>{link.label}</strong>
            <span>{link.description}</span>
          </a>
        ))}
      </section>

      <section className="notes-card">
        <div className="panel-title">AI Studio upload notes</div>
        <ul>
          <li>React is the default web-app framework in AI Studio Build mode.</li>
          <li>Gemini secrets should move to server-side runtime code in the next step.</li>
          <li>This repo now has a clean root React entry plus preserved legacy HTML pages.</li>
        </ul>
      </section>
    </div>
  );
}

export default App;