import express from 'express';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import fs from 'node:fs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const port = Number(process.env.PORT || 3000);

app.use(express.json({ limit: '60mb' }));

function getApiKey() {
    return process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY || '';
}

function getApiKeySource() {
    if (process.env.GEMINI_API_KEY) return 'GEMINI_API_KEY';
    if (process.env.GOOGLE_API_KEY) return 'GOOGLE_API_KEY';
    return null;
}

function parseErrorMessage(raw) {
    if (!raw) return '';
    try {
        const parsed = JSON.parse(raw);
        return String(parsed?.error?.message || raw);
    } catch {
        return String(raw);
    }
}

app.get('/api/gemini/health', (req, res) => {
    const source = getApiKeySource();
    const configured = Boolean(source);
    res.status(200).json({
        ok: true,
        configured,
        keySource: source,
        message: configured
            ? `Gemini runtime key is configured via ${source}.`
            : 'Gemini runtime key is missing. Configure GEMINI_API_KEY or GOOGLE_API_KEY on the server runtime.'
    });
});

app.post('/api/gemini/generate-content', async (req, res) => {
    const apiKey = getApiKey();
    if (!apiKey) {
        res.status(500).send('Gemini API key is not configured on server (GEMINI_API_KEY or GOOGLE_API_KEY).');
        return;
    }

    const body = req.body || {};
    const contents = body.contents;
    const generationConfig = body.generationConfig || {};
    const requestedModels = Array.isArray(body.modelCandidates) ? body.modelCandidates : [];
    const modelCandidates = requestedModels.length
        ? requestedModels
        : ['gemini-3.5-flash', 'gemini-2.5-flash', 'gemini-2.0-flash'];
    const versions = ['v1', 'v1beta'];

    if (!Array.isArray(contents) || !contents.length) {
        res.status(400).send('Invalid payload: "contents" array is required.');
        return;
    }

    const failures = [];

    for (const model of modelCandidates) {
        for (const version of versions) {
            const endpoint = `https://generativelanguage.googleapis.com/${version}/models/${encodeURIComponent(model)}:generateContent?key=${encodeURIComponent(apiKey)}`;

            try {
                const upstream = await fetch(endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ contents, generationConfig })
                });

                if (upstream.ok) {
                    const payload = await upstream.json();
                    res.status(200).json(payload);
                    return;
                }

                const errorText = await upstream.text();
                failures.push(`${version}/${model}: ${upstream.status} ${parseErrorMessage(errorText)}`);

                if (upstream.status === 401 || upstream.status === 403) {
                    res.status(upstream.status).send(parseErrorMessage(errorText));
                    return;
                }
            } catch (error) {
                failures.push(`${version}/${model}: network error ${error.message || String(error)}`);
            }
        }
    }

    res.status(502).send(`Gemini proxy failed for all candidates. ${failures.join(' | ')}`);
});

const distPath = path.join(__dirname, 'dist');
if (fs.existsSync(distPath)) {
    app.use(express.static(distPath));
    app.get('*', (req, res) => {
        res.sendFile(path.join(distPath, 'index.html'));
    });
}

app.listen(port, () => {
    // eslint-disable-next-line no-console
    console.log(`Server listening on http://localhost:${port}`);
});
