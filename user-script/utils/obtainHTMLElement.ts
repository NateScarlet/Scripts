export default function obtainHTMLElement<
  K extends keyof HTMLElementTagNameMap
>(tag: K, id: string): HTMLElementTagNameMap[K] {
  const el =
    (document.getElementById(id) as HTMLElementTagNameMap[K]) ??
    document.createElement(tag);
  el.id = id;
  return el;
}
