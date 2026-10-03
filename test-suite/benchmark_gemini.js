const assert = require('assert');
const GeminiService = require('../js/gemini-service.js');

async function runBenchmark() {
    console.log('🚀 Running Gemini Service Chunk Processing Benchmark...\n');

    const imageDatas = Array.from({ length: 100 }, (_, i) => `image_data_page_${i + 1}`);
    const renderAllPdfPageImagesFn = async (pdf, task) => {
        return {
            imageDatas,
            pagePreviews: Array.from({ length: 100 }, (_, i) => `preview_${i + 1}`)
        };
    };

    const originalFetch = global.fetch;

    // Mock fetch with simulated 50ms delay per API HTTP request
    global.fetch = async (url, opts) => {
        await new Promise((res) => setTimeout(res, 50));
        return {
            ok: true,
            status: 200,
            headers: new Map(),
            json: async () => ({
                candidates: [{
                    content: {
                        parts: [{ text: 'Mock OCR page text result' }]
                    }
                }]
            })
        };
    };

    const dummyPdf = { numPages: 100 };
    const apiKey = 'test-api-key';

    const startTime = Date.now();
    const result = await GeminiService.extractTextViaGemini(dummyPdf, apiKey, {
        chunkSizeOverride: 20, // 100 / 20 = 5 chunks
        renderAllPdfPageImagesFn,
        maybeFixHebrewWordOrderFn: (s) => s
    });
    const durationMs = Date.now() - startTime;

    global.fetch = originalFetch;

    assert.strictEqual(result.pages.length, 5, '5 chunk responses returned');
    assert.strictEqual(result.pages[0], 'Mock OCR page text result');

    console.log(`⏱️ Benchmark execution time: ${durationMs}ms`);
    console.log(`📄 Total chunk pages processed: ${result.pages.length}`);
    return durationMs;
}

if (require.main === module) {
    runBenchmark().then((durationMs) => {
        console.log(`\nBaseline duration: ${durationMs}ms`);
    }).catch((err) => {
        console.error('Benchmark error:', err);
        process.exit(1);
    });
}

module.exports = { runBenchmark };
