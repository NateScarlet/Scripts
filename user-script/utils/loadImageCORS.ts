import loadImage from "./loadImage";
import parseHeader from "./parseHeader";

export default async function loadImageCORS(
  url: string
): Promise<HTMLImageElement> {
  return new Promise((resolve, reject): void => {
    GM.xmlHttpRequest({
      method: "GET",
      url,
      // https://github.com/greasemonkey/greasemonkey/issues/1834#issuecomment-37084558
      overrideMimeType: "text/plain; charset=x-user-defined",
      onload: async ({ responseText, responseHeaders }) => {
        const headers = parseHeader(responseHeaders);
        const data = new Blob(
          [Uint8Array.from(responseText.split("").map((i) => i.charCodeAt(0)))],
          { type: headers.get("content-type")?.[0] ?? "image/jpeg" }
        );
        const src = URL.createObjectURL(data);
        const image = await loadImage(src);
        image.alt = url;
        resolve(image);
        URL.revokeObjectURL(src);
      },
      onerror: ({ context }) => {
        reject({ context });
      },
    });
  });
}
