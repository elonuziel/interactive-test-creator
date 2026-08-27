const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const QuizExport = require('../../quiz-export.js');

const questions = require('../fixtures/questions.json');
const fixturePath = path.resolve(__dirname, '../fixtures/questions.json');

async function writeStandaloneQuiz() {
    const [template, css, core, app] = await Promise.all([
        fs.promises.readFile(path.resolve(__dirname, '../../quiz_player.html'), 'utf8'),
        fs.promises.readFile(path.resolve(__dirname, '../../style.css'), 'utf8'),
        fs.promises.readFile(path.resolve(__dirname, '../../quiz-core.js'), 'utf8'),
        fs.promises.readFile(path.resolve(__dirname, '../../app.js'), 'utf8')
    ]);
    let html = QuizExport.injectStylesheet(template, css);
    html = QuizExport.injectInlineQuestions(html, questions);
    html = QuizExport.injectScript(html, 'quiz-core.js', core);
    html = QuizExport.injectScript(html, 'app.js', app);
    const outputPath = path.resolve(__dirname, '../fixtures/generated-quiz.html');
    await fs.promises.writeFile(outputPath, html, 'utf8');
    return outputPath;
}

async function importQuestions(page) {
    await page.goto('/index.html');
    await page.locator('#json-file').setInputFiles({
        name: path.basename(fixturePath),
        mimeType: 'application/json',
        buffer: Buffer.from(JSON.stringify(questions))
    });
    await expect(page.locator('.question-card')).toHaveCount(2);
}

test('builder imports and edits a question', async ({ page }) => {
    await importQuestions(page);

    const questionInput = page.locator('.question-card textarea').first();
    await questionInput.fill('שאלה שנערכה');
    await expect(questionInput).toHaveValue('שאלה שנערכה');

    const optionInput = page.locator('.question-card .option-row input[type="text"]').first();
    await optionInput.fill('תשובה שנערכה');
    await expect(optionInput).toHaveValue('תשובה שנערכה');
});

test('builder exports a standalone quiz with embedded questions', async ({ page }) => {
    await importQuestions(page);

    const downloadPromise = page.waitForEvent('download');
    await page.locator('#download-quiz').click();
    await page.locator('#confirm-download-btn').click();
    const download = await downloadPromise;
    const exportedHtml = await require('fs').promises.readFile(await download.path(), 'utf8');

    expect(exportedHtml).toContain('id="quiz-data"');
    expect(exportedHtml).toContain('שאלת בדיקה');
    expect(exportedHtml).not.toContain('</script><script>alert');
    expect(exportedHtml).toContain('<script>');
    expect(exportedHtml).not.toContain('<script src="app.js"></script>');
});

test('welcome screen controls immediate feedback before starting', async ({ page }) => {
    const standalonePath = await writeStandaloneQuiz();
    await page.goto(`file://${standalonePath}`);

    await expect(page.locator('.welcome-feedback-toggle')).toBeVisible();
    await expect(page.locator('#immediate-feedback-toggle')).not.toBeChecked();

    await page.locator('.welcome-feedback-toggle').click();
    await expect(page.locator('#immediate-feedback-toggle')).toBeChecked();

    await page.locator('#start-btn').click();
    await expect(page.locator('#quiz-screen')).toHaveClass(/active/);
    await expect(page.locator('#immediate-feedback-toggle')).toBeChecked();
});

test('standalone player loads embedded questions and persists answers', async ({ page }) => {
    const standalonePath = await writeStandaloneQuiz();
    await page.goto(`file://${standalonePath}`);

    await page.locator('#start-btn').click();
    await expect(page.locator('#quiz-screen')).toHaveClass(/active/);
    await expect(page.locator('.option')).toHaveCount(2);
    await expect(page.locator('#question-text')).toBeFocused();
    await page.locator('.option').first().click();
    await page.reload();

    await expect(page.locator('#resume-notice')).not.toHaveClass(/hidden/);
});

test('builder exposes Freebuff actions with accessible explainer controls', async ({ page }) => {
    await page.goto('/index.html');

    await expect(page.locator('#freebuff-digital-btn')).toBeHidden();
    await expect(page.locator('#freebuff-scanned-btn')).toBeHidden();

    await page.evaluate(() => {
        document.getElementById('digital-actions-box')?.classList.remove('hidden');
    });

    await page.locator('#freebuff-digital-info').focus();
    await expect(page.locator('#freebuff-digital-info')).toHaveAttribute('aria-describedby', 'freebuff-digital-tooltip');
    await expect(page.locator('#freebuff-digital-tooltip')).toContainText('Freebuff');

    const popupPromise = page.waitForEvent('popup');
    await page.locator('#freebuff-digital-btn').click();
    const popup = await popupPromise;
    await expect(popup).toHaveURL('https://freebuff.com/chat');
    await popup.close();
});

test('builder blocks export while a question is invalid', async ({ page }) => {
    await importQuestions(page);
    await page.locator('.question-card textarea').first().fill('');

    await expect(page.locator('#validation-summary')).toContainText('שאלות לא תקינות');
    await expect(page.locator('.question-card').first()).toHaveClass(/is-invalid/);
    await expect(page.locator('#download-quiz')).toBeDisabled();
    await expect(page.locator('#take-quiz')).toBeDisabled();
});

