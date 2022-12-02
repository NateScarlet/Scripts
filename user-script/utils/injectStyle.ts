export default function injectStyle(css: string) {
  const style = document.createElement("style");
  style.innerHTML = css;
  document.head.appendChild(style);
  const dispose = () => {
    style.remove();
  };
  return {
    dispose,
  };
}
