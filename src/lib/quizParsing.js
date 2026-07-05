export function normalizeWhitespace(value) {
  return String(value || '')
    .replace(/\u00A0/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

export function stripExamFooterArtifacts(value) {
  return String(value || '').replace(/-+\s*סוף\s+המבחן\s*-+/g, ' ');
}

export function parseCsvRows(csvText) {
  const rows = [];
  let row = [];
  let value = '';
  let inQuotes = false;

  for (let i = 0; i < csvText.length; i++) {
    const char = csvText[i];
    const next = csvText[i + 1];

    if (char === '"') {
      if (inQuotes && next === '"') {
        value += '"';
        i++;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (char === ',' && !inQuotes) {
      row.push(value);
      value = '';
    } else if ((char === '\n' || char === '\r') && !inQuotes) {
      if (char === '\r' && next === '\n') i++;
      row.push(value);
      value = '';
      if (row.some((cell) => String(cell).trim() !== '')) rows.push(row);
      row = [];
    } else {
      value += char;
    }
  }

  if (value.length || row.length) {
    row.push(value);
    if (row.some((cell) => String(cell).trim() !== '')) rows.push(row);
  }

  return rows;
}

export function extractAnswersForForm(rows, formNumber) {
  let headers = null;
  let selectedRow = null;

  for (const row of rows) {
    if (!row.length) continue;
    if ((row[0] || '').includes('שאלון')) {
      headers = row;
      continue;
    }
    if (headers && (row[0] || '').trim() === String(formNumber || '').trim()) {
      selectedRow = row;
      break;
    }
  }

  if (!headers || !selectedRow) {
    throw new Error(`Form ${formNumber} was not found in answer rows.`);
  }

  const answers = new Map();
  for (let i = 0; i < headers.length; i++) {
    const header = String(headers[i] || '').trim();
    if (!header.startsWith('שאלה')) continue;

    const qNumMatch = header.match(/\d+/);
    if (!qNumMatch) continue;

    const questionNumber = Number(qNumMatch[0]);
    const rawCell = String(selectedRow[i] || '');

    const answerMatch = rawCell.match(/\((\d+)\)/);
    if (answerMatch) {
      answers.set(questionNumber, Number(answerMatch[1]) - 1);
      continue;
    }

    if (rawCell.includes('מבוטלת') || rawCell.includes('והת')) {
      answers.set(questionNumber, null);
    }
  }

  return answers;
}
