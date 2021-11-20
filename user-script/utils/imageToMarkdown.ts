export default function imageToMarkdown(
  img: HTMLImageElement,
  {
    background,
  }: {
    background?: string | CanvasGradient | CanvasPattern;
  } = {}
): string {
  const canvas = document.createElement("canvas");
  canvas.width = img.naturalWidth;
  canvas.height = img.naturalHeight;
  const ctx = canvas.getContext("2d");
  if (background) {
    ctx.fillStyle = background;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
  }
  ctx.drawImage(img, 0, 0);
  return `![${img.alt}](${canvas.toDataURL()} "${img.title}")`;
}
