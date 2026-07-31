import sys, re
sys.stdout.reconfigure(encoding='utf-8')

text = open('tests/2022_litoral/gemini-code-1785449968097.md', encoding='utf-8').read()

# Refined Hebrew diagram keywords regex with word boundary / whitespace delimiters
kw = re.compile(
    r'(?:^|[\s\(\[\:\,\"\'-])(?:לפניכם|לפניך|גרף|הגרף|תרשים|התרשים|תמונה|התמונה|טבלה|הטבלה|איור|האיור|מפה|המפה|דיאגרמה|הדיאגרמה|צילום|סכמה|הסכמה|שרטוט|עקומה|מוצג|המוצג|במוצג|באיור|בגרף|בטבלה|בתרשים)(?:$|[\s\)\.\:\,\"\'-])',
    re.I
)

print("Matching Questions:")
for line in text.splitlines():
    if line.startswith('### שאלה'):
        m = kw.search(line)
        if m:
            print("MATCH:", line[:80], "==>", repr(m.group(0)))
        else:
            print("NO MATCH:", line[:60])