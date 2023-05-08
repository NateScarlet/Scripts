export default function setHTMLElementDisplayHidden(
  el: HTMLElement,
  want: boolean
) {
  const actual = el.style.display == "none";
  if (actual === want) {
    return;
  }
  if (want) {
    el.style.display = "none";
  } else {
    el.style.display = "";
  }
}
