import { For } from "solid-js";
import { tagColor } from "../lib/tagColor";

// "N Year" tags repeat what the semester tag already says, so they are not shown.
export default function Tags(props) {
  return (
    <span class="tags">
      <For each={(props.tags ?? []).filter((tag) => !/ Year$/.test(tag))}>
        {(tag) => <span class="tag" style={{ "--tag-color": tagColor(tag) }}>{tag}</span>}
      </For>
    </span>
  );
}
