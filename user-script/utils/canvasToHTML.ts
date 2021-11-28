export default function canvasToHTML(
  canvas: HTMLCanvasElement,
  alt: string = "",
  title: string = ""
): string {
  return `<img src="${canvas.toDataURL()}" alt="${alt}" title="${title}"/>`;
}
