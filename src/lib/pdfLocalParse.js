import { normalizeWhitespace, stripExamFooterArtifacts } from './quizParsing';

let cachedPdfJsLib = null;

async function loadPdfJsLib() {
  if (cachedPdfJsLib) return cachedPdfJsLib;

  const mod = await import('/vendor/pdfjs/pdf.min.mjs');
  const pdfjsLib = mod.default || mod;
  if (pdfjsLib?.GlobalWorkerOptions) {
    pdfjsLib.GlobalWorkerOptions.workerSrc = '/vendor/pdfjs/pdf.worker.min.mjs';
  }

  cachedPdfJsLib = pdfjsLib;
  return cachedPdfJsLib;
}

function fixHebrewWordOrder(text) {
  return String(text || '')
    .split('\n')
    .map((line) => {
      const trimmed = line.trim();
      if (!trimmed) return '';
      return trimmed.split(/\s+/).reverse().join(' ');
    })
    .join('\n');
}

function maybeFixHebrewWordOrder(text) {
  const lines = String(text || '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .slice(0, 200);

  if (!lines.length) return String(text || '');

  let normalSignals = 0;
  let reversedSignals = 0;

  for (const line of lines) {
    if (/שאלה\s+מספר|מבחן\s+מס/.test(line)) normalSignals++;
    if (/מספר\s+שאלה|מס\s+מבחן/.test(line)) reversedSignals++;
  }

  return reversedSignals > normalSignals ? fixHebrewWordOrder(text) : String(text || '');
}

function groupPdfTextItemsToLines(items) {
  const normalized = items
    .filter((item) => item.str && item.str.trim())
    .map((item) => ({ text: item.str.trim(), x: item.transform[4], y: item.transform[5] }));

  normalized.sort((a, b) => {
    if (Math.abs(a.y - b.y) > 2) return b.y - a.y;
    return a.x - b.x;
  });

  const lines = [];
  for (const item of normalized) {
    const line = lines.find((candidate) => Math.abs(candidate.y - item.y) <= 2);
    if (!line) {
      lines.push({ y: item.y, chunks: [item] });
    } else {
      line.chunks.push(item);
    }
  }

  lines.sort((a, b) => b.y - a.y);
  return lines.map((line) => line.chunks.sort((a, b) => a.x - b.x).map((chunk) => chunk.text).join(' '));
}

export async function extractPdfTextDigital(arrayBuffer) {
  const pdfjsLib = await loadPdfJsLib();
  const loadingTask = pdfjsLib.getDocument({ data: arrayBuffer });
  const pdf = await loadingTask.promise;

  const pages = [];
  let nonWhitespaceChars = 0;

  for (let pageNumber = 1; pageNumber <= pdf.numPages; pageNumber++) {
    const page = await pdf.getPage(pageNumber);
    const textContent = await page.getTextContent();
    const lineText = groupPdfTextItemsToLines(textContent.items).join('\n');
    pages.push(lineText);
    nonWhitespaceChars += lineText.replace(/\s/g, '').length;
  }

  return {
    numPages: pdf.numPages,
    isScanned: nonWhitespaceChars < Math.max(pdf.numPages * 60, 120),
    text: maybeFixHebrewWordOrder(pages.join('\n')),
    rawPages: pages
  };
}

export function parseQuestionsFromText(text, rawPages) {
  const lines = String(text || '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  const filteredLinePageMap = [];
  if (Array.isArray(rawPages) && rawPages.length) {
    rawPages.forEach((pageText, pageIdx) => {
      const processedLines = maybeFixHebrewWordOrder(pageText || '')
        .split('\n')
        .map((l) => l.trim())
        .filter(Boolean);
      for (let i = 0; i < processedLines.length; i++) {
        filteredLinePageMap.push(pageIdx);
      }
    });
  }

  const qPattern = /(?:שאלה\s+(?:מספר\s*)?:?\s*\d+\s*:?|\d+\s*:?\s*מספר\s+שאלה|^\.?\s*\d+\s*[\.\)]\s+(?![אבגדהוזחטי]\s*$)|^\.?\s*\d+\s*-\s+(?![אבגדהוזחטי]\s*$))/;
  const ansPatternStart = /^([אבגדהוזחטי1-9])\s*[\.]\s*(.*)$|^([אבגדהוזחטי1-9])[\)]\s*(.*)$|^[\.]\s*([אבגדהוזחטי])\s*(.*)$/;
  const ansPatternEnd = /^(.*)\s+([אבגדהוזחטי1-9])\s*[\.\)]$|^(.*)\s+[\.]\s*([אבגדהוזחטי])$/;
  const noisePattern = /^עמוד\s+\d+\s+מתוך\s+\d+$/;
  const footerPattern = /^-+\s*סוף\s+המבחן\s*-+$/;

  const rawQuestions = [];
  let current = null;
  let stateMode = 0;

  function pushCurrent() {
    if (!current) return;
    rawQuestions.push(current);
    current = null;
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (!line || noisePattern.test(line) || line.includes('קוד מבחן') || line.includes('מבחן מס')) continue;

    const reversedLine = line.split(/\s+/).reverse().join(' ');
    if (footerPattern.test(line) || footerPattern.test(reversedLine)) continue;

    if (qPattern.test(line) || qPattern.test(reversedLine)) {
      pushCurrent();
      current = { text: [], answers: [], lineIdx: i };
      stateMode = 1;
      continue;
    }

    if (!current) continue;

    const match = line.match(ansPatternStart) || reversedLine.match(ansPatternStart);
    const endMatch = !match && (line.match(ansPatternEnd) || reversedLine.match(ansPatternEnd));

    if (match || endMatch) {
      stateMode = 2;
      let letter;
      let answerText;

      if (match) {
        letter = match[1] || match[3] || match[5];
        answerText = (match[2] || match[4] || match[6] || '').trim();
      } else {
        letter = endMatch[2] || endMatch[4];
        answerText = (endMatch[1] || '').trim();
      }

      if (!letter) continue;
      current.answers.push({ text: answerText ? [answerText] : [] });
      continue;
    }

    if (stateMode === 1) {
      current.text.push(line);
    } else if (stateMode === 2 && current.answers.length > 0) {
      current.answers[current.answers.length - 1].text.push(line);
    }
  }

  pushCurrent();

  const formatted = rawQuestions
    .map((q) => {
      const question = normalizeWhitespace(stripExamFooterArtifacts(q.text.join(' ')));
      const options = q.answers
        .map((a) => normalizeWhitespace(stripExamFooterArtifacts(a.text.join(' '))))
        .filter(Boolean);
      const pageIdx = filteredLinePageMap[q.lineIdx] ?? 0;
      return { question, options, correctIndex: 0, sourcePage: pageIdx + 1 };
    })
    .filter((q) => q.question && q.options.length >= 2);

  if (!formatted.length) {
    throw new Error('לא נמצאו שאלות בפורמט הנתמך.');
  }

  return formatted;
}

export function mergeAnswers(questions, answerMap) {
  return questions.map((question, index) => {
    const answer = answerMap.get(index + 1);
    if (typeof answer === 'number' && answer >= 0 && answer < question.options.length) {
      return { ...question, correctIndex: answer, shuffleOptions: false };
    }
    return { ...question, shuffleOptions: false };
  });
}
