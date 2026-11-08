const IMAGE_EXTENSIONS = new Set([
  ".avif", ".bmp", ".gif", ".jpeg", ".jpg", ".png", ".svg", ".webp",
]);

const ICONS_BY_EXTENSION = {
  ".7z": "/assets/icons/archive.png",
  ".css": "/assets/icons/code.png",
  ".html": "/assets/icons/code.png",
  ".js": "/assets/icons/code.png",
  ".json": "/assets/icons/code.png",
  ".md": "/assets/icons/text.png",
  ".mov": "/assets/icons/video.png",
  ".mp4": "/assets/icons/video.png",
  ".mkv": "/assets/icons/video.png",
  ".webm": "/assets/icons/video.png",
  ".pdf": "/assets/icons/pdf.png",
  ".py": "/assets/icons/code.png",
  ".ts": "/assets/icons/code.png",
  ".tsx": "/assets/icons/code.png",
  ".c": "/assets/icons/code.png",
  ".cpp": "/assets/icons/code.png",
  ".rar": "/assets/icons/archive.png",
  ".txt": "/assets/icons/txt.png",
  ".zip": "/assets/icons/archive.png",
};

export function fileExtension(id) {
  const filename = id.split(/[\\/]/).pop() ?? "";
  const dot = filename.lastIndexOf(".");
  return dot < 0 ? "" : filename.slice(dot).toLowerCase();
}

export function isImage(doc) {
  return IMAGE_EXTENSIONS.has(fileExtension(doc.id));
}

export function fileIcon(doc) {
  const extension = fileExtension(doc.id);
  return ICONS_BY_EXTENSION[extension]
    ?? (IMAGE_EXTENSIONS.has(extension)
      ? "/assets/icons/image.png"
      : "/assets/icons/unknown.png");
}

export function formatSize(bytes) {
  const nominal = bytes ?? 0;
  if (nominal < 1024) return `${nominal} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let value = nominal / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value >= 100 ? Math.round(value) : value.toFixed(1)} ${units[unit]}`;
}

const HOST_LABELS = {
  mega: "MEGA",
  drive: "Google Drive",
  dropbox: "Dropbox",
};

export function externalLabel(doc) {
  const host = doc.host && HOST_LABELS[doc.host];
  return host ? `Open on ${host}` : "Open external link";
}

export function fileBaseName(id) {
  return id.split(/[\\/]/).pop() ?? "";
}
