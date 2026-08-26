// Standalone quiz template helpers shared by the builder and export tests.
(function (root, factory) {
    if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.QuizExport = factory();
    }
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
    'use strict';

    function escapeScriptText(value) {
        return String(value).replace(/<\/(script)/gi, '<\\/$1');
    }

    function injectStylesheet(html, css) {
        const marker = '<link rel="stylesheet" href="style.css">';
        if (!html.includes(marker)) throw new Error('Quiz template is missing the stylesheet marker.');
        return html.replace(marker, `<style>${css}</style>`);
    }

    function injectInlineQuestions(html, questions) {
        const marker = '<script id="quiz-data" type="application/json"></script>';
        if (!html.includes(marker)) throw new Error('Quiz template is missing the quiz-data marker.');
        const payload = escapeScriptText(JSON.stringify(questions, null, 2));
        return html.replace(marker, `<script id="quiz-data" type="application/json">${payload}</script>`);
    }

    function setBuilderLink(html, href) {
        return html.replace(
            /<a\s+[^>]*id="builder-nav-link"[^>]*>[\s\S]*?<\/a>/i,
            `<a href="${href}" id="builder-nav-link" class="nav-link" title="פתח יוצר מבחן אונליין">יוצר מבחן אונליין ←</a>`
        );
    }

    function injectScript(html, scriptName, code) {
        const marker = `<script src="${scriptName}"></script>`;
        if (!html.includes(marker)) return html;
        const payload = escapeScriptText(code);
        return html.replace(marker, `<script>${payload}</script>`);
    }

    return { escapeScriptText, injectStylesheet, injectInlineQuestions, setBuilderLink, injectScript };
}));
