export default function canvasToMarkdown(
  canvas: HTMLCanvasElement,
  alt: string = "",
  title: string = ""
): string {
  return `![${alt}](${canvas.toDataURL()} "${title}")`;
}
