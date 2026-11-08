export default function Sections(props) {
  return (
    <nav class="sections" aria-label="File sections">
      <For each={props.sections}>
        {(section) => (
          <button
            type="button"
            class="sections__tab"
            classList={{ active: props.active() === section.root }}
            onClick={() => props.onPick(section.root)}
          >
            {section.label}
            <span class="sections__count">{props.counts()[section.root] ?? 0}</span>
          </button>
        )}
      </For>
    </nav>
  );
}
