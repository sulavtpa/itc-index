const SEARCH_STOP_WORDS = new Set([
  "course", "courses", "subject", "subjects", "syllabus", "table", "tables",
]);

export function normalize(value) {
  return value
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function editDistanceWithinOne(first, second) {
  if (Math.abs(first.length - second.length) > 1) return false;
  let row = Array.from({ length: second.length + 1 }, (_, index) => index);
  for (let i = 1; i <= first.length; i += 1) {
    const next = [i];
    let minimum = i;
    for (let j = 1; j <= second.length; j += 1) {
      const cost = first[i - 1] === second[j - 1] ? 0 : 1;
      next[j] = Math.min(next[j - 1] + 1, row[j] + 1, row[j - 1] + cost);
      minimum = Math.min(minimum, next[j]);
    }
    if (minimum > 1) return false;
    row = next;
  }
  return row[second.length] <= 1;
}

function tokenScore(queryToken, terms) {
  let best = 0;
  for (const term of terms) {
    if (term === queryToken) best = Math.max(best, 12);
    else if (term.startsWith(queryToken)) best = Math.max(best, 9);
    else if (term.includes(queryToken)) best = Math.max(best, 6);
    else if (queryToken.length >= 4 && term.length >= 4
      && editDistanceWithinOne(queryToken, term)) {
      best = Math.max(best, 2);
    }
  }
  return best;
}

function getSemester(doc) {
  const match = doc.id.match(/(?:^|\/)(\d+)(?:st|nd|rd|th)-sem(?:ester)?(?:-|\.|$)/i);
  return match ? Number(match[1]) : null;
}

function getSearchText(doc) {
  return [doc.id, doc.title, ...doc.tags, doc.description].join(" ");
}

export function search(query, documents) {
  const normalizedQuery = normalize(query);
  if (!normalizedQuery) return [];
  const queryTokens = normalizedQuery
    .split(/\s+/)
    .filter((token) => !SEARCH_STOP_WORDS.has(token));
  if (!queryTokens.length) return [];

  return documents
    .map((doc) => {
      const normalizedText = normalize(getSearchText(doc));
      const normalizedTitle = normalize(doc.title);
      const titleTerms = normalizedTitle.split(/\s+/);
      const terms = normalizedText.split(/\s+/);
      const semester = getSemester(doc);
      const year = semester ? Math.ceil(semester / 2) : null;
      let score = normalizedText.includes(normalizedQuery) ? 10 : 0;
      if (normalizedTitle.includes(normalizedQuery)) score += 12;
      for (const [tokenIndex, token] of queryTokens.entries()) {
        const ordinal = token.match(/^(\d+)(?:st|nd|rd|th)$/);
        let match;
        if (ordinal) {
          const number = Number(ordinal[1]);
          const isYearQuery = queryTokens[tokenIndex + 1] === "year";
          match = (isYearQuery ? year : semester) === number ? 12 : 0;
        } else if (/^\d+$/.test(token)) {
          const number = Number(token);
          match = semester === number || terms.includes(token) ? 12 : 0;
        } else {
          match = tokenScore(token, terms);
        }
        if (!match) return { doc, score: 0 };
        score += match + tokenScore(token, titleTerms) * 4;
      }
      return { doc, score };
    })
    .filter((result) => result.score > 0)
    .sort((a, b) => b.score - a.score || a.doc.title.localeCompare(b.doc.title))
    .map((result) => result.doc);
}
