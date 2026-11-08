import { createMemo, createResource, createSignal, Show } from "solid-js";
import Results from "./components/Results";
import Preview from "./components/Preview";
import Sections from "./components/Sections";
import Faq from "./components/Faq";
import { search } from "./lib/search";

const SECTIONS = [
  { root: "all", label: "All" },
  { root: "courses", label: "Course Tables" },
  { root: "past-questions", label: "Past Questions" },
  { root: "syllabus", label: "Syllabus" },
  { root: "timetable", label: "Timetable" },
  { root: "projects", label: "Projects" },
  { root: "misc", label: "Misc" },
];

const SECTION_LABELS = Object.fromEntries(SECTIONS.map((s) => [s.root, s.label]));

export default function App() {
  const [docs, { refetch }] = createResource(() =>
    fetch("/index.json", { headers: { Accept: "application/json" } })
      .then((response) => {
        if (!response.ok) throw new Error(`index.json: HTTP ${response.status}`);
        return response.json();
      }));

  const [query, setQuery] = createSignal(
    new URLSearchParams(window.location.search).get("q") ?? "");
  const [section, setSection] = createSignal("all");
  const [selected, setSelected] = createSignal(null);
  const [selectedElement, setSelectedElement] = createSignal(null);

  const counts = createMemo(() => {
    const all = docs() ?? [];
    const map = { all: all.length };
    for (const doc of all) map[doc.section] = (map[doc.section] ?? 0) + 1;
    return map;
  });

  const sectionDocs = createMemo(() => {
    const all = docs() ?? [];
    return section() === "all" ? all : all.filter((doc) => doc.section === section());
  });

  const results = createMemo(() => (query().trim()
    ? search(query(), sectionDocs())
    : sectionDocs()));

  const titleText = () => {
    if (!docs()) return "Loading…";
    if (query().trim()) {
      const count = results().length;
      return `${count} ${count === 1 ? "result" : "results"}`;
    }
    const count = sectionDocs().length;
    return `${SECTION_LABELS[section()]} · ${count} ${count === 1 ? "file" : "files"}`;
  };

  const pick = (doc, element) => {
    setSelectedElement(element ?? null);
    setSelected(doc);
    if (mediaQuery.matches) {
      element?.blur();
      if (!history.state?.preview) history.pushState({ preview: true }, "");
    }
  };

  const closePreview = (restoreFocus = false) => {
    if (!selected()) return;
    const pushed = Boolean(history.state?.preview);
    setSelected(null);
    if (restoreFocus && selectedElement()) {
      selectedElement().focus({ preventScroll: true });
    }
    setSelectedElement(null);
    if (pushed && history.state?.preview) {
      ignorePop = true;
      history.back();
    }
  };

  let ignorePop = false;
  const mediaQuery = window.matchMedia("(max-width: 860px)");
  window.addEventListener("popstate", () => {
    if (ignorePop) {
      ignorePop = false;
      return;
    }
    setSelected(null);
  });

  const onKeyDown = (event) => {
    if (event.key !== "Escape") return;
    if (selected()) {
      closePreview(true);
    } else if (query()) {
      setQuery("");
      searchInput?.focus();
    }
  };
  let searchInput = null;

  return (
    <>
      <header class="masthead">
        <a class="brand" href="./" aria-label="ITC Index home" onClick={() => setQuery("")}>
          <span class="folder" aria-hidden="true">
            <span class="folder__back">
              <span class="paper"></span><span class="paper"></span><span class="paper"></span>
              <span class="folder__front"></span><span class="folder__front right"></span>
            </span>
          </span>
          <span class="brand__text">itc index</span>
        </a>
      </header>

      <main class="page">
        <form class="search" id="search-form" role="search"
          onSubmit={(event) => event.preventDefault()}>
          <label class="visually-hidden" for="search-input">Search files</label>
          <svg class="search__icon" viewBox="0 0 24 24" aria-hidden="true">
            <circle cx="10.8" cy="10.8" r="6.8" />
            <path d="m16 16 5 5" />
          </svg>
          <input
            id="search-input"
            ref={searchInput}
            type="search"
            placeholder="Try “10 archi”"
            autocomplete="off"
            autocapitalize="off"
            spellcheck={false}
            enterkeyhint="search"
            value={query()}
            onInput={(event) => setQuery(event.currentTarget.value)}
            aria-controls="results-list"
          />
          <button class="icon-btn search__clear" type="button" aria-label="Clear search"
            hidden={!query()} onClick={() => { setQuery(""); }}>
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18" /></svg>
          </button>
        </form>

        <Show when={docs.error} fallback={null}>
          <div class="results__list" style={{ "margin-top": "28px" }}>
            <p class="empty">
              The file list could not be loaded. Check your connection and try again.
              <br />
              <button class="button" type="button" onClick={() => refetch()}>Try again</button>
            </p>
          </div>
        </Show>
        <Show when={!docs.error && docs()} fallback={
          <Show when={!docs.error}>
            <div class="results__list" style={{ "margin-top": "28px" }}>
              <p class="empty">Loading files…</p>
            </div>
          </Show>
        }>
          <Sections
            sections={SECTIONS}
            active={section}
            counts={counts}
            onPick={(root) => { setSection(root); setSelected(null); }}
          />
          <div class="layout" id="layout">
            <section class="results" aria-labelledby="results-heading">
              <h1 class="results__heading" id="results-heading" aria-live="polite">
                {titleText()}
              </h1>
              <Results
                items={results}
                query={() => (query().trim() ? query().trim() : "")}
                selected={selected}
                onSelect={(doc, element) => pick(doc, element)}
              />
            </section>

            <Preview doc={selected} onClose={closePreview} />
          </div>
        </Show>

        <div class="backdrop" id="backdrop"
          classList={{ show: Boolean(selected()) && mediaQuery.matches }}
          onClick={() => closePreview(true)}
        ></div>

        <Faq />
      </main>

      <footer class="site-footer">
        <span class="footer-brand">
          <img src="/assets/icons/itcircle.png" alt="" aria-hidden="true">
          KhEC IT Circle
        </span>
        <div class="footer-links">
          <a href="https://www.instagram.com/itcirclekhec/" target="_blank" rel="noopener noreferrer">Instagram</a>
          <a href="https://khecitcircle.codeberg.page/itcircle-linktree/" target="_blank" rel="noopener noreferrer">IT Circle</a>
          <a href="https://github.com/sulavtpa/itc-index" target="_blank" rel="noopener noreferrer">Repository</a>
        </div>
      </footer>
    </>
  );
}
