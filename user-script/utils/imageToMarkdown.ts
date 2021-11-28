import canvasToMarkdown from "./canvasToMarkdown";
import imageToCanvas from "./imageToCanvas";

export default function imageToMarkdown(
  img: HTMLImageElement,
  {
    background,
  }: {
    background?: string | CanvasGradient | CanvasPattern;
  } = {}
): string {
  return canvasToMarkdown(
    imageToCanvas(img, { background }),
    img.alt,
    img.title
  );
}
