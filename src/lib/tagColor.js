// Generates a deterministic, theme-safe color for any tag name.
// FNV-1a hash -> hue, with saturation/lightness kept in a band that reads well
// on the light UI. Same tag always renders the same color, site-wide.

const FNV_OFFSET = 0x811c9dc5;
const FNV_PRIME = 0x01000193;

function fnv1a(text) {
  let hash = FNV_OFFSET;
  for (let i = 0; i < text.length; i += 1) {
    hash ^= text.charCodeAt(i);
    hash = Math.imul(hash, FNV_PRIME) >>> 0;
  }
  return hash >>> 0;
}

export function tagColor(name) {
  const hash = fnv1a(name);
  const hue = hash % 360;
  const saturation = 42 + ((hash >>> 8) % 14); // 42-55%
  const lightness = 40 + ((hash >>> 16) % 8); // 40-47%
  return `hsl(${hue} ${saturation}% ${lightness}%)`;
}
