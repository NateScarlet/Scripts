import urlLastPart from "./urlLastPart";

export default function downloadFile(
  file: Blob,
  filename: string = `${urlLastPart(location.pathname)} ${document.title}.md`
): void {
  const anchor = document.createElement("a");
  anchor.href = URL.createObjectURL(file);
  anchor.download = filename;
  anchor.style["display"] = "none";
  document.body.append(anchor);
  anchor.click();
  setTimeout(() => {
    document.body.removeChild(anchor);
    URL.revokeObjectURL(anchor.href);
  }, 0);
}
