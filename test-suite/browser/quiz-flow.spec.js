const { test, expect } = require('@playwright/test');

const questions = [
    {
        question: 'שאלת בדיקה',
        options: ['תשובה ראשונה', 'תשובה שנייה'],
        correctIndex: 0
    }
];

async function importQuestions(page) {
    await page.goto('/index.html');
    await page.locator('#json-file').setInputFiles({
        name: 'questions.json',
        mimeType: 'application/json',
        buffer: Buffer.from(JSON.stringify(questions))
    });
    await expect(page.locator('.question-card')).toHaveCount(1);
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
    expect(exportedHtml).toContain('<script>');
    expect(exportedHtml).not.toContain('<script src="app.js"></script>');
});

test('standalone player loads embedded questions and persists answers', async ({ page }) => {
    await page.goto('/quiz_player.html');
    await page.evaluate((data) => {
        document.getElementById('quiz-data').textContent = JSON.stringify(data);
    }, questions);
    await page.reload();

    await page.locator('#start-btn').click();
    await expect(page.locator('#quiz-screen')).toHaveClass(/active/);
    await page.locator('.option').first().click();
    await page.reload();

    await expect(page.locator('#resume-notice')).not.toHaveClass(/hidden/);
});
