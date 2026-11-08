import { createEffect, createSignal, Show } from "solid-js";
import Tags from "./Tags";
import { externalLabel, fileBaseName, isImage } from "../lib/files";

export default function Preview(props) {
  const [failed, setFailed] = createSignal(false);

  // Reset the image-load state whenever a new file is previewed.
  createEffect(() => {
    props.doc()?.id;
    setFailed(false);
  });

  return (
    <aside
      class="preview"
      id="preview"
      aria-label="File preview"
      data-state={props.doc() ? "open" : "empty"}
      inert={props.doc() ? undefined : true}
    >
      <p class="preview__empty">Select a file to preview it here.</p>

      <div class="preview__head">
        <h2 class="preview__title">{props.doc()?.title ?? ""}</h2>
        <button class="icon-btn" id="preview-close" type="button"
          aria-label="Close preview" onClick={() => props.onClose(true)}>
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18" /></svg>
        </button>
      </div>

      <div class="preview__body" id="preview-body">
        <Tags tags={props.doc()?.tags ?? []} />
        <div class="preview__media" id="preview-media">
          <Show when={props.doc()}>
            {(doc) => (
              <Show
                when={isImage(doc())}
                fallback={
                  <Show
                    when={doc().source === "external"}
                    fallback={<p class="preview__note">This file type can’t be previewed. You can still download it.</p>}
                  >
                    <p class="preview__note">
                      This file is hosted externally, so there is nothing to preview here.
                      The button below opens it directly.
                    </p>
                  </Show>
                }
              >
                <a href={encodeURI(doc().id)} target="_blank" rel="noopener noreferrer"
                  aria-label={`Open ${doc().title} full size`}>
                  <img alt={doc().title} decoding="async" loading="lazy"
                    src={encodeURI(doc().id)}
                    onError={() => setFailed(true)}
                  />
                </a>
              </Show>
            )}
          </Show>
        </div>
      </div>

      <div class="preview__foot">
        <Show
          when={props.doc()}
          fallback={null}
        >
          {(doc) => (
            <Show
              when={doc().source === "external"}
              fallback={
                <a class="button" href={encodeURI(doc().id)} download={fileBaseName(doc().id)}>
                  <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12m0 0 4-4m-4 4-4-4M5 17v3h14v-3" /></svg>
                  Download
                </a>
              }
            >
              <a class="button button--external" href={doc().link} target="_blank" rel="noopener noreferrer">
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 5h5v5m0-5-9 9M9 5H6a1 1 0 0 0-1 1v12a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-3" /></svg>
                {externalLabel(doc())}
              </a>
            </Show>
          )}
        </Show>
      </div>
    </aside>
  );
}
