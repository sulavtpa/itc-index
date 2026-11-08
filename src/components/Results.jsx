import { For, Show } from "solid-js";
import Tags from "./Tags";
import { fileIcon, formatSize, externalLabel } from "../lib/files";

export default function Results(props) {
  return (
    <div class="results__list" id="results-list">
      <Show
        when={!props.error}
        fallback={
          <p class="empty">
            The file list could not be loaded. Check your connection and try again.
          </p>
        }
      >
        <Show when={props.items().length > 0} fallback={
          <p class="empty">
            {props.query()
              ? `Nothing matches “${props.query()}”. Try a department and semester, like “3rd sem civil”.`
              : props.error ? "No files available." : "No files in this section yet."}
          </p>
        }>
          <For each={props.items()}>
            {(doc) => (
              <FileRow
                doc={doc}
                selected={props.selected()?.id === doc.id}
                onSelect={(element) => props.onSelect(doc, element)}
              />
            )}
          </For>
        </Show>
      </Show>
    </div>
  );
}

function FileRow(props) {
  const external = () => props.doc.source === "external";
  const label = () => (external() ? externalLabel(props.doc) : "Download");
  return (
    <button
      class="file"
      type="button"
      aria-current={props.selected ? "true" : "false"}
      onClick={(event) => props.onSelect(event.currentTarget)}    >
      <img class="file__icon" src={fileIcon(props.doc)} alt="" width="32" height="32" />
      <span class="file__info">
        <span class="file__title">{props.doc.title}</span>
        <span class="file__description">{props.doc.description}</span>
        <Tags tags={props.doc.tags} />
      </span>
      <span class="file__meta">
        {props.doc.size > 0 && <span class="file__size">{formatSize(props.doc.size)}</span>}
        {external() && <span class="file__ext">{label()}</span>}
      </span>
    </button>
  );
}
