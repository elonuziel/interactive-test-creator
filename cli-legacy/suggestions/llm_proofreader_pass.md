# Suggestion: LLM Proofreader Pass for RTL Text Cleanup

## Problem
The heuristic Python pipeline on `main` extracts ~90% of Hebrew exam questions cleanly from digital PDFs. However, some lines have RTL chunk-ordering issues that PyMuPDF cannot resolve:

- **Question text**: words in correct order within chunks, but chunks reversed (e.g., `: מיליון שנה הן 6-העדויות...` instead of `העדויות...הן:`)
- **Option text**: mixed Hebrew/Latin lines with reversed parentheses and LTR word order (e.g., `(zoea) ( יש...Eriphia verrucosa )` instead of `(Eriphia verrucosa) יש...(zoea)`)
- **Table data**: table cell values extracted as plain text and merged into questions/options

These affect roughly 5-10% of questions across typical Hebrew exam PDFs.

## Proposed Solution
Add an optional **LLM proofreader pass** after the heuristic extraction, similar to `feat-site`'s `verifyTestWithGemini()`:

```python
# New script: python_scripts/8_proofread_llm.py
python 8_proofread_llm.py "questions.json" -o "questions_clean.json" --api-key "sk-..."
```

The script would:
1. Load the parsed `questions.json`
2. Send the JSON to an LLM (Gemini / GPT-4o) with a prompt:
   - Fix RTL word-order issues in Hebrew text
   - Fix reversed parentheses in mixed Hebrew/Latin lines
   - Ensure options are logically separated and not truncated
   - Maintain the exact JSON schema
3. Run `7_check_json.py` on the output to verify integrity

## Design Decisions
- **Optional**: the pipeline works without it; the LLM pass is an opt-in enhancement
- **Model**: Gemini 1.5 Flash (cheap, fast) or GPT-4o-mini for cost-sensitive use
- **Batch mode**: send all questions at once (33 questions = 1 API call)
- **Conservative**: the prompt should instruct the LLM to only fix clear errors, not rewrite correct text

## Estimated Impact
- Fixes Q1, Q10, Q13, Q33 text ordering
- Fixes Q11-style option text scrambling
- Cost: ~$0.01-0.05 per exam with Gemini Flash

## Related
- `feat-site` branch: `verifyTestWithGemini()` in `generator.js` (lines ~810-870)
- `quiz_builder.html`: Gemini proofreader UI in browser-based generator
