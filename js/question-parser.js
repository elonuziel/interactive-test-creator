(function (root, factory) {
    if (typeof define === 'function' && define.amd) {
        define([], factory);
    } else if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.QuestionParser = factory();
    }
}(typeof self !== 'undefined' ? self : this, function () {
    'use strict';

    function normalizeWhitespace(value) {
        return String(value || '').replace(/\u00A0/g, ' ').replace(/\s+/g, ' ').trim();
    }

    function stripExamFooterArtifacts(value) {
        if (!value) return '';
        return String(value)
            .replace(/\[cite:\s*\d+\]/gi, '')
            .replace(/-+\s*סוף\s+המבחן\s*-+/g, ' ');
    }

    function stripQuestionHeaderPrefix(value) {
        if (!value) return '';
        let t = String(value).replace(/^#+\s*/, '').trim();
        const prefixPattern = /^(?:(?:שאלה(?:\s+מספר)?\s*:?\s*:?\d+\s*:?|:?\d+\s*:?\s*(?:שאלה(?:\s+מספר)?|מספר\s+שאלה)|מספר\s+שאלה\s*:?\s*:?\d+\s*:?|\d+\s*[\.\)\(-])\s*)+:?\s*/i;
        const cleaned = t.replace(prefixPattern, '').trim();
        return cleaned || t;
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

        if (!lines.length) {
            return text;
        }

        let normalSignals = 0;
        let reversedSignals = 0;

        for (const line of lines) {
            if (/שאלה\s+מספר|מבחן\s+מס/.test(line)) {
                normalSignals++;
            }
            if (/מספר\s+שאלה|מס\s+מבחן/.test(line)) {
                reversedSignals++;
            }
        }

        const strongReversedEvidence = reversedSignals >= 4 && reversedSignals >= (normalSignals + 2);
        return strongReversedEvidence ? fixHebrewWordOrder(text) : text;
    }

    function parseQuestionsFromMarkdown(markdownText) {
        if (!markdownText) return [];

        let cleanText = String(markdownText).trim();
        cleanText = cleanText.replace(/^```(?:markdown|md|txt)?\s*/i, '').replace(/\s*```$/i, '').trim();
        if (!cleanText) return [];

        const lines = cleanText.split(/\r?\n/);
        const headerRe = /^###\s*שאלה\s*(\d{1,3})\s*:\s*(.+?)\s*(?:\((?:עמוד|עמ'|page)\s*(\d{1,3})\))?\s*$/i;
        const optionRe = /^[-*+]\s*([אבגדהוזחטי])\.\s*(.+)$/;

        const parsed = [];
        let current = null;

        function pushCurrentIfValid() {
            if (!current) return;
            const questionText = normalizeWhitespace(String(current.question || ''));
            const options = (current.options || []).map((opt) => normalizeWhitespace(String(opt || ''))).filter(Boolean);
            if (questionText && options.length >= 2) {
                parsed.push({
                    question: questionText,
                    options,
                    correctIndex: 0,
                    sourcePage: current.sourcePage || 1
                });
            }
        }

        for (const rawLine of lines) {
            const line = String(rawLine || '').trim();
            if (!line) continue;

            const headerMatch = line.match(headerRe);
            if (headerMatch) {
                pushCurrentIfValid();
                current = {
                    question: normalizeWhitespace(headerMatch[2] || ''),
                    options: [],
                    sourcePage: Number(headerMatch[3]) || 1
                };
                continue;
            }

            if (!current) continue;

            const optionMatch = line.match(optionRe);
            if (optionMatch) {
                current.options.push(optionMatch[2] || '');
                continue;
            }

            if (current.options.length > 0) {
                const lastIdx = current.options.length - 1;
                current.options[lastIdx] = `${current.options[lastIdx]} ${line}`.trim();
            } else {
                current.question = `${current.question} ${line}`.trim();
            }
        }

        pushCurrentIfValid();
        return parsed;
    }

    function parseQuestionsFromText(text, rawPages = null, pageImages = null, callbacks = {}) {
        if (!text) return [];

        let cleanText = String(text).trim();
        cleanText = cleanText.replace(/^```(?:markdown|md|json|txt)?\s*/i, '').replace(/\s*```$/i, '').trim();

        if (cleanText.startsWith('[') || cleanText.startsWith('{')) {
            try {
                const parsed = JSON.parse(cleanText);
                const questionsArray = Array.isArray(parsed) ? parsed : (parsed.questions || parsed.data);
                if (Array.isArray(questionsArray) && questionsArray.length > 0) {
                    return normalizeQuestionsJson(questionsArray);
                }
            } catch (e) {
                console.warn('JSON parse attempt failed, falling back to line-by-line parser:', e);
            }
        }

        const lines = cleanText.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
        const filteredLinePageMap = [];
        if (rawPages && rawPages.length) {
            rawPages.forEach((pageText, pageIdx) => {
                const processedLines = maybeFixHebrewWordOrder(pageText || '')
                    .split('\n')
                    .map(l => l.trim())
                    .filter(Boolean);
                for (let i = 0; i < processedLines.length; i++) {
                    filteredLinePageMap.push(pageIdx);
                }
            });
        }
        const qPatternTextual = /(?:^#*\s*(?:\*\*)?שאלה\s+(?:מספר\s*)?:?\s*:?\d+\s*:?|^#*\s*(?:\*\*)?:?\d+\s*:?\s*מספר\s+שאלה)/i;
        const qPatternNumeric = /(?:^\.?\s*#*\s*(?:\*\*)?\s*[\(\[]?\s*:?\d+\s*[\.\)\(\-\]]?\s+(?![אבגדהוזחטי]\s*$))/i;
        const qNumericCapture = /^\.?\s*#*\s*(?:\*\*)?\s*[\(\[]?\s*:?\s*(\d{1,3})\s*[\.\)\(\-\]]?\s+/i;
        const ansPatternStart = /^(?:[-\*\+\u2022]\s*)?(?:\*\*)?[\(\[]?([אבגדהוזחטיa-e1-9])\s*[\)\]\.]\s*(?:\*\*)?\s*(.*)$|^[\.]\s*([אבגדהוזחטי])\s*(.*)$/i;
        const ansPatternEnd = /^(.*)\s+([אבגדהוזחטי1-9])\s*[\.\)]$|^(.*)\s+[\.]\s*([אבגדהוזחטי])$/;
        const ansInlineGlobal = /(?:^|[\s\u2022\-\*\+\(\[])([אבגדהוזחטי])\s*[\.\)]\s*/g;
        const noisePattern = /^עמוד\s+\d+\s+מתוך\s+\d+$/;
        const footerPattern = /^-+\s*סוף\s+המבחן\s*-+$/;
        const qInlineLocator = /\s(#*\s*(?:שאלה\s+(?:מספר\s*)?:?\s*:?\d+\s*:?|[\(\[]?\s*:??\d+\s*[\)\(\.-\]]?)\s+)/i;
        const hebOptionOrder = { 'א': 1, 'ב': 2, 'ג': 3, 'ד': 4, 'ה': 5, 'ו': 6, 'ז': 7, 'ח': 8, 'ט': 9 };

        function parseInlineAnswers(lineText) {
            if (!lineText) return null;

            const matches = [];
            ansInlineGlobal.lastIndex = 0;
            let m;
            while ((m = ansInlineGlobal.exec(lineText)) !== null) {
                matches.push({
                    letter: m[1],
                    markerStart: m.index,
                    textStart: ansInlineGlobal.lastIndex
                });
            }

            if (!matches.length) return null;

            const prefix = lineText.slice(0, matches[0].markerStart).trim();
            const hasOnlyTrivialPrefix = /^[-\*\+\u2022\(\[\]\)\.:\s]*$/.test(prefix);

            if (matches.length < 2 && hasOnlyTrivialPrefix) {
                return null;
            }

            if (matches.length >= 2) {
                let prevOrder = 0;
                let jumps = 0;
                for (const mm of matches) {
                    const ord = hebOptionOrder[mm.letter] || 0;
                    if (!ord) return null;
                    if (prevOrder > 0) {
                        const delta = ord - prevOrder;
                        if (delta <= 0) return null;
                        if (delta > 2) jumps++;
                    }
                    prevOrder = ord;
                }
                if (jumps > 0) return null;
            }

            const options = [];
            for (let k = 0; k < matches.length; k++) {
                const cur = matches[k];
                const next = matches[k + 1];
                const textEnd = next ? next.markerStart : lineText.length;
                const optionText = lineText.slice(cur.textStart, textEnd).trim();
                options.push({ letter: cur.letter, text: optionText });
            }

            if (options.length === 1 && !prefix) {
                return null;
            }

            return { prefix, options };
        }

        function splitInlineQuestionHeader(lineText) {
            if (!lineText) return null;
            const m = lineText.match(qInlineLocator);
            if (!m || typeof m.index !== 'number') return null;
            const markerStart = m.index + 1;
            if (markerStart <= 0 || markerStart >= lineText.length) return null;
            return {
                before: lineText.slice(0, markerStart).trim(),
                after: lineText.slice(markerStart).trim()
            };
        }

        function splitAnswerLineWithEmbeddedHeader(lineText) {
            if (!lineText) return null;
            const ansStart = lineText.match(/^(\s*(?:[-\*\+\u2022]\s*)?[אבגדהוזחטי]\s*[\.)]\s*)(.*)$/);
            if (!ansStart) return null;

            const prefix = ansStart[1] || '';
            const body = (ansStart[2] || '').trim();
            if (!body) return null;

            const headerTailRe1 = /([\?？][^\n]*[\)\(]\s*\d{1,3}\s*)$/;
            const headerTailRe2 = /((?:על\s+פי|מהו|מה\s+יהיה|איזו|ממה|מטעמי|הינך|היכן|כיצד)[^\n]*[\)\(]\s*\d{1,3}\s*)$/;
            const m = body.match(headerTailRe1) || body.match(headerTailRe2);
            if (!m) return null;

            const headerPart = (m[1] || '').trim();
            if (!headerPart || headerPart.length < 8) return null;

            const cutIdx = body.lastIndexOf(headerPart);
            if (cutIdx <= 0) return null;

            const optionPart = body.slice(0, cutIdx).trim();
            if (!optionPart) return null;

            let optionClean = optionPart;
            let headerRaw = headerPart;

            const qMarkIdx = optionClean.lastIndexOf('?');
            if (qMarkIdx > 0 && (optionClean.length - qMarkIdx) <= 120) {
                headerRaw = `${optionClean.slice(qMarkIdx).trim()} ${headerRaw}`.trim();
                optionClean = optionClean.slice(0, qMarkIdx).trim();
            }

            if (!optionClean) return null;

            let normalizedHeader = headerRaw;
            if (!extractNumericHeaderNumber(normalizedHeader)) {
                const rev = normalizedHeader.split(/\s+/).reverse().join(' ');
                if (extractNumericHeaderNumber(rev) || qPatternNumeric.test(rev) || qPatternTextual.test(rev)) {
                    normalizedHeader = rev;
                }
            }

            return {
                optionLine: `${prefix}${optionClean}`.trim(),
                headerLine: normalizedHeader
            };
        }

        function preprocessEmbeddedHeaders(inputLines) {
            const out = [];
            const source = [];
            for (let i = 0; i < inputLines.length; i++) {
                const line = String(inputLines[i] || '').trim();
                if (!line) continue;
                const split = splitAnswerLineWithEmbeddedHeader(line);
                if (split) {
                    if (split.optionLine) {
                        out.push(split.optionLine.trim());
                        source.push(i);
                    }
                    if (split.headerLine) {
                        out.push(split.headerLine.trim());
                        source.push(i);
                    }
                } else {
                    out.push(line);
                    source.push(i);
                }
            }
            return { lines: out, sourceIdx: source };
        }

        function normalizeEmbeddedHeaderText(headerText) {
            let t = normalizeWhitespace(String(headerText || ''));
            t = t.replace(/^[:\-–—\s]+/, '').trim();

            let m = t.match(/^(.*?)[\)\(]\s*(\d{1,3})\s*$/);
            if (m) {
                return normalizeWhitespace(`${m[2]}) ${m[1].trim()}`);
            }

            m = t.match(/^(.*?)(\d{1,3})\s*\)\s*$/);
            if (m) {
                return normalizeWhitespace(`${m[2]}) ${m[1].trim()}`);
            }

            m = t.match(/^(.*?)(\d{1,2})\s+(\d{1,2})\s*\)\s*$/);
            if (m) {
                return normalizeWhitespace(`${m[2]}${m[3]}) ${m[1].trim()}`);
            }

            return t;
        }

        function extractEmbeddedHeaderFromOptionText(optionText) {
            const t = normalizeWhitespace(String(optionText || ''));
            if (!t) return null;

            const cueWords = /(?:על\s+פי|מהו|מה\s+יהיה|איזו|ממה|מטעמי|הינך|היכן|כיצד|מהם|מה\s+החשיבות|איזה\s+מערכת)/;
            const numberMarkers = /(?:\)\s*\d{1,3}|\d{1,3}\s*\)|\d{1,2}\s+\d{1,2}\s*\))/g;

            let marker;
            while ((marker = numberMarkers.exec(t)) !== null) {
                const start = marker.index;
                const before = normalizeWhitespace(t.slice(0, start));
                const after = normalizeWhitespace(t.slice(start));
                if (!before || !after || after.length < 8) continue;
                if (!/[\?？]/.test(after) && !cueWords.test(after)) continue;
                const header = normalizeEmbeddedHeaderText(after);
                if (!header) continue;
                return { before, header };
            }

            const cueMatch = t.match(/(?:על\s+פי|מהו|מה\s+יהיה|איזו|ממה|מטעמי|הינך|היכן|כיצד|מהם|מה\s+החשיבות|איזה\s+מערכת)/);
            if (cueMatch && typeof cueMatch.index === 'number' && cueMatch.index > 4) {
                const before = normalizeWhitespace(t.slice(0, cueMatch.index));
                const after = normalizeWhitespace(t.slice(cueMatch.index));
                if (before && after && /(?:\)\s*\d{1,3}|\d{1,3}\s*\)|\d{1,2}\s+\d{1,2}\s*\))/.test(after)) {
                    const header = normalizeEmbeddedHeaderText(after);
                    if (header) return { before, header };
                }
            }

            return null;
        }

        function splitMergedQuestions(rawQs) {
            const out = [];

            for (const q of rawQs) {
                if (!q || !Array.isArray(q.answers) || q.answers.length <= 6) {
                    out.push(q);
                    continue;
                }

                let current = {
                    text: Array.isArray(q.text) ? [...q.text] : [String(q.text || '')],
                    answers: [],
                    lineIdx: q.lineIdx
                };

                for (const a of q.answers) {
                    const optionText = normalizeWhitespace(Array.isArray(a.text) ? a.text.join(' ') : String(a.text || ''));
                    const split = extractEmbeddedHeaderFromOptionText(optionText);

                    if (split) {
                        current.answers.push({ text: [split.before] });
                        out.push(current);
                        current = {
                            text: [split.header],
                            answers: [],
                            lineIdx: q.lineIdx
                        };
                    } else {
                        current.answers.push({ text: optionText ? [optionText] : [] });
                    }
                }

                if (current.text.length || current.answers.length) {
                    out.push(current);
                }
            }

            return out;
        }

        function splitCorruptedMergedOptions(rawQs) {
            const out = [];

            for (const q of rawQs) {
                if (!q || !Array.isArray(q.answers)) {
                    out.push(q);
                    continue;
                }

                const nextAnswers = [];
                for (const a of q.answers) {
                    const t = normalizeWhitespace(Array.isArray(a.text) ? a.text.join(' ') : String(a.text || ''));
                    const m = t.match(/^(.*?[\.!?])\s*\.?\s*\d+\s+(.+?)\s*[\.]\s*([אבגדהוזחטי])\s*$/);
                    if (m) {
                        const first = normalizeWhitespace(m[1]);
                        const second = normalizeWhitespace(m[2]);
                        if (first) nextAnswers.push({ text: [first] });
                        if (second) nextAnswers.push({ text: [second] });
                    } else {
                        nextAnswers.push({ text: t ? [t] : [] });
                    }
                }

                out.push({ ...q, answers: nextAnswers });
            }

            return out;
        }

        function expandInlineQuestionLines(inputLines) {
            const expanded = [];
            const sourceIdx = [];

            for (let i = 0; i < inputLines.length; i++) {
                const original = String(inputLines[i] || '').trim();
                if (!original) continue;

                const embeddedSplit = splitAnswerLineWithEmbeddedHeader(original);
                if (embeddedSplit) {
                    const first = embeddedSplit.optionLine.trim();
                    const second = embeddedSplit.headerLine.trim();
                    if (first) {
                        expanded.push(first);
                        sourceIdx.push(i);
                    }
                    if (second) {
                        expanded.push(second);
                        sourceIdx.push(i);
                    }
                    continue;
                }

                let segment = original;
                let guard = 0;

                while (segment && guard < 6) {
                    guard++;
                    const split = splitInlineQuestionHeader(segment);
                    if (!split || !split.after) {
                        expanded.push(segment.trim());
                        sourceIdx.push(i);
                        break;
                    }

                    const splitRev = split.after.split(/\s+/).reverse().join(' ');
                    const splitIsHeader = qPatternTextual.test(split.after) || qPatternNumeric.test(split.after)
                        || qPatternTextual.test(splitRev) || qPatternNumeric.test(splitRev);

                    if (!splitIsHeader) {
                        expanded.push(segment.trim());
                        sourceIdx.push(i);
                        break;
                    }

                    if (split.before) {
                        expanded.push(split.before.trim());
                        sourceIdx.push(i);
                    }

                    segment = split.after.trim();
                }
            }

            return { expanded, sourceIdx };
        }

        function extractNumericHeaderNumber(lineText) {
            if (!lineText) return null;
            const m = lineText.match(qNumericCapture);
            if (!m) return null;
            const n = Number(m[1]);
            return Number.isFinite(n) ? n : null;
        }

        function buildStrictNumericBlocks(inputLines) {
            const strictHeaderRe = /^\s*(\d{1,3})\s*[\(\)\.\-]\s*/;
            const optionStartRe = /^(?:[-\*\+\u2022]\s*)?([אבגדהוזחטי])\s*[\.)]\s*(.*)$/;

            const headers = [];
            for (let i = 0; i < inputLines.length; i++) {
                const line = String(inputLines[i] || '').trim();
                if (!line) continue;
                const m = line.match(strictHeaderRe);
                if (m) {
                    headers.push({ idx: i, num: Number(m[1]) });
                }
            }

            if (headers.length < 12) {
                return null;
            }

            let sequentialHits = 0;
            for (let i = 1; i < headers.length; i++) {
                const d = headers[i].num - headers[i - 1].num;
                if (d === 1 || d === 2) sequentialHits++;
            }
            const sequentialRatio = headers.length > 1 ? (sequentialHits / (headers.length - 1)) : 0;
            if (sequentialRatio < 0.65) {
                return null;
            }

            const out = [];
            for (let h = 0; h < headers.length; h++) {
                const start = headers[h].idx;
                const end = h + 1 < headers.length ? headers[h + 1].idx : inputLines.length;
                const block = inputLines.slice(start, end).map((l) => String(l || '').trim()).filter(Boolean);
                if (!block.length) continue;

                const qObj = { text: [block[0]], answers: [], lineIdx: start };
                for (let bi = 1; bi < block.length; bi++) {
                    const line = block[bi];
                    const m = line.match(optionStartRe);
                    if (m) {
                        const t = (m[2] || '').trim();
                        qObj.answers.push({ text: t ? [t] : [] });
                        continue;
                    }

                    if (qObj.answers.length > 0) {
                        qObj.answers[qObj.answers.length - 1].text.push(line);
                    } else {
                        qObj.text.push(line);
                    }
                }

                out.push(qObj);
            }

            return out;
        }

        function detectQuestionHeaderNumber(lineText) {
            if (!lineText) return null;
            const textual = lineText.match(/שאלה(?:\s+מספר)?\s*:?[\s:]*?(\d{1,3})/i);
            if (textual) {
                const n = Number(textual[1]);
                if (Number.isFinite(n)) return n;
            }
            return extractNumericHeaderNumber(lineText);
        }

        const preprocessed = preprocessEmbeddedHeaders(lines);
        const baseLines = preprocessed.lines;
        const baseSourceIdx = preprocessed.sourceIdx;

        const strictBlocks = buildStrictNumericBlocks(baseLines);
        const useStrictNumericMode = Array.isArray(strictBlocks) && strictBlocks.length >= 20;
        const { expanded: workingLines, sourceIdx: workingLineSourceIdx } = useStrictNumericMode
            ? { expanded: baseLines, sourceIdx: baseSourceIdx }
            : expandInlineQuestionLines(baseLines);

        const rawQuestions = [];
        const headerIndices = [];

        if (useStrictNumericMode) {
            rawQuestions.push(...strictBlocks);
        } else {
            let lastHeaderNum = null;
            for (let i = 0; i < workingLines.length; i++) {
                const line = workingLines[i];
                if (!line || noisePattern.test(line) || line.includes('קוד מבחן') || line.includes("מבחן מס") || line.includes('מבחן מס')) {
                    continue;
                }
                const reversedLine = line.split(/\s+/).reverse().join(' ');
                if (footerPattern.test(line) || footerPattern.test(reversedLine)) {
                    continue;
                }
                const textualHeader = qPatternTextual.test(line) || qPatternTextual.test(reversedLine);
                const directNumeric = extractNumericHeaderNumber(line);
                const reverseNumeric = extractNumericHeaderNumber(reversedLine);

                let numericCandidate = directNumeric;
                if (!Number.isFinite(numericCandidate) && Number.isFinite(reverseNumeric)) {
                    numericCandidate = reverseNumeric;
                }

                let numericHeader = false;
                if (Number.isFinite(numericCandidate) && numericCandidate >= 1 && numericCandidate <= 300) {
                    if (!Number.isFinite(lastHeaderNum)) {
                        numericHeader = numericCandidate <= 80;
                    } else {
                        const delta = numericCandidate - lastHeaderNum;
                        numericHeader = delta === 1 || delta === 2;
                    }
                }

                const isQuestionHeader = textualHeader || numericHeader;
                if (isQuestionHeader) {
                    headerIndices.push(i);
                    const detectedNum = detectQuestionHeaderNumber(line) || detectQuestionHeaderNumber(reversedLine);
                    if (Number.isFinite(detectedNum)) {
                        lastHeaderNum = detectedNum;
                    }
                }
            }

            for (let h = 0; h < headerIndices.length; h++) {
                const startIdx = headerIndices[h];
                const endIdx = h + 1 < headerIndices.length ? headerIndices[h + 1] : workingLines.length;
                const blockLines = workingLines.slice(startIdx, endIdx);
                if (!blockLines.length) continue;

                const q = {
                    text: [blockLines[0]],
                    answers: [],
                    lineIdx: Number.isInteger(workingLineSourceIdx[startIdx]) ? workingLineSourceIdx[startIdx] : startIdx
                };

                for (let bi = 1; bi < blockLines.length; bi++) {
                    let line = blockLines[bi];
                    if (!line || noisePattern.test(line) || line.includes('קוד מבחן') || line.includes("מבחן מס") || line.includes('מבחן מס')) {
                        continue;
                    }

                    const reversedLine = line.split(/\s+/).reverse().join(' ');
                    if (footerPattern.test(line) || footerPattern.test(reversedLine)) {
                        continue;
                    }

                    const qSplit = splitInlineQuestionHeader(line);
                    const qSplitReversed = qSplit && qSplit.after ? qSplit.after.split(/\s+/).reverse().join(' ') : '';
                    const qSplitIsHeader = qSplit && qSplit.after && (
                        qPatternTextual.test(qSplit.after)
                        || qPatternTextual.test(qSplitReversed)
                        || qPatternNumeric.test(qSplit.after)
                        || qPatternNumeric.test(qSplitReversed)
                    );
                    if (qSplitIsHeader) {
                        if (qSplit.before) {
                            if (q.answers.length > 0) {
                                q.answers[q.answers.length - 1].text.push(qSplit.before);
                            } else {
                                q.text.push(qSplit.before);
                            }
                        }
                        break;
                    }

                    const inlineParsed = parseInlineAnswers(line);
                    if (inlineParsed && inlineParsed.options.length) {
                        if (inlineParsed.prefix) {
                            if (q.answers.length > 0) {
                                q.answers[q.answers.length - 1].text.push(inlineParsed.prefix);
                            } else {
                                q.text.push(inlineParsed.prefix);
                            }
                        }
                        for (const opt of inlineParsed.options) {
                            q.answers.push({ text: opt.text ? [opt.text] : [] });
                        }
                        continue;
                    }

                    const isLineStartMatch = ansPatternStart.test(line);
                    let match = line.match(ansPatternStart) || reversedLine.match(ansPatternStart);
                    const isLineEndMatch = !match && ansPatternEnd.test(line);
                    let endMatch = (!match) && (line.match(ansPatternEnd) || reversedLine.match(ansPatternEnd));

                    if (match || endMatch) {
                        let letter, answerText;
                        if (match) {
                            letter = match[1] || match[3] || match[5];
                            answerText = (match[2] || match[4] || match[6] || '').trim();
                            if (!isLineStartMatch && answerText) {
                                answerText = answerText.split(/\s+/).reverse().join(' ');
                            }
                        } else {
                            letter = endMatch[2] || endMatch[4];
                            answerText = (endMatch[1] || endMatch[3] || '').trim();
                            if (!isLineEndMatch && answerText) {
                                answerText = answerText.split(/\s+/).reverse().join(' ');
                            }
                        }

                        if (letter) {
                            q.answers.push({ text: answerText ? [answerText] : [] });
                        }
                        continue;
                    }

                    if (q.answers.length > 0) {
                        q.answers[q.answers.length - 1].text.push(line);
                    } else {
                        q.text.push(line);
                    }
                }

                rawQuestions.push(q);
            }
        }

        const normalizedRawQuestions = splitCorruptedMergedOptions(splitMergedQuestions(rawQuestions));
        const imageKeywords = /(?:^|[\s\(\[\:\,"\'-])(?:לפניכם|לפניך|גרף|הגרף|תרשים|התרשים|תמונה|התמונה|טבלה|הטבלה|איור|האיור|מפה|המפה|דיאגרמה|הדיאגרמה|צילום|סכמה|הסכמה|שרטוט|עקומה|עקומות|מוצג|המוצג|במוצג|באיור|בגרף|בטבלה|בתרשים)(?:$|[\s\)\.\:\,\?\!\"'-])/i;

        const diagnostics = [];
        const formatted = normalizedRawQuestions
            .map((q, idx) => {
                let rawQuestionText = normalizeWhitespace(stripExamFooterArtifacts(q.text.join(' ')));
                rawQuestionText = stripQuestionHeaderPrefix(rawQuestionText);

                const mappedPageIdx = filteredLinePageMap[q.lineIdx];
                let pageIdx = Number.isInteger(mappedPageIdx) ? mappedPageIdx : 0;
                const pageMatch = rawQuestionText.match(/\((?:עמוד|עמ'|page)\s*(\d+)\)/i);
                if (pageMatch && !Number.isInteger(mappedPageIdx)) {
                    pageIdx = Math.max(0, parseInt(pageMatch[1], 10) - 1);
                }
                const cleanQuestionText = stripQuestionHeaderPrefix(rawQuestionText.replace(/\s*\((?:עמוד|עמ'|page)\s*\d+\)$/i, '')).trim();

                const options = q.answers
                    .map((a) => normalizeWhitespace(stripExamFooterArtifacts(a.text.join(' '))))
                    .filter(Boolean);

                const obj = { question: cleanQuestionText, options, correctIndex: 0, sourcePage: pageIdx + 1 };

                if (imageKeywords.test(cleanQuestionText)) {
                    if (pageImages && pageIdx >= 0 && pageIdx < pageImages.length && pageImages[pageIdx]) {
                        obj.image = pageImages[pageIdx];
                    }
                    obj._needsPageRender = true;
                }

                if (!cleanQuestionText || options.length < 2) {
                    diagnostics.push({
                        index: idx + 1,
                        sourcePage: pageIdx + 1,
                        lineIdx: q.lineIdx,
                        questionPreview: cleanQuestionText.slice(0, 80),
                        optionCount: options.length,
                        dropReason: !cleanQuestionText ? 'empty-question' : 'insufficient-options'
                    });
                }

                return obj;
            })
            .filter((q) => q.question && q.options.length >= 2);

        if (diagnostics.length) {
            console.warn(`[parseQuestionsFromText] Dropped ${diagnostics.length} question candidate(s).`, diagnostics);
            const sample = diagnostics
                .slice(0, 3)
                .map((d) => `#${d.index}(${d.optionCount})`)
                .join(', ');
            if (callbacks.setStatus) {
                callbacks.setStatus(`זוהו ${formatted.length} שאלות תקינות. ${diagnostics.length} מועמדות הושמטו (דוגמאות: ${sample}).`, true);
            }
            if (callbacks.showToast) {
                callbacks.showToast(`הושמטו ${diagnostics.length} מועמדות שאלה. דוגמאות: ${sample}`, 'error', 7000);
            }
        }

        const suspicious = formatted
            .map((q, idx) => ({ idx: idx + 1, n: q.options.length }))
            .filter((x) => x.n > 6);
        if (suspicious.length && callbacks.showToast) {
            const sample = suspicious.slice(0, 3).map((s) => `#${s.idx}(${s.n})`).join(', ');
            callbacks.showToast(`זוהו שאלות עם מספר תשובות חריג (חשד למיזוג): ${sample}`, 'error', 8000);
        }

        if (!formatted.length) {
            throw new Error('לא נמצאו שאלות בפורמט הנתמך.');
        }

        return formatted;
    }

    function normalizeQuestionsJson(data) {
        if (!Array.isArray(data) || data.length === 0) {
            throw new Error('קובץ ה-JSON הינו ריק או אינו במבנה מערך.');
        }

        return data.map((item, index) => {
            if (typeof item !== 'object' || item === null) {
                throw new Error(`שאלה מס' ${index + 1} אינה אובייקט תקין.`);
            }

            const rawQuestion = item.question || item.title || item.text || '';
            const cleanQuestion = stripQuestionHeaderPrefix(normalizeWhitespace(rawQuestion));
            let options = item.options || item.answers || item.choices || [];
            if (!Array.isArray(options)) options = [];

            options = options.map(opt => (typeof opt === 'object' && opt !== null && opt.text) ? opt.text : String(opt || ''));

            let correctIndex = item.correctIndex !== undefined ? Number(item.correctIndex) : (item.correctAnswerIndex !== undefined ? Number(item.correctAnswerIndex) : undefined);
            let shuffleOptions = item.shuffleOptions || false;

            if (correctIndex === undefined || isNaN(correctIndex) || correctIndex < 0 || correctIndex >= options.length) {
                if (typeof item.correctAnswer === 'number' && item.correctAnswer >= 1 && item.correctAnswer <= options.length) {
                    correctIndex = item.correctAnswer - 1;
                } else {
                    correctIndex = 0;
                    shuffleOptions = true;
                }
            }

            return {
                id: item.id || (index + 1),
                question: cleanQuestion,
                options: options,
                correctIndex: correctIndex,
                image: item.image || item.pageImage || null,
                sourcePage: item.sourcePage || item.page || (index + 1),
                shuffleOptions: shuffleOptions
            };
        });
    }

    function normalizeQuestionsFromAnyJson(rawData, validateQuestionsFn) {
        const toQuestionsArray = (input) => {
            if (!input) return null;
            if (Array.isArray(input) && input.length > 0) return input;
            if (typeof input !== 'object') return null;

            const directArray = [input.questions, input.data, input.items, input.quiz, input.test]
                .find((v) => Array.isArray(v) && v.length > 0);
            if (directArray) return directArray;

            const objectValues = Object.values(input || {});
            const nestedArray = objectValues.find((v) => Array.isArray(v) && v.length > 0);
            if (nestedArray) return nestedArray;

            const numericKeys = Object.keys(input).filter((k) => /^\d+$/.test(k));
            if (numericKeys.length > 0) {
                const sortedNumericKeys = numericKeys.sort((a, b) => Number(a) - Number(b));
                const values = sortedNumericKeys.map((k) => input[k]);

                if (values.every((v) => typeof v === 'number' && Number.isFinite(v))) {
                    return sortedNumericKeys.map((k) => {
                        const ansNum = Number(input[k]);
                        const safeIndex = Math.max(0, Math.min(3, ansNum - 1));
                        return {
                            question: `שאלה ${k}`,
                            options: ['א', 'ב', 'ג', 'ד'],
                            correctIndex: safeIndex
                        };
                    });
                }

                if (values.every((v) => v && typeof v === 'object')) {
                    return values;
                }
            }

            return null;
        };

        const asArray = toQuestionsArray(rawData);
        if (!asArray || !asArray.length) {
            throw new Error('JSON לא זוהה כמבנה שאלות נתמך.');
        }

        const normalized = normalizeQuestionsJson(asArray);
        const validator = validateQuestionsFn || (typeof window !== 'undefined' && window.QuizCore ? window.QuizCore.validateQuestions : null);
        if (validator) {
            const validationErrors = validator(normalized);
            if (validationErrors.length) {
                throw new Error(`מבנה השאלות אינו תקין: ${validationErrors.slice(0, 5).join(' ')}`);
            }
        }
        return normalized;
    }

    function parseXlsxToRows(arrayBuffer) {
        const xlsx = (typeof window !== 'undefined' ? window.XLSX : null);
        if (!xlsx) {
            throw new Error('ספריית XLSX לא נטענה. אנא רענן את העמוד.');
        }
        const workbook = xlsx.read(new Uint8Array(arrayBuffer), { type: 'array' });
        const sheetName = workbook.SheetNames[0];
        const sheet = workbook.Sheets[sheetName];
        const rows = xlsx.utils.sheet_to_json(sheet, { header: 1, defval: '', raw: false });
        return rows.filter((row) => row.some((cell) => String(cell).trim() !== ''));
    }

    async function tryMergeAnswersFromCsv({ explicit = false, elements, state, progressController, showToastFn, setStatusFn, renderPreviewFn } = {}) {
        const csv = elements?.csvFile?.files?.[0];
        let formNumber = elements?.formNumber?.value?.trim();
        if (!formNumber && typeof window !== 'undefined' && window.QuizCore?.detectFormNumber) {
            const detected = window.QuizCore.detectFormNumber(state?.examText || '', state?.pdfFileName || '');
            formNumber = detected?.rawValue || '';
            if (formNumber && elements?.formNumber) elements.formNumber.value = formNumber;
        }

        if (explicit) {
            if (!state.questions || !state.questions.length) {
                if (showToastFn) showToastFn('יש להעלות קודם קובץ שאלות (JSON או Markdown)!', 'error');
                return;
            }
            if (!csv) {
                if (showToastFn) showToastFn('יש לבחור קובץ תשובות (CSV/XLS)!', 'error');
                return;
            }
            if (!formNumber) {
                if (showToastFn) showToastFn('יש להזין מספר שאלון להתאמת התשובות!', 'error');
                return;
            }
        }

        if (!csv || !formNumber || !state.questions || !state.questions.length) return;

        let task = null;
        if (explicit && progressController) {
            task = progressController.startTask('ממזג מפתח תשובות', {
                icon: '🔗',
                cancellable: false,
                detail: `קורא נתונים וממזג תשובות לשאלון ${formNumber}...`
            });
        }

        try {
            if (task) task.update(30, 'מפענח קובץ תשובות...');
            let answerRows = null;
            const fileName = csv.name.toLowerCase();
            if (fileName.endsWith('.xlsx') || fileName.endsWith('.xls')) {
                const xlsxBuffer = await csv.arrayBuffer();
                answerRows = parseXlsxToRows(xlsxBuffer);
            } else {
                const csvText = await csv.text();
                const quizCore = (typeof window !== 'undefined' ? window.QuizCore : null);
                answerRows = quizCore ? quizCore.parseCsvRows(csvText.replace(/^\uFEFF/, '')) : [];
            }

            if (task) task.update(70, `מחלץ תשובות עבור שאלון ${formNumber}...`);
            const quizCore = (typeof window !== 'undefined' ? window.QuizCore : null);
            const answerMap = quizCore ? quizCore.extractAnswersForForm(answerRows, formNumber) : null;
            if (!answerMap || !answerMap.size) {
                if (explicit) {
                    if (showToastFn) showToastFn(`לא נמצאו תשובות לשאלון ${formNumber} בקובץ שנבחר.`, 'error');
                    if (task) task.fail(`לא נמצאו תשובות לשאלון ${formNumber}.`);
                }
                return;
            }

            state.questions = quizCore.mergeAnswers(state.questions, answerMap);
            if (renderPreviewFn) renderPreviewFn();
            const msg = `תשובות מ-CSV/XLS מוזגו בהצלחה לשאלון ${formNumber}!`;
            if (task) {
                task.finish(msg);
            } else if (setStatusFn) {
                setStatusFn(msg, false, true);
            }
        } catch (e) {
            console.warn('Could not merge CSV answers automatically:', e);
            if (explicit) {
                if (showToastFn) showToastFn(`שגיאה במיזוג תשובות: ${e.message}`, 'error');
                if (task) task.fail(`שגיאה במיזוג תשובות: ${e.message}`);
            }
        }
    }

    async function autoAttachDiagramPageImages({ state, elements, progressController, setStatusFn, showToastFn, renderPreviewFn, renderPageImageDataFn } = {}) {
        if (!state.questions || !state.questions.length) {
            if (showToastFn) showToastFn('יש להעלות קודם קובץ שאלות (JSON או Markdown)!', 'error');
            return;
        }

        let pdfBuffer = state.pdfArrayBuffer || state.pdfBytes;
        if (!pdfBuffer || pdfBuffer.byteLength === 0) {
            const pdfInput = elements?.pdfFile?.files?.[0];
            if (!pdfInput) {
                alert('אנא בחר קודם את קובץ ה-PDF של המבחן בשדה "קובץ PDF".');
                return;
            }
            try {
                pdfBuffer = await pdfInput.arrayBuffer();
                state.pdfArrayBuffer = pdfBuffer.slice(0);
            } catch (e) {
                alert('קריאת קובץ ה-PDF נכשלה. אנא בחר את הקובץ מחדש.');
                return;
            }
        }

        const pdfjs = (typeof window !== 'undefined' ? (window.pdfjsLib || window['pdfjs-dist/build/pdf'] || window.pdfjs) : null);
        if (!pdfjs?.getDocument) {
            alert('ספריית PDF.js לא נטענה בדפדפן. רענן את העמוד ונסה שוב.');
            return;
        }

        const task = progressController ? progressController.startTask('מחבר תמונות עמוד לשאלות', {
            icon: '🖼️',
            cancellable: true,
            detail: 'מנתח עמודי PDF ומחפש תרשימים וטבלאות...'
        }) : null;

        try {
            if (task) task.update(10, 'טוען קובץ PDF לבדיקת תרשימים...');
            if (setStatusFn) setStatusFn('מנתח עמודי PDF ומחבר תמונות לשאלות עם תרשימים/טבלאות...');
            const loadingTask = pdfjs.getDocument({ data: new Uint8Array(pdfBuffer.slice(0)) });
            const pdfDoc = await loadingTask.promise;

            const normalizeForSearch = (value) => String(value || '')
                .replace(/\((?:עמוד|עמ'|page)\s*\d+\)/gi, ' ')
                .replace(/[^\u0590-\u05FFA-Za-z0-9\s]/g, ' ')
                .replace(/\s+/g, ' ')
                .trim()
                .toLowerCase();

            const pdfPageTexts = [];
            for (let p = 1; p <= pdfDoc.numPages; p++) {
                if (task && task.isAborted()) {
                    task.abort('חיבור התמונות נעצר.');
                    return;
                }
                const scanPct = 10 + Math.round((p / pdfDoc.numPages) * 20);
                if (task) task.update(scanPct, `סורק טקסט עמוד ${p} מתוך ${pdfDoc.numPages}...`);
                try {
                    const page = await pdfDoc.getPage(p);
                    const textContent = await page.getTextContent();
                    const pageText = textContent.items.map((it) => (it && it.str) ? it.str : '').join(' ');
                    pdfPageTexts.push(normalizeForSearch(pageText));
                } catch {
                    pdfPageTexts.push('');
                }
            }

            const findBestPageByQuestionText = (questionText, preferredPage) => {
                if (!questionText || !pdfPageTexts.length) return preferredPage;
                const normalizedQuestion = normalizeForSearch(questionText);
                if (!normalizedQuestion) return preferredPage;

                const tokens = normalizedQuestion
                    .split(' ')
                    .filter((t) => t.length >= 3)
                    .slice(0, 24);

                if (!tokens.length) return preferredPage;

                let bestPage = preferredPage;
                let bestScore = -1;

                for (let idx = 0; idx < pdfPageTexts.length; idx++) {
                    const pageText = pdfPageTexts[idx];
                    if (!pageText) continue;

                    let score = 0;
                    for (const token of tokens) {
                        if (pageText.includes(token)) score++;
                    }

                    if (score > bestScore) {
                        bestScore = score;
                        bestPage = idx + 1;
                    }
                }

                return bestScore > 0 ? bestPage : preferredPage;
            };

            const imageKeywords = /(?:^|[\s\(\[\:\,"\'-])(?:לפניכם|לפניך|גרף|הגרף|תרשים|התרשים|תמונה|התמונה|טבלה|הטבלה|איור|האיור|מפה|המפה|דיאגרמה|הדיאגרמה|צילום|סכמה|הסכמה|שרטוט|עקומה|עקומות|מוצג|המוצג|במוצג|באיור|בגרף|בטבלה|בתרשים)(?:$|[\s\)\.\:\,\?\!\"'-])/i;
            let attachedCount = 0;
            const totalQ = state.questions.length;

            for (let i = 0; i < totalQ; i++) {
                if (task && task.isAborted()) {
                    task.abort('חיבור התמונות נעצר.');
                    return;
                }
                const renderPct = 30 + Math.round((i / totalQ) * 65);
                if (task) task.update(renderPct, `בודק שאלה ${i + 1} מתוך ${totalQ}...`);

                const q = state.questions[i];
                const questionText = q.question || '';
                const isDiagramQuestion = imageKeywords.test(questionText);
                const requestedPage = q.sourcePage || 1;
                const clampedRequestedPage = Math.min(Math.max(1, requestedPage), pdfDoc.numPages);
                const targetPage = findBestPageByQuestionText(questionText, clampedRequestedPage);

                const shouldAttachImage = isDiagramQuestion || q.hasVisualElement || q._needsPageRender;
                if (shouldAttachImage && pdfDoc.numPages >= 1) {
                    try {
                        if (task) task.update(renderPct, `מרנדר עמוד ${targetPage} לשאלה ${i + 1}...`);
                        const page = await pdfDoc.getPage(targetPage);
                        const imageData = await renderPageImageDataFn(page, 2.5);
                        q.image = `data:image/png;base64,${imageData}`;
                        attachedCount++;
                    } catch (e) {
                        console.warn(`Could not render page ${targetPage} for question ${i + 1}:`, e);
                    }
                }
            }

            if (renderPreviewFn) renderPreviewFn();
            if (attachedCount > 0) {
                if (task) task.finish(`חוברו בהצלחה ${attachedCount} תמונות עמוד לשאלות עם תרשימים/טבלאות!`);
            } else {
                if (task) task.finish('לא נמצאו שאלות המפנות לתרשימים/טבלאות לחיבור עמוד.');
            }
        } catch (err) {
            console.error('Error auto-attaching diagram images:', err);
            alert(`שגיאה בחיבור תמונות עמוד: ${err.message || err}`);
            if (task) task.fail(`שגיאה בחיבור תמונות עמוד: ${err.message || err}`);
        }
    }

    function stripAllQuestionHeaderPrefixes({ state, renderPreviewFn, showToastFn } = {}) {
        if (!state?.questions || state.questions.length === 0) {
            if (showToastFn) showToastFn('אין שאלות טעונות במערכת לניקוי.', 'info');
            return;
        }
        let count = 0;
        state.questions.forEach((q) => {
            const original = q.question;
            const cleaned = stripQuestionHeaderPrefix(original);
            if (cleaned !== original) {
                q.question = cleaned;
                count++;
            }
        });
        if (renderPreviewFn) renderPreviewFn();
        if (count > 0) {
            if (showToastFn) showToastFn(`נוקו כותרות 'שאלה מספר X' מ-${count} שאלות בהצלחה!`, 'success');
        } else {
            if (showToastFn) showToastFn('כל השאלות כבר נקיות מכותרות.', 'info');
        }
    }

    return {
        normalizeWhitespace,
        stripExamFooterArtifacts,
        stripQuestionHeaderPrefix,
        fixHebrewWordOrder,
        maybeFixHebrewWordOrder,
        parseQuestionsFromMarkdown,
        parseQuestionsFromText,
        normalizeQuestionsJson,
        normalizeQuestionsFromAnyJson,
        parseXlsxToRows,
        tryMergeAnswersFromCsv,
        autoAttachDiagramPageImages,
        stripAllQuestionHeaderPrefixes
    };
}));

