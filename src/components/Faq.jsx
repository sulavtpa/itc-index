export default function Faq() {
  return (
    <section class="faq" aria-labelledby="faq-heading">
      <h2 id="faq-heading">Questions</h2>
      <details>
        <summary>How do I find a file?</summary>
        <p>
          Pick a section tab, or type a department, a semester or a year. Short forms work,
          for example “10 archi”, “3rd sem civil” or “2nd year bit”. Tap a result to preview
          it, then download it.
        </p>
      </details>
      <details>
        <summary>What does “Open on MEGA” mean?</summary>
        <p>
          Some files are too large to keep in our repository, so they live on an external
          host instead. Those entries open the download page on that host rather than
          downloading directly. The IT Circle shares such links because of space limits,
          but we cannot control those sites’ availability.
        </p>
      </details>
      <details>
        <summary>Can I trust these files?</summary>
        <p>
          The files are shared by the KhEC IT Circle, but they can be outdated or contain
          mistakes. Check anything important against the official syllabus. The IT Circle
          is not responsible for problems caused by using them.
        </p>
      </details>
      <details>
        <summary>How do I contribute?</summary>
        <p>
          Clone the repository and run <code>py contribute.py</code>. It walks you through
          adding, updating or deleting a file, builds the index and submits a pull request.
          No GitHub experience needed.
        </p>
      </details>
      <details>
        <summary>I found a mistake or a missing file</summary>
        <p>
          Tell us, even if it is a small detail. Message the IT Circle on{" "}
          <a href="https://www.instagram.com/itcirclekhec/" target="_blank" rel="noopener noreferrer">
            Instagram</a>{" "}
          and we will fix it.
        </p>
      </details>
      <details>
        <summary>Where are the files stored?</summary>
        <p>
          Most files live in our{" "}
          <a href="https://github.com/sulavtpa/itc-index" target="_blank" rel="noopener noreferrer">
            GitHub repository</a>{" "}
          and the site is hosted on Vercel. Oversized files are hosted externally and linked
          from here.
        </p>
      </details>
    </section>
  );
}
